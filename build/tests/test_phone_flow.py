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
#       its sheet visible; x -> back in the list, same tab, map back where it was
#   [2] an agenda entry: the same, closed by swiping the sheet down, and the
#       Agenda tab is still the one showing
#   [3] Map in the bottom bar while such a spot is open: the plain map, back
#       where it was, not the spot's location; the same via another screen
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
    pg.tap("#closeSpot")
    pg.wait_for_timeout(400)
    s = pg.evaluate(STATE)
    ok(s["view"] == ["viewSpots"] and s["nav"] == "viewSpots" and not s["sheet"],
       f"x brings you back to the Spots screen ({s['view']}, {s['nav']})")
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
    top = pg.evaluate("() => document.getElementById('spotSheet').getBoundingClientRect().top")
    swipe(pg, cdp, 195, top + 12, top + 330)
    s = pg.evaluate(STATE)
    ok(s["view"] == ["viewSpots"] and not s["sheet"], f"swiping it down brings you back ({s['view']})")
    ok(s["tab"] == "agenda", f"to the Agenda tab you came from ({s['tab']})")
    ok(km(s["center"], home["center"]) < 0.5, "map back where it was")

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

    print("\n[3b] a GPS position arriving while a spot from the list is showing")
    pg.tap('#nav button[data-view="viewSpots"]')
    pg.tap('#spotList .spot[data-id="501"]')
    pg.wait_for_function("() => document.getElementById('spotSheet').classList.contains('open')", timeout=5000)
    settle(pg)
    pg.evaluate("() => fixApply({coords: {latitude: 51.20, longitude: 4.40, accuracy: 8}, timestamp: Date.now()}, true)")
    pg.wait_for_timeout(800)
    s = pg.evaluate(STATE)
    ok(km(s["center"], [3.10, 50.95]) < 40 and s["sheet"], "the map stays on the spot, the sheet open")
    pg.tap("#closeSpot")
    pg.wait_for_timeout(500)
    s = pg.evaluate(STATE)
    ok(s["view"] == ["viewSpots"], "closing still returns to the list")
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
    pg.tap("#closeSpot")
    pg.wait_for_timeout(500)
    ok(pg.evaluate("() => map.getPadding()") == pad_before, "and the map's padding is what it was")

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
    ok(not s["sheet"] and s["view"] == ["viewSpots"], "at the top, a swipe down closes it and you are back in the list")
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
    # Closed with x, then straight away the next spot: the back entry of the
    # first is removed (asynchronously) while the second one needs its own.
    pg.tap('#spotTab .seg[data-tab="spots"]')
    pg.tap('#spotList .spot[data-id="501"]')
    pg.wait_for_function("() => document.getElementById('spotSheet').classList.contains('open')", timeout=5000)
    pg.tap("#closeSpot")
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
    br.close()

print("\n" + ("ALL OK" if not fails else f"{len(fails)} PROBLEMS: " + " | ".join(fails)))
sys.exit(1 if fails else 0)
