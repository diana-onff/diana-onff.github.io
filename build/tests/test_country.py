# One country setting, and everything that reads it.
#
# Diana used to carry three separate notions of "country" that knew nothing of
# one another: the one the spots filter offered, the one the worldwide points
# were narrowed to (its own dropdown in Settings), and the one whose boundaries
# were actually in memory. That last one was never asked at all — it went by
# your callsign — so picking the Netherlands in Settings changed the spots and
# left the map Belgian.
#
# There is one value now. This checks that all three read it, that changing it
# swaps the boundaries while the app is running rather than at the next start,
# and that a country we have no boundaries for is honest about it instead of
# showing an empty map.
#
# The repo has real boundaries for one country only, so the second one here is
# invented and served by the test — which is the point: switching between two
# countries that both have boundaries has to work before there is a second real
# one to try it with.
import json, pathlib, re, sys
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[2]
BASE = "http://localhost:8011/web/"
fails = []


def ok(c, m):
    print(("  ✓ " if c else "  ✗ ") + m)
    if not c:
        fails.append(m)


def square(ref, name, lon, lat, d=0.03):
    ring = [[lon, lat], [lon + d, lat], [lon + d, lat + d], [lon, lat + d], [lon, lat]]
    return {"type": "Feature", "properties": {"ref": ref, "name": name},
            "geometry": {"type": "MultiPolygon", "coordinates": [[ring]]}}


PAFF_ZONES = {"type": "FeatureCollection", "features": [
    square("PAFF-9001", "Testpark Noord", 5.80, 52.20),
    square("PAFF-9002", "Testpark Zuid", 5.85, 52.10),
    square("PAFF-9003", "Testpark Oost", 5.90, 52.15)]}
PAFF_POINTS = {"type": "FeatureCollection", "features": [
    {"type": "Feature", "properties": {"ref": "PAFF-9004", "name": "Zonder Grens"},
     "geometry": {"type": "Point", "coordinates": [5.95, 52.30]}}]}
PAFF_ACTIVITY = {"refs": {"PAFF-9001": {"q": 321, "last": "2025-05-05"}}}

MANIFEST = {"generated": "2026-09-14T00:00:00Z", "countries": [
    {"program": "ONFF", "country": "Belgium", "refs": 946, "points": 2,
     "files": {"zones": "zones/onff.geojson", "points": "zones/onff-points.geojson",
               "activity": "zones/onff-activity.json"}},
    {"program": "PAFF", "country": "Netherlands", "refs": 3, "points": 1,
     "files": {"zones": "zones/paff.geojson", "points": "zones/paff-points.geojson",
               "activity": "zones/paff-activity.json"}}]}


def json_route(body):
    return lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(body))


def file_route(path):
    return lambda r: r.fulfill(status=200, content_type="application/json", path=str(path))


def routes(ctx):
    ctx.route(re.compile(r"https://tiles\.openfreemap\.org/.*"), lambda r: r.fulfill(
        status=200, content_type="application/json",
        body=json.dumps({"version": 8, "sources": {}, "layers": [
            {"id": "bg", "type": "background", "paint": {"background-color": "#e8e4d8"}}]})))
    ctx.route(re.compile(r"https://spots\.wwff\.co/.*"), lambda r: r.fulfill(
        status=200, content_type="application/json", body="[]"))
    ctx.route(re.compile(r"https://docs\.google\.com/.*"), lambda r: r.abort())
    ctx.route("**/data/countries.json", json_route(MANIFEST))
    ctx.route("**/data/zones/onff.geojson", file_route(ROOT / "data" / "onff.geojson"))
    ctx.route("**/data/zones/onff-points.geojson", file_route(ROOT / "data" / "onff-points.geojson"))
    ctx.route("**/data/zones/onff-activity.json", file_route(ROOT / "data" / "onff-activity.json"))
    ctx.route("**/data/zones/paff.geojson", json_route(PAFF_ZONES))
    ctx.route("**/data/zones/paff-points.geojson", json_route(PAFF_POINTS))
    ctx.route("**/data/zones/paff-activity.json", json_route(PAFF_ACTIVITY))


SOURCE_REFS = """() => {
    const s = map.getSource('onff');
    if(!s || !s._data) return null;
    return [...new Set(s._data.features.map(f => f.properties.ref.split('-')[0]))];
}"""


def source_refs(pg):
    """What MapLibre is actually holding — not what the globals say it should
    be. The two came apart once already: paintZones() only ever ADDED its
    source, so a country switch that forgot to hand it new data would leave the
    old boundaries on screen while every variable said otherwise."""
    return pg.evaluate(SOURCE_REFS)


def wait_source(pg, prog):
    """Wait until the map holds that country. Not a fixed sleep: when the style
    happens to be busy the redraw goes through redrawOverlays(), which tries
    again every 80 ms, so how long it takes is genuinely variable."""
    try:
        pg.wait_for_function(
            "prog => { const s = map.getSource('onff');"
            "  if(!s || !s._data) return false;"
            "  const p = [...new Set(s._data.features.map(f => f.properties.ref.split('-')[0]))];"
            "  return p.length === 1 && p[0] === prog; }",
            arg=prog, timeout=15000)
    except Exception:
        pass    # let the assertion below report what it really is


