# Field info and search reach every WWFF reference, not only the loaded country (since 2.2.3).
#
#     python3 build/tests/test_nearby_world.py
#
# Reported from Spain: with EAFF as the country, a search for an EAFF number
# found nothing, and Field info > Areas said Diana did not know where you were,
# while GPS and locator were both fine. Both looked only at the loaded
# country's boundaries, and Diana has none for Spain. Now the worldwide list
# (the blue dots) takes part too: in the search below the loaded country's own
# results, in Field info merged by distance, and a tap on such a reference
# opens the same panel as its blue dot. For Belgium nothing about its own rows
# changes; references across the border are added. The message about a
# missing position only shows when there really is no position.
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
    ctx.route(re.compile(r"https://(spots\.wwff\.co|raw\.githubusercontent\.com|api\.github\.com|docs\.google\.com)/.*"),
              lambda r: r.abort())


ROWS = """() => { const r = nearbyRows(); return r && {total: r.total, loading: r.loading,
  rows: r.map(x => ({ref: x.ref, d: x.d, qso: x.qso, date: x.date, world: !!x.world}))}; }"""


def ready(pg):
    pg.wait_for_function("() => worldLoaded && worldPoints.features.length > 1000", timeout=60000)
    pg.wait_for_function("() => (ensureWorldActivity(), worldActivityLoaded)", timeout=60000)
    pg.wait_for_timeout(500)


def field_info(pg):
    pg.click('#nav button[data-view="viewNearby"]')
    pg.wait_for_timeout(500)


