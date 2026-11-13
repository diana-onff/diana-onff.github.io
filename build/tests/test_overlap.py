# Areas that lie on top of each other (since 2.2.10).
#
#     python3 build/tests/test_overlap.py
#
# Reported from Portugal: a reserve (CTFF-0018) lies inside a larger area
# (CTFF-0188). The larger one was drawn on top, a tap always gave the larger
# one, and the reserve could not be selected at all. The live data has this in
# every country, Belgium included.
#
# Now the smallest area under the finger is the one that opens, it is drawn on
# top, and the panel lists the other areas at that point as buttons to switch
# with. Checked on the real data, with pairs found in the data itself (so the
# test keeps working when the files change):
#   [1] a tap inside the small area opens the small one, also where it used to
#       be hidden under the larger;
#   [2] the panel offers the larger one, and switching works both ways;
#   [3] a tap in the larger area outside the small one opens the larger one,
#       without any buttons;
#   [4] the small one is drawn on top;
#   [5] a GPS position inside both opens the smallest and names both;
#   [6] in Belgium an area without overlap opens as before, no buttons.
import re, json, sys
from playwright.sync_api import sync_playwright
import preconsent  # noqa: F401  answered welcome screen, see preconsent.py

BASE = "http://localhost:8011/web/"
fails = []


def ok(c, m):
    print(("  ✓ " if c else "  ✗ ") + m)
    if not c:
        fails.append(m)


def context(br, prog):
    ctx = br.new_context(service_workers="block", viewport={"width": 420, "height": 860}, locale="en-GB")
    ctx.add_init_script("try{localStorage.setItem('diana.lang','en');localStorage.setItem('diana.wizard.done','1');"
                        f"localStorage.setItem('diana.call','ON3VZ');localStorage.setItem('diana.homeprog','{prog}');}}catch(e){{}}")
    ctx.route(re.compile(r"https://tiles\.openfreemap\.org/.*"), lambda r: r.fulfill(
        status=200, content_type="application/json",
        body=json.dumps({"version": 8, "sources": {}, "layers": [
            {"id": "bg", "type": "background", "paint": {"background-color": "#e8e4d8"}}]})))
    ctx.route(re.compile(r"https://(spots\.wwff\.co|raw\.githubusercontent\.com|api\.github\.com|docs\.google\.com)/.*"),
              lambda r: r.abort())
    return ctx


# In the page: pairs (small inside big) with a point in both and in nothing
# else, and a point in the big one only. `hidden` says the small one comes
# earlier in the file, which is the case that could not be tapped before.
FIND = """() => {
  const fs = zones.features, n = fs.length, box = fs.map(f => bboxOf(f.geometry));
  const at = (lon, lat) => { const r = [];
    for (let i = 0; i < n; i++) { const b = box[i];
      if (lon < b[0] || lon > b[2] || lat < b[1] || lat > b[3]) continue;
      if (pointInGeom(lon, lat, fs[i].geometry)) r.push(i); }
    return r; };
  const out = [];
  for (let i = 0; i < n && out.length < 3; i++) {
    const a = fs[i], ba = box[i], ha = Number(a.properties.area_ha);
    if (!(ha > 20)) continue;
    let both = null, big = -1;
    for (let gx = 1; gx < 12 && !both; gx++) for (let gy = 1; gy < 12 && !both; gy++) {
      const lon = ba[0] + (ba[2] - ba[0]) * gx / 12, lat = ba[1] + (ba[3] - ba[1]) * gy / 12;
      const h = at(lon, lat);
      if (h.length === 2 && h.includes(i)) { const j = h[0] === i ? h[1] : h[0];
        if (Number(fs[j].properties.area_ha) > ha * 1.5) { both = [lon, lat]; big = j; } }
    }
    if (!both) continue;
    const bb = box[big]; let only = null;
    for (let gx = 1; gx < 40 && !only; gx++) for (let gy = 1; gy < 40 && !only; gy++) {
      const lon = bb[0] + (bb[2] - bb[0]) * gx / 40, lat = bb[1] + (bb[3] - bb[1]) * gy / 40;
      const h = at(lon, lat);
      if (h.length === 1 && h[0] === big) only = [lon, lat];
    }
    if (!only) continue;
    out.push({small: a.properties.ref, big: fs[big].properties.ref, both, only, hidden: i < big});
  }
  out.sort((x, y) => (y.hidden ? 1 : 0) - (x.hidden ? 1 : 0));
  return out;
}"""

