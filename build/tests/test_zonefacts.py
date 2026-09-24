# Locator, CQ zone, ITU zone and ITU region on the map's own selection panel.
#
#     python3 build/tests/test_zonefacts.py
#
# The Nearby > Info tab (nearinfo.js, test_nearinfo.py) already works these
# four out for wherever you are standing. This is the same four numbers for
# whatever area you tapped on the map, added to the existing panel in
# map.js's select()/selectPoint(), kept deliberately small on request: just
# the numbers, no nearest-reference list and no boundary-proximity note.
#
# The zone file (geo/radio-zones.json) is the one nearinfo.js already loads
# on first use, lazily; a selection made before the Info tab has ever been
# opened has to trigger that load itself and fill the tile in once it lands,
# without redrawing or re-fitting the rest of the panel out from under
# whatever the person is reading. Locator needs no such file, so it has no
# excuse to be late.
import re, json, sys
from playwright.sync_api import sync_playwright
import preconsent  # noqa: F401  answered welcome screen, see preconsent.py

BASE = "http://localhost:8011/web/?embed=1"   # embed=1: skip the ~9 MB worldwide layer, not needed here
fails = []


def ok(c, m):
    print(("  ✓ " if c else "  ✗ ") + m)
    if not c:
        fails.append(m)


def routes(ctx, hold_zones=None):
    ctx.route(re.compile(r"https://tiles\.openfreemap\.org/.*"), lambda r: r.fulfill(
        status=200, content_type="application/json",
        body=json.dumps({"version": 8, "sources": {}, "layers": [
            {"id": "bg", "type": "background", "paint": {"background-color": "#e8e4d8"}}]})))
    ctx.route(re.compile(r"https://spots\.wwff\.co/static/spots\.json"), lambda r: r.fulfill(
        status=200, content_type="application/json", body="[]"))
    ctx.route(re.compile(r"https://spots\.wwff\.co/static/agendas.*"), lambda r: r.fulfill(
        status=200, content_type="application/json", body="[]"))
    ctx.route(re.compile(r"https://docs\.google\.com/.*"), lambda r: r.abort())
    if hold_zones is not None:
        # Rather than an arbitrary sleep (which, inside a route handler, can
        # stall the whole driver connection and every wait_for_timeout() on
        # the main thread right along with it), the request is parked here
        # and only let through once the test itself calls release().
        def catch(route):
            hold_zones.append(route)
        ctx.route(re.compile(r".*geo/radio-zones\.json"), catch)


LOCATOR_RE = re.compile(r"^[A-Z]{2}\d{2}[A-Z]{2}$")

READ_FACTS = """() => {
  const facts = document.getElementById('facts');
  const locFact = [...facts.querySelectorAll('.fact')].find(
    f => (f.querySelector('.k') || {}).textContent === 'Locator');
  const loc = locFact ? locFact.querySelector('.v') : null;
  const zoneEl = document.getElementById('zoneRadioZones');
  return {
    html: facts.innerHTML,
    locatorText: loc ? loc.textContent : null,
    zoneHidden: zoneEl ? zoneEl.style.display === 'none' : null,
    zoneText: zoneEl ? zoneEl.textContent : null,
  };
}"""

with sync_playwright() as p:
    br = p.chromium.launch()

    print("\n[1] the zone file already loaded (the ordinary case once the Info tab has been seen)")
    ctx = br.new_context(service_workers="block", viewport={"width": 420, "height": 860})
    routes(ctx)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE, wait_until="load")
    pg.wait_for_timeout(2000)
    pg.evaluate("() => select('ONFF-0001')")
    pg.wait_for_function("() => !!radioZones", timeout=10000)
    pg.wait_for_timeout(200)
    st = pg.evaluate(READ_FACTS)
    ok(bool(st["locatorText"]) and LOCATOR_RE.match(st["locatorText"] or ""),
       f"Locator shows a real six-character grid ({st['locatorText']})")
    expected = pg.evaluate("""() => {
      const [lon, lat] = selectedPos;
      const val = list => { const h = zonesAt(list, lat, lon); return h.length ? h.join('/') : t('info.unknown'); };
      return `${val(radioZones.cq)} · ${val(radioZones.itu)} · ${val(radioZones.region)}`;
    }""")
    ok(expected in st["zoneText"], f"CQ/ITU/region matches the app's own zonesAt() ({st['zoneText']!r} vs {expected!r})")

    print("\n[2] a reference without a boundary gets the same tiles (selectPoint())")
    nopoly = pg.evaluate("() => (noPolyByRef && noPolyByRef.size) ? [...noPolyByRef.keys()][0] : null")
    if nopoly:
        pg.evaluate("(ref) => select(ref)", nopoly)
        pg.wait_for_timeout(200)
        st2 = pg.evaluate(READ_FACTS)
        ok(bool(st2["locatorText"]) and LOCATOR_RE.match(st2["locatorText"] or ""),
           f"Locator also shows for a no-boundary reference ({st2['locatorText']})")
    else:
        print("  · (skipped: this checkout has no boundary-less ONFF reference)")

    ctx.close()

    print("\n[3] selecting before the zone file has ever been asked for: Locator is instant, the rest catches up")
    held = []
    ctx2 = br.new_context(service_workers="block", viewport={"width": 420, "height": 860})
    routes(ctx2, hold_zones=held)
    pg2 = ctx2.new_page()
    pg2.on("pageerror", lambda e: errs.append(str(e)))
    pg2.goto(BASE, wait_until="load")
    pg2.wait_for_timeout(2000)
    ok(pg2.evaluate("() => radioZones") is None, "the zone file has not been fetched yet")
    pg2.evaluate("() => select('ONFF-0001')")
    # The request is parked in `held` by catch() above rather than answered,
    # so this is a real "still waiting" state, not a race against how fast
    # the local file happens to load.
    for _ in range(50):
        if held:
            break
        pg2.wait_for_timeout(20)
    ok(bool(held), "the zone file was actually requested (ensureRadioZones() fired)")
    early = pg2.evaluate(READ_FACTS)
    ok(bool(early["locatorText"]) and LOCATOR_RE.match(early["locatorText"] or ""),
       f"Locator is there immediately, before the zone file answers ({early['locatorText']})")
    ok(early["zoneHidden"] is True, f"the CQ/ITU/region tile stays out of sight rather than showing empty ({early})")

    held.pop().continue_()   # let the parked request through
    pg2.wait_for_function("() => !!radioZones", timeout=10000)
    pg2.wait_for_timeout(200)
    later = pg2.evaluate(READ_FACTS)
    ok(later["zoneHidden"] is False and bool(later["zoneText"]),
       f"and fills in on its own once the file lands, sheet never re-fit or rebuilt ({later['zoneText']})")

    print("\n[4] closing the sheet stops any further refresh")
    pg2.evaluate("() => closeSheet()")
    ok(pg2.evaluate("() => selectedPos") is None, "selectedPos is cleared on close")
    pg2.evaluate("() => refreshSelectedRadioFacts()")   # must be a harmless no-op now
    ctx2.close()

    print("\n[5] no JS errors")
    real = [e for e in errs if "Failed to load resource" not in e]
    ok(not real, "no page errors: " + (real[0][:160] if real else "ok"))

    br.close()

print("\n" + ("ALL OK" if not fails else f"{len(fails)} PROBLEMS: " + " | ".join(fails)))
sys.exit(1 if fails else 0)
