# Every reference can be tapped (since 2.2.0).
#
#     python3 build/tests/test_worldsheet.py
#
# A blue dot from the worldwide layer used to open a bare popup with its
# reference and name. It now opens the same panel as a reference without a
# boundary, filled with what Diana knows about it anywhere (locator, zones,
# QSO count or ATNO, distance and bearing, website) and nothing else, so no
# empty boxes. Every panel also has "Announce an activation" next to "Spot
# yourself here", and both forms take the reference from whatever was tapped,
# a boundary, a point without one, or a blue dot. Before this, only a
# boundary filled them in. For a country whose boundaries Diana has but has
# not loaded, the panel offers to show that country in detail.
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


PANEL = """() => {
  const facts = [...document.querySelectorAll('#facts .fact')];
  return {
    open: document.getElementById('sheet').classList.contains('open'),
    badges: document.getElementById('badges').textContent,
    amber: !!document.querySelector('#badges .pill.amber'),
    name: document.getElementById('zoneName').textContent,
    keys: facts.map(f => (f.querySelector('.k') || {}).textContent),
    empty: facts.filter(f => !(f.querySelector('.v') || {textContent: ''}).textContent.trim()).length,
    qso: (document.querySelector('#facts .fact.qso .v') || {}).textContent || null,
    note: document.getElementById('zoneNote').textContent,
    agenda: !document.getElementById('zoneAgenda').hidden,
    country: document.getElementById('zoneCountry').hidden ? null : document.getElementById('zoneCountry').textContent,
  };
}"""


def tap_world(pg, ref):
    """Tap the blue dot of `ref` for real, through the map's own click handler."""
    pos = pg.evaluate("""ref => {
      const f = worldPoints.features.find(x => x.properties.ref === ref);
      return f ? f.geometry.coordinates : null; }""", ref)
    if not pos:
        return False
    pg.evaluate("p => map.jumpTo({center: p, zoom: 13})", pos)
    pg.wait_for_timeout(1500)
    xy = pg.evaluate("""p => { const pt = map.project(p), r = map.getCanvas().getBoundingClientRect();
      return [r.left + pt.x, r.top + pt.y]; }""", pos)
    pg.mouse.click(xy[0], xy[1])
    pg.wait_for_timeout(1200)
    return True


