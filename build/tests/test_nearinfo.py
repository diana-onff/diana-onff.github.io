"""Nearby > Info: the locator, CQ zone, ITU zone, ITU region and nearest WWFF
references, and the tab itself.

The arithmetic is checked in the page (radiogeo.js is plain functions, loaded
like every other file), against places whose zones and region are not in
doubt, and the nearest-reference search against brute force.

    python3 -m http.server 8011          # from the repo root
    python3 build/tests/test_nearinfo.py
"""
import re, json, sys
from playwright.sync_api import sync_playwright
import preconsent  # noqa: F401  answered welcome screen, see preconsent.py

BASE = "http://localhost:8011/web/"
HOBOKEN = {"latitude": 51.175, "longitude": 4.345}
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
    ctx.route(re.compile(r"https://spots\.wwff\.co/.*"),
              lambda r: r.fulfill(status=200, content_type="application/json", body="[]"))
    ctx.route(re.compile(r"https://docs\.google\.com/.*"), lambda r: r.abort())


# (lat, lon, CQ zone, ITU zone, ITU region). Zones where the whole city sits
# well inside one; regions including the Article 5 exceptions (Russia and
# Central Asia are Region 1 east of line A, Iran is Region 3 west of it) and
# both sides of the date line.
PLACES = {
    "Hoboken":      (51.175,   4.345, 14, 27, 1),
    "Berlin":       (52.52,   13.40,  14, 28, 1),
    "Helsinki":     (60.17,   24.94,  15, 18, 1),
    "Rome":         (41.90,   12.50,  15, 28, 1),
    "Madrid":       (40.40,   -3.70,  14, 37, 1),
    "Reykjavik":    (64.10,  -21.90,  40, 17, 1),
    "New York":     (40.70,  -74.00,   5,  8, 2),
    "Anchorage":    (61.20, -149.90,   1,  1, 2),
    "Honolulu":     (21.30, -157.80,  31, 61, 2),
    "Tokyo":        (35.68,  139.70,  25, 45, 3),
    "Sydney":      (-33.87,  151.20,  30, 59, 3),
    "Suva":        (-18.10,  178.40,  32, 56, 3),
    "Cape Town":   (-33.90,   18.40,  38, 57, 1),
    "Moscow":       (55.75,   37.60,  16, 29, 1),
    "Kamchatka":    (53.00,  158.70,  19, 35, 1),
}
REGIONS_ONLY = {
    "Novosibirsk": (55.0, 82.9, 1), "Almaty": (43.24, 76.9, 1), "Ulaanbaatar": (47.9, 106.9, 1),
    "Tbilisi": (41.7, 44.8, 1), "Tabriz": (38.08, 46.3, 3), "Tehran": (35.7, 51.4, 3),
    "Baghdad": (33.3, 44.4, 1), "Muscat": (23.6, 58.4, 1), "Kabul": (34.5, 69.2, 3),
    "Beijing": (39.9, 116.4, 3), "Chukotka": (64.73, 177.5, 1), "Wrangel": (71.2, -179.5, 1),
    "Adak": (51.88, -176.6, 2), "Tahiti": (-17.5, -149.6, 3), "Easter Island": (-27.1, -109.4, 2),
    "Nuuk": (64.2, -51.7, 2), "Azores": (37.7, -25.7, 1), "Caspian Sea": (42.0, 50.5, 1),
}


def page(br, geo=True, **kw):
    opts = dict(service_workers="block", viewport={"width": 420, "height": 860},
                timezone_id="Europe/Brussels")
    if geo:
        opts.update(geolocation=dict(HOBOKEN, accuracy=8), permissions=["geolocation"])
    opts.update(kw)
    ctx = br.new_context(**opts)
    routes(ctx)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE, wait_until="load")
    pg.wait_for_function("() => typeof index !== 'undefined' && index && index.length > 0", timeout=20000)
    return ctx, pg, errs


def open_info(pg):
    pg.evaluate("() => document.querySelector('#nav button[data-view=\"viewNearby\"]').click()")
    pg.wait_for_timeout(300)
    pg.click("#nearTab .seg[data-neartab='info']")
    pg.wait_for_function("() => typeof radioZones !== 'undefined' && radioZones !== null", timeout=15000)
    pg.wait_for_timeout(300)


