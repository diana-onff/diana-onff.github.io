# Diana with more than one country on board.
#
# Until now the app fetched one pair of Belgian files whose names were written
# into the code. It reads data/countries.json instead now, and puts as many
# countries in memory as you ask for. There is only one country with real
# boundaries today, so the second one here is invented and served by the test:
# that is the point — the machinery has to work before the data for it exists,
# because that is the only way to find out that it works while nothing can
# break yet.
#
# Also checks the way back: a data set from before the manifest existed has no
# countries.json, and Diana has to fall back on the old Belgian filenames, or
# updating the app before the data would leave an empty map.
import json, pathlib, re, sys
from playwright.sync_api import sync_playwright
import preconsent  # noqa: F401  answered welcome screen, see preconsent.py

ROOT = pathlib.Path(__file__).resolve().parents[2]
BASE = "http://localhost:8011/web/"
fails = []

def ok(c, m):
    print(("  ✓ " if c else "  ✗ ") + m)
    if not c:
        fails.append(m)

def square(ref, name, lon, lat, d=0.02):
    ring = [[lon, lat], [lon + d, lat], [lon + d, lat + d], [lon, lat + d], [lon, lat]]
    return {"type": "Feature", "properties": {"ref": ref, "name": name},
            "geometry": {"type": "MultiPolygon", "coordinates": [[ring]]}}

# Two Dutch "reserves" on the Veluwe, far enough from any real ONFF boundary
# that nothing can be confused with anything.
PAFF_ZONES = {"type": "FeatureCollection", "features": [
    square("PAFF-9001", "Testpark Noord", 5.80, 52.20),
    square("PAFF-9002", "Testpark Zuid", 5.85, 52.10)]}
PAFF_POINTS = {"type": "FeatureCollection", "features": [
    {"type": "Feature", "properties": {"ref": "PAFF-9003", "name": "Testpark Zonder Grens"},
     "geometry": {"type": "Point", "coordinates": [5.9, 52.3]}}]}
PAFF_ACTIVITY = {"refs": {"PAFF-9001": {"q": 321, "last": "2025-05-05"}}}

MANIFEST = {"generated": "2026-09-13T00:00:00Z", "countries": [
    {"program": "ONFF", "country": "Belgium", "refs": 946, "points": 2,
     "files": {"zones": "zones/onff.geojson", "points": "zones/onff-points.geojson",
               "activity": "zones/onff-activity.json"}},
    {"program": "PAFF", "country": "Netherlands", "refs": 2, "points": 1,
     "files": {"zones": "zones/paff.geojson", "points": "zones/paff-points.geojson",
               "activity": "zones/paff-activity.json"}}]}

def json_route(body):
    return lambda r: r.fulfill(status=200, content_type="application/json",
                               body=json.dumps(body))

def file_route(path):
    return lambda r: r.fulfill(status=200, content_type="application/json", path=str(path))

def routes(ctx, manifest=True):
    ctx.route(re.compile(r"https://tiles\.openfreemap\.org/.*"), lambda r: r.fulfill(
        status=200, content_type="application/json",
        body=json.dumps({"version": 8, "sources": {}, "layers": [
            {"id": "bg", "type": "background", "paint": {"background-color": "#e8e4d8"}}]})))
    ctx.route(re.compile(r"https://spots\.wwff\.co/.*"), lambda r: r.fulfill(
        status=200, content_type="application/json", body="[]"))
    ctx.route(re.compile(r"https://docs\.google\.com/.*"), lambda r: r.abort())

    if manifest:
        ctx.route("**/data/countries.json", json_route(MANIFEST))
        # Belgium is the real thing, under its new name.
        ctx.route("**/data/zones/onff.geojson", file_route(ROOT / "data" / "onff.geojson"))
        ctx.route("**/data/zones/onff-points.geojson", file_route(ROOT / "data" / "onff-points.geojson"))
        ctx.route("**/data/zones/onff-activity.json", file_route(ROOT / "data" / "onff-activity.json"))
        ctx.route("**/data/zones/paff.geojson", json_route(PAFF_ZONES))
        ctx.route("**/data/zones/paff-points.geojson", json_route(PAFF_POINTS))
        ctx.route("**/data/zones/paff-activity.json", json_route(PAFF_ACTIVITY))
    else:
        ctx.route("**/data/countries.json", lambda r: r.fulfill(status=404, body="no"))