with sync_playwright() as p:
    br = p.chromium.launch()
    errs = []

    # ------------------------------------------------------------------ Spain
    ctx = br.new_context(service_workers="block", viewport={"width": 420, "height": 860}, locale="nl-BE")
    ctx.add_init_script("try{localStorage.setItem('diana.lang','nl');localStorage.setItem('diana.wizard.done','1');"
                        "localStorage.setItem('diana.call','ON4BB');localStorage.setItem('diana.callp','EA/ON4BB/P');"
                        "localStorage.setItem('diana.grid','JN11JX');localStorage.setItem('diana.homeprog','EAFF');}catch(e){}")
    routes(ctx)
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE, wait_until="load")
    ready(pg)

    print("\n[1] Spain, EAFF, a country without boundaries in Diana, locator JN11JX")
    ok(pg.evaluate("() => homeCountry()") == "EAFF" and pg.evaluate("() => index.length") == 0,
       "EAFF is the country and Diana has no boundaries for it")
    field_info(pg)
    box = pg.evaluate("() => $('nearBox').textContent")
    ok("weet nog niet" not in box, f"no more 'Diana weet nog niet waar je bent' ({box.strip()[:60]})")
    r = pg.evaluate(ROWS)
    ok(r and len(r["rows"]) > 0 and all(x["world"] for x in r["rows"]),
       f"Areas lists the references around the locator ({r and r['total']})")
    ok(r and any(x["ref"].startswith("EAFF-") for x in r["rows"]), "Spanish references among them")
    ok(r and all(x["d"] <= 25000 for x in r["rows"]), "all within the 25 km")
    ok(pg.evaluate("() => !$('nearList').parentElement.hidden"), "the list card is shown")
    first = pg.evaluate("() => document.querySelector('#nearList .spot[data-ref]').dataset.ref")
    line = pg.evaluate("() => document.querySelector('#nearList .spot .f').textContent")
    ok("QSO" in line or "ATNO" in line or "datum" in line, f"each row says what is known ({line})")

    print("\n[2] tapping a row opens its panel, and Spot takes the reference")
    pg.click(f'#nearList .spot[data-ref="{first}"]')
    pg.wait_for_timeout(900)
    ok(pg.evaluate("() => $('sheet').classList.contains('open')") and pg.evaluate("() => selected") == first,
       f"{first}: the panel opens")
    ok(first in pg.evaluate("() => $('badges').textContent"), "with the reference in the badges")
    pg.click("#zoneSpot")
    pg.wait_for_timeout(700)
    ok(pg.evaluate("() => $('spReference').value") == first, "Spot yourself here fills it in")

    print("\n[3] search finds EAFF references")
    pg.click('#nav button[data-view="map"]')
    pg.wait_for_timeout(500)
    res = pg.evaluate("() => search('0012').map(z => z.ref)")
    ok(res == ["EAFF-0012"], f"a bare number finds your own programme's reference only ({res})")
    res = pg.evaluate("() => search('eaff-001').map(z => z.ref)")
    ok(len(res) >= 5 and all("EAFF-001" in x for x in res), f"part of a reference ({res[:12]})")
    name = pg.evaluate("() => worldPoints.features.find(f => f.properties.ref === 'EAFF-0012').properties.name")
    res = pg.evaluate("n => search(n.slice(0, 12)).map(z => z.ref)", name)
    ok("EAFF-0012" in res, f"by name ({name[:12]}…)")
    pg.click("#btnSearch")
    pg.fill("#q", "EAFF-0012")
    pg.wait_for_timeout(300)
    ok(pg.evaluate("() => document.querySelectorAll('#results .res[data-ref]').length") == 1, "shown in the result list")
    pg.click('#results .res[data-ref="EAFF-0012"]')
    pg.wait_for_timeout(900)
    ok(pg.evaluate("() => selected") == "EAFF-0012" and pg.evaluate("() => $('sheet').classList.contains('open')"),
       "tapping the result opens its panel")
    pg.click("#zoneAgenda")
    pg.wait_for_timeout(700)
    ok(pg.evaluate("() => $('agReference').value") == "EAFF-0012", "and Announce fills it in")
    ctx.close()

    # ------------------------------------------------------------------ Belgium
    ctx = br.new_context(service_workers="block", viewport={"width": 420, "height": 860}, locale="en-GB")
    ctx.add_init_script("try{localStorage.setItem('diana.lang','en');localStorage.setItem('diana.wizard.done','1');"
                        "localStorage.setItem('diana.call','ON3VZ');localStorage.setItem('diana.homeprog','ONFF');}catch(e){}")
    routes(ctx)
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE, wait_until="load")
    pg.wait_for_function("() => index && index.length > 500", timeout=60000)
    ready(pg)

    print("\n[4] Belgium at the Dutch border (Knokke, 25 km)")
    pg.evaluate("() => { here = {lat: 51.35, lon: 3.36}; cfg.nearkm = 25; nearMetric = 'dist'; nearShown = 100; }")
    field_info(pg)
    r = pg.evaluate(ROWS)
    home = [x for x in r["rows"] if not x["world"]]
    world = [x for x in r["rows"] if x["world"]]
    ok(home and all(x["ref"].startswith("ONFF-") for x in home), f"{len(home)} Belgian references, as before")
    ok(world and all(not x["ref"].startswith("ONFF-") for x in world), f"plus {len(world)} across the border ({[x['ref'] for x in world][:4]})")
    refs = [x["ref"] for x in r["rows"]]
    ok(len(refs) == len(set(refs)), "no reference twice")
    ok(all(r["rows"][i]["d"] <= r["rows"][i + 1]["d"] for i in range(len(r["rows"]) - 1)), "merged by distance")

    pg.evaluate("() => { nearMetric = 'qso'; renderNearby(); }")
    q = pg.evaluate(ROWS)["rows"]
    known = [x["qso"] for x in q if x["qso"] is not None]
    ok(known == sorted(known) and all(x["qso"] is not None for x in q[:len(known)]),
       "QSO count: fewest first, unknown counts last")
    pg.evaluate("() => { nearMetric = 'recency'; renderNearby(); }")
    rc = pg.evaluate(ROWS)["rows"]
    tail = [x for x in rc if x["world"] and x["qso"] != 0 and not x["date"]]   # since 2.2.5 only those without a date
    ok(rc[len(rc) - len(tail):] == tail if tail else True, "Last active: foreign ones without a date at the end")
    hd = [x["date"] or "" for x in rc if not x["world"]]
    ok(hd == sorted(hd), "and the Belgian ones in the same order as before, longest untouched first")
    wl = pg.evaluate("() => [...document.querySelectorAll('#nearList .spot')].filter(e => !e.dataset.ref.startsWith('ONFF-')).map(e => e.querySelector('.f').textContent)")
    # Since 2.2.5 with the date from data/lastact/ when that file is there.
    ok(wl and all(("no activation date known" in x) or ("last active" in x) or x == "ATNO" for x in wl),
       f"a foreign row says when it was last active, or that the date is not known ({wl[:1]})")
    pg.evaluate("() => { nearMetric = 'dist'; renderNearby(); }")

    print("\n[5] Belgian search and panels are unchanged")
    ok(pg.evaluate("() => search('0012').map(z => z.ref)") == ["ONFF-0012"], "'0012' is still ONFF-0012 only")
    res = pg.evaluate("() => search('ONFF-01').map(z => z.ref)")
    ok(len(res) == 40 and all(x.startswith("ONFF-") for x in res), "a full page of Belgian results stays Belgian")
    pg.evaluate("() => select('ONFF-0685')")
    pg.wait_for_timeout(600)
    ok("Area" in pg.evaluate("() => $('facts').textContent"), "a Belgian boundary opens as before")
    pg.evaluate("() => select('PAFF-0081')")
    pg.wait_for_timeout(600)
    ok(pg.evaluate("() => selected") == "PAFF-0081" and "Netherlands" in pg.evaluate("() => $('badges').textContent"),
       "a Dutch reference opens its blue-dot panel")
    pg.evaluate("() => { const was = selected; select('XXFF-9999'); window.__same = selected === was; }")
    ok(pg.evaluate("() => window.__same"), "an unknown reference still does nothing")

    print("\n[6] the messages")
    pg.evaluate("() => { here = null; cfg.grid = ''; renderNearby(); }")
    field_info(pg)
    ok("does not know where you are" in pg.evaluate("() => $('nearBox').textContent"), "no position at all: that message, as before")
    ok(pg.evaluate("() => $('nearList').parentElement.hidden"), "without the empty white card")
    pg.evaluate("() => { here = {lat: 51.17, lon: 4.34}; worldLoaded = false; worldLoading = null; worldPoints = {type:'FeatureCollection', features:[]}; renderNearby(); }")
    r = pg.evaluate(ROWS)
    ok(r is not None, "with a position, never 'unknown position', even while the worldwide list reloads")
    pg.wait_for_function("() => worldLoaded && worldPoints.features.length > 1000", timeout=60000)
    pg.wait_for_timeout(500)
    ok(pg.evaluate(ROWS)["loading"] is False, "Field info loads the worldwide list itself when it is missing")

    print("\n[7] fast enough on a phone (CPU slowed down 4x)")
    cdp = ctx.new_cdp_session(pg)
    cdp.send("Emulation.setCPUThrottlingRate", {"rate": 4})
    ms = pg.evaluate("() => { cfg.nearkm = 100; const t0 = performance.now(); for(let i=0;i<5;i++) nearbyRows(); return (performance.now()-t0)/5; }")
    ok(ms < 150, f"Field info list at 100 km: {ms:.0f} ms")
    ms = pg.evaluate("() => { const t0 = performance.now(); search('bos'); search('zz'); return (performance.now()-t0)/2; }")
    ok(ms < 250, f"a search over the worldwide list: {ms:.0f} ms")
    cdp.send("Emulation.setCPUThrottlingRate", {"rate": 1})
    pg.evaluate("() => { cfg.nearkm = 25; }")

    ok(not errs, f"no page errors ({errs[:2]})")
    br.close()

print("\nOK" if not fails else f"\n{len(fails)} failure(s)")
sys.exit(1 if fails else 0)