ALSO = "() => [...document.querySelectorAll('#zoneAlso .alsobtn')].map(b => b.dataset.ref)"


def tap(pg, lonlat, zoom=13):
    """Puts the point in the middle of the map and taps it there."""
    pg.evaluate("() => closeSheet()")
    pg.evaluate("([p, z]) => map.jumpTo({center: p, zoom: z})", [lonlat, zoom])
    # Wait until the areas are really drawn at that point: a tap on a map that
    # has not painted yet reaches nothing, in the test as on a phone.
    pg.wait_for_function("p => !map.isMoving() && map.queryRenderedFeatures(map.project(p), {layers: ['onff-fill']}).length > 0",
                         arg=lonlat, timeout=30000)
    pg.wait_for_timeout(400)
    xy = pg.evaluate("p => { const b = map.getCanvas().getBoundingClientRect(), q = map.project(p); return [b.left + q.x, b.top + q.y]; }", lonlat)
    # The start screen lies over the map for the first seconds; a tap then
    # lands on it and not on the map.
    pg.wait_for_function("([x, y]) => { const e = document.elementFromPoint(x, y); return !!e && e.tagName === 'CANVAS'; }",
                         arg=xy, timeout=30000)
    pg.mouse.click(xy[0], xy[1])
    pg.wait_for_timeout(700)


