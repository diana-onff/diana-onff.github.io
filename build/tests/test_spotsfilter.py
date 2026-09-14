import re, json, sys
from playwright.sync_api import sync_playwright
BASE = "http://localhost:8011/web/"
fails = []


def ok(c, m):
    print(("  ✓ " if c else "  ✗ ") + m)
    if not c:
        fails.append(m)


import time
NOW = int(time.time())
# Deliberately out of order, and deliberately not all the same age: the list
# has to put the newest on top, whether or not a GPS fix is in.
SPOTS = [
    {"id": 1, "reference": "ONFF-0001", "activator": "ON1TEST", "latitude": 50.85, "longitude": 4.35,
     "frequency_khz": 14285, "mode": "SSB", "spot_time": NOW - 25 * 60},
    {"id": 2, "reference": "PAFF-0123", "activator": "PA1TEST", "latitude": 52.1, "longitude": 5.1,
     "frequency_khz": 7130, "mode": "SSB", "spot_time": NOW - 2 * 60},
    {"id": 3, "reference": "VKFF-0456", "activator": "VK1TEST", "latitude": -35.3, "longitude": 149.1,
     "frequency_khz": 21200, "mode": "SSB", "spot_time": NOW - 12 * 60},
]


def routes(ctx):
    ctx.route(re.compile(r"https://tiles\.openfreemap\.org/.*"), lambda r: r.fulfill(
        status=200, content_type="application/json",
        body=json.dumps({"version": 8, "sources": {}, "layers": [
            {"id": "bg", "type": "background", "paint": {"background-color": "#e8e4d8"}}]})))
    ctx.route(re.compile(r"https://spots\.wwff\.co/static/spots\.json"), lambda r: r.fulfill(
        status=200, content_type="application/json", body=json.dumps(SPOTS)))
    ctx.route(re.compile(r"https://spots\.wwff\.co/static/agendas.*"), lambda r: r.fulfill(
        status=200, content_type="application/json", body="[]"))
    ctx.route(re.compile(r"https://docs\.google\.com/.*"), lambda r: r.abort())


