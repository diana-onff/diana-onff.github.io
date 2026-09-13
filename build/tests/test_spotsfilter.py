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

    print("\n[5] one specific country via Settings")
    pg.evaluate("""() => {
        const sel = document.getElementById('setSpotCountry');
        const opt = [...sel.options].find(o => o.textContent === 'Netherlands');
        sel.value = opt.value; sel.dispatchEvent(new Event('change'));
    }""")
    pg.wait_for_timeout(200)
    vis_nl = pg.evaluate("() => visibleSpots().map(s=>s.reference)")
    ok(vis_nl == ["PAFF-0123"], f"only the Dutch spot (got {vis_nl})")

    print("\n[6] the two screens stay in sync")
    # This used to read "no button active once a country has been chosen",
    # because the first button was hardwired to ONFF and could not represent
    # anything else. It carries a real programme code now, so picking the
    # Netherlands in Settings is something the quick bar can show — and does.
    home = pg.evaluate("() => document.querySelector('#spotFilter [data-home]').textContent")
    ok(home == "PAFF", f"the quick button followed the choice ({home})")
    ok(pg.evaluate("() => document.querySelector('#spotFilter [data-home]').classList.contains('on')"),
       "and is the active one")
    ok(pg.evaluate("() => document.querySelector('#setSpotFilter [data-home]').textContent") == "PAFF",
       "the same in Settings")

    print("\n[7] the choice survives a reload")
    # Key renamed to spotFilter2 when 'worldwide' became the factory setting: an
    # old choice left hanging around during testing was not allowed to keep
    # overruling it.
    saved = pg.evaluate("() => localStorage.getItem('diana.spotFilter2')")
    ok(saved == "PAFF", f"'PAFF' saved (got '{saved}')")
    pg.reload(wait_until="load")
    pg.wait_for_timeout(2000)
    after_reload = pg.evaluate("() => spotFilter")
    ok(after_reload == "PAFF", f"filter still 'PAFF' after a reload (got '{after_reload}')")
    sel_after = pg.evaluate("() => document.getElementById('setSpotCountry').value")
    ok(sel_after == "PAFF", "the country dropdown shows the saved choice after a reload")

    print("\n[8] back to worldwide via the quick filter")
    pg.evaluate("() => document.querySelector('#spotFilter [data-filter=\"all\"]').click()")
    pg.wait_for_timeout(200)
    country_reset = pg.evaluate("() => document.getElementById('setSpotCountry').value")
    ok(country_reset == "", "the country dropdown is empty again after 'Worldwide'")

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
