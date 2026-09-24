# The arc lines to the spots: do they keep pointing at where you actually are?
#
#     python3 build/tests/test_spot_arcs.py
#
# A field report: the marker was standing correctly in the middle of a forest,
# but every line to a spot and to an announced activation fanned out from a
# point hundreds of metres away instead — and a page reload fixed it. Traced
# to paintSpots(): it used to refuse to touch anything, sources included,
# unless map.isStyleLoaded() said the style was completely done loading. But
# fixApply() calls map.easeTo() to the new position and only THEN calls
# paintSpots() — on every single GPS tick — so the style was, more often than
# not, still busy loading the tiles that pan had just asked for. Updating a
# source that is already part of the style needs none of that; only adding a
# brand new one does. The old code treated both the same way, so a position
# update landing during a busy style got silently dropped: the marker moved
# on with the very next fix, the lines waited for a style that stayed busy
# past the ~8 s a retry is willing to wait for, and then nothing asked again
# until the next spots refresh — or a reload rebuilt everything from scratch.
#
# GPS is a real Playwright geolocation mock (not the gh() stubbing pattern —
# there is no GitHub here), Spotline is intercepted the same way
# test_worldpoints.py does it.
import json, re, sys, math
from playwright.sync_api import sync_playwright
import preconsent  # noqa: F401  answered welcome screen, see preconsent.py

BASE = "http://localhost:8011/web/?embed=1"   # embed=1: skip the ~9 MB worldwide layer
fails = []

# A: somewhere in Hoboken. B: ~600 m east of it — far enough that "the old
# position" and "the new one" are never mistaken for rounding.
A = {"latitude": 51.1740, "longitude": 4.3400, "accuracy": 8}
B = {"latitude": 51.1740, "longitude": 4.3486, "accuracy": 8}

SPOTS = [{"id": 1, "activator": "ON4AA", "reference": "ONFF-0001",
          "latitude": 50.5, "longitude": 4.0, "frequency_khz": 14244, "mode": "SSB",
          "spot_time": 0}]   # spot_time patched in below, once "now" is known


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
        status=200, content_type="application/json", body=json.dumps(SPOTS)))
    ctx.route(re.compile(r"https://spots\.wwff\.co/static/agendas.*"), lambda r: r.fulfill(
        status=200, content_type="application/json", body="[]"))
    ctx.route(re.compile(r"https://docs\.google\.com/.*"), lambda r: r.abort())


READ = """() => {
  const src = map.getSource('spot-arcs');
  const d = src ? src._data : null;
  const first = d && d.features && d.features[0] ? d.features[0].geometry.coordinates[0] : null;
  const mk = marker.getLngLat();
  return {marker: [mk.lng, mk.lat], arcFrom: first, arcsExist: !!src};
}"""


def metres(p, q):
    if not p or not q:
        return None
    dx = (p[0] - q[0]) * 111320 * math.cos(math.radians(p[1]))
    dy = (p[1] - q[1]) * 110540
    return round(math.hypot(dx, dy))


def fix(pg, pos, final=True):
    pg.evaluate("""(a) => fixApply({coords:{latitude:a.lat, longitude:a.lon, accuracy:a.acc},
                                     timestamp:Date.now()}, a.final)""",
                {"lat": pos["latitude"], "lon": pos["longitude"], "acc": pos["accuracy"], "final": final})