with sync_playwright() as p:
    br = p.chromium.launch()
    errs = []

    ctx = context(br, "CTFF")
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE, wait_until="load")
    pg.wait_for_function("() => loadedPrograms.includes('CTFF') && zones.features.length > 50 && map.getLayer('onff-fill')", timeout=60000)
    pairs = pg.evaluate(FIND)
    ok(bool(pairs), f"the data has areas inside larger ones ({[(x['small'], x['big'], x['hidden']) for x in pairs]})")
    if not pairs:
        print("\nnothing to test"); sys.exit(1)
    pr = pairs[0]
    small, big = pr["small"], pr["big"]

    print(f"\n[1] a tap inside the small area ({small}, inside {big}{', listed before it' if pr['hidden'] else ''})")
    tap(pg, pr["both"])
    ok(pg.evaluate("() => selected") == small and pg.evaluate("() => $('sheet').classList.contains('open')"),
       f"opens the small one ({pg.evaluate('() => selected')})")

    print("\n[2] the panel offers the other one, and switching works both ways")
    also = pg.evaluate(ALSO)
    ok(also == [big] and pg.evaluate("() => !$('zoneAlso').hidden"), f"a button for {big} ({also})")
    txt = pg.evaluate("() => $('zoneAlso').textContent")
    ok("Tap to switch" in txt and " ha" in txt, f"with its name and size ({txt[:90]})")
    pg.click(f'#zoneAlso .alsobtn[data-ref="{big}"]')
    pg.wait_for_timeout(500)
    ok(pg.evaluate("() => selected") == big and big in pg.evaluate("() => $('badges').textContent"), f"a tap on it opens {big}")
    ok(pg.evaluate(ALSO) == [small], "and from there a button leads back")
    pg.click(f'#zoneAlso .alsobtn[data-ref="{small}"]')
    pg.wait_for_timeout(500)
    ok(pg.evaluate("() => selected") == small, f"back at {small}")
    pg.click("#zoneSpot")
    pg.wait_for_timeout(600)
    ok(pg.evaluate("() => $('spReference').value") == small, "Spot yourself here takes the one that is open")
    pg.click('#nav button[data-view="map"]')
    pg.wait_for_timeout(400)

    print("\n[3] a tap in the larger area, outside the small one")
    tap(pg, pr["only"])
    ok(pg.evaluate("() => selected") == big, f"opens the larger one ({pg.evaluate('() => selected')})")
    ok(pg.evaluate("() => $('zoneAlso').hidden") and pg.evaluate(ALSO) == [], "without buttons: nothing else lies there")

    print("\n[4] the small one is drawn on top")
    pg.evaluate("p => map.jumpTo({center: p, zoom: 13})", pr["both"])
    pg.wait_for_function("p => !map.isMoving() && map.queryRenderedFeatures(map.project(p), {layers: ['onff-fill']}).length > 0",
                         arg=pr["both"], timeout=30000)
    top = pg.evaluate("p => map.queryRenderedFeatures(map.project(p), {layers: ['onff-fill']}).map(f => f.properties.ref)", pr["both"])
    ok(top and top[0] == small, f"topmost at that point: {top[:3]}")
    ok(pg.evaluate("r => kleinsteEerst([r[1], r[0], r[1], r[0]])", [small, big]) == [small, big],
       "and the order does not depend on what the map returns, nor on doubles")

    print("\n[5] a GPS position inside both")
    pg.evaluate("() => closeSheet()")
    pg.evaluate("p => evaluate(p[1], p[0], 5, false)", pr["both"])
    pg.wait_for_timeout(700)
    ok(pg.evaluate("() => selected") == small, "opens the smallest")
    ok(pg.evaluate(ALSO) == [big], "with the other one a button away")
    st = pg.evaluate("() => document.querySelector('.status') ? document.body.innerText : ''")
    ok(small in st and big in st, "and the status names both")

    for extra in pairs[1:]:
        tap(pg, extra["both"])
        ok(pg.evaluate("() => selected") == extra["small"], f"also {extra['small']} inside {extra['big']}")
    ctx.close()

    print("\n[6] Belgium: an area without overlap opens as before")
    ctx = context(br, "ONFF")
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE, wait_until="load")
    pg.wait_for_function("() => loadedPrograms.includes('ONFF') && zones.features.length > 500 && map.getLayer('onff-fill')", timeout=60000)
    lone = pg.evaluate("""() => { const fs = zones.features;
      for (const f of fs) { const b = bboxOf(f.geometry); if (!(Number(f.properties.area_ha) > 50)) continue;
        for (let g = 1; g < 10; g++) { const lon = b[0] + (b[2]-b[0]) * g / 10, lat = b[1] + (b[3]-b[1]) * g / 10;
          const h = fs.filter(x => { const c = bboxOf(x.geometry);
            return lon >= c[0] && lon <= c[2] && lat >= c[1] && lat <= c[3] && pointInGeom(lon, lat, x.geometry); });
          if (h.length === 1 && h[0] === f) return {ref: f.properties.ref, p: [lon, lat]}; } }
      return null; }""")
    tap(pg, lone["p"])
    ok(pg.evaluate("() => selected") == lone["ref"] and pg.evaluate("() => $('sheet').classList.contains('open')"),
       f"{lone['ref']} opens on a tap")
    ok(pg.evaluate("() => $('zoneAlso').hidden"), "no buttons")
    pg.evaluate("() => select('PAFF-0081')")
    pg.wait_for_timeout(500)
    ok(pg.evaluate("() => selected") == "PAFF-0081" and pg.evaluate("() => $('zoneAlso').hidden"), "a blue dot's panel has none either")
    ctx.close()

    ok(not errs, f"no page errors ({errs[:2]})")
    br.close()

print("\n" + ("ALL OK" if not fails else f"{len(fails)} PROBLEMS: " + " | ".join(fails)))
sys.exit(1 if fails else 0)