with sync_playwright() as p:
    br = p.chromium.launch()
    ctx = br.new_context(service_workers="block", viewport={"width": 420, "height": 860}, locale="en-GB")
    ctx.add_init_script("try{localStorage.setItem('diana.lang','en');localStorage.setItem('diana.grid','JO21EE');"
                        "localStorage.setItem('diana.call','ON3VZ');localStorage.setItem('diana.callp','ON3VZ/P');"
                        "localStorage.setItem('diana.wizard.done','1');}catch(e){}")
    routes(ctx)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE, wait_until="load")
    pg.wait_for_function("() => typeof worldPoints !== 'undefined' && worldPoints && worldPoints.features.length > 1000", timeout=30000)
    pg.wait_for_timeout(1500)
    ok(pg.evaluate("() => homeCountry()") == "ONFF", "starts on Belgium (from the callsign)")

    # A country without boundaries in Diana: France.
    fref = pg.evaluate("() => (worldPoints.features.find(f => /^FFF-\\d+$/.test(f.properties.ref)) || {properties:{}}).properties.ref")
    print(f"\n[1] a blue dot from a country without boundaries ({fref})")
    ok(tap_world(pg, fref), "the dot is on the map")
    a = pg.evaluate(PANEL)
    ok(a["open"], "a real tap opens the panel, not a popup")
    ok(pg.evaluate("() => !document.querySelector('.maplibregl-popup')"), "no popup any more")
    ok(fref in a["badges"] and "France" in a["badges"], f"reference and country in the badges ({a['badges']})")
    ok(a["amber"], "marked as without boundary")
    ok("Locator" in a["keys"] and "From you" in a["keys"], f"locator and distance from you ({a['keys']})")
    ok(a["empty"] == 0, "no empty boxes")
    pg.wait_for_function("() => document.querySelector('#facts .fact.qso')", timeout=15000)
    q = pg.evaluate("() => document.querySelector('#facts .fact.qso .v').textContent")
    ok(bool(re.fullmatch(r"ATNO|[\d,.  ]+", q.strip())), f"QSO count or ATNO once the worldwide file is in ({q})")
    ok("WWFF directory" in a["note"], "the note explains the position comes from the WWFF list")
    ok(a["agenda"] and a["country"] is None, "announce button shown, no country button for France")

    print("\n[2] spot yourself from that panel fills in the reference")
    pg.click("#zoneSpot")
    pg.wait_for_timeout(800)
    ok(pg.evaluate("() => $('spReference').value") == fref, "Spot has the reference")
    ok(pg.evaluate("r => !$('selfCtx').hidden && $('selfCtx1').textContent.startsWith(r)", fref), "and says where it came from")

    print("\n[3] announce from that panel fills in the reference")
    pg.click('#nav button[data-view="map"]')
    pg.wait_for_timeout(800)
    tap_world(pg, fref)
    pg.click("#zoneAgenda")
    pg.wait_for_timeout(800)
    ok(pg.evaluate("() => $('viewAgendaNew').classList.contains('on')"), "Agenda form opens")
    ok(pg.evaluate("() => $('agReference').value") == fref, "Agenda has the reference")

    print("\n[4] a point of the loaded country without a boundary")
    pg.click('#nav button[data-view="map"]')
    pg.wait_for_timeout(800)
    npref = pg.evaluate("() => noPoly.features.length ? noPoly.features[0].properties.ref : null")
    if npref:
        pg.evaluate("r => select(r)", npref)
        pg.wait_for_timeout(600)
        b = pg.evaluate(PANEL)
        ok(b["open"] and b["country"] is None, f"{npref}: panel open, no country button")
        ok("{prog}" not in b["note"] and "ONFF" in b["note"], "its note names the programme")
        pg.click("#zoneSpot")
        pg.wait_for_timeout(800)
        ok(pg.evaluate("() => $('spReference').value") == npref, "Spot now fills in a reference without a boundary too")
        pg.click('#nav button[data-view="map"]')
        pg.wait_for_timeout(800)

    print("\n[5] a boundary of the loaded country still works as before")
    pg.evaluate("() => select('ONFF-0685')")
    pg.wait_for_timeout(600)
    c = pg.evaluate(PANEL)
    ok(c["open"] and not c["amber"] and c["country"] is None and c["agenda"], "panel, no country button, announce shown")
    ok("Area" in c["keys"], "the KMZ facts are still there")
    pg.click("#zoneSpot")
    pg.wait_for_timeout(800)
    ok(pg.evaluate("() => $('spReference').value") == "ONFF-0685", "Spot is filled in as before")
    pg.click('#nav button[data-view="map"]')
    pg.wait_for_timeout(800)

    print("\n[6] a country Diana has boundaries for, but not loaded: the Netherlands")
    filt = pg.evaluate("() => spotFilter")
    nref = pg.evaluate("() => worldPoints.features.some(x => x.properties.ref === 'PAFF-0019') ? 'PAFF-0019' : null")
    ok(nref == "PAFF-0019", "PAFF-0019 is a blue dot while Belgium is loaded")
    tap_world(pg, nref)
    d = pg.evaluate(PANEL)
    ok(d["open"] and not d["amber"], "panel open, not marked as without boundary")
    ok(d["country"] and "Netherlands" in d["country"], f"offers to show the Netherlands ({d['country']})")
    pg.click("#zoneCountry")
    pg.wait_for_function("() => loadedPrograms.includes('PAFF')", timeout=30000)
    pg.wait_for_timeout(1500)
    e = pg.evaluate(PANEL)
    ok(pg.evaluate("() => homeCountry()") == "PAFF", "the country setting is now the Netherlands")
    ok(e["open"] and "Area" in e["keys"] and "PAFF-0019" in e["badges"], "the same reserve reopens, now with its boundary")
    ok(pg.evaluate("() => spotFilter") == filt, "the spots filter was left alone")
    ok(pg.evaluate("() => $('setSpotCountry').value") == "PAFF", "Settings shows the Netherlands")

    ok(not errs, f"no page errors ({errs[:2]})")
    br.close()

print("\nOK" if not fails else f"\n{len(fails)} failure(s)")
sys.exit(1 if fails else 0)
