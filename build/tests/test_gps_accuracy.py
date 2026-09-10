# "Am I inside this zone?" has to treat the GPS's own reported accuracy the
# same way on both sides of a boundary. Before this test existed, a point
# that fell just outside a real boundary was reported as a flat "you are
# outside", even when the offset was well within the GPS's own error margin —
# while the mirror case (just inside, near the edge) already got a "check
# visually, GPS accuracy is..." caveat. This locks in the fix: both sides of
# a boundary get the same "too close to call" treatment once the reported
# accuracy is bigger than the real distance to the edge.
import re, json, sys
from playwright.sync_api import sync_playwright

URL = "http://localhost:8011/web/index.html"

def ok(cond, msg):
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        sys.exit(1)

def route_all(ctx):
    # No network in this container: intercept anything that wants to go out,
    # same as the rest of build/tests/. select()'s markSelected() needs a
    # loaded map style, hence the minimal-but-valid style body here.
    ctx.route(re.compile(r"https://tiles\.openfreemap\.org/.*"), lambda r: r.fulfill(
        status=200, content_type="application/json",
        body=json.dumps({"version":8,"sources":{},"layers":[
            {"id":"bg","type":"background","paint":{"background-color":"#e8e4d8"}}]})))
    ctx.route(re.compile(r"https://spots\.wwff\.co/.*"), lambda r: r.fulfill(
        status=200, content_type="application/json", body="[]"))
    ctx.route(re.compile(r"https://docs\.google\.com/.*"), lambda r: r.abort())

with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(service_workers="block")
    route_all(ctx)
    pg = ctx.new_page()
    pg.goto(URL, wait_until="load")
    pg.wait_for_timeout(2500)

    # Find a real polygon vertex, then use the app's own pointInGeom() to
    # confirm which direction is genuinely outside — rather than assuming a
    # perturbation direction, since real ONFF polygons are not all wound the
    # same way and several are made of many disconnected parcels.
    point = pg.evaluate("""
      () => {
        const f = zones.features.find(x => x.geometry &&
          x.geometry.coordinates.length && x.geometry.coordinates[0][0].length > 3);
        const [vlon, vlat] = f.geometry.coordinates[0][0][0];
        const eps = 0.00003; // roughly 2-3 m at Belgian latitudes
        for (const [dlon, dlat] of [[-eps,0],[eps,0],[0,-eps],[0,eps]]) {
          const lon = vlon + dlon, lat = vlat + dlat;
          if (!pointInGeom(lon, lat, f.geometry)) {
            const d = distanceToZone(lat, lon, f);
            return {ref: f.properties.ref, lat, lon, d};
          }
        }
        return null;
      }
    """)
    ok(point is not None, "found a usable near-boundary test point in the real dataset")
    ref, lat, lon, d = point["ref"], point["lat"], point["lon"], point["d"]
    print(f"  (using {ref}, real distance to the boundary: {d:.2f} m)")

    print("\n[1] just outside, accuracy well above the real offset -> 'near', not 'out'")
    pg.evaluate(f"() => evaluate({lat}, {lon}, {d + 15})")
    ok("near" in pg.evaluate("() => document.getElementById('status').className").split(),
       "status is 'near' when the reported accuracy exceeds the real offset")

    print("\n[2] same point, accuracy tighter than the real offset -> genuinely 'out'")
    pg.evaluate(f"() => evaluate({lat}, {lon}, {max(d - 0.5, 0.01)})")
    ok("out" in pg.evaluate("() => document.getElementById('status').className").split(),
       "status is 'out' once accuracy is tighter than the real offset")

    print("\n[3] far outside any zone, generous accuracy -> plain 'out', never 'near'")
    pg.evaluate("() => evaluate(51.7, 2.5, 50)")  # North Sea, well off the Belgian coast
    ok("out" in pg.evaluate("() => document.getElementById('status').className").split(),
       "a genuinely distant point never gets the 'near' treatment")

    print("\nALL OK")
    browser.close()
