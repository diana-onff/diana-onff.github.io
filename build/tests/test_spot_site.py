# "More info" on the spot detail sheet, and agenda rows that open that sheet.
#
#     python3 build/tests/test_spot_site.py
#
# Two things, because the one needs the other.
#
# The link: the WWFF directory has a website for most references (ONFF, DLFF,
# OZFF and PAFF together: some 2,300 of 2,900), which Diana never showed. It
# now sits on the spot sheet as "More info", from data/sites/<prog>.json
# (kmz2geojson.py writes one file per programme). What is guarded here:
# the file is only fetched when a sheet opens, and only for that programme;
# the sheet does not wait for it; the link ALWAYS opens in a new tab or
# window (target=_blank, rel=noopener noreferrer), so Diana itself, the map
# and a running GPS fix stay exactly where they were; and nothing but http(s)
# ever ends up in the href.
#
# The agenda: an agenda row looked like a live spot but a tap on it did
# nothing (the row had no data-id, and the click handler only listens for
# that). Found in the field. Agenda rows now open the same sheet, with what an
# announcement has: band and mode, the area, its locator, and the link.
# Everything in an announcement was typed in by someone, so it is escaped.
import re, json, sys, time
from playwright.sync_api import sync_playwright
import preconsent  # noqa: F401  answered welcome screen, see preconsent.py

BASE = "http://localhost:8011/web/"
fails = []


def ok(c, m):
    print(("  ✓ " if c else "  ✗ ") + m)
    if not c:
        fails.append(m)


NOW = time.time()
ts = lambda off: time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(NOW + off))

SPOTS = [
    {"id": 101, "activator": "ON3VZ/P", "reference": "ONFF-0037", "reference_name": "Leiemeersen",
     "frequency_khz": 14285, "mode": "SSB", "latitude": 50.95, "longitude": 3.10, "spot_time": NOW - 60},
    {"id": 102, "activator": "ON4NO", "reference": "ONFF-0002", "reference_name": "Kalmthoutse Heide",
     "frequency_khz": 7144, "mode": "SSB", "latitude": 51.39, "longitude": 4.43, "spot_time": NOW - 120},
    {"id": 103, "activator": "PA0XX", "reference": "PAFF-0001", "reference_name": "Somewhere",
     "frequency_khz": 7030, "mode": "CW", "latitude": 52.1, "longitude": 5.1, "spot_time": NOW - 180},
    {"id": 104, "activator": "ON5EV", "reference": "ONFF-0003", "reference_name": "Zwin",
     "frequency_khz": 3700, "mode": "SSB", "latitude": 51.36, "longitude": 3.36, "spot_time": NOW - 240},
]
AGENDA = [
    {"id": 7, "reference": "ONFF-0037", "activator_call": "ON3VZ/P", "band": "20m,40m", "mode": "SSB",
     "utc_start": ts(-1800), "utc_end": ts(5400),
     "remarks": "<img src=x onerror=\"window.__pwned=1\">QRV with <b>5 W</b>"},
    {"id": 8, "reference": "ONFF-0002", "activator_call": "ON4NO", "band": "40m", "mode": "CW",
     "utc_start": ts(86400), "utc_end": ts(86400 + 7200)},
]
ONFF_SITES = {"refs": {
    "ONFF-0037": "http://valleivandezuidleie.be/info-over-de-vallei-van-de-zuidleie/leiemeersen-noord/",
    "ONFF-0002": "http://www.natuurenbos.be/kalmthoutseheide",
    # A link that would never come out of the build, but the app must not trust that.
    "ONFF-0003": "javascript:window.__pwned=2",
}}


