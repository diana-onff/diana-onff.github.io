"""The setup wizard (since 2.1.0): once, straight after the welcome screen on a
new device; settings written into Settings; a tour along the real screens;
and again on request from Settings, starting from what is already set.

Like test_privacy.py this does NOT import preconsent: it is about the first
visit itself.

    python3 build/tests/test_wizard.py      (local server on :8011)
"""
import json
import re

from playwright.sync_api import sync_playwright

BASE = "http://localhost:8011/web/"
HOBOKEN = {"latitude": 51.1750, "longitude": 4.3450}
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
    ctx.route(re.compile(r"https://cloud\.umami\.is/.*"),
              lambda r: r.fulfill(status=200, content_type="application/javascript", body="/* stub */"))


def js(pg, expr):
    return pg.evaluate("() => " + expr)


def ls(pg, key):
    return js(pg, f"localStorage.getItem('diana.{key}')")


def shown(pg, sel):
    return js(pg, f"!!document.querySelector('{sel}') && !document.querySelector('{sel}').hidden")


with sync_playwright() as p:
    br = p.chromium.launch()
    ctx = br.new_context(service_workers="block", locale="nl-BE", viewport={"width": 420, "height": 860},
                         geolocation=dict(HOBOKEN, accuracy=8), permissions=["geolocation"])
    routes(ctx)
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(BASE, wait_until="load")
    pg.wait_for_timeout(1500)

    print("\n[1] a new device: welcome screen first, then the wizard, in English")
    ok(shown(pg, "#consent") and not shown(pg, "#wizard"), "the welcome screen comes first, no wizard yet")
    pg.click("#consentNo")
    pg.wait_for_timeout(300)
    ok(shown(pg, "#wizard"), "answering it opens the wizard")
    ok(js(pg, "document.getElementById('wzTitle').textContent") == "Welcome to Diana",
       "in English, even with a Dutch browser")
    ok(ls(pg, "nearkm") == "10", "Field info is set to 10 km without asking")
    ok(not shown(pg, "#wzClose"), "a first run has no close button")

    print("\n[2] picking a language switches the wizard at once and is saved")
    pg.click("#wzLangs .seg[data-lang='nl']")
    pg.wait_for_timeout(200)
    ok(js(pg, "document.getElementById('wzTitle').textContent") == "Welkom bij Diana", "the wizard is now Dutch")
    ok(ls(pg, "lang") == "nl", "and the choice is in Settings")

    print("\n[3] station: what you type lands in Settings")
    pg.click("#wzNext")
    pg.fill("#wzCall", "on3vz")
    pg.fill("#wzCallP", "on3vz/p")
    pg.fill("#wzGrid", "jo21ee")
    ok(ls(pg, "call") == "ON3VZ" and ls(pg, "callp") == "ON3VZ/P" and ls(pg, "grid") == "JO21EE",
       f"callsigns and locator saved, in capitals ({ls(pg, 'call')}, {ls(pg, 'callp')}, {ls(pg, 'grid')})")
    ok(js(pg, "document.getElementById('setCall').value") == "ON3VZ", "and shown in the Settings field")

    print("\n[4] country: the list is there and follows the callsign")
    pg.click("#wzNext")
    pg.wait_for_timeout(1000)
    ok(js(pg, "!!document.getElementById('wzCountry') && document.getElementById('wzCountry').value") == "ONFF",
       "Belgium (ONFF) is preselected for ON3VZ")

    print("\n[5] quick words: empty on a first run, and empty is what gets saved")
    pg.click("#wzNext")
    vals = js(pg, "[0,1,2,3,4].map(i => document.getElementById('wzChip'+i).value)")
    ok(vals == ["", "", "", "", ""], f"the five fields start empty ({vals})")
    pg.click("#wzNext")
    ok(json.loads(ls(pg, "chips") or "null") == ["", "", "", "", ""], "skipping saves five empty words")

    print("\n[6] band list, and the statistics question once more after a no")
    pg.click("#wzBands .seg[data-bands='short']")
    ok(ls(pg, "bands") == "short", "HF only is saved")
    pg.click("#wzNext")
    ok(js(pg, "!!document.getElementById('wzStats')"), "the statistics step is there, because the answer was no")
    pg.click("#wzStats .seg[data-stats='1']")
    ok(ls(pg, "consent.stats") == "1", "and a yes there is saved")

    print("\n[7] the last settings step: saved, where to change it, how long it is kept")
    pg.click("#wzNext")
    body = js(pg, "document.getElementById('wzBody').textContent")
    ok("Instellingen" in body and "browsergegevens" in body, "it says where to change things and that clearing the browser data loses them")
    ok(ls(pg, "wizard.done") == "1", "the wizard counts as done")

    print("\n[8] the tour: real screens, card above the bottom bar, then back to the map")
    pg.click("#wzTourGo")
    pg.wait_for_timeout(300)
    ok(not shown(pg, "#wizard") and shown(pg, "#wzTour"), "the settings card is gone, the tour card is up")
    seen = []
    for _ in range(7):
        seen.append(js(pg, "document.querySelector('#nav button.wzhl') && document.querySelector('#nav button.wzhl').dataset.view"))
        pg.click("#wzTNext")
        pg.wait_for_timeout(150)
    ok(seen == ["map", "viewSpots", "viewSelf", "viewAgendaNew", "viewNearby", "viewRules", "viewSet"],
       f"seven screens, each with its bottom-bar button marked ({seen})")
    ok(not shown(pg, "#wzTour") and js(pg, "document.querySelector('#nav button.on').dataset.view") == "map",
       "after the last one: tour gone, back on the map")

    print("\n[9] not again on the next start; again on request, with what is already set")
    pg.reload(wait_until="load")
    pg.wait_for_timeout(1500)
    ok(not shown(pg, "#consent") and not shown(pg, "#wizard"), "a restart shows neither screen")
    js(pg, "document.querySelector('#nav button[data-view=\"viewSet\"]').click()")
    pg.click("#setNearKm .seg[data-km='25']")
    pg.click("#wzRerun")
    pg.click("#wzNext")
    ok(js(pg, "document.getElementById('wzCall').value") == "ON3VZ", "Settings → run again starts from your settings")
    ok(ls(pg, "nearkm") == "25", "and leaves the distance it does not ask about alone")
    ok(shown(pg, "#wzClose"), "run again from Settings, it can be closed")
    pg.go_back()
    pg.wait_for_timeout(300)
    ok(not shown(pg, "#wizard") and js(pg, "document.getElementById('viewSet').classList.contains('on')"),
       "the back button closes it and leaves you in Settings")

    ok(not errors, f"no page errors ({errors[:2]})")
    br.close()

print("\n" + ("ALL OK" if not fails else f"{len(fails)} FAILED: " + "; ".join(fails)))
