"""Choosing the country in an embed (since 2.2.14).

The iframe on the WWFF website always showed Belgium: an iframe has nothing
saved and no callsign, so the app fell back to ONFF, and the bottom bar (with
Settings) is hidden in an embed. Now ?prog= picks the opening country and a
picker on the map lets the visitor switch. Neither writes anything to storage.

    python3 -m http.server 8011          # from the repo root
    python3 build/tests/test_embed_country.py
"""
import re, json, os, sys
from playwright.sync_api import sync_playwright
import preconsent  # noqa: F401
BASE = "http://localhost:8011/web/"
fails = []


def ok(c, m):
    print(("  ✓ " if c else "  ✗ ") + m)
    if not c:
        fails.append(m)


def routes(ctx):
    ctx.route(re.compile(r"https://tiles\.openfreemap\.org/.*"), lambda r: r.fulfill(
        status=200, content_type="application/json",
        body=json.dumps({"version": 8, "sources": {}, "layers": [
            {"id": "bg", "type": "background", "paint": {"background-color": "#e8e4d8"}}]})))
    ctx.route(re.compile(r"https://spots\.wwff\.co/.*"), lambda r: r.fulfill(
        status=200, content_type="application/json", body="[]"))
    ctx.route(re.compile(r"https://docs\.google\.com/.*"), lambda r: r.abort())
    ctx.route(re.compile(r"https://(?!localhost).*umami.*"), lambda r: r.abort())


def open_page(br, query, width=420):
    ctx = br.new_context(service_workers="block", viewport={"width": width, "height": 800})
    routes(ctx)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE + query, wait_until="load")
    pg.wait_for_function("() => typeof loadedPrograms !== 'undefined' && loadedPrograms.length > 0",
                         timeout=20000)
    pg.wait_for_timeout(600)
    return ctx, pg, errs


def center(pg):
    return pg.evaluate("() => { const c = map.getCenter(); return [c.lng, c.lat]; }")


def saved(pg):
    return pg.evaluate("() => localStorage.getItem('diana.homeprog')")


exe = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
with sync_playwright() as p:
    br = p.chromium.launch(executable_path=exe if os.path.exists(exe) else None)
    have = sorted(c["program"] for c in json.load(open("data/countries.json"))["countries"])

    print("\n[1] the WWFF iframe as it is today: ?embed=1&world=1")
    ctx, pg, errs = open_page(br, "?embed=1&world=1")
    vis = pg.is_visible("#embCountry")
    ok(vis, "the country picker is visible in the embed")
    opts = pg.evaluate("() => [...document.querySelectorAll('#embCountry option')].map(o => o.value)")
    ok(sorted(opts) == have, f"it offers exactly the countries with boundaries {have} (got {opts})")
    ok(pg.input_value("#embCountry") == "ONFF", "without ?prog= it opens on ONFF, as before")
    ok(pg.evaluate("() => loadedPrograms") == ["ONFF"], "ONFF boundaries are loaded")
    label = pg.get_attribute("#embCountry", "aria-label")
    ok(bool(label), f"the picker has an accessible name ({label!r})")

    print("\n[2] picking Germany in the embed")
    pg.select_option("#embCountry", "DLFF")
    pg.wait_for_function("() => loadedPrograms.join() === 'DLFF'", timeout=20000)
    pg.wait_for_timeout(1500)
    lon, lat = center(pg)
    ok(5 < lon < 15.5 and 47 < lat < 55.5, f"the map moved over Germany (centre {lon:.2f}, {lat:.2f})")
    n = pg.evaluate("() => map.getSource('onff') ? zones.features.filter(f => (f.properties.ref||'').startsWith('DLFF')).length : -1")
    ok(n > 1000, f"the German boundaries are what the map holds ({n})")
    ok(saved(pg) is None, "nothing is written to storage")
    ok(not errs, f"no page errors {errs}")
    ctx.close()

    print("\n[3] opening with ?embed=1&world=1&prog=PAFF")
    ctx, pg, errs = open_page(br, "?embed=1&world=1&prog=paff")
    ok(pg.evaluate("() => loadedPrograms") == ["PAFF"], "PAFF boundaries are loaded, ONFF is not")
    ok(pg.input_value("#embCountry") == "PAFF", "the picker shows PAFF")
    lon, lat = center(pg)
    ok(3 < lon < 7.5 and 50.5 < lat < 54, f"the map opens over the Netherlands ({lon:.2f}, {lat:.2f})")
    ok(saved(pg) is None, "nothing is written to storage")
    ok(not errs, f"no page errors {errs}")
    ctx.close()

    print("\n[4] a phone of 360 px: the picker fits beside the three buttons")
    ctx, pg, errs = open_page(br, "?embed=1&world=1&prog=DLFF", width=360)
    box = pg.locator("#embCountry").bounding_box()
    btn = pg.locator("#btnSearch").bounding_box()
    ok(box["x"] >= 0 and box["x"] + box["width"] <= btn["x"],
       f"picker {box['x']:.0f}..{box['x'] + box['width']:.0f} px stays left of the search button at {btn['x']:.0f} px")
    ctx.close()

    print("\n[5] outside an embed")
    ctx, pg, errs = open_page(br, "")
    ok(not pg.is_visible("#embCountry"), "no picker in the normal app (Settings has the country)")
    ctx.close()
    ctx, pg, errs = open_page(br, "?prog=OZFF")
    ok(pg.evaluate("() => loadedPrograms") == ["OZFF"], "?prog=OZFF opens with Denmark in the normal app too")
    ok(saved(pg) is None, "without saving it")
    pg.evaluate("() => setHomeCountry('ONFF')")
    pg.wait_for_function("() => loadedPrograms.join() === 'ONFF'", timeout=20000)
    ok(saved(pg) == "ONFF" and pg.evaluate("() => homeCountry()") == "ONFF",
       "a choice in Settings ends ?prog= and is saved as always")
    ctx.close()

    print("\n[6] the embed code in the Admin panel")
    ctx, pg, errs = open_page(br, "?admin=1")
    pg.evaluate("() => { const e = $('embProg'); e.value = 'dlff'; e.dispatchEvent(new Event('input')); }")
    code = pg.text_content("#embCode")
    ok("prog=DLFF" in code, "the country field adds prog=DLFF")
    ctx.close()
    br.close()

print("\nALL OK" if not fails else f"\n{len(fails)} FAILED")
sys.exit(1 if fails else 0)