with sync_playwright() as p:
    br = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
                            if __import__('os').path.exists("/opt/pw-browsers/chromium-1194/chrome-linux/chrome") else None)
    ctx = br.new_context(service_workers="block", viewport={"width": 420, "height": 860})
    routes(ctx)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE, wait_until="load")
    pg.wait_for_timeout(2000)

    print("\n[1] factory setting: worldwide, not ONFF-only")
    default_filter = pg.evaluate("() => spotFilter")
    ok(default_filter == "all", f"spotFilter default is 'all' (got '{default_filter}')")

    print("\n[2] wwff-programs.json has been loaded")
    n = pg.evaluate("() => wwffPrograms.length")
    ok(n > 100, f"more than 100 programmes loaded (got {n})")
    onff_country = pg.evaluate("() => (wwffPrograms.find(p=>p.program==='ONFF')||{}).country")
    ok(onff_country == "Belgium", f"ONFF → Belgium (got '{onff_country}')")

    print("\n[3] worldwide shows all three spots")
    pg.evaluate("() => { showSpots=true; startSpots(); }")
    pg.wait_for_timeout(600)
    vis = pg.evaluate("() => visibleSpots().length")
    ok(vis == 3, f"3 spots visible under 'worldwide' (got {vis})")

    print("\n[4] the first button is a country, and filters to it")
    pg.evaluate("() => document.querySelector('#spotFilter [data-home]').click()")
    pg.wait_for_timeout(200)
    vis_onff = pg.evaluate("() => visibleSpots().map(s=>s.reference)")
    ok(vis_onff == ["ONFF-0001"], f"only ONFF-0001 (got {vis_onff})")

    print("\n[5] Settings' country picker only changes the polygons now, not the filter")
    # This used to also narrow the spots filter to whatever you picked here —
    # so loading a country's boundaries just to have a look silently hid every
    # other country's spots you were watching. The two are independent choices
    # now: this picker decides which polygons load, full stop. The picker lists
    # "Netherlands — PAFF" and is grouped by whether Diana has boundaries for a
    # country, so it is looked up by value, not by its label.
    pg.evaluate("""() => {
        const sel = document.getElementById('setSpotCountry');
        sel.value = 'PAFF'; sel.dispatchEvent(new Event('change'));
    }""")
    pg.wait_for_timeout(900)
    ok(pg.evaluate("() => homeCountry()") == "PAFF", "the country itself did change")
    ok(pg.evaluate("() => spotFilter") == "ONFF", "but the spots filter is exactly where it was")
    vis_still = pg.evaluate("() => visibleSpots().map(s=>s.reference)")
    ok(vis_still == ["ONFF-0001"], f"still only ONFF-0001 visible (got {vis_still})")

    print("\n[6] the two quick-filter bars still agree — with each other, not the country picker")
    # Both read whichever programme the filter is actually narrowed to, which is
    # no longer guaranteed to be the same thing as your country.
    home = pg.evaluate("() => document.querySelector('#spotFilter [data-home]').textContent")
    ok(home == "ONFF", f"the quick button still reads the active filter, not the new country ({home})")
    ok(pg.evaluate("() => document.querySelector('#spotFilter [data-home]').classList.contains('on')"),
       "and is the active one")
    ok(pg.evaluate("() => document.querySelector('#setSpotFilter [data-home]').textContent") == "ONFF",
       "the same in Settings")
    ok(pg.evaluate("() => document.getElementById('setSpotCountry').value") == "PAFF",
       "while the country picker itself keeps showing what it was actually set to")

    print("\n[7] both choices survive a reload, independently")
    # Key renamed to spotFilter2 when 'worldwide' became the factory setting: an
    # old choice left hanging around during testing was not allowed to keep
    # overruling it. It has its own storage key, separate from the country.
    ok(pg.evaluate("() => localStorage.getItem('diana.homeprog')") == "PAFF", "'PAFF' saved as the country")
    ok(pg.evaluate("() => localStorage.getItem('diana.spotFilter2')") == "ONFF",
       "'ONFF' saved as the filter, not overwritten by the country choice")
    pg.reload(wait_until="load")
    pg.wait_for_timeout(2000)
    ok(pg.evaluate("() => homeCountry()") == "PAFF", "still the Netherlands as your country")
    ok(pg.evaluate("() => spotFilter") == "ONFF", "and the filter still narrowed to Belgium")
    sel_after = pg.evaluate("() => document.getElementById('setSpotCountry').value")
    ok(sel_after == "PAFF", "the country dropdown shows the saved choice after a reload")

    print("\n[8] back to worldwide via the quick filter")
    # The picker used to blank out here, because it was the filter in dropdown
    # form. It is your country now — the one setting behind the boundaries and
    # the foreign points — and looking at the world for a moment does not mean
    # you have stopped living somewhere, regardless of what you had narrowed
    # the spots to before.
    pg.evaluate("() => document.querySelector('#spotFilter [data-filter=\"all\"]').click()")
    pg.wait_for_timeout(200)
    country_kept = pg.evaluate("() => document.getElementById('setSpotCountry').value")
    ok(country_kept == "PAFF", f"the picker still names your country ({country_kept})")
    ok(pg.evaluate("() => spotFilter") == "all", "while the filter itself is worldwide")
    # With the filter back on Worldwide, "your country" for the quick bar's own
    # button is no longer pinned to the stale ONFF narrowing — it falls back to
    # the country that is actually yours.
    ok(pg.evaluate("() => document.querySelector('#spotFilter [data-home]').textContent") == "PAFF",
       "and the quick button now offers the country you actually have set")

    print("\n[8b] without a choice, the country comes from your callsign")
    # "Without a choice" has to mean it: a country picked earlier is remembered
    # on purpose and outranks the callsign, so clear that first.
    pg.evaluate("""() => {
        localStorage.removeItem('diana.homeprog');
        setSpotFilter('all');
        cfg.call = 'PA0TEST'; cfg.callp = ''; syncSpotFilterUI();
    }""")
    ok(pg.evaluate("() => homeProgram()") == "PAFF", "PA0TEST → PAFF")
    ok(pg.evaluate("() => document.querySelector('#spotFilter [data-home]').textContent") == "PAFF",
       "and the button says so")
    for call, prog in [("DL1ABC", "DLFF"), ("ON3VZ", "ONFF"), ("G0XYZ", "GXFF"),
                       ("OZ1AA", "OZFF"), ("XYZ9Q", "ONFF")]:
        got = pg.evaluate(f"() => {{ localStorage.removeItem('diana.homeprog');"
                          f" cfg.call = '{call}'; return homeProgram(); }}")
        ok(got == prog, f"{call} → {got}" + ("" if got == prog else f" (expected {prog})"))
    pg.evaluate("() => { cfg.call = 'ON3VZ'; syncSpotFilterUI(); }")

    print("\n[8b2] Worldwide does not forget which country is yours")
    # The first version fell back to the callsign's country the moment you
    # tapped Worldwide, so a Belgian who had picked the Netherlands found
    # Belgium waiting for him on the way back.
    pg.evaluate("() => { cfg.call = 'ON3VZ'; setSpotFilter('PAFF'); }")
    pg.wait_for_timeout(150)
    ok(pg.evaluate("() => document.querySelector('#spotFilter [data-home]').textContent") == "PAFF",
       "picked the Netherlands")
    pg.evaluate("() => document.querySelector('#spotFilter [data-filter=\"all\"]').click()")
    pg.wait_for_timeout(150)
    ok(pg.evaluate("() => document.querySelector('#spotFilter [data-home]').textContent") == "PAFF",
       "the button still offers the Netherlands while showing the world")
    pg.evaluate("() => document.querySelector('#spotFilter [data-home]').click()")
    pg.wait_for_timeout(150)
    ok(pg.evaluate("() => spotFilter") == "PAFF", "and one tap goes back there, not to Belgium")
    pg.reload(wait_until="load"); pg.wait_for_timeout(2000)
    pg.evaluate("() => { setSpotFilter('all'); showSpots=true; startSpots(); }")
    pg.wait_for_timeout(400)
    ok(pg.evaluate("() => document.querySelector('#spotFilter [data-home]').textContent") == "PAFF",
       "and it is still the Netherlands after a restart")

    print("\n[8c] every programme in the prefix table really exists")
    # A guess that points at a programme WWFF does not have would filter the
    # list down to nothing, silently. Checked against the directory we ship.
    missing = pg.evaluate("""() => {
        const known = new Set(wwffPrograms.map(p => p.program));
        return [...new Set(Object.values(PREFIX_PROGRAM))].filter(p => !known.has(p));
    }""")
    ok(not missing, f"no invented programme codes (missing: {missing})")

    print("\n[8d] a filter saved under the old name still works")
    pg.evaluate("() => localStorage.setItem('diana.spotFilter2', 'onff')")
    pg.reload(wait_until="load"); pg.wait_for_timeout(2000)
    ok(pg.evaluate("() => spotFilter") == "ONFF",
       "the old 'onff' value is read as the programme code ONFF")
    pg.evaluate("() => { setSpotFilter('all'); showSpots=true; startSpots(); }")
    pg.wait_for_timeout(600)

    print("\n[9] the list reads newest first, and says how old each spot is")
    # This used to sort by distance the moment a GPS fix came in — and the age
    # was pushed off the row to make room for the bearing, so in the field you
    # could not tell a two-minute spot from a fifty-minute one. On a list that
    # only holds the last hour, that is the one thing you are reading it for.
    pg.evaluate("() => { spotFilter='all'; here=null; renderSpots(); }")
    pg.wait_for_timeout(200)
    order = pg.evaluate("() => [...document.querySelectorAll('#spotList .spot')].map(r=>r.dataset.id)")
    ok(order == ["2", "3", "1"], f"without a fix: newest first ({order})")

    pg.evaluate("() => { here = {lat:50.85, lon:4.35}; renderSpots(); }")
    pg.wait_for_timeout(200)
    order = pg.evaluate("() => [...document.querySelectorAll('#spotList .spot')].map(r=>r.dataset.id)")
    ok(order == ["2", "3", "1"], f"with a fix on top of spot 1: still newest first ({order})")

    rows = pg.evaluate("() => [...document.querySelectorAll('#spotList .spot .d')].map(d=>d.textContent)")
    ok(all("′" in r for r in rows), f"every row carries its age ({rows[0]!r})")
    ok(any("km" in r or " m" in r for r in rows), f"and the distance is there too ({rows[0]!r})")

    print("\n[10] no JS errors")
    real = [e for e in errs if "Failed to load resource" not in e]
    ok(not real, "no page errors: " + (real[0][:160] if real else "ok"))

    br.close()

print("\n" + ("ALL OK" if not fails else f"{len(fails)} PROBLEMS: " + " | ".join(fails)))
sys.exit(1 if fails else 0)
