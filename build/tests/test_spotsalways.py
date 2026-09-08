"""Spots are always on the map; only the lines leading to them can be toggled.

And: the map opens where you are standing, exactly as if you had pressed the
location button — without there being a setting for it any more.
"""
import re, json, sys
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8011/web/"
fails = []
SPOTS = [{"id": 1, "reference": "ONFF-0001", "activator": "ON4TEST/P", "latitude": 50.85,
          "longitude": 4.35, "frequency_khz": 14285, "mode": "SSB", "spot_time": 9999999999}]


def ok(c, m):
    print(("  \u2713 " if c else "  \u2717 ") + m)
    if not c:
        fails.append(m)


def routes(ctx):
    ctx.route(re.compile(r"https://tiles\.openfreemap\.org/.*"), lambda r: r.fulfill(
        status=200, content_type="application/json",
        body=json.dumps({"version": 8, "sources": {}, "layers": [
            {"id": "bg", "type": "background", "paint": {"background-color": "#e8e4d8"}}]})))
    ctx.route(re.compile(r"https://spots\.wwff\.co/static/spots\.json"), lambda r: r.fulfill(
        status=200, content_type="application/json", body=json.dumps(SPOTS)))
    ctx.route(re.compile(r"https://spots\.wwff\.co/static/agendas.*"), lambda r: r.fulfill(
        status=200, content_type="application/json", body="[]"))
    ctx.route(re.compile(r"https://docs\.google\.com/.*"), lambda r: r.abort())


with sync_playwright() as p:
    br = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
                           if __import__("os").path.exists("/opt/pw-browsers/chromium-1194/chrome-linux/chrome") else None)

    print("\n[1] the map opens where you are standing, unasked")
    ctx = br.new_context(service_workers="block", viewport={"width": 420, "height": 860},
                         permissions=["geolocation"],
                         geolocation={"latitude": 51.05, "longitude": 3.72})
    routes(ctx)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE, wait_until="load")
    pg.wait_for_timeout(4500)
    c = pg.evaluate("() => { const c = map.getCenter(); return [+c.lng.toFixed(2), +c.lat.toFixed(2), Math.round(map.getZoom())]; }")
    ok(abs(c[0] - 3.72) < 0.05 and abs(c[1] - 51.05) < 0.05, f"centred on the GPS position {c}")
    ok(c[2] >= 12, f"zoomed in the way the location button does (zoom {c[2]})")
    ok(pg.evaluate("() => !!here"), "'here' is set, so the arc lines can be drawn")
    ok(pg.evaluate("() => !!document.querySelector('.maplibregl-marker')"), "position marker is on the map")

    print("\n[2] there is nothing left to choose in Settings")
    ok(pg.evaluate("() => !document.getElementById('setView')"), "the start-view card no longer exists")

    print("\n[3] spots are on by default, but can be switched off")
    ok(pg.evaluate("() => showSpots === true"), "showSpots is on by default")
    ok(pg.evaluate("() => !!document.querySelector('[data-layer=spots]')"),
       "the spots switch is in the layers panel")
    ok(pg.evaluate("() => document.querySelector('[data-layer=spots]').classList.contains('on')"),
       "and that switch is set to on")

    print("\n[4] the lines leading to them can be, and that choice stays saved")
    pg.wait_for_timeout(1200)
    ok(pg.evaluate("() => map.getLayoutProperty('spot-arcs-line','visibility')") == "visible",
       "lines are on by default")
    pg.evaluate("() => document.querySelector('.opt[data-layer=arcs]').click()")
    pg.wait_for_timeout(300)
    ok(pg.evaluate("() => map.getLayoutProperty('spot-arcs-line','visibility')") == "none", "lines off")
    ok(pg.evaluate("() => map.getLayoutProperty('spots-icon','visibility')") == "visible",
       "the spots themselves stay put")
    pg.reload(wait_until="load")
    pg.wait_for_timeout(4500)
    ok(pg.evaluate("() => showArcs === false"), "lines still off after a reload")
    ok(pg.evaluate("() => showSpots === true"), "spots are simply back on after a reload")
    real = [e for e in errs if "Failed to load resource" not in e]
    ok(not real, "no JS errors: " + (real[0][:140] if real else "ok"))
    ctx.close()

    print("\n[5] location refused: no complaint, just a usable map")
    ctx = br.new_context(service_workers="block", viewport={"width": 420, "height": 860})
    routes(ctx)
    pg = ctx.new_page()
    pg.goto(BASE, wait_until="load")
    pg.wait_for_timeout(4500)
    ok(not pg.evaluate("() => { const r = document.getElementById('status').getBoundingClientRect(); return r.width > 0 && r.height > 0; }"),
       "no error message in view")
    ok(pg.evaluate("() => map.getZoom()") > 5, "the map is on the areas, not on an empty globe")
    br.close()

print("\n" + ("ALL OK" if not fails else f"{len(fails)} PROBLEMS: " + " | ".join(fails)))
sys.exit(1 if fails else 0)