with sync_playwright() as p:
    br = p.chromium.launch()

    print("\n[1] no manifest: the Belgian files under their old names, as before")
    ctx = br.new_context(service_workers="block", viewport={"width": 420, "height": 860})
    routes(ctx, manifest=False)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE, wait_until="load")
    pg.wait_for_timeout(2500)
    ok(pg.evaluate("() => loadedPrograms") == ["ONFF"], "ONFF is loaded")
    ok(pg.evaluate("() => zones.features.length") > 900, "with all of its boundaries")
    ok(pg.evaluate("() => countries[0].legacy === true"), "and it knows it fell back")
    ctx.close()

    print("\n[2] with a manifest, two countries go in at once")
    ctx = br.new_context(service_workers="block", viewport={"width": 420, "height": 860})
    routes(ctx)
    ctx.add_init_script("localStorage.setItem('diana.countries', JSON.stringify(['ONFF','PAFF']))")
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE, wait_until="load")
    pg.wait_for_timeout(3000)
    ok(pg.evaluate("() => loadedPrograms") == ["ONFF", "PAFF"], "both countries loaded")
    n = pg.evaluate("() => zones.features.length")
    ok(n > 940, f"the boundaries are pooled, not replaced ({n})")
    ok(pg.evaluate("() => zones.features.some(f => f.properties.ref === 'PAFF-9001')"),
       "a Dutch reference is among them")
    ok(pg.evaluate("() => index.some(z => z.ref === 'PAFF-9003')"),
       "and a Dutch reference without a boundary is in the index too")
    ok(pg.evaluate("() => (activityOf('PAFF-9001')||{}).qso") == 321,
       "the Dutch activity figures came along")
    ok(pg.evaluate("() => (activityOf('ONFF-0002')||{}).qso") > 1000,
       "and the Belgian ones are still there")

    print("\n[3] standing in a Dutch reserve gives a Dutch answer")
    pg.evaluate("() => { hideStatus(); evaluate(52.21, 5.81, 10); }")
    pg.wait_for_timeout(300)
    cls = pg.evaluate("() => document.getElementById('status').className")
    ok("in" in cls.split(), f"inside ({cls})")
    ok("PAFF-9001" in pg.evaluate("() => document.getElementById('stT2').textContent"),
       "and it names the Dutch reference")

    print("\n[4] Nearby counts the Dutch ones too")
    pg.evaluate("() => { here = {lat: 52.2, lon: 5.8}; cfg.nearkm = 50; nearShown = 100; renderNearby(); }")
    pg.wait_for_timeout(300)
    rows = pg.evaluate("() => nearbyRows().map(r => r.ref)")
    ok(any(r.startswith("PAFF") for r in rows), f"Dutch references are in the list ({rows[:3]})")

    print("\n[5] a country on board is not also drawn as bare points")
    pg.evaluate("""() => {
        worldPoints = {type:'FeatureCollection', features: [
            {type:'Feature', properties:{ref:'PAFF-9001', name:'x'}, geometry:{type:'Point', coordinates:[5.8,52.2]}},
            {type:'Feature', properties:{ref:'ONFF-0001', name:'y'}, geometry:{type:'Point', coordinates:[4.3,50.8]}},
            {type:'Feature', properties:{ref:'DLFF-0001', name:'z'}, geometry:{type:'Point', coordinates:[7.0,51.0]}}]};
        worldLoaded = true; worldFilter = 'all';
    }""")
    left = pg.evaluate("() => worldFilteredData().features.map(f => f.properties.ref)")
    ok(left == ["DLFF-0001"], f"only the country without boundaries is left as a point ({left})")

    print("\n[6] one country that will not load does not take the other down")
    ctx2 = br.new_context(service_workers="block", viewport={"width": 420, "height": 860})
    routes(ctx2)
    ctx2.route("**/data/zones/paff.geojson", lambda r: r.fulfill(status=500, body="nope"))
    ctx2.add_init_script("localStorage.setItem('diana.countries', JSON.stringify(['ONFF','PAFF']))")
    pg2 = ctx2.new_page()
    pg2.goto(BASE, wait_until="load")
    pg2.wait_for_timeout(3000)
    ok(pg2.evaluate("() => loadedPrograms") == ["ONFF"], "the Netherlands dropped out")
    ok(pg2.evaluate("() => zones.features.length") > 900, "and Belgium is untouched")
    ctx2.close()

    print("\n[7] nothing thrown along the way")
    ok(not errs, f"no page errors: {errs[:2] or 'ok'}")

    print("\n" + ("ALL OK" if not fails else f"{len(fails)} PROBLEMS"))
    br.close()
    sys.exit(1 if fails else 0)