def js(pg, expr):
    return pg.evaluate("() => " + expr)


with sync_playwright() as p:
    br = p.chromium.launch()
    ctx, pg, errs = page(br)
    open_info(pg)

    print("\n[1] Maidenhead locator")
    ok(js(pg, "maidenhead(51.175, 4.345, 3)") == "JO21EE", "Hoboken is JO21EE")
    ok(js(pg, "maidenhead(41.714775, -72.72726, 3)") == "FN31PR", "Newington CT is FN31PR")
    ok(js(pg, "maidenhead(-33.87, 151.2, 3)") == "QF56OD", "Sydney is QF56OD")
    ok(js(pg, "maidenhead(51.175, 4.345, 4)").startswith("JO21EE") and len(js(pg, "maidenhead(51.175, 4.345, 4)")) == 8,
       "eight characters extend the six")
    ok(re.fullmatch(r"[A-R]{2}\d\d[A-X]{2}", js(pg, "maidenhead(90, 180, 3)")) is not None, "the pole and date line stay valid")
    same = js(pg, """(() => { let bad = 0; for(let i = 0; i < 2000; i++){
        const la = Math.random()*170-85, lo = Math.random()*358-179;
        if(locator(la, lo) !== maidenhead(la, lo, 3)) bad++; } return bad; })()""")
    ok(same == 0, "the app's locator() and maidenhead() agree on 2000 random points")

    print("\n[2] CQ zone, ITU zone, ITU region")
    for name, (la, lo, cq, itu, reg) in PLACES.items():
        got = js(pg, f"[zonesAt(radioZones.cq,{la},{lo}), zonesAt(radioZones.itu,{la},{lo}), zonesAt(radioZones.region,{la},{lo})]")
        ok(got == [[cq], [itu], [reg]], f"{name}: CQ {got[0]} ITU {got[1]} region {got[2]} (expected {cq}/{itu}/{reg})")
    for name, (la, lo, reg) in REGIONS_ONLY.items():
        got = js(pg, f"zonesAt(radioZones.region,{la},{lo})")
        ok(got == [reg], f"{name}: region {got} (expected {reg})")

    print("\n[3] close to a boundary, the neighbouring zone is named too")
    a = js(pg, "zoneAround(radioZones.cq, 47.84, 12.98, 8)")
    ok(a["here"] == [14] and a["also"] == [15], f"Freilassing, under a km from Austria: 14, also 15 ({a})")
    b = js(pg, "zoneAround(radioZones.cq, 47.6, 12.9, 8)")
    ok(b["here"] == [14] and b["also"] == [], f"six km from that line with a sharp fix: 14 only ({b})")
    c = js(pg, "zoneAround(radioZones.cq, 47.6, 12.9, 10000)")
    ok(c["also"] == [15], f"the same spot with a 10 km margin: 15 is possible ({c})")

    print("\n[4] nearest references: the grid search matches brute force")
    bad = js(pg, """(() => {
        const pts = worldPoints.features.length
          ? worldPoints.features.map(f => ({ref: f.properties.ref, lat: f.geometry.coordinates[1], lon: f.geometry.coordinates[0]}))
          : index.map(z => ({ref: z.ref, lat: z.lat ?? (z.bbox[1]+z.bbox[3])/2, lon: z.lon ?? (z.bbox[0]+z.bbox[2])/2}));
        const g = gridIndex(pts);
        let bad = 0;
        const probes = [[51.175,4.345],[64.1,-21.9],[-54.8,-68.3],[71.2,-179.5],[0,179.99],[-89,0],[89,45]];
        for(let i = 0; i < 150; i++) probes.push([Math.random()*170-85, Math.random()*360-180]);
        for(const [la, lo] of probes){
          const fast = nearestIn(g, la, lo, 3).map(p => p.ref);
          const slow = pts.map(p => ({ref: p.ref, d: haversine(la, lo, p.lat, p.lon)}))
                          .sort((a, b) => a.d - b.d).slice(0, 3);
          const fd = nearestIn(g, la, lo, 3).map(p => Math.round(p.d));
          if(fd.join() !== slow.map(p => Math.round(p.d)).join()) bad++;
        }
        return bad; })()""")
    ok(bad == 0, f"157 positions, including the poles and the date line: {bad} differ")
    rt = js(pg, "(() => { const [la, lo] = destination(51.175, 4.345, 37, 12000); return Math.round(haversine(51.175, 4.345, la, lo)); })()")
    ok(abs(rt - 12000) <= 1, f"destination() and haversine() agree ({rt} m)")

    print("\n[5] the tab")
    txt = js(pg, "document.getElementById('nearInfo').innerText")
    ok(js(pg, "document.getElementById('nearAreas').hidden") and not js(pg, "document.getElementById('nearInfoWrap').hidden"),
       "Info shown, the area list hidden")
    ok(js(pg, "document.getElementById('infoLoc').textContent") == "JO21EE", "locator from the GPS position")
    ok([js(pg, f"document.getElementById('{i}').textContent") for i in ("infoCq", "infoItu", "infoRegion")] == ["14", "27", "1"],
       "CQ 14, ITU 27, region 1 on screen")
    ok("±8 m" in txt, "accuracy shown")
    ok("51.17500° N, 4.34500° E" in txt, "decimal position shown")
    rows = js(pg, "document.querySelectorAll('#infoWwff .spot').length")
    ok(rows == 3, f"three nearest references ({rows})")
    ok(js(pg, "[...document.querySelectorAll('#infoWwff .spot')].every(r => r.dataset.ref.startsWith('ONFF'))"),
       "near Antwerp they are all ONFF")
    ok("Europe/Brussels" in js(pg, "document.getElementById('infoTz').textContent"), "local time names the time zone")
    t1 = js(pg, "document.getElementById('infoUtc').textContent")
    pg.wait_for_timeout(1300)
    ok(js(pg, "document.getElementById('infoUtc').textContent") != t1, "the clock ticks")
    ok("MIT" in txt and "Natural Earth" in txt, "the zone card names its sources")

    print("\n[6] the choice of tab is remembered, and follows the language")
    pg.reload(wait_until="load")
    pg.wait_for_function("() => typeof index !== 'undefined' && index && index.length > 0", timeout=20000)
    ok(js(pg, "nearTab") == "info", "still on Info after a reload")
    js(pg, "document.querySelector('#nav button[data-view=\"viewSet\"]').click()")
    pg.click("#setLang .seg[data-lang='nl']")
    open_info(pg)
    ok("ITU-regio" in js(pg, "document.getElementById('nearInfo').innerText"), "Dutch labels")
    pg.click("#nearTab .seg[data-neartab='areas']")
    pg.wait_for_timeout(300)
    ok(not js(pg, "document.getElementById('nearAreas').hidden") and js(pg, "document.querySelectorAll('#nearList .spot').length") > 0,
       "back to the area list, which still works")

    print("\n[7] tapping a nearest reference opens it on the map")
    pg.click("#nearTab .seg[data-neartab='info']")
    pg.wait_for_timeout(500)
    ref = js(pg, "document.querySelector('#infoWwff .spot').dataset.ref")
    pg.click("#infoWwff .spot")
    pg.wait_for_timeout(600)
    ok(js(pg, "selected") == ref, f"{ref} selected on the map")
    ok(len(errs) == 0, f"no page errors: {errs}")
    ctx.close()

    print("\n[8] no GPS: the locator from Settings, said as such")
    ctx, pg, errs = page(br, geo=False)
    js(pg, "(() => { cfg.grid = 'JO21EE'; here = null; })()")
    open_info(pg)
    txt = js(pg, "document.getElementById('nearInfo').innerText")
    ok(js(pg, "document.getElementById('infoLoc').textContent") == "JO21EE", "locator from Settings")
    ok("no GPS" in txt, "and it says there is no GPS")
    ok(js(pg, "document.getElementById('infoCq').textContent") == "14", "zones from the middle of that square")
    ok(len(errs) == 0, f"no page errors: {errs}")
    ctx.close()

    br.close()

print("\n" + ("ALL OK" if not fails else f"{len(fails)} FAILED: " + "; ".join(fails)))
sys.exit(1 if fails else 0)
