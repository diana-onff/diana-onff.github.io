import re, json, sys
from playwright.sync_api import sync_playwright
import preconsent  # noqa: F401  answered welcome screen, see preconsent.py
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
    ctx.route(re.compile(r"https://spots\.wwff\.co/static/spots\.json"), lambda r: r.fulfill(
        status=200, content_type="application/json", body="[]"))
    ctx.route(re.compile(r"https://spots\.wwff\.co/static/agendas.*"), lambda r: r.fulfill(
        status=200, content_type="application/json", body="[]"))
    ctx.route(re.compile(r"https://docs\.google\.com/.*"), lambda r: r.abort())


with sync_playwright() as p:
    br = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
                            if __import__('os').path.exists("/opt/pw-browsers/chromium-1194/chrome-linux/chrome") else None)
    ctx = br.new_context(service_workers="block", viewport={"width": 420, "height": 860})
    routes(ctx)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE, wait_until="load")
    pg.wait_for_timeout(3000)   # the real wwff-world.geojson is ~9 MB, give it a moment

    print("\n[1] factory setting: the worldwide layer is on")
    default_on = pg.evaluate("() => showWorld")
    ok(default_on is True, f"showWorld default is true (got {default_on})")
    default_filter = pg.evaluate("() => spotFilter")
    ok(default_filter == "all", f"the worldwide/your-country choice starts at 'all' (got '{default_filter}')")

    print("\n[2] the worldwide points layer is loaded and drawn")
    pg.wait_for_function("() => worldLoaded === true", timeout=15000)
    n = pg.evaluate("() => worldPoints.features.length")
    ok(n > 60000, f"more than 60.000 points loaded (got {n})")
    # This checkout's data/wwff-world.geojson is a fixture from before a second
    # country existed, when the build still left ONFF out of this file entirely.
    # It no longer does that (see kmz2geojson.py: the file now carries every
    # country, this run's own included, because it is shared by every viewer and
    # only the app can tell which ONE of them a given visitor has loaded — see
    # worldFilteredData() below). A freshly built file would have ONFF in it too;
    # this fixture simply predates that build and is not meant to prove the point
    # by itself — worldFilteredData() in step [3] is what actually tests it.
    has_onff = pg.evaluate("() => worldPoints.features.some(f => f.properties.ref.startsWith('ONFF'))")
    ok(not has_onff, "this fixture (from before the build carried every country) still has none")
    src_exists = pg.evaluate("() => !!map.getSource('wwff-world')")
    ok(src_exists, "MapLibre source 'wwff-world' exists")
    # world-cluster-count is a text layer and needs glyphs — the mock test style
    # does not have those (no more than np-label, which has had the same
    # 'if(glyphs)' wait for a while now).
    layers_exist = pg.evaluate(
        "() => ['world-clusters','world-point'].every(l => !!map.getLayer(l))")
    ok(layers_exist, "the cluster and point layers exist")

    print("\n[3] these points follow the one country choice, not a second list")
    # There used to be a separate dropdown here ("show only this country") that
    # knew nothing of the country picked for the spots, so you could have two
    # different countries set without noticing. The points answer to the same
    # choice as everything else now: worldwide, or your own country.
    ok(not pg.evaluate("() => !!document.getElementById('setWorldCountry')"),
       "the second country dropdown is gone")
    pg.evaluate("() => setHomeCountry('PAFF')")
    pg.wait_for_timeout(900)
    ok(pg.evaluate("() => localStorage.getItem('diana.homeprog')") == "PAFF",
       "the Netherlands is your country now")
    wide = pg.evaluate("() => worldFilteredData().features.length")
    ok(wide > 60000, f"on worldwide you still see every other country ({wide})")

    pg.evaluate("() => document.querySelector('#spotFilter [data-home]').click()")
    pg.wait_for_timeout(600)
    filtered_n = pg.evaluate("() => worldFilteredData().features.length")
    all_paff = pg.evaluate(
        "() => worldFilteredData().features.every(f => f.properties.ref.toUpperCase().split('-')[0] === 'PAFF')")
    ok(filtered_n > 0 and all_paff, f"on your own country, only its points are left ({filtered_n})")
    ok(filtered_n < wide, f"which is fewer than worldwide ({filtered_n} against {wide})")

    print("\n[4] the choice survives a reload")
    stored = pg.evaluate("() => localStorage.getItem('diana.spotFilter2')")
    ok(stored == "PAFF", f"'PAFF' saved in localStorage (got '{stored}')")
    pg.reload(wait_until="load")
    pg.wait_for_timeout(3000)
    pg.wait_for_function("() => worldLoaded === true", timeout=15000)
    after_reload = pg.evaluate("() => spotFilter")
    ok(after_reload == "PAFF", f"still on your own country after a reload (got '{after_reload}')")
    sel_after = pg.evaluate("() => document.getElementById('setSpotCountry').value")
    ok(sel_after == "PAFF", "and the picker in Settings says so")

    print("\n[5] back to worldwide")
    pg.evaluate("() => document.querySelector('#spotFilter [data-filter=\"all\"]').click()")
    pg.wait_for_timeout(400)
    back_n = pg.evaluate("() => worldFilteredData().features.length")
    ok(back_n > 60000, f"every country's points are back ({back_n})")
    ok(pg.evaluate("() => document.getElementById('setSpotCountry').value") == "PAFF",
       "and your country is still the Netherlands")
    pg.evaluate("() => setHomeCountry('ONFF')")
    pg.wait_for_timeout(1200)

    print("\n[6] the layer can be switched off and on from the layers panel")
    pg.evaluate("() => document.querySelector('.opt[data-layer=\"world\"]').click()")
    pg.wait_for_timeout(200)
    off_vis = pg.evaluate("() => map.getLayoutProperty('world-point','visibility')")
    ok(off_vis == 'none', f"layer hidden after switching off (got '{off_vis}')")
    pg.evaluate("() => document.querySelector('.opt[data-layer=\"world\"]').click()")
    pg.wait_for_timeout(200)
    on_vis = pg.evaluate("() => map.getLayoutProperty('world-point','visibility')")
    ok(on_vis == 'visible', f"layer visible again after switching on (got '{on_vis}')")

    print("\n[7] an embed without ?world=1 leaves the layer off")
    pg2 = ctx.new_page()
    pg2.on("pageerror", lambda e: errs.append(str(e)))
    pg2.goto(BASE + "?embed=1", wait_until="load")
    pg2.wait_for_timeout(2000)
    embed_off = pg2.evaluate("() => showWorld")
    ok(embed_off is False, f"showWorld is off in a bare embed (got {embed_off})")
    # Spots are precisely the exception: they always belong on it, in an embed too.
    embed_spots = pg2.evaluate("() => showSpots")
    ok(embed_spots is True, f"showSpots is on in an embed after all (got {embed_spots})")
    pg2.close()

    print("\n[8] an embed WITH ?world=1 does switch the layer on")
    pg3 = ctx.new_page()
    pg3.on("pageerror", lambda e: errs.append(str(e)))
    pg3.goto(BASE + "?embed=1&world=1", wait_until="load")
    pg3.wait_for_timeout(3000)
    embed_on = pg3.evaluate("() => showWorld")
    ok(embed_on is True, f"showWorld is on with ?world=1 (got {embed_on})")
    pg3.close()

    print("\n[9] no JS errors")
    real = [e for e in errs if "Failed to load resource" not in e]
    ok(not real, "no page errors: " + (real[0][:160] if real else "ok"))

    br.close()

print("\n" + ("ALL OK" if not fails else f"{len(fails)} PROBLEMS: " + " | ".join(fails)))
sys.exit(1 if fails else 0)
