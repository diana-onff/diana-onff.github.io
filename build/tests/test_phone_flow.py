# On a phone: from the Spots list to the map and back, and the area panel.
#
#     python3 build/tests/test_phone_flow.py
#
# A phone-sized page with touch, and real taps and swipes on what is actually
# visible, not JavaScript clicks on elements that may sit behind something
# else. That difference is the point: an earlier test clicked the rows from
# JavaScript and checked the sheet's "open" class, and passed, while on a real
# phone the sheet opened BEHIND the Spots screen (the sheet belongs to the
# map, the Spots screen lies over the whole map) and nothing seemed to happen.
#
#   [1] a live spot in the list: tap -> the map, zoomed in on the spot, with
#       its sheet visible; x -> only the sheet closes, you stay on that map
#       (since 1.27.0, asked by a user); the phone's back button -> back in
#       the list, same tab, map back where it was
#   [2] an agenda entry: "<- Terug naar Agenda" returns to the Agenda tab;
#       swiping the sheet down is like x, and back still finds the list
#   [3a] stayed on the map on purpose: with no position known at all, Map in
#       the bottom bar has nothing to centre on and leaves it there
#   [3] Map in the bottom bar while such a spot is open, no position known:
#       the plain map, back where it was, not the spot's location; the same
#       via another screen
#   [4] the area panel on a small phone: scrolled down, a downward swipe
#       scrolls back up instead of dragging the panel; only at the top does it
#       close; a new area starts at the top again
#   [3b] a GPS fix arriving meanwhile does not pull the map away from the
#       spot; after closing, Map shows your position
#   [3c] padding an earlier panel left on the map does not hide the spot
#   [3d] on a small phone the spot is still visible above its sheet
#   [5] "More info" in the area panel, for an area with and without a boundary
#   [6] the phone's back button: from a spot or agenda entry back to the list
#       and tab it came from, never out of the app; closed any other way, no
#       back entry is left behind
#   [7] Map in the bottom bar always centres the map on you (1.28.0), on 390
#       and 360 px: after x and with the sheet still open, zoom unchanged, no
#       padding left; then Spots and back without a camera jump; without GPS
#       on the locator from Settings, and the message says so; a position
#       wider than 30 m or older than 2 minutes starts a new measurement, a
#       sharp and recent one does not;
#       with no position at all, the map goes back where it was
# Screenshots of [1], [2] and [5] go to $DIANA_SHOTS if that is set.
import json, os, re, sys, time
from playwright.sync_api import sync_playwright
import preconsent  # noqa: F401  answered welcome screen, see preconsent.py

BASE = "http://localhost:8011/web/?lang=nl"
SHOTS = os.environ.get("DIANA_SHOTS")
fails = []


def ok(c, m):
    print(("  ✓ " if c else "  ✗ ") + m)
    if not c:
        fails.append(m)


NOW = time.time()
ts = lambda off: time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(NOW + off))
SPOTS = [{"id": 501, "activator": "ON3VZ/P", "reference": "ONFF-0037", "reference_name": "Leiemeersen",
          "frequency_khz": 14285, "mode": "SSB", "latitude": 50.95, "longitude": 3.10, "spot_time": NOW - 120},
         {"id": 502, "activator": "DL1AB", "reference": "DLFF-0058", "reference_name": "Fichtelgebirge",
          "frequency_khz": 7144, "mode": "SSB", "latitude": 50.05, "longitude": 11.85, "spot_time": NOW - 300}]
AGENDA = [{"id": 71, "reference": "ONFF-0002", "activator_call": "ON4NO/P", "band": "40m", "mode": "CW",
           "utc_start": ts(-1800), "utc_end": ts(5400)}]
SITES = {"refs": {"ONFF-0037": "http://valleivandezuidleie.be/leiemeersen-noord/",
                  "ONFF-0002": "http://www.natuurenbos.be/kalmthoutseheide",
                  "ONFF-0004": "http://www.antarcticstation.org/"}}


def routes(ctx):
    ctx.route(re.compile(r"https://tiles\.openfreemap\.org/.*"), lambda r: r.fulfill(
        status=200, content_type="application/json",
        body=json.dumps({"version": 8, "sources": {}, "layers": [
            {"id": "bg", "type": "background", "paint": {"background-color": "#dfe9df"}}]})))
    ctx.route(re.compile(r"https://spots\.wwff\.co/static/spots\.json"), lambda r: r.fulfill(
        status=200, content_type="application/json", body=json.dumps(SPOTS)))
    ctx.route(re.compile(r"https://spots\.wwff\.co/static/agendas_active\.json"), lambda r: r.fulfill(
        status=200, content_type="application/json", body=json.dumps(AGENDA)))
    ctx.route(re.compile(r"https://spots\.wwff\.co/static/agendas\.json"), lambda r: r.fulfill(
        status=200, content_type="application/json", body="[]"))
    ctx.route(re.compile(r"https://docs\.google\.com/.*"), lambda r: r.abort())
    ctx.route(re.compile(r".*/data/sites/onff\.json$"), lambda r: r.fulfill(
        status=200, content_type="application/json", body=json.dumps(SITES)))
    ctx.route(re.compile(r".*/data/sites/(?!onff)[a-z0-9]+\.json$"), lambda r: r.fulfill(status=404, body=""))


VISIBLE = """(sel) => {
  const el = document.querySelector(sel); if (!el) return false;
  const r = el.getBoundingClientRect();
  if (r.width === 0 || r.height === 0) return false;
  const x = r.left + r.width / 2, y = r.top + Math.min(r.height / 2, 40);
  const top = document.elementFromPoint(x, y);
  return !!top && (top === el || el.contains(top));
}"""
STATE = """() => ({
  view: [...document.querySelectorAll('.view.on')].map(v => v.id),
  nav: (document.querySelector('#nav button.on') || {}).dataset?.view,
  tab: (document.querySelector('#spotTab .seg.on') || {}).dataset?.tab,
  sheet: document.getElementById('spotSheet').classList.contains('open'),
  call: document.getElementById('spCall').textContent,
  center: map.getCenter().toArray(), zoom: map.getZoom(),
})"""


