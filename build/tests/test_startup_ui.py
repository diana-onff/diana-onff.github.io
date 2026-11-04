# What the map and the filter buttons show while Diana is still starting (since 2.2.4).
#
#     python3 build/tests/test_startup_ui.py
#
# Reported: "after a restart it is back on ONFF instead of Worldwide, and the
# blue dots are not on the map". The saved choice was fine. Two things made
# it look otherwise:
#
#   1. The country / Worldwide buttons were only brought in line with the saved
#      choice once all data had loaded. Until then they showed the page's own
#      starting state, ONFF lit on the Spots screen, for seconds on a slow
#      connection.
#   2. The blue dots shared a map source with the numbers on their clusters.
#      Text needs the map's fonts; a source whose fonts do not arrive draws
#      nothing at all. So while the fonts were slow, or when they failed, not
#      a single blue dot was drawn. The same held for the points without a
#      boundary and for the spots. Labels now come from a twin source with the
#      same data.
#
# Every check here runs with the fonts BLOCKED, the way a broken connection
# would leave them, and with the data held back for seconds where it matters.
import re, json, sys, time
from playwright.sync_api import sync_playwright
import preconsent  # noqa: F401  answered welcome screen, see preconsent.py

BASE = "http://localhost:8011/web/"
fails = []

# A style that asks for fonts, as the real OpenFreeMap styles do.
STYLE = json.dumps({"version": 8, "glyphs": "https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf",
                    "sources": {}, "layers": [{"id": "bg", "type": "background", "paint": {"background-color": "#e8e4d8"}}]})


def ok(c, m):
    print(("  ✓ " if c else "  ✗ ") + m)
    if not c:
        fails.append(m)


def bars(pg):
    return pg.evaluate("""() => ({
      spots: [...$('spotFilter').children].filter(c => c.classList.contains('on')).map(c => c.dataset.filter),
      set:   [...$('setSpotFilter').children].filter(c => c.classList.contains('on')).map(c => c.dataset.filter),
      f: spotFilter })""")


def context(br, init, slow_data=0, spots=None):
    ctx = br.new_context(service_workers="block", viewport={"width": 420, "height": 860}, locale="en-GB")
    ctx.add_init_script(init)
    ctx.route(re.compile(r"https://tiles\.openfreemap\.org/styles/.*"), lambda r: r.fulfill(
        status=200, content_type="application/json", body=STYLE))
    ctx.route(re.compile(r"https://tiles\.openfreemap\.org/fonts/.*"), lambda r: r.abort())
    body = json.dumps(spots or [])
    ctx.route(re.compile(r"https://spots\.wwff\.co/static/spots\.json"), lambda r: r.fulfill(
        status=200, content_type="application/json", body=body))
    ctx.route(re.compile(r"https://spots\.wwff\.co/static/agendas.*"), lambda r: r.fulfill(
        status=200, content_type="application/json", body="[]"))
    ctx.route(re.compile(r"https://(raw\.githubusercontent\.com|api\.github\.com|docs\.google\.com)/.*"), lambda r: r.abort())
    if slow_data:
        def late(route):
            time.sleep(slow_data)
            route.continue_()
        ctx.route(re.compile(r".*/data/wwff-programs\.json"), late)
    return ctx


def rendered(pg, layers):
    return pg.evaluate("ls => { const have = ls.filter(l => map.getLayer(l)); "
                       "return have.length ? map.queryRenderedFeatures({layers: have}).length : -1; }", layers)


BASIC = ("try{localStorage.setItem('diana.lang','en');localStorage.setItem('diana.wizard.done','1');"
         "localStorage.setItem('diana.call','ON3VZ');%s}catch(e){}")