def routes(ctx, held=None, seen=None):
    ctx.route(re.compile(r"https://tiles\.openfreemap\.org/.*"), lambda r: r.fulfill(
        status=200, content_type="application/json",
        body=json.dumps({"version": 8, "sources": {}, "layers": [
            {"id": "bg", "type": "background", "paint": {"background-color": "#e8e4d8"}}]})))
    ctx.route(re.compile(r"https://spots\.wwff\.co/static/spots\.json"), lambda r: r.fulfill(
        status=200, content_type="application/json", body=json.dumps(SPOTS)))
    ctx.route(re.compile(r"https://spots\.wwff\.co/static/agendas_active\.json"), lambda r: r.fulfill(
        status=200, content_type="application/json", body=json.dumps(AGENDA[:1])))
    ctx.route(re.compile(r"https://spots\.wwff\.co/static/agendas\.json"), lambda r: r.fulfill(
        status=200, content_type="application/json", body=json.dumps(AGENDA)))
    ctx.route(re.compile(r"https://docs\.google\.com/.*"), lambda r: r.abort())
    ctx.route(re.compile(r"http://(valleivandezuidleie\.be|www\.natuurenbos\.be)/.*"), lambda r: r.fulfill(
        status=200, content_type="text/html", body="<title>extern</title><p>external site</p>"))

    def sites(route):
        prog = route.request.url.rsplit("/", 1)[-1]
        if seen is not None:
            seen.append(prog)
        if held is not None:          # answer later, when the test says so
            held.append(route)
            return
        if prog == "onff.json":
            route.fulfill(status=200, content_type="application/json", body=json.dumps(ONFF_SITES))
        else:
            route.fulfill(status=404, body="not found")
    ctx.route(re.compile(r".*/data/sites/[a-z0-9]+\.json$"), sites)


def tap(pg, selector):
    pg.evaluate("(s) => document.querySelector(s).click()", selector)


def release(held):
    """Let the held-back link files through, in the order they were asked for."""
    while held:
        route = held.pop(0)
        prog = route.request.url.rsplit("/", 1)[-1]
        if prog == "onff.json":
            route.fulfill(status=200, content_type="application/json", body=json.dumps(ONFF_SITES))
        else:
            route.fulfill(status=404, body="not found")


SHEET = """() => {
  const s = document.getElementById('spotSheet');
  const a = s.querySelector('.fact.site a');
  const site = s.querySelector('.fact.site');
  return {
    open: s.classList.contains('open'),
    call: document.getElementById('spCall').textContent,
    ref: document.getElementById('spRef').textContent,
    ago: document.getElementById('spAgo').textContent,
    facts: document.getElementById('spFacts').innerText,
    href: a ? a.getAttribute('href') : null,
    target: a ? a.getAttribute('target') : null,
    rel: a ? a.getAttribute('rel') : null,
    text: a ? a.textContent.trim() : null,
    label: site ? site.querySelector('.k').textContent : null,
    hint: site ? (site.querySelector('.s') || {}).textContent : null,
    links: s.querySelectorAll('.fact.site').length,
  };
}"""

