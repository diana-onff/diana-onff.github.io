# The "check your location permission" banner and its permanent Settings line.
#
#     python3 build/tests/test_acc_hint.py
#
# A field report: on one phone, at one real spot, a comparison walking app held
# a steady 15 m of accuracy while Diana sat at 98 m and then, on a separate try
# four minutes later, 136 m — never sharper, no matter how often the ◎ button
# was pressed. enableHighAccuracy was already on, so the missing piece is not
# in geo.js's own fix-reconciliation logic: it is that a browser (or the OS,
# for one site specifically) can be told to hand over only an "approximate"
# location, deliberately fuzzed into an area the size of a small town, and no
# amount of retrying inside the page changes that. The fix is not a sharper
# GPS algorithm — it is telling the person where to look: a banner that shows
# up once a fix stays worse than FIX_HINT_M (75 m), points at the browser's own
# location setting (both in general and for this one site), and — modelled
# directly on the existing "install this as an app?" bar — disappears for good
# the moment it is dismissed, everywhere except Settings, which keeps saying
# the same thing regardless, because "stop interrupting me" is not "stop
# telling me".
import re, sys
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8011/web/?embed=1"   # embed=1: skip the ~9 MB worldwide layer
fails = []

HERE = {"latitude": 51.1740, "longitude": 4.3400}


def ok(c, m):
    print(("  ✓ " if c else "  ✗ ") + m)
    if not c:
        fails.append(m)


def routes(ctx):
    import json
    ctx.route(re.compile(r"https://tiles\.openfreemap\.org/.*"), lambda r: r.fulfill(
        status=200, content_type="application/json",
        body=json.dumps({"version": 8, "sources": {}, "layers": [
            {"id": "bg", "type": "background", "paint": {"background-color": "#e8e4d8"}}]})))
    ctx.route(re.compile(r"https://spots\.wwff\.co/static/spots\.json"), lambda r: r.fulfill(
        status=200, content_type="application/json", body="[]"))
    ctx.route(re.compile(r"https://spots\.wwff\.co/static/agendas.*"), lambda r: r.fulfill(
        status=200, content_type="application/json", body="[]"))
    ctx.route(re.compile(r"https://docs\.google\.com/.*"), lambda r: r.abort())


def fix(pg, acc, final=True):
    pg.evaluate("""(a) => fixApply({coords:{latitude:a.lat, longitude:a.lon, accuracy:a.acc},
                                     timestamp:Date.now()}, a.final)""",
                {"lat": HERE["latitude"], "lon": HERE["longitude"], "acc": acc, "final": final})


READ = """() => ({
  hintHidden: $('accHint').hidden,
  hintTxt: $('accHintTxt').textContent,
  setTxt: $('setFixState').textContent,
  wantHint: t('gps.hintacc'),
  wantSetHint: t('set.fixhint'),
  wantCoarse: t('set.fixcoarse'),
  off: localStorage.getItem('diana.acc.hintoff'),
})"""


def load(ctx):
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE, wait_until="load")
    pg.wait_for_timeout(2500)
    pg.wait_for_function("() => map.isStyleLoaded()", timeout=20000)
    return pg, errs


with sync_playwright() as p:
    br = p.chromium.launch()
    ctx = br.new_context(service_workers="block", viewport={"width": 420, "height": 860},
                          permissions=["geolocation"], geolocation=HERE)
    routes(ctx)
    pg, errs = load(ctx)

    print("\n[1] a poor fix (98 m, above FIX_HINT_M) shows the banner, worded with the live figure")
    fix(pg, 98)
    st = pg.evaluate(READ)
    ok(not st["hintHidden"], f"banner visible ({st})")
    ok(st["hintTxt"] == st["wantHint"].replace("{a}", "98"), f"banner text carries ±98 ({st})")
    ok(st["wantSetHint"] in st["setTxt"], f"Settings also carries the same tip ({st})")

    print("\n[2] a sharp fix (15 m) hides the banner again, on its own — no dismiss needed")
    fix(pg, 15)
    st = pg.evaluate(READ)
    ok(st["hintHidden"], f"banner hidden once the fix is sharp ({st})")
    ok(st["wantSetHint"] not in st["setTxt"], f"and Settings drops the tip too ({st})")
    ok(st["wantCoarse"] not in st["setTxt"], f"a 15 m fix isn't 'too coarse' either ({st})")

    print("\n[3] right at the threshold (75 m exactly): not yet a permission-shaped problem")
    fix(pg, 75)
    st = pg.evaluate(READ)
    ok(st["hintHidden"], f"banner still hidden at exactly 75 m ({st})")
    ok(st["wantSetHint"] not in st["setTxt"], f"Settings tip absent at 75 m ({st})")
    ok(st["wantCoarse"] in st["setTxt"], f"but still flagged as too coarse (>25 m) ({st})")

    print("\n[4] one metre over (76 m): now it shows")
    fix(pg, 76)
    st = pg.evaluate(READ)
    ok(not st["hintHidden"], f"banner appears at 76 m ({st})")
    ok(st["wantSetHint"] in st["setTxt"], f"and so does the Settings tip ({st})")

    print("\n[5] dismissing the banner hides it, remembers that, and does not touch Settings")
    # A real Playwright click needs the element visually on screen, but this
    # banner is deliberately display:none in the ?embed=1 mode these tests run
    # in (same as the install bar) — dispatch the click in-page instead, the
    # way a tap on it would fire either way.
    pg.evaluate("() => $('accHintClose').click()")
    st = pg.evaluate(READ)
    ok(st["hintHidden"], f"banner hidden right after the click ({st})")
    ok(st["off"] == "1", f"the dismissal was written to localStorage ({st})")
    ok(st["wantSetHint"] in st["setTxt"], f"Settings still carries the tip — dismiss ≠ forget ({st})")

    print("\n[6] a fresh poor fix after dismissing: the banner stays gone, Settings still speaks")
    fix(pg, 120)
    st = pg.evaluate(READ)
    ok(st["hintHidden"], f"banner does not come back on a new bad fix ({st})")
    ok(st["wantSetHint"] in st["setTxt"], f"Settings keeps saying it regardless ({st})")

    print("\n[7] the dismissal survives a reload — it is a permanent 'stop interrupting me'")
    pg.close()
    pg, errs2 = load(ctx)
    errs += errs2
    fix(pg, 130)
    st = pg.evaluate(READ)
    ok(st["off"] == "1", f"the flag is still set after reload ({st})")
    ok(st["hintHidden"], f"and the banner respects it from a cold load ({st})")
    ok(st["wantSetHint"] in st["setTxt"], f"Settings is unaffected by any of this ({st})")

    print("\n[8] nothing thrown along the way")
    real = [e for e in errs if "Failed to load resource" not in e]
    ok(not real, f"no page errors: {real[:2] or 'ok'}")

    print("\n" + ("ALL OK" if not fails else f"{len(fails)} PROBLEMS"))
    br.close()
    sys.exit(1 if fails else 0)