def km(a, b):
    import math
    dlat = math.radians(b[1] - a[1]); dlon = math.radians(b[0] - a[0])
    x = math.sin(dlat / 2) ** 2 + math.cos(math.radians(a[1])) * math.cos(math.radians(b[1])) * math.sin(dlon / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(x))


def settle(pg):
    pg.wait_for_function("() => !map.isMoving() && !map.isEasing()", timeout=10000)
    pg.wait_for_timeout(300)


def swipe(pg, cdp, x, y0, y1, steps=8):
    """A real finger movement, through the browser's own touch input."""
    cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x, "y": y0}]})
    for i in range(1, steps + 1):
        cdp.send("Input.dispatchTouchEvent",
                 {"type": "touchMove", "touchPoints": [{"x": x, "y": y0 + (y1 - y0) * i / steps}]})
        time.sleep(0.02)
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    pg.wait_for_timeout(500)


def shot(pg, name):
    if SHOTS:
        pg.screenshot(path=os.path.join(SHOTS, name))


with sync_playwright() as p:
    br = p.chromium.launch()
    ctx = br.new_context(service_workers="block", viewport={"width": 390, "height": 844},
                         device_scale_factor=2, is_mobile=True, has_touch=True)
    routes(ctx)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    cdp = ctx.new_cdp_session(pg)
    pg.goto(BASE, wait_until="load")
    pg.wait_for_function("() => zones && zones.features && zones.features.length > 0", timeout=20000)
    pg.wait_for_function("() => !document.querySelector('.splash') || getComputedStyle(document.querySelector('.splash')).display === 'none' || document.querySelector('.splash').classList.contains('gone') || document.querySelector('.splash').hidden", timeout=15000)
    pg.wait_for_timeout(2500)
    settle(pg)
    home = pg.evaluate(STATE)

    print("\n[1] a live spot: list -> map with its sheet -> back")
    pg.tap('#nav button[data-view="viewSpots"]')
    pg.wait_for_function("() => document.querySelectorAll('#spotList .spot[data-id]').length >= 2", timeout=15000)
    pg.tap('#spotList .spot[data-id="501"]')
    pg.wait_for_function("() => document.getElementById('spotSheet').classList.contains('open')", timeout=5000)
    settle(pg)
    s = pg.evaluate(STATE)
    ok(s["view"] == [] and s["nav"] == "map", f"the map is showing, Map lit in the bar ({s['view']}, {s['nav']})")
    ok(pg.evaluate(VISIBLE, "#spotSheet") and pg.evaluate(VISIBLE, "#spCall"),
       "the sheet is really visible, on top, not behind anything")
    ok(s["call"] == "ON3VZ/P", f"for the spot that was tapped ({s['call']})")
    ok(km(s["center"], [3.10, 50.95]) < 40 and abs(s["zoom"] - 11) < 0.01,
       f"the map zoomed in near the spot (zoom {s['zoom']:.1f}, {km(s['center'], [3.10, 50.95]):.0f} km)")
    spot_px = pg.evaluate("() => map.project([3.10, 50.95]).y")
    sheet_top = pg.evaluate("() => document.getElementById('spotSheet').getBoundingClientRect().top")
    ok(spot_px < sheet_top, f"with the spot above the sheet, not behind it ({spot_px:.0f} < {sheet_top:.0f} px)")
    shot(pg, "1-spot-from-list.png")
    lbl = pg.evaluate("() => document.getElementById('spBack').textContent")
    ok(pg.evaluate(VISIBLE, "#spBack") and lbl == "← Terug naar Spots", f"with a visible '← Terug naar Spots' ({lbl!r})")
    pg.tap("#closeSpot")
    pg.wait_for_timeout(400)
    s = pg.evaluate(STATE)
    ok(s["view"] == [] and not s["sheet"] and km(s["center"], [3.10, 50.95]) < 40 and abs(s["zoom"] - 11) < 0.01,
       f"x closes only the info window: you stay on the zoomed-in map at the spot ({s['view']}, zoom {s['zoom']:.1f})")
    ok(pg.evaluate("() => history.state && history.state.diana") == "back", "(the way back to the list is kept)")
    pg.go_back()
    pg.wait_for_timeout(500)
    s = pg.evaluate(STATE)
    ok(s["view"] == ["viewSpots"] and s["nav"] == "viewSpots" and not s["sheet"],
       f"then the phone's back button brings you back to the Spots screen ({s['view']}, {s['nav']})")
    ok(s["tab"] == "spots", f"on the same tab ({s['tab']})")
    ok(km(s["center"], home["center"]) < 0.5 and abs(s["zoom"] - home["zoom"]) < 0.05,
       f"and the map is back where it was ({km(s['center'], home['center']):.2f} km, zoom {s['zoom']:.1f})")

    print("\n[2] an agenda entry, closed by swiping")
    pg.tap('#spotTab .seg[data-tab="agenda"]')
    pg.wait_for_function("() => document.querySelector('#spotList .spot[data-ag]')", timeout=5000)
    pg.tap('#spotList .spot[data-ag="71"]')
    pg.wait_for_function("() => document.getElementById('spotSheet').classList.contains('open')", timeout=5000)
    settle(pg)
    ok(pg.evaluate(VISIBLE, "#spotSheet") and pg.evaluate(STATE)["call"] == "ON4NO/P",
       "the agenda entry's sheet is visible on the map")
    pg.wait_for_function("() => document.querySelector('#spotSheet .fact.site a')", timeout=5000)
    shot(pg, "2-agenda-from-list.png")
    ok(pg.evaluate("() => document.getElementById('spBack').textContent") == "← Terug naar Agenda",
       "the button names the list you came from: Agenda")
    pg.tap("#spBack")
    pg.wait_for_timeout(400)
    s = pg.evaluate(STATE)
    ok(s["view"] == ["viewSpots"] and not s["sheet"] and s["tab"] == "agenda",
       f"the button brings you back to the Agenda tab ({s['view']}, {s['tab']})")
    ok(km(s["center"], home["center"]) < 0.5, "map back where it was")
    ok(pg.evaluate("() => history.state") is None, "(and takes the back entry with it)")
    pg.tap('#spotList .spot[data-ag="71"]')
    pg.wait_for_function("() => document.getElementById('spotSheet').classList.contains('open')", timeout=5000)
    settle(pg)
    top = pg.evaluate("() => document.getElementById('spotSheet').getBoundingClientRect().top")
    swipe(pg, cdp, 195, top + 12, top + 330)
    s = pg.evaluate(STATE)
    ok(s["view"] == [] and not s["sheet"], f"swiping it down: like x, you stay on the map ({s['view']})")
    pg.go_back()
    pg.wait_for_timeout(500)
    s = pg.evaluate(STATE)
    ok(s["view"] == ["viewSpots"] and s["tab"] == "agenda", f"and back returns to the Agenda tab ({s['tab']})")

    print("\n[3] leaving through the bottom bar instead")
    pg.tap('#spotTab .seg[data-tab="spots"]')
    pg.tap('#spotList .spot[data-id="502"]')
    pg.wait_for_function("() => document.getElementById('spotSheet').classList.contains('open')", timeout=5000)
    settle(pg)
    pg.tap('#nav button[data-view="map"]')
    pg.wait_for_timeout(400)
    s = pg.evaluate(STATE)
    ok(s["view"] == [] and not s["sheet"], "Map: the plain map, sheet closed")
    ok(km(s["center"], home["center"]) < 0.5, f"where it was before, not at the spot ({km(s['center'], home['center']):.1f} km)")
    pg.tap('#nav button[data-view="viewSpots"]')
    pg.tap('#spotList .spot[data-id="502"]')
    pg.wait_for_function("() => document.getElementById('spotSheet').classList.contains('open')", timeout=5000)
    settle(pg)
    pg.tap('#nav button[data-view="viewSet"]')
    pg.wait_for_timeout(300)
    pg.tap('#nav button[data-view="map"]')
    pg.wait_for_timeout(400)
    s = pg.evaluate(STATE)
    ok(km(s["center"], home["center"]) < 0.5 and not s["sheet"], "via another screen and back to Map: the same")

    print("\n[3a] stayed on the map on purpose, then Map in the bottom bar")
    pg.tap('#nav button[data-view="viewSpots"]')
    pg.tap('#spotList .spot[data-id="502"]')
    pg.wait_for_function("() => document.getElementById('spotSheet').classList.contains('open')", timeout=5000)
    settle(pg)
    pg.tap("#closeSpot")
    pg.wait_for_timeout(300)
    pg.tap('#nav button[data-view="map"]')
    pg.wait_for_timeout(400)
    s = pg.evaluate(STATE)
    ok(km(s["center"], [11.85, 50.05]) < 40 and s["view"] == [], "no position known: the map stays where you chose to stay")
    ok(pg.evaluate("() => history.state") is None, "and back is no longer tied to the list")
    # Stayed, then the locate button: the map goes to your position, like anywhere else.
    pg.tap('#nav button[data-view="viewSpots"]')
    pg.tap('#spotList .spot[data-id="502"]')
    pg.wait_for_function("() => document.getElementById('spotSheet').classList.contains('open')", timeout=5000)
    settle(pg)
    pg.tap("#closeSpot")
    pg.wait_for_timeout(300)
    pg.evaluate("() => fixApply({coords: {latitude: 51.10, longitude: 4.30, accuracy: 8}, timestamp: Date.now()}, true)")
    pg.wait_for_timeout(900)
    s = pg.evaluate(STATE)
    ok(km(s["center"], [4.30, 51.10]) < 1, f"stayed, a GPS fix you asked for moves the map ({km(s['center'], [4.30, 51.10]):.1f} km)")
    # Stayed, then a spot icon on the map: a spot from the map, no way back to the list.
    pg.evaluate("() => openSpotFromMap(501)")       # what tapping the icon calls
    pg.wait_for_timeout(500)
    ok(pg.evaluate("() => document.getElementById('spotSheet').classList.contains('open')")
       and pg.evaluate("() => document.getElementById('spBack').hidden")
       and not pg.evaluate("() => document.body.classList.contains('spot-view')")
       and pg.evaluate("() => history.state") is None,
       "stayed, then a spot icon on the map: a sheet from the map, without a way back to the list")
    pg.tap("#closeSpot")
    pg.tap('#nav button[data-view="map"]')
    pg.wait_for_timeout(300)
    pg.evaluate("() => map.jumpTo({center: [%f, %f], zoom: %f})" % (home["center"][0], home["center"][1], home["zoom"]))

    print("\n[3b] a GPS position arriving while a spot from the list is showing")
    pg.tap('#nav button[data-view="viewSpots"]')
    pg.tap('#spotList .spot[data-id="501"]')
    pg.wait_for_function("() => document.getElementById('spotSheet').classList.contains('open')", timeout=5000)
    settle(pg)
    pg.evaluate("() => fixApply({coords: {latitude: 51.20, longitude: 4.40, accuracy: 8}, timestamp: Date.now()}, true)")
    pg.wait_for_timeout(800)
    s = pg.evaluate(STATE)
    ok(km(s["center"], [3.10, 50.95]) < 40 and s["sheet"], "the map stays on the spot, the sheet open")
    pg.tap("#spBack")
    pg.wait_for_timeout(500)
    s = pg.evaluate(STATE)
    ok(s["view"] == ["viewSpots"], "back to the list as usual")
    ok(km(s["center"], [4.40, 51.20]) < 1 and s["zoom"] >= 12,
       f"and Map then shows your own position ({km(s['center'], [4.40, 51.20]):.1f} km, zoom {s['zoom']:.1f})")
    here_cam = s

    print("\n[3c] padding left on the map by an earlier panel does not push the spot away")
    pg.tap('#nav button[data-view="map"]')
    pg.evaluate("() => select('ONFF-0004')")          # an area without a boundary: pads the map
    pg.wait_for_timeout(800)
    pg.evaluate("() => closeSheet()")
    pad_before = pg.evaluate("() => map.getPadding()")
    pg.tap('#nav button[data-view="viewSpots"]')
    pg.tap('#spotList .spot[data-id="501"]')
    pg.wait_for_function("() => document.getElementById('spotSheet').classList.contains('open')", timeout=5000)
    settle(pg)
    y = pg.evaluate("() => map.project([3.10, 50.95]).y")
    top_ = pg.evaluate("() => document.getElementById('spotSheet').getBoundingClientRect().top")
    cnt = pg.evaluate("() => document.getElementById('counts').getBoundingClientRect().bottom")
    ok(cnt < y < top_, f"the spot between the top bar and the sheet ({cnt:.0f} < {y:.0f} < {top_:.0f} px)")
    pg.tap("#spBack")
    pg.wait_for_timeout(500)
    ok(pg.evaluate("() => map.getPadding()") == pad_before, "and back in the list the map's padding is what it was")

    print("\n[3d] a small phone")
    pg.set_viewport_size({"width": 360, "height": 640})
    pg.wait_for_timeout(500)
    pg.tap('#spotList .spot[data-id="501"]')
    pg.wait_for_function("() => document.getElementById('spotSheet').classList.contains('open')", timeout=5000)
    settle(pg)
    y = pg.evaluate("() => map.project([3.10, 50.95]).y")
    top_ = pg.evaluate("() => document.getElementById('spotSheet').getBoundingClientRect().top")
    cnt = pg.evaluate("() => document.getElementById('counts').getBoundingClientRect().bottom")
    ok(cnt < y < top_, f"the spot is visible above its sheet ({cnt:.0f} < {y:.0f} < {top_:.0f} px)")
    hit = pg.evaluate("([x, y]) => { const e = document.elementFromPoint(x, y); return e ? (e.closest('.status,.sheet,.topbar,.counts') ? 'covered' : 'map') : null; }",
                      [pg.evaluate("() => map.project([3.10, 50.95]).x"), y])
    ok(hit == "map", f"and nothing lies on top of it, not even the GPS message ({hit})")
    shot(pg, "1b-spot-small-phone.png")
    # What does not fit on the small screen scrolls, and swiping never strands you.
    sp = pg.evaluate("() => { const s = document.getElementById('spotSheet'); const r = s.getBoundingClientRect(); return {h: s.scrollHeight, c: s.clientHeight, top: r.top, bottom: r.bottom}; }")
    ok(sp["h"] > sp["c"], f"(the spot sheet is taller than its room here: {sp['h']} > {sp['c']} px)")
    mid = (sp["top"] + sp["bottom"]) / 2
    swipe(pg, cdp, 180, mid + 80, mid - 120)
    down = pg.evaluate("() => document.getElementById('spotSheet').scrollTop")
    ok(down > 30, f"a swipe up scrolls the rest into view ({down} px)")
    for _ in range(4):
        swipe(pg, cdp, 180, mid - 80, mid + 100)
        if pg.evaluate("() => document.getElementById('spotSheet').scrollTop") == 0:
            break
    ok(pg.evaluate("() => document.getElementById('spotSheet').scrollTop") == 0
       and pg.evaluate("() => document.getElementById('spotSheet').classList.contains('open')"),
       "a swipe down scrolls back to the top, the sheet stays open")
    top_ = pg.evaluate("() => document.getElementById('spotSheet').getBoundingClientRect().top")
    swipe(pg, cdp, 180, top_ + 12, top_ + 300)
    s = pg.evaluate(STATE)
    ok(not s["sheet"] and s["view"] == [], "at the top, a swipe down closes it, and you stay on the map")
    pg.set_viewport_size({"width": 390, "height": 844})
    pg.wait_for_timeout(300)

    print("\n[4] the area panel on a small phone")
    pg.tap('#nav button[data-view="map"]')
    pg.set_viewport_size({"width": 360, "height": 640})
    pg.wait_for_timeout(400)
    pg.evaluate("() => select('ONFF-0037')")
    pg.wait_for_timeout(700)
    sh = "#sheet"
    info = pg.evaluate("() => { const s = document.getElementById('sheet'); return {h: s.scrollHeight, c: s.clientHeight}; }")
    ok(info["h"] > info["c"] + 50, f"(the panel is taller than the room it gets: {info['h']} > {info['c']} px)")
    box = pg.evaluate("() => { const r = document.getElementById('sheet').getBoundingClientRect(); return {top: r.top, bottom: r.bottom}; }")
    mid = (box["top"] + box["bottom"]) / 2
    swipe(pg, cdp, 180, mid + 120, mid - 150)          # finger up: scroll down
    down = pg.evaluate("() => document.getElementById('sheet').scrollTop")
    ok(down > 50, f"a swipe up scrolls the panel down ({down} px)")
    swipe(pg, cdp, 180, mid - 100, mid + 120)          # finger down: scroll back up
    s_after = pg.evaluate("() => ({top: document.getElementById('sheet').scrollTop, open: document.getElementById('sheet').classList.contains('open')})")
    ok(s_after["open"] and s_after["top"] < down, f"a swipe down scrolls back up, the panel stays open ({down} -> {s_after['top']} px)")
    for _ in range(4):
        if pg.evaluate("() => document.getElementById('sheet').scrollTop") == 0:
            break
        swipe(pg, cdp, 180, mid - 100, mid + 120)
    ok(pg.evaluate("() => document.getElementById('sheet').scrollTop") == 0 and pg.evaluate(VISIBLE, "#zoneName"),
       "all the way back to the top, the area's name visible again")
    pg.evaluate("() => { document.getElementById('sheet').scrollTop = 200; }")
    pg.evaluate("() => select('ONFF-0002')")
    pg.wait_for_timeout(500)
    ok(pg.evaluate("() => document.getElementById('sheet').scrollTop") == 0, "a new area starts at the top")
    top = pg.evaluate("() => document.getElementById('sheet').getBoundingClientRect().top")
    swipe(pg, cdp, 180, top + 12, top + 320)
    ok(not pg.evaluate("() => document.getElementById('sheet').classList.contains('open')"),
       "at the top, a swipe down still closes it")

    print("\n[5] 'Meer info' in the area panel")
    pg.set_viewport_size({"width": 390, "height": 844})
    pg.evaluate("() => select('ONFF-0037')")
    pg.wait_for_function("() => document.querySelector('#facts .fact.site a')", timeout=5000)
    a = pg.evaluate("() => { const a = document.querySelector('#facts .fact.site a'); return {href: a.getAttribute('href'), t: a.getAttribute('target'), rel: a.getAttribute('rel'), label: a.closest('.fact').querySelector('.k').textContent, hint: a.closest('.fact').querySelector('.s').textContent}; }")
    ok(a["href"] == SITES["refs"]["ONFF-0037"] and a["t"] == "_blank" and "noopener" in a["rel"],
       f"an area with a boundary: the link, opening in its own page ({a['href']})")
    ok(a["label"] == "Meer info" and a["hint"] == "opent in je browser", f"({a['label']!r}, {a['hint']!r})")
    pg.evaluate("() => { const s = document.getElementById('sheet'); s.scrollTop = s.scrollHeight; }")
    pg.wait_for_timeout(300)
    shot(pg, "3-area-panel-link.png")
    pg.evaluate("() => select('ONFF-0004')")
    pg.wait_for_function("() => document.querySelector('#facts .fact.site a')", timeout=5000)
    ok(pg.evaluate("() => document.querySelector('#facts .fact.site a').getAttribute('href')") == SITES["refs"]["ONFF-0004"],
       "an area without a boundary: its link too")
    ok(pg.evaluate("() => document.querySelectorAll('#facts .fact.site').length") == 1, "once")
    print("\n[6] the phone's back button")
    pg.evaluate("() => closeSheet()")
    pg.tap('#nav button[data-view="viewSpots"]')
    pg.tap('#spotTab .seg[data-tab="spots"]')
    pg.wait_for_function("() => document.querySelectorAll('#spotList .spot[data-id]').length >= 2", timeout=5000)
    cam0 = pg.evaluate(STATE)
    pg.tap('#spotList .spot[data-id="501"]')
    pg.wait_for_function("() => document.getElementById('spotSheet').classList.contains('open')", timeout=5000)
    settle(pg)
    pg.go_back()
    pg.wait_for_timeout(500)
    s = pg.evaluate(STATE)
    ok(s["view"] == ["viewSpots"] and not s["sheet"] and s["tab"] == "spots",
       f"back from a spot: the list you came from ({s['view']}, {s['tab']})")
    ok(km(s["center"], cam0["center"]) < 0.5, "the map back where it was")
    ok(pg.url.startswith("http://localhost:8011/web/"), f"still inside Diana ({pg.url})")
    ok(pg.evaluate("() => history.state") is None, "and no back entry left behind")
    pg.tap('#spotTab .seg[data-tab="agenda"]')
    pg.wait_for_function("() => document.querySelector('#spotList .spot[data-ag]')", timeout=5000)
    pg.tap('#spotList .spot[data-ag="71"]')
    pg.wait_for_function("() => document.getElementById('spotSheet').classList.contains('open')", timeout=5000)
    settle(pg)
    pg.go_back()
    pg.wait_for_timeout(500)
    s = pg.evaluate(STATE)
    ok(s["view"] == ["viewSpots"] and s["tab"] == "agenda" and not s["sheet"], "from an agenda entry: the Agenda tab")
    # Back to the list with the button, then straight away the next spot: the
    # back entry of the first is removed (asynchronously) while the second one
    # needs its own.
    pg.tap('#spotTab .seg[data-tab="spots"]')
    pg.tap('#spotList .spot[data-id="501"]')
    pg.wait_for_function("() => document.getElementById('spotSheet').classList.contains('open')", timeout=5000)
    pg.tap("#spBack")
    pg.tap('#spotList .spot[data-id="502"]')
    pg.wait_for_function("() => document.getElementById('spotSheet').classList.contains('open')", timeout=5000)
    pg.wait_for_timeout(600)
    ok(pg.evaluate("() => history.state && history.state.diana") == "back", "(a quick second spot still gets its back entry)")
    pg.go_back()
    pg.wait_for_timeout(500)
    s = pg.evaluate(STATE)
    ok(s["view"] == ["viewSpots"] and not s["sheet"], "and back closes that one too, into the list")
    ok(pg.evaluate("() => history.state") is None, "(nothing left over)")
    # Left through the bottom bar: back is no longer tied to the spot.
    pg.tap('#spotList .spot[data-id="501"]')
    pg.wait_for_function("() => document.getElementById('spotSheet').classList.contains('open')", timeout=5000)
    pg.tap('#nav button[data-view="viewNearby"]')
    pg.wait_for_timeout(600)
    ok(pg.evaluate("() => history.state") is None and not pg.evaluate(STATE)["sheet"],
       "left through the bottom bar: the back entry is gone with the spot")

    ok(not errs, f"no page errors ({errs[:2]})")
    ctx.close()

    # ------------------------------------------------------------------
    # [7] Map in the bottom bar always centres the map on you (1.28.0).
    #     With GPS: on that position. Without GPS: on the middle of the
    #     locator square from Settings, and the message says so. The zoom
    #     stays as it was; only the middle moves. A position less sharp than
    #     30 m starts a new measurement. Both on 390 and on 360 px.
    # ------------------------------------------------------------------
    ME = [4.05, 51.05]                 # where the phone "is"

    def new_page(**kw):
        c = br.new_context(service_workers="block", viewport={"width": 390, "height": 844},
                           device_scale_factor=2, is_mobile=True, has_touch=True, **kw)
        routes(c)
        g = c.new_page()
        g.on("pageerror", lambda e: errs.append(str(e)))
        g.goto(BASE, wait_until="load")
        g.wait_for_function("() => zones && zones.features && zones.features.length > 0", timeout=20000)
        g.wait_for_timeout(2500)
        settle(g)
        return c, g

    def from_list(g, sid):
        g.tap('#nav button[data-view="viewSpots"]')
        g.tap('#spotTab .seg[data-tab="spots"]')
        g.wait_for_function("() => document.querySelectorAll('#spotList .spot[data-id]').length >= 2", timeout=15000)
        g.tap('#spotList .spot[data-id="%d"]' % sid)
        g.wait_for_function("() => document.getElementById('spotSheet').classList.contains('open')", timeout=5000)
        settle(g)

    def zoom_to(g, z):
        # What a pinch would do: a different zoom than the spot's, to prove
        # that Map keeps whatever zoom you have.
        g.evaluate("(z) => map.jumpTo({zoom: z})", z)
        g.wait_for_timeout(200)

    def tap_map(g):
        g.tap('#nav button[data-view="map"]')
        g.wait_for_timeout(250)
        settle(g)

    def on_me(g, where, z, label):
        s = g.evaluate(STATE)
        px = g.evaluate("(p) => { const q = map.project(p), c = map.getContainer(); return [q.x - c.clientWidth / 2, q.y - c.clientHeight / 2]; }", where)
        pad = g.evaluate("() => map.getPadding()")
        ok(s["view"] == [] and s["nav"] == "map" and not s["sheet"], f"{label}: the plain map, sheet closed ({s['view']}, sheet {s['sheet']})")
        ok(km(s["center"], where) < 0.05 and abs(px[0]) < 2 and abs(px[1]) < 2,
           f"{label}: centred on you ({km(s['center'], where):.2f} km, {px[0]:.0f}/{px[1]:.0f} px off the middle)")
        ok(abs(s["zoom"] - z) < 0.01, f"{label}: zoom unchanged ({s['zoom']:.2f}, was {z:.2f})")
        ok(all(abs(pad[k]) < 0.5 for k in ("top", "bottom", "left", "right")), f"{label}: no padding left over ({pad})")

    def with_gps(g, cam_ok, w):
        print(f"\n[7] Map centres on you, with GPS ({w} px)")
        # Spot from the list, x (stayed on the map), another zoom, then Map.
        from_list(g, 502)
        g.tap("#closeSpot")
        g.wait_for_timeout(300)
        zoom_to(g, 8.5)
        tap_map(g)
        on_me(g, ME, 8.5, "after x")
        ok(g.evaluate("() => history.state") is None, "after x: back is no longer tied to the list")
        # Spot from the list, sheet still open, then Map.
        from_list(g, 502)
        zoom_to(g, 9.25)
        tap_map(g)
        on_me(g, ME, 9.25, "sheet still open")
        g.wait_for_timeout(1200)
        s = g.evaluate(STATE)
        ok(km(s["center"], ME) < 0.05, "and nothing pulls it away afterwards (no old camera coming back)")
        # Then Spots and back again, with the button and with the phone's back button.
        cam = g.evaluate(STATE)
        from_list(g, 501)
        g.tap("#spBack")
        g.wait_for_timeout(500)
        s = g.evaluate(STATE)
        ok(s["view"] == ["viewSpots"] and km(s["center"], cam["center"]) < 0.05 and abs(s["zoom"] - cam["zoom"]) < 0.01,
           f"then Spots, a spot, '← Terug': the map as Map left it ({km(s['center'], cam['center']):.2f} km, zoom {s['zoom']:.2f})")
        g.tap('#spotList .spot[data-id="502"]')
        g.wait_for_function("() => document.getElementById('spotSheet').classList.contains('open')", timeout=5000)
        settle(g)
        g.go_back()
        g.wait_for_timeout(600)
        s = g.evaluate(STATE)
        ok(s["view"] == ["viewSpots"] and km(s["center"], cam["center"]) < 0.05 and abs(s["zoom"] - cam["zoom"]) < 0.01,
           f"and with the phone's back button: the same, no camera jump ({km(s['center'], cam['center']):.2f} km)")
        cam_ok.append(True)

    def watch_closed(g):
        # Polled with evaluate: the running watch ends on a timer (FIX_WAIT_MS).
        for _ in range(100):
            if g.evaluate("() => fixRun === null"):
                return True
            g.wait_for_timeout(250)
        return False

    def gps_margin(g, c):
        print("\n[7] the 30 m rule: a wide position asks for a new one, a sharp one does not")
        ok(watch_closed(g), "(the startup measurement has finished)")
        # Every status message, in order: the emulated GPS answers so quickly
        # that "searching" is gone again before anyone could read it.
        g.evaluate("() => { window.__said = []; const show = showStatus; window.showStatus = (k, a, b, top) => { __said.push(a); show(k, a, b, top); }; }")
        P1, P2, P3 = [4.20, 51.15], [4.25, 51.18], [4.60, 51.30]
        # A position with a 80 m margin, then the phone finds a sharp one elsewhere.
        g.evaluate("(p) => fixApply({coords: {latitude: p[1], longitude: p[0], accuracy: 80}, timestamp: Date.now()}, true)", P1)
        g.wait_for_timeout(300)
        c.set_geolocation({"latitude": P2[1], "longitude": P2[0], "accuracy": 3})
        g.evaluate("() => { map.jumpTo({center: [5.5, 50.6], zoom: 9}); __said.length = 0; }")
        g.tap('#nav button[data-view="map"]')
        g.wait_for_timeout(150)
        said = g.evaluate("() => __said")
        ok(said[:1] == ["Locatie zoeken…"], f"wider than 30 m: Map starts a new measurement, and says so ({said})")
        moved = False
        for _ in range(40):
            g.wait_for_timeout(250)
            if km(g.evaluate("() => map.getCenter().toArray()"), P2) < 0.05 and not g.evaluate("() => map.isMoving() || map.isEasing()"):
                moved = True
                break
        z = g.evaluate("() => map.getZoom()")
        ok(moved, "and the map follows to the new, sharper position")
        ok(abs(z - 9) < 0.01, f"still at the zoom you had ({z:.2f})")
        ok(watch_closed(g), "(that measurement has finished)")
        # Now sharp (3 m): Map only centres, no new measurement.
        c.set_geolocation({"latitude": P3[1], "longitude": P3[0], "accuracy": 3})
        g.evaluate("() => map.jumpTo({center: [5.5, 50.6], zoom: 9})")
        g.evaluate("() => { hideStatus(); __said.length = 0; }")
        tap_map(g)
        g.wait_for_timeout(1500)
        s = g.evaluate(STATE)
        said = g.evaluate("() => __said")
        ok(km(s["center"], P2) < 0.05 and g.evaluate("() => fixRun") is None and said == [],
           f"30 m or better: no new measurement, the map on the position in hand ({km(s['center'], P2):.2f} km, {said})")
        # Just as sharp, but older than 2 minutes: you may have moved, so Map measures again.
        g.evaluate("() => { lastFix.at -= 3 * 60 * 1000; fixLog = []; map.jumpTo({center: [5.5, 50.6], zoom: 9}); hideStatus(); __said.length = 0; }")
        g.tap('#nav button[data-view="map"]')
        g.wait_for_timeout(150)
        said = g.evaluate("() => __said")
        moved = measured_to(g, P3)
        z = g.evaluate("() => map.getZoom()")
        ok(said[:1] == ["Locatie zoeken…"] and moved and abs(z - 9) < 0.01,
           f"sharp but older than 2 minutes: a new measurement, the map follows, zoom kept ({said[:2]}, zoom {z:.2f})")
        ok(watch_closed(g), "(that measurement has finished)")

    def measured_to(g, where):
        # Polls until the map has come to rest on `where` (a measurement the
        # Map button started has answered), or gives up after ten seconds.
        for _ in range(40):
            g.wait_for_timeout(250)
            if km(g.evaluate("() => map.getCenter().toArray()"), where) < 0.05 and not g.evaluate("() => map.isMoving() || map.isEasing()"):
                return True
        return False

    def fresh(g, c, where, acc, start, z):
        # The phone's next answer, a clean slate of readings (earlier test
        # positions would otherwise be weighed together with it), the map
        # somewhere else at zoom z, no message showing.
        watch_closed(g)
        c.set_geolocation({"latitude": where[1], "longitude": where[0], "accuracy": acc})
        g.evaluate("([s, z]) => { fixLog = []; map.jumpTo({center: s, zoom: z}); hideStatus(); __said.length = 0; }", [start, z])

    def gps_more(g, c):
        print("\n[7] inside an area, programmatic clicks, no GPS yet, a recording, and ◎")
        # A position inside an area: the measurement that Map starts says so,
        # but opens no area panel and keeps your zoom.
        IN = g.evaluate("""() => {
          for (const z of index) {
            if (!z.bbox) continue;
            const f = zones.features.find(x => x.properties.ref === z.ref);
            if (!f || !f.geometry) continue;
            for (let i = 1; i < 6; i++) for (let j = 1; j < 6; j++) {
              const lon = z.bbox[0] + (z.bbox[2] - z.bbox[0]) * i / 6, lat = z.bbox[1] + (z.bbox[3] - z.bbox[1]) * j / 6;
              if (pointInGeom(lon, lat, f.geometry)) return [lon, lat, z.ref];
            }
          }
          return null; }""")
        ok(IN is not None, f"(a point inside {IN and IN[2]})")
        g.evaluate("(p) => fixApply({coords: {latitude: p[1] + 0.05, longitude: p[0] + 0.05, accuracy: 80}, timestamp: Date.now()}, true)", IN)
        g.evaluate("() => closeSheet()")
        fresh(g, c, IN[:2], 3, [5.9, 50.3], 9)
        g.tap('#nav button[data-view="map"]')
        arrived = measured_to(g, IN[:2])
        g.wait_for_timeout(600)
        z = g.evaluate("() => map.getZoom()")
        said = g.evaluate("() => __said")
        area = g.evaluate("() => document.getElementById('sheet').classList.contains('open')")
        ok(arrived and abs(z - 9) < 0.01 and not area,
           f"inside an area: on you at your zoom, no area panel taking over (zoom {z:.2f}, panel {area})")
        ok(any(x.startswith("Je staat in") for x in said), f"and the message still says where you are ({said})")
        watch_closed(g)

        # The code opening the map (a list row, a Nearby reference) is not your tap on Map.
        g.evaluate("() => { map.jumpTo({center: [5.9, 50.3], zoom: 9}); __said.length = 0; }")
        g.evaluate("() => document.querySelector('#nav button[data-view=\"map\"]').click()")
        g.wait_for_timeout(800)
        s = g.evaluate(STATE)
        ok(km(s["center"], [5.9, 50.3]) < 0.05 and g.evaluate("() => fixRun") is None and g.evaluate("() => __said") == [],
           "a programmatic click on Map does not centre, measure or say anything")

        # No GPS position yet, permission given: the locator first, then quietly the real position.
        Q = [4.45, 51.22]
        g.evaluate("() => { here = null; ringFix = null; cfg.grid = 'JO20SX'; }")
        fresh(g, c, Q, 3, [5.9, 50.3], 9)
        g.tap('#nav button[data-view="map"]')
        g.wait_for_timeout(150)
        said = g.evaluate("() => __said")
        ok(said[:1] == ["Kaart op je locator JO20SX"] and "Locatie zoeken…" not in said,
           f"no GPS yet: the locator, said so, and the measurement starts quietly ({said})")
        arrived = measured_to(g, Q)
        z = g.evaluate("() => map.getZoom()")
        ok(arrived and abs(z - 9) < 0.01, f"then the map follows to the real position, at your zoom ({z:.2f})")
        g.evaluate("() => { cfg.grid = ''; }")
        watch_closed(g)

        # A recording keeps the position current itself: Map only centres.
        g.evaluate("() => fixApply({coords: {latitude: 51.0, longitude: 4.1, accuracy: 80}, timestamp: Date.now()}, true)")
        g.evaluate("() => { closeSheet(); sess.on = true; }")
        fresh(g, c, [4.7, 51.3], 3, [5.9, 50.3], 9)
        tap_map(g)
        g.wait_for_timeout(1200)
        s = g.evaluate(STATE)
        ok(km(s["center"], [4.1, 51.0]) < 0.05 and g.evaluate("() => fixRun") is None and g.evaluate("() => __said") == [],
           "during a recording: Map centres, no extra measurement")
        g.evaluate("() => { sess.on = false; }")

        # The ◎ button is unchanged: it still zooms in to at least 12.
        fresh(g, c, [4.7, 51.3], 3, [5.9, 50.3], 9)
        if g.evaluate(VISIBLE, "#accHint"):
            g.tap("#accHintClose")        # the 80 m positions above raised the accuracy tip
        g.tap('button[title="Waar sta ik?"]')
        arrived = measured_to(g, [4.7, 51.3])
        z = g.evaluate("() => map.getZoom()")
        ok(arrived and z >= 12 - 0.01, f"◎ still zooms in as before (zoom {z:.2f})")
        watch_closed(g)

    gps_ctx, g = new_page(permissions=["geolocation"],
                          geolocation={"latitude": ME[1], "longitude": ME[0], "accuracy": 10})
    ok(g.evaluate("() => !!here") and km(g.evaluate("() => [here.lon, here.lat]"), ME) < 0.05, "(the phone has a GPS position)")
    done = []
    with_gps(g, done, 390)
    g.set_viewport_size({"width": 360, "height": 640})
    g.wait_for_timeout(400)
    with_gps(g, done, 360)
    g.set_viewport_size({"width": 390, "height": 844})
    gps_margin(g, gps_ctx)
    gps_more(g, gps_ctx)
    gps_ctx.close()

    # Without GPS (no permission), with a locator in Settings.
    loc_ctx = br.new_context(service_workers="block", viewport={"width": 390, "height": 844},
                             device_scale_factor=2, is_mobile=True, has_touch=True)
    loc_ctx.add_init_script("try { localStorage.setItem('diana.grid', 'JO20SX'); } catch (e) {}")
    routes(loc_ctx)
    g = loc_ctx.new_page()
    g.on("pageerror", lambda e: errs.append(str(e)))
    g.goto(BASE, wait_until="load")
    g.wait_for_function("() => zones && zones.features && zones.features.length > 0", timeout=20000)
    g.wait_for_timeout(2500)
    settle(g)
    LOC = g.evaluate("() => gridToLatLon('JO20SX')")
    ok(g.evaluate("() => here") is None and LOC is not None, f"(no GPS position, locator JO20SX = {LOC})")
    for w, h in ((390, 844), (360, 640)):
        print(f"\n[7] Map without GPS: the locator from Settings ({w} px)")
        g.set_viewport_size({"width": w, "height": h})
        g.wait_for_timeout(300)
        from_list(g, 502)
        g.tap("#closeSpot")
        g.wait_for_timeout(300)
        zoom_to(g, 8.5)
        g.evaluate("() => hideStatus()")
        tap_map(g)
        on_me(g, LOC, 8.5, "after x")
        st = g.evaluate("() => ({cls: document.getElementById('status').className, t1: document.getElementById('stT1').textContent, t2: document.getElementById('stT2').textContent})")
        ok("show" in st["cls"] and "JO20SX" in st["t1"] and "GPS" in st["t2"] and g.evaluate(VISIBLE, "#stT1"),
           f"and the message says so: {st['t1']!r} / {st['t2']!r}")
        from_list(g, 502)
        zoom_to(g, 9.25)
        tap_map(g)
        on_me(g, LOC, 9.25, "sheet still open")
        cam = g.evaluate(STATE)
        from_list(g, 501)
        g.go_back()
        g.wait_for_timeout(600)
        s = g.evaluate(STATE)
        ok(s["view"] == ["viewSpots"] and km(s["center"], cam["center"]) < 0.05,
           f"then a spot and the phone's back button: the map as Map left it ({km(s['center'], cam['center']):.2f} km)")

    print("\n[7] no GPS and no locator either")
    g.set_viewport_size({"width": 390, "height": 844})
    g.evaluate("() => { cfg.grid = ''; }")
    g.evaluate("() => map.jumpTo({center: [4.4, 50.8], zoom: 8})")
    before = g.evaluate(STATE)
    from_list(g, 502)
    g.evaluate("() => hideStatus()")
    tap_map(g)
    s = g.evaluate(STATE)
    st = g.evaluate("() => document.getElementById('stT1').textContent")
    ok(km(s["center"], before["center"]) < 0.5 and not s["sheet"],
       f"with the sheet open, Map puts the map back where it was, not at the spot ({km(s['center'], before['center']):.1f} km)")
    ok(st == "Geen positie bekend", f"and says it knows no position ({st!r})")
    loc_ctx.close()

    ok(not errs, f"no page errors in [7] ({errs[:2]})")
    br.close()

print("\n" + ("ALL OK" if not fails else f"{len(fails)} PROBLEMS: " + " | ".join(fails)))
sys.exit(1 if fails else 0)