with sync_playwright() as p:
    import time
    SPOTS[0]["spot_time"] = int(time.time()) - 60

    br = p.chromium.launch()
    ctx = br.new_context(service_workers="block", viewport={"width": 420, "height": 860},
                          permissions=["geolocation"], geolocation=A)
    routes(ctx)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE, wait_until="load")
    pg.wait_for_timeout(3000)
    pg.wait_for_function("() => map.isStyleLoaded()", timeout=20000)
    pg.evaluate("() => paintSpots()")
    pg.wait_for_function("() => !!map.getSource('spot-arcs')", timeout=20000)

    print("\n[1] to start with, the lines do come from the marker")
    st = pg.evaluate(READ)
    ok(metres(st["arcFrom"], st["marker"]) == 0, f"arc origin matches the marker ({st})")

    print("\n[2] a position update that lands while the style reports itself busy")
    # This is the ordinary case on a phone: fixApply() has just called
    # map.easeTo() to the new spot, which is exactly what keeps a style busy.
    pg.evaluate("() => { window.__real = map.isStyleLoaded.bind(map); map.isStyleLoaded = () => false; }")
    fix(pg, B)
    pg.wait_for_timeout(200)
    st = pg.evaluate(READ)
    ok(st["marker"][0] > 4.345, f"the marker moved to B ({st['marker']})")
    ok(metres(st["arcFrom"], st["marker"]) == 0,
       f"and the lines moved with it, style still 'busy' — this was the bug ({st})")

    print("\n[3] busy for a lot longer than the old ~8 s retry budget: still no gap")
    pg.wait_for_timeout(9000)
    st = pg.evaluate(READ)
    ok(metres(st["arcFrom"], st["marker"]) == 0, f"still together after 9 s of a busy style ({st})")
    pg.evaluate("() => { map.isStyleLoaded = window.__real; }")

    print("\n[4] a full style switch really does wipe the sources — and that case still waits, correctly")
    pg.evaluate("""() => {
        ['agenda-arcs-line','spot-arcs-line','agenda-dot','spots-pulse','spots-icon',
         'agenda-label','spots-call'].forEach(l => { if(map.getLayer(l)) map.removeLayer(l); });
        ['spots','agenda-pts','spot-arcs','agenda-arcs'].forEach(s => { if(map.getSource(s)) map.removeSource(s); });
    }""")
    pg.evaluate("() => { window.__real = map.isStyleLoaded.bind(map); map.isStyleLoaded = () => false; }")
    fix(pg, A)
    pg.wait_for_timeout(200)
    ok(not pg.evaluate("() => !!map.getSource('spot-arcs')"),
       "correctly nothing yet — creating a source needs the style done loading")
    pg.evaluate("() => { map.isStyleLoaded = window.__real; }")
    pg.wait_for_function("() => !!map.getSource('spot-arcs')", timeout=5000)
    pg.wait_for_timeout(200)
    st = pg.evaluate(READ)
    ok(metres(st["arcFrom"], st["marker"]) == 0,
       f"and it catches up the moment the style is ready again ({st})")

    print("\n[5] while that creation is still waiting, a newer position wins — not the older one")
    pg.evaluate("""() => {
        ['agenda-arcs-line','spot-arcs-line','agenda-dot','spots-pulse','spots-icon',
         'agenda-label','spots-call'].forEach(l => { if(map.getLayer(l)) map.removeLayer(l); });
        ['spots','agenda-pts','spot-arcs','agenda-arcs'].forEach(s => { if(map.getSource(s)) map.removeSource(s); });
    }""")
    pg.evaluate("() => { window.__real = map.isStyleLoaded.bind(map); map.isStyleLoaded = () => false; }")
    fix(pg, A)     # first wave, while nothing can be created yet
    pg.wait_for_timeout(100)
    fix(pg, B)     # a second, newer fix before the style frees up
    pg.evaluate("() => { map.isStyleLoaded = window.__real; }")
    pg.wait_for_function("() => !!map.getSource('spot-arcs')", timeout=5000)
    pg.wait_for_timeout(200)
    st = pg.evaluate(READ)
    ok(st["marker"][0] > 4.345, f"the marker is on B, the newer of the two ({st['marker']})")
    ok(metres(st["arcFrom"], st["marker"]) == 0,
       f"and so are the lines — not stuck on A, the fix that arrived first ({st})")

    print("\n[6] coming back to the app refreshes the spots, not just a wait for the 30 s timer")
    calls = {"n": 0}
    pg.expose_function("__spotsFetched", lambda: calls.__setitem__("n", calls["n"] + 1))
    pg.evaluate("() => { const orig = fetchSpots; fetchSpots = (...a) => { __spotsFetched(); return orig(...a); }; }")
    pg.evaluate("""() => {
        Object.defineProperty(document, 'visibilityState', {value: 'visible', configurable: true});
        document.dispatchEvent(new Event('visibilitychange'));
    }""")
    pg.wait_for_timeout(300)
    ok(calls["n"] > 0, "visibilitychange re-fetched the spots without waiting for the timer")

    print("\n[7] nothing thrown along the way")
    real = [e for e in errs if "Failed to load resource" not in e]
    ok(not real, f"no page errors: {real[:2] or 'ok'}")

    print("\n" + ("ALL OK" if not fails else f"{len(fails)} PROBLEMS"))
    br.close()
    sys.exit(1 if fails else 0)
