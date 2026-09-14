# Nearby — the screen that replaced the activation heatmap.
#
# The heatmap read a published Google Sheet with one tab per year, seven years
# back, and called every reference it could not find there "never activated":
# 741 of the 946, most of which have been activated many times over. This test
# exists mostly to keep that from coming back. The figures on this screen come
# from data/onff-activity.json (the WWFF directory, shipped with the release),
# and ONFF-0002 — the reference that gave the game away, thousands of QSOs and
# reported as never touched — is checked by name.
import re, json, sys
from playwright.sync_api import sync_playwright

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
    ctx.route(re.compile(r"https://spots\.wwff\.co/.*"), lambda r: r.fulfill(
        status=200, content_type="application/json", body="[]"))
    # The sheet the old heatmap lived on. Nothing may go out to it any more.
    ctx.route(re.compile(r"https://docs\.google\.com/.*"), lambda r: r.abort())

with sync_playwright() as p:
    br = p.chromium.launch()
    ctx = br.new_context(service_workers="block", viewport={"width": 420, "height": 860})
    routes(ctx)
    sheet_calls = []
    ctx.on("request", lambda r: sheet_calls.append(r.url) if "docs.google.com" in r.url else None)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE, wait_until="load")
    pg.wait_for_timeout(2500)

    print("\n[1] without a position it says so, instead of showing an empty list")
    pg.evaluate("() => { here = null; cfg.grid = ''; }")
    pg.evaluate("() => document.querySelector('#nav button[data-view=\"viewNearby\"]').click()")
    pg.wait_for_timeout(800)
    ok(pg.evaluate("() => nearbyRows() === null"), "no GPS and no locator → no rows")
    ok(len(pg.evaluate("() => document.getElementById('nearBox').textContent").strip()) > 20,
       "and an explanation is shown")

    print("\n[2] a locator alone is enough — the GPS does not have to have answered")
    pg.evaluate("() => { cfg.grid = 'JO21EE'; renderNearby(); }")
    pg.wait_for_timeout(300)
    n = pg.evaluate("() => nearbyRows().length")
    ok(n > 0, f"references are listed from the locator alone (got {n})")
    ok("JO21EE" in pg.evaluate("() => document.getElementById('nearBox').textContent"),
       "and the header says the distances come from the locator")

    print("\n[2b] the radius is a setting, and 25 km is what you get unasked")
    ok(pg.evaluate("() => cfg.nearkm") == 25, "25 km by default")
    ok(all(d <= 25000 for d in pg.evaluate("() => nearbyRows().map(r=>r.d)")),
       "nothing outside the radius is listed")
    narrow = pg.evaluate("() => { cfg.nearkm=10; renderNearby(); return nearbyRows().length; }")
    ok(narrow < n, f"10 km reaches less far ({n} -> {narrow})")
    wide = pg.evaluate("() => { cfg.nearkm=100; renderNearby(); return nearbyRows().total; }")
    ok(wide > n, f"100 km reaches further ({n} -> {wide} within reach)")

    print("\n[2c] Belgium is dense enough that the list has a ceiling — so it says so")
    capped = pg.evaluate("() => ({shown: nearbyRows().length, total: nearbyRows().total})")
    ok(capped["shown"] == 100 and capped["total"] > 100,
       f"at 100 km: {capped['shown']} shown of {capped['total']} within reach")
    ok("/" in pg.evaluate("() => document.getElementById('nearBox').textContent"),
       "the header shows both numbers rather than pretending the list is complete")
    pg.evaluate("() => { cfg.nearkm=10; renderNearby(); }")
    ok("/" not in pg.evaluate("() => document.getElementById('nearBox').textContent"),
       "and shows one number when nothing was cut")
    ok(pg.is_hidden("#nearMore"), "and offers no 'show more' when there is no more")

    print("\n[2d] more than a pageful grows in place — no page 2 to navigate to")
    pg.evaluate("() => { cfg.nearkm=100; nearShown=100; renderNearby(); }")
    ok(not pg.is_hidden("#nearMore"), "the 'show more' button appears")
    before = pg.evaluate("() => document.querySelectorAll('#nearList .spot').length")
    pg.click("#nearMore"); pg.wait_for_timeout(300)
    after = pg.evaluate("() => document.querySelectorAll('#nearList .spot').length")
    ok(after == before + 100, f"it appends the next hundred in place ({before} -> {after})")
    ok(pg.evaluate("() => document.getElementById('nearBox').textContent").strip().startswith("200 /"),
       "and the header counts along")
    pg.click("#nearMetric .seg[data-metric='qso']"); pg.wait_for_timeout(300)
    ok(pg.evaluate("() => document.querySelectorAll('#nearList .spot').length") == 100,
       "changing the ordering starts again at the first pageful — it is a new question")
    pg.click("#nearMetric .seg[data-metric='dist']"); pg.wait_for_timeout(200)
    pg.evaluate("() => { cfg.nearkm=25; nearShown=100; saveSettings(); renderNearby(); }")
    ok("25 km" in pg.evaluate("() => document.getElementById('nearBox').textContent"),
       "and the header names the radius, not the distance of the last one on the list")
    pg.evaluate("() => { cfg.nearkm=25; saveSettings(); renderNearby(); }")

    print("\n[3] from a real position the nearest really is the nearest")
    # Standing in the Zwin, on the coast near Knokke.
    pg.evaluate("() => { here = {lat: 51.35, lon: 3.36}; renderNearby(); }")
    pg.wait_for_timeout(300)
    rows = pg.evaluate("() => nearbyRows().map(r => ({ref:r.ref, d:r.d, qso:r.qso, date:r.date}))")
    ok(rows[0]["d"] < rows[-1]["d"], "sorted by distance, closest first")
    ok(all(rows[i]["d"] <= rows[i+1]["d"] for i in range(len(rows)-1)), "and the whole list is in order")
    ok(rows[0]["d"] < 30000, f"the closest one is genuinely close ({rows[0]['ref']}, {rows[0]['d']/1000:.1f} km)")

    print("\n[4] the QSO figures are the real ones — this is what the heatmap got wrong")
    a = pg.evaluate("() => activityOf('ONFF-0002')")
    ok(a and a["qso"] > 1000, f"ONFF-0002 has its thousands of QSOs (got {a and a['qso']})")
    ok(a and a["date"], f"and a last activation ({a and a['date']})")
    known = pg.evaluate("() => Object.keys(activity).length")
    ok(known > 900, f"{known} references carry figures, not 205")
    ok(not sheet_calls, f"and nothing was asked of Google Sheets (calls: {len(sheet_calls)})")

    print("\n[5] the switch reorders the same references, it does not fetch other ones")
    refs_dist = pg.evaluate("() => nearbyRows().map(r => r.ref).sort()")
    pg.evaluate("() => { nearMetric = 'qso'; renderNearby(); }")
    by_qso = pg.evaluate("() => nearbyRows().map(r => ({ref:r.ref, qso:r.qso}))")
    ok(sorted(r["ref"] for r in by_qso) == refs_dist, "the same references, in a different order")
    ok(all(by_qso[i]["qso"] <= by_qso[i+1]["qso"] for i in range(len(by_qso)-1)),
       "fewest QSOs first — the ones worth a visit")

    pg.evaluate("() => { nearMetric = 'recency'; renderNearby(); }")
    by_date = pg.evaluate("() => nearbyRows().map(r => r.date || '')")
    ok(by_date == sorted(by_date), "by last active: longest untouched first")

    print("\n[6] tapping a reference opens it on the map")
    pg.evaluate("() => { nearMetric = 'dist'; renderNearby(); }")
    pg.wait_for_timeout(200)
    first = pg.evaluate("() => document.querySelector('#nearList .spot[data-ref]').dataset.ref")
    pg.click("#nearList .spot[data-ref]")
    pg.wait_for_timeout(900)
    ok(pg.evaluate("() => selected") == first, f"{first} is selected")
    ok("open" in pg.evaluate("() => document.getElementById('sheet').className"), "its panel is open")
    ok(not pg.evaluate("() => document.getElementById('viewNearby').classList.contains('on')"),
       "and we are back on the map to see it")

    print("\n[6b] and Map is the way home: nothing stays outlined")
    # Reported from the field: pick a reference in Nearby, look at it on the
    # map, tap Map — and the area stayed orange, as though you were still
    # standing in it.
    ok(pg.evaluate("() => selected") is not None, "something is selected to begin with")
    pg.evaluate("() => document.querySelector('#nav button[data-view=\"map\"]').click()")
    pg.wait_for_timeout(400)
    ok(pg.evaluate("() => selected") is None, "the selection is let go")
    ok(pg.evaluate("() => map._lastSel") is None, "and the outline on the map with it")
    ok("open" not in pg.evaluate("() => document.getElementById('sheet').className"),
       "the panel is closed too")

    print("\n[6c] a message can be seen from whatever screen you are on")
    # The update notice is asked for from Settings, and used to appear behind
    # it: the full screens sat above the message bar. You only saw it after
    # wandering back to the map.
    pg.evaluate("() => document.querySelector('#nav button[data-view=\"viewSet\"]').click()")
    pg.wait_for_timeout(300)
    # Only a message about the app itself rises above a full screen; a
    # confirmation belonging to the screen you are on must NOT, or it would
    # cover the buttons you just used.
    pg.evaluate("() => showStatus('in', 'Test message', 'from the settings screen', true)")
    pg.wait_for_timeout(200)
    top = pg.evaluate("""() => {
        const b = document.getElementById('status').getBoundingClientRect();
        const el = document.elementFromPoint(b.left + b.width/2, b.top + b.height/2);
        return el ? el.closest('#status') !== null : false;
    }""")
    ok(top, "a message about the app is the thing you would touch, not the screen behind it")
    pg.evaluate("() => { hideStatus(); showStatus('in', 'Ordinary', 'belongs to this screen'); }")
    pg.wait_for_timeout(150)
    covered = pg.evaluate("""() => {
        const b = document.getElementById('status').getBoundingClientRect();
        const el = document.elementFromPoint(b.left + b.width/2, b.top + b.height/2);
        return el ? el.closest('#status') !== null : false;
    }""")
    ok(not covered, "an ordinary one stays under the screen, so it cannot cover its buttons")
    pg.evaluate("() => hideStatus()")

    print("\n[7] nothing thrown along the way")
    ok(not errs, f"no page errors: {errs or 'ok'}")

    print("\nALL OK" if not fails else f"\n{len(fails)} FAILED")
    br.close()
    sys.exit(1 if fails else 0)