with sync_playwright() as p:
    br = p.chromium.launch()
    ctx = br.new_context(service_workers="block", viewport={"width": 420, "height": 860})
    routes(ctx)
    # A Belgian callsign and no country ever chosen: the fallback everyone
    # starts with.
    ctx.add_init_script("localStorage.setItem('diana.call', 'ON3VZ')")
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE, wait_until="load")
    pg.wait_for_timeout(3000)

    print("\n[1] without a choice, your callsign decides — and the map follows")
    ok(pg.evaluate("() => homeCountry()") == "ONFF", "ON3VZ → ONFF")
    ok(pg.evaluate("() => loadedPrograms") == ["ONFF"], "and Belgium is what got loaded")
    ok(pg.evaluate("() => zones.features.length") > 900, "with its boundaries")
    wait_source(pg, "ONFF")
    ok(source_refs(pg) == ["ONFF"], "and the map is holding them")

    print("\n[2] Settings says which country it is and what we have for it")
    pg.evaluate("() => document.querySelector('#nav button[data-view=\"viewSet\"]').click()")
    pg.wait_for_timeout(400)
    ok(pg.evaluate("() => document.getElementById('setSpotCountry').value") == "ONFF",
       "the picker names your country")
    regel = pg.evaluate("() => document.getElementById('setCountryState').textContent")
    ok("946" in regel, f"and says what is on board ({regel!r})")

    print("\n[3] changing it swaps the boundaries there and then")
    pg.evaluate("() => setHomeCountry('PAFF')")
    pg.wait_for_timeout(1200)
    ok(pg.evaluate("() => loadedPrograms") == ["PAFF"], "the Netherlands is loaded")
    ok(pg.evaluate("() => zones.features.length") == 3, "three Dutch boundaries")
    ok(not pg.evaluate("() => zones.features.some(f => f.properties.ref.startsWith('ONFF'))"),
       "and not one Belgian one left in memory")
    wait_source(pg, "PAFF")
    ok(source_refs(pg) == ["PAFF"], "the map itself was handed the new data too")
    ok(pg.evaluate("() => index.some(z => z.ref === 'PAFF-9004')"),
       "the reference without a boundary came along, into the search index")
    ok(pg.evaluate("() => (activityOf('PAFF-9001')||{}).qso") == 321,
       "and so did the QSO figures")

    print("\n[4] no restart needed anywhere else either")
    ok(pg.evaluate("() => document.querySelector('#spotFilter [data-home]').textContent") == "PAFF",
       "the spots button followed")
    ok("3" in pg.evaluate("() => document.getElementById('counts').textContent"),
       "the count under the map followed")
    ok("PAFF" in pg.evaluate("() => document.getElementById('setCountryState').textContent"),
       "and Settings says so")

    print("\n[5] standing in a Dutch reserve now gives a Dutch answer")
    pg.evaluate("() => { hideStatus(); evaluate(52.21, 5.81, 10); }")
    pg.wait_for_timeout(300)
    cls = pg.evaluate("() => document.getElementById('status').className")
    ok("in" in cls.split(), f"inside ({cls})")
    ok("PAFF-9001" in pg.evaluate("() => document.getElementById('stT2').textContent"),
       "and it names the Dutch reference")

    print("\n[6] a selection from the country that just left is let go")
    pg.evaluate("() => select('PAFF-9002')")
    pg.wait_for_timeout(300)
    ok(pg.evaluate("() => selected") == "PAFF-9002", "something Dutch is selected")
    pg.evaluate("() => setHomeCountry('ONFF')")
    pg.wait_for_timeout(2500)
    ok(pg.evaluate("() => selected") is None, "after the switch nothing is selected")
    ok(pg.evaluate("() => loadedPrograms") == ["ONFF"], "and Belgium is back")
    wait_source(pg, "ONFF")
    ok(source_refs(pg) == ["ONFF"], "on the map as well")

    print("\n[7] a country we have no boundaries for says so, and keeps its points")
    pg.evaluate("() => setHomeCountry('DLFF')")
    pg.wait_for_timeout(1500)
    ok(pg.evaluate("() => loadedPrograms") == [], "nothing is loaded — we have no German boundaries")
    ok(pg.evaluate("() => zones.features.length") == 0, "so there are no areas")
    regel = pg.evaluate("() => document.getElementById('setCountryState').textContent")
    ok("DLFF" in regel and len(regel) > 20, f"and Settings explains why ({regel!r})")
    ok(pg.evaluate("() => homeProgram()") == "DLFF", "it is still your country")
    # The worldwide layer is the only place German references exist at all, so
    # that is exactly what must be left on the map.
    pg.wait_for_function("() => worldLoaded === true", timeout=20000)
    pg.evaluate("() => document.querySelector('#spotFilter [data-home]').click()")
    pg.wait_for_timeout(600)
    n = pg.evaluate("() => worldFilteredData().features.length")
    alles_dl = pg.evaluate(
        "() => worldFilteredData().features.every(f => f.properties.ref.split('-')[0] === 'DLFF')")
    ok(n > 0 and alles_dl, f"the German references are there as points ({n})")
    ok("<b>" in pg.evaluate("() => document.getElementById('counts').innerHTML"),
       "and the line under the map counts those instead of reporting zero areas")

    print("\n[8] the choice survives a restart")
    pg.reload(wait_until="load")
    pg.wait_for_timeout(3000)
    ok(pg.evaluate("() => homeCountry()") == "DLFF", "still Germany after a reload")
    ok(pg.evaluate("() => loadedPrograms") == [], "still nothing loaded for it")
    pg.evaluate("() => setHomeCountry('ONFF')")
    pg.wait_for_timeout(2500)
    ok(pg.evaluate("() => loadedPrograms") == ["ONFF"], "and back to Belgium in one step")

    print("\n[9] nothing thrown along the way")
    ok(not errs, f"no page errors: {errs[:2] or 'ok'}")

    print("\n" + ("ALL OK" if not fails else f"{len(fails)} PROBLEMS"))
    br.close()
    sys.exit(1 if fails else 0)