with sync_playwright() as p:
    br = p.chromium.launch()
    errs = []

    seen = []
    ctx = br.new_context(service_workers="block", viewport={"width": 420, "height": 860})
    routes(ctx, seen=seen)
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE, wait_until="load")
    pg.wait_for_function("() => document.querySelectorAll('#spotList .spot[data-id]').length >= 4", timeout=15000)
    pg.wait_for_timeout(500)

    print("\n[1] nothing is fetched until a sheet opens")
    ok(seen == [], f"no data/sites/ request on start ({seen})")

    print("\n[2] a live spot: the link, and how it opens")
    tap(pg, '#spotList .spot[data-id="101"]')
    pg.wait_for_function("() => document.querySelector('#spotSheet .fact.site a')", timeout=5000)
    s = pg.evaluate(SHEET)
    ok(s["open"] and s["call"] == "ON3VZ/P", f"the sheet opens for the spot ({s['call']})")
    ok(s["href"] == ONFF_SITES["refs"]["ONFF-0037"], f"the link is the directory's own ({s['href']})")
    ok(s["target"] == "_blank", f"it opens in a new tab or window, never in Diana's own ({s['target']})")
    ok(s["rel"] and "noopener" in s["rel"].split() and "noreferrer" in s["rel"].split(),
       f"with noopener noreferrer ({s['rel']})")
    ok(s["text"] == "valleivandezuidleie.be", f"showing just the host name ({s['text']!r})")
    ok(s["label"] == "More info" and s["hint"] == "opens in your browser",
       f"labelled, with the hint underneath ({s['label']!r}, {s['hint']!r})")
    ok(seen == ["onff.json"], f"only this programme's file was fetched ({seen})")

    print("\n[3] tapping it leaves Diana where it was")
    with ctx.expect_page(timeout=5000) as popup:
        pg.click('#spotSheet .fact.site a')
    other = popup.value
    other.wait_for_load_state()
    ok("valleivandezuidleie.be" in other.url, f"the site opens in a page of its own ({other.url})")
    ok(pg.url.startswith(BASE), f"Diana's own page did not navigate away ({pg.url})")
    ok(pg.evaluate("() => document.getElementById('spotSheet').classList.contains('open')"),
       "and the sheet is still open, exactly as it was")
    ok(other.evaluate("() => window.opener") is None, "the opened page gets no handle on Diana's window")
    other.close()

    print("\n[4] the same programme a second time: no new download")
    pg.evaluate("() => document.getElementById('closeSpot').click()")
    tap(pg, '#spotList .spot[data-id="102"]')
    pg.wait_for_function("() => document.getElementById('spRef').textContent === 'ONFF-0002'", timeout=5000)
    pg.wait_for_function("() => document.querySelector('#spotSheet .fact.site a')", timeout=5000)
    s = pg.evaluate(SHEET)
    ok(s["text"] == "natuurenbos.be" and s["links"] == 1, f"its own link, once ({s['text']!r}, {s['links']})")
    ok(seen == ["onff.json"], f"still only one fetch ({seen})")

    print("\n[5] only http and https ever reach the href")
    tap(pg, '#spotList .spot[data-id="104"]')
    pg.wait_for_function("() => document.getElementById('spRef').textContent === 'ONFF-0003'", timeout=5000)
    pg.wait_for_timeout(300)
    s = pg.evaluate(SHEET)
    ok(s["links"] == 0, "a javascript: link in the file gets no line at all")
    ok(pg.evaluate("() => window.__pwned") is None, "and nothing ran")

    print("\n[6] a programme with no file: the sheet simply has no link")
    tap(pg, '#spotList .spot[data-id="103"]')
    pg.wait_for_function("() => document.getElementById('spRef').textContent === 'PAFF-0001'", timeout=5000)
    pg.wait_for_timeout(400)
    s = pg.evaluate(SHEET)
    ok(s["open"] and s["links"] == 0, f"open, no link ({s['links']})")
    ok("paff.json" in seen, "it was asked for")
    # One attempt can be two requests: fetchFirst() tries the published
    # layout and the repository layout. What matters is that a second tap
    # within the minute makes no new attempt at all.
    before = seen.count("paff.json")
    tap(pg, '#spotList .spot[data-id="103"]')
    pg.wait_for_timeout(300)
    ok(seen.count("paff.json") == before, f"and not again straight away ({before} -> {seen.count('paff.json')})")

    print("\n[7] agenda rows open the sheet (a tap used to do nothing)")
    pg.evaluate("() => document.getElementById('closeSpot').click()")
    pg.evaluate("() => document.querySelector('#spotTab .seg[data-tab=\"agenda\"]').click()")
    pg.wait_for_function("() => document.querySelectorAll('#spotList .spot[data-ag]').length === 2", timeout=5000)
    tap(pg, '#spotList .spot[data-ag="7"]')
    pg.wait_for_function("() => document.getElementById('spotSheet').classList.contains('open')", timeout=5000)
    pg.wait_for_function("() => document.querySelector('#spotSheet .fact.site a')", timeout=5000)
    s = pg.evaluate(SHEET)
    ok(s["call"] == "ON3VZ/P" and s["ref"] == "ONFF-0037", f"the announcement's call and reference ({s['call']}, {s['ref']})")
    ok("live" in s["ago"] and "until" in s["ago"] and "UTC" in s["ago"], f"running now, until when ({s['ago']!r})")
    ok("band / mode" in s["facts"].lower() and "20m,40m · SSB" in s["facts"], "band and mode")
    ok("Leiemeersen" in s["facts"], "the area's name, from Diana's own data")
    ok("locator there" in s["facts"].lower(), "and its locator, from the area's position")
    ok(s["href"] == ONFF_SITES["refs"]["ONFF-0037"] and s["target"] == "_blank", "with the same link, same way of opening")

    print("\n[8] what someone typed into an announcement stays text")
    ok("QRV with <b>5 W</b>" in s["facts"], "the remark is shown as typed")
    ok(pg.evaluate("() => document.querySelector('#spFacts img, #spFacts b')") is None, "no element was made of it")
    pg.wait_for_timeout(300)
    ok(pg.evaluate("() => window.__pwned") is None, "and nothing ran")

    print("\n[9] an announcement for later: its date and time instead")
    tap(pg, '#spotList .spot[data-ag="8"]')
    pg.wait_for_function("() => document.getElementById('spRef').textContent === 'ONFF-0002'", timeout=5000)
    s = pg.evaluate(SHEET)
    start = AGENDA[1]["utc_start"]
    ok(start[5:10] in s["ago"] and start[11:16] in s["ago"] and "UTC" in s["ago"],
       f"when it starts ({s['ago']!r})")
    ok("40m · CW" in s["facts"], "band and mode")

    print("\n[10] in Dutch")
    pg.evaluate("() => { lang = 'nl'; applyLang(); }")
    tap(pg, '#spotList .spot[data-ag="8"]')
    pg.wait_for_function("() => document.querySelector('#spotSheet .fact.site a')", timeout=5000)
    s = pg.evaluate(SHEET)
    ok(s["label"] == "Meer info" and s["hint"] == "opent in je browser", f"({s['label']!r}, {s['hint']!r})")
    ok(not errs, f"no page errors ({errs[:2]})")
    ctx.close()

    print("\n[11] a slow connection: the sheet does not wait for the link")
    ctx = br.new_context(service_workers="block", viewport={"width": 420, "height": 860})
    held = []
    routes(ctx, held=held)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE, wait_until="load")
    pg.wait_for_function("() => document.querySelectorAll('#spotList .spot[data-id]').length >= 4", timeout=15000)
    tap(pg, '#spotList .spot[data-id="101"]')
    for _ in range(50):                      # until the link file has been asked for (and held back)
        if held:
            break
        pg.wait_for_timeout(100)
    s = pg.evaluate(SHEET)
    ok(s["open"] and s["links"] == 0 and len(held) >= 1,
       f"the sheet is open at once, still without the link ({len(held)} request(s) held back)")
    release(held)
    pg.wait_for_function("() => document.querySelector('#spotSheet .fact.site a')", timeout=8000)
    s = pg.evaluate(SHEET)
    ok(s["links"] == 1 and s["text"] == "valleivandezuidleie.be", "and the link joins it once the file lands")
    ok(not errs, f"no page errors ({errs[:2]})")
    ctx.close()

    print("\n[12] closed or moved on before the file lands: no stray link")
    ctx = br.new_context(service_workers="block", viewport={"width": 420, "height": 860})
    held = []
    routes(ctx, held=held)
    pg = ctx.new_page()
    pg.goto(BASE, wait_until="load")
    pg.wait_for_function("() => document.querySelectorAll('#spotList .spot[data-id]').length >= 4", timeout=15000)
    tap(pg, '#spotList .spot[data-id="101"]')
    pg.wait_for_timeout(100)
    tap(pg, '#spotList .spot[data-id="103"]')        # PAFF: no file, no link
    pg.wait_for_timeout(300)
    release(held)                                     # now the ONFF file lands
    pg.wait_for_timeout(1000)
    s = pg.evaluate(SHEET)
    ok(s["ref"] == "PAFF-0001" and s["links"] == 0, f"the PAFF sheet did not get ONFF-0037's link ({s['links']})")
    release(held)                                     # nothing left hanging when the context closes
    ctx.unroute_all(behavior="ignoreErrors")
    ctx.close()
    br.close()