with sync_playwright() as p:
    br = p.chromium.launch()
    errs = []

    print("\n[1] the buttons show the saved choice from the first moment")
    for saved, want_spots in (("all", "all"), ("ONFF", "ONFF")):
        ctx = context(br, BASIC % f"localStorage.setItem('diana.spotFilter2','{saved}');", slow_data=4)
        pg = ctx.new_page(); pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(BASE, wait_until="domcontentloaded")
        pg.wait_for_timeout(300)
        b = bars(pg)
        ok(b["f"] == saved and b["spots"] == [want_spots] and b["set"] == [want_spots],
           f"saved {saved}, data still held back: Spots {b['spots']}, Settings {b['set']}")
        pg.wait_for_timeout(5000)
        b = bars(pg)
        ok(b["spots"] == [want_spots] and b["set"] == [want_spots], f"and still so once the data is in ({b['spots']})")
        ctx.close()
    ctx = context(br, BASIC % "")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE, wait_until="domcontentloaded")
    pg.wait_for_timeout(300)
    ok(bars(pg)["spots"] == ["all"], "nothing saved yet: Worldwide, the default")
    ctx.close()

    print("\n[2] blue dots without fonts")
    ctx = context(br, BASIC % "localStorage.setItem('diana.spotFilter2','all');")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE, wait_until="load")
    pg.wait_for_function("() => worldLoaded && map.getSource('wwff-world')", timeout=60000)
    pg.evaluate("() => map.jumpTo({center: [5.5, 51.6], zoom: 7})")
    pg.wait_for_timeout(2500)
    n = rendered(pg, ["world-clusters", "world-point"])
    ok(n > 0, f"over the Netherlands with the fonts blocked: {n} blue dots or clusters drawn")
    pg.evaluate("() => map.jumpTo({center: [5.5, 51.6], zoom: 12})")
    pg.wait_for_timeout(2500)
    ok(rendered(pg, ["world-point"]) > 0, "zoomed in to single dots: drawn too")
    tw = pg.evaluate("() => [map.getSource('wwff-world')._data.features.length, map.getSource('wwff-world-txt')._data.features.length]")
    ok(tw[0] == tw[1] and tw[0] > 1000, f"the label twin carries exactly the same points ({tw})")
    ok(pg.evaluate("() => ['world-cluster-count','world-label'].every(l => map.getLayer(l).source === 'wwff-world-txt')"),
       "numbers and labels read the twin, the dots the original")

    print("\n[3] after picking another country the twin follows")
    pg.evaluate("() => setSpotFilter('ONFF')")
    pg.wait_for_timeout(800)
    tw = pg.evaluate("() => [map.getSource('wwff-world')._data.features.length, map.getSource('wwff-world-txt')._data.features.length]")
    ok(tw[0] == tw[1], f"same count in both after a filter change ({tw})")
    pg.evaluate("() => setSpotFilter('all')")
    pg.wait_for_timeout(800)

    print("\n[4] tapping a blue dot and a cluster still works")
    pg.evaluate("() => map.jumpTo({center: [5.5, 51.6], zoom: 12})")
    pg.wait_for_timeout(2000)
    f = pg.evaluate("""() => { const r = map.queryRenderedFeatures({layers:['world-point']})[0];
        if(!r) return null; const pt = map.project(r.geometry.coordinates), b = map.getCanvas().getBoundingClientRect();
        return {ref: r.properties.ref, x: b.left + pt.x, y: b.top + pt.y}; }""")
    if f:
        pg.mouse.click(f["x"], f["y"]); pg.wait_for_timeout(1000)
        ok(pg.evaluate("() => selected") == f["ref"] and pg.evaluate("() => $('sheet').classList.contains('open')"),
           f"a blue dot opens its panel ({f['ref']})")
    else:
        ok(False, "a blue dot to tap")
    pg.evaluate("() => { closeSheet(); map.jumpTo({center: [5.5, 51.6], zoom: 6}); }")
    pg.wait_for_timeout(2000)
    # The cluster nearest the middle of the screen: the top bar and the panel
    # cover the edges, and a tap there never reaches the map.
    c = pg.evaluate("""() => { const b = map.getCanvas().getBoundingClientRect();
        const rs = map.queryRenderedFeatures({layers:['world-clusters']}).map(r => {
          const pt = map.project(r.geometry.coordinates); return {x: b.left + pt.x, y: b.top + pt.y,
          d: Math.hypot(pt.x - b.width/2, pt.y - b.height/2)}; }).sort((a, c) => a.d - c.d);
        return rs.length ? {x: rs[0].x, y: rs[0].y, z: map.getZoom()} : null; }""")
    if c:
        pg.mouse.click(c["x"], c["y"]); pg.wait_for_timeout(2500)
        z2 = pg.evaluate("() => map.getZoom()")
        ok(z2 > c["z"] + 0.5, f"a cluster still zooms in ({c['z']:.1f} -> {z2:.1f})")
    else:
        ok(False, "a cluster to tap")
    ctx.close()

    print("\n[5] points without a boundary, and spots, without fonts")
    ctx = context(br, BASIC % "localStorage.setItem('diana.homeprog','PAFF');", spots=[
        {"id": 1, "activator": "ON4AA", "reference": "ONFF-0001", "latitude": 50.5, "longitude": 4.0,
         "frequency_khz": 14244, "mode": "SSB", "spot_time": int(time.time()) - 60}])
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE, wait_until="load")
    pg.wait_for_function("() => loadedPrograms.includes('PAFF') && noPoly.features.length > 0 && map.getSource('onff-np')", timeout=60000)
    pos = pg.evaluate("() => noPoly.features[0].geometry.coordinates")
    pg.evaluate("p => map.jumpTo({center: p, zoom: 11})", pos)
    pg.wait_for_timeout(2500)
    ok(rendered(pg, ["np-dot"]) > 0, "a Dutch point without a boundary is drawn")
    ok(pg.evaluate("() => map.getLayer('np-label').source") == "onff-np-txt", "its label reads the twin")
    pg.wait_for_function("() => map.getSource('spots') && map.getSource('spots')._data.features.length > 0", timeout=30000)
    pg.evaluate("() => map.jumpTo({center: [4.0, 50.5], zoom: 9})")
    pg.wait_for_timeout(2500)
    ok(rendered(pg, ["spots-icon"]) > 0, "a spot is drawn")
    ok(pg.evaluate("() => map.getLayer('spots-call').source") == "spots-txt"
       and pg.evaluate("() => map.getLayer('agenda-label').source") == "agenda-txt", "spot and agenda labels read their twins")
    ctx.close()

    ok(not errs, f"no page errors ({errs[:2]})")
    br.close()

print("\nOK" if not fails else f"\n{len(fails)} failure(s)")
sys.exit(1 if fails else 0)