# ---------------------------------------------------------------- [13]
# Everything in Spotline's files was typed in by someone: every field is shown
# as text, in the list, the agenda list and the sheet, never as page code.
EVIL = '<img src=x onerror="window.__pwned=(window.__pwned||0)+1">'
HOSTILE_SPOTS = [{"id": 901, "activator": "ON9XX" + EVIL, "reference": "ONFF-0037" + EVIL,
                  "reference_name": "Name" + EVIL, "frequency_khz": "14285" + EVIL, "mode": "SSB" + EVIL,
                  "remarks": "hi" + EVIL, "spotter": "ON1ZZ" + EVIL,
                  "latitude": 50.95, "longitude": 3.10, "spot_time": time.time() - 60}]
HOSTILE_AGENDA = [{"id": 902, "reference": "ONFF-0002" + EVIL, "activator_call": "ON8YY" + EVIL,
                   "band": "40m" + EVIL, "mode": "CW" + EVIL, "remarks": "x" + EVIL,
                   "utc_start": ts(-600) + EVIL, "utc_end": ts(3600)}]

with sync_playwright() as p:
    print("\n[13] text typed into Spotline stays text")
    br = p.chromium.launch()
    ctx = br.new_context(service_workers="block", viewport={"width": 420, "height": 860})
    routes(ctx)
    ctx.route(re.compile(r"https://spots\.wwff\.co/static/spots\.json"), lambda r: r.fulfill(
        status=200, content_type="application/json", body=json.dumps(HOSTILE_SPOTS)))
    ctx.route(re.compile(r"https://spots\.wwff\.co/static/agendas_active\.json"), lambda r: r.fulfill(
        status=200, content_type="application/json", body=json.dumps(HOSTILE_AGENDA)))
    ctx.route(re.compile(r"https://spots\.wwff\.co/static/agendas\.json"), lambda r: r.fulfill(
        status=200, content_type="application/json", body="[]"))
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE, wait_until="load")
    pg.evaluate("() => setSpotFilter && setSpotFilter('all')")
    pg.wait_for_function("() => document.querySelectorAll('#spotList .spot[data-id]').length >= 1", timeout=15000)
    pg.wait_for_timeout(800)
    INJECTED = "(sel) => document.querySelectorAll(sel + ' img, ' + sel + ' [onerror]').length"
    ok(pg.evaluate(INJECTED, "#spotList") == 0, "the live list: no element made of it")
    row = pg.evaluate("() => document.querySelector('#spotList .spot[data-id]').textContent")
    ok("ON9XX<img" in row and "SSB<img" in row and "ONFF-0037<img" in row,
       "it shows as the literal text that was sent")
    tap(pg, '#spotList .spot[data-id="901"]')
    pg.wait_for_function("() => document.getElementById('spotSheet').classList.contains('open')", timeout=5000)
    pg.wait_for_timeout(500)
    ok(pg.evaluate(INJECTED, "#spotSheet") == 0, "the spot sheet: no element made of it either")
    facts = pg.evaluate("() => document.getElementById('spFacts').textContent")
    ok("Name<img" in facts and "hi<img" in facts and "14285<img" in facts, "remark, name and frequency shown as text")
    pg.evaluate("() => document.getElementById('closeSpot').click()")
    pg.evaluate("() => document.querySelector('#spotTab .seg[data-tab=\"agenda\"]').click()")
    pg.wait_for_function("() => document.querySelector('#spotList .spot[data-ag]')", timeout=5000)
    pg.wait_for_timeout(300)
    ok(pg.evaluate(INJECTED, "#spotList") == 0, "the agenda list: no element made of it")
    ag = pg.evaluate("() => document.querySelector('#spotList .spot[data-ag]').textContent")
    ok("ON8YY<img" in ag and "40m<img" in ag and "CW<img" in ag, "call, band and mode as text")
    tap(pg, '#spotList .spot[data-ag="902"]')
    pg.wait_for_function("() => document.getElementById('spotSheet').classList.contains('open')", timeout=5000)
    pg.wait_for_timeout(500)
    ok(pg.evaluate(INJECTED, "#spotSheet") == 0, "the agenda sheet: nothing either")
    pg.wait_for_timeout(500)
    ok(pg.evaluate("() => window.__pwned") is None, "and nothing ran, anywhere")
    ok(not errs, f"no page errors ({errs[:2]})")
    ctx.close()
    br.close()

print("\n" + ("ALL OK" if not fails else f"{len(fails)} PROBLEMS: " + " | ".join(fails)))
sys.exit(1 if fails else 0)
