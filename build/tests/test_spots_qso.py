# QSO count (or ATNO) next to a spot or an announced activation's reference.
#
#     python3 build/tests/test_spots_qso.py
#
# Kristof asked for the QSO count Diana already knows (from the same WWFF
# directory used everywhere else) to show up next to a spot, and, when a
# reference has never been activated, an ATNO tag instead. The worldwide
# counts come from data/wwff-activity.json (ref -> count, built in
# kmz2geojson.py's point_refs()), because spots and the agenda are not limited
# to the one country whose boundaries happen to be loaded.
#
# The trap this guards: the real directory never writes a literal 0. A
# never-activated reference has an EMPTY count, so the per-country activity
# table leaves it out altogether, and a first version of this feature (which
# only looked for q == 0) would never have shown a single ATNO. Case [2b]
# below is that real path: a Belgian reference missing from the home table,
# 0 in the worldwide file, must still come out as ATNO.
#
# Both data files are mocked, so every case is exact rather than whatever the
# real directory happens to hold today.
import re, json, sys, time
from playwright.sync_api import sync_playwright
import preconsent  # noqa: F401  answered welcome screen, see preconsent.py

BASE = "http://localhost:8011/web/"
fails = []


def ok(c, m):
    print(("  ✓ " if c else "  ✗ ") + m)
    if not c:
        fails.append(m)


# spot_time is Unix epoch seconds (ageMin() in spots.js). time.time() is that
# in any time zone; a naive datetime.utcnow().timestamp() is not, and made
# every spot two hours old (and filtered out) on a Belgian computer.
NOW = time.time()
REFS = ["PAFF-0001", "PAFF-0002", "PAFF-0003", "ONFF-0001", "ONFF-0962", "ONFF-0005"]

SPOTS = [{"id": i + 1, "activator": f"ON4A{chr(65 + i)}", "reference": ref,
          "frequency_khz": 14244.5 + i, "mode": "SSB",   # a long, realistic frequency: the widest line
          "latitude": 50.5 + i / 10, "longitude": 5.5, "spot_time": NOW - 60}
         for i, ref in enumerate(REFS)]

WORLD = {
    "PAFF-0001": 42,      # another country, a real count
    "PAFF-0002": 0,       # another country, never activated -> ATNO
                          # PAFF-0003 absent: no figures at all -> silent
    "ONFF-0001": 1,       # also in the home table, which must win (3,675)
    "ONFF-0962": 0,       # NOT in the home table, 0 here -> ATNO (the real path)
    "ONFF-0005": 0,       # home table says activated without a count -> silent
}
HOME = {
    "ONFF-0001": {"q": 3675, "last": "2026-03-05"},
    "ONFF-0005": {"q": 0, "last": "2025-01-01"},
}


def base_routes(ctx):
    ctx.route(re.compile(r"https://tiles\.openfreemap\.org/.*"), lambda r: r.fulfill(
        status=200, content_type="application/json",
        body=json.dumps({"version": 8, "sources": {}, "layers": [
            {"id": "bg", "type": "background", "paint": {"background-color": "#e8e4d8"}}]})))
    ctx.route(re.compile(r"https://spots\.wwff\.co/static/spots\.json"), lambda r: r.fulfill(
        status=200, content_type="application/json", body=json.dumps(SPOTS)))
    ctx.route(re.compile(r"https://spots\.wwff\.co/static/agendas_active\.json"), lambda r: r.fulfill(
        status=200, content_type="application/json", body=json.dumps([
            {"id": 1, "reference": "PAFF-0001", "activator_call": "PA1AA", "band": "40m", "mode": "SSB",
             "utc_start": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(NOW - 3600)),
             "utc_end": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(NOW + 3600))}])))
    ctx.route(re.compile(r"https://spots\.wwff\.co/static/agendas\.json"), lambda r: r.fulfill(
        status=200, content_type="application/json", body="[]"))
    ctx.route(re.compile(r"https://docs\.google\.com/.*"), lambda r: r.abort())
    ctx.route(re.compile(r".*zones/onff-activity\.json"), lambda r: r.fulfill(
        status=200, content_type="application/json", body=json.dumps({"refs": HOME})))


ROW = """(ref) => {
  const row = [...document.querySelectorAll('#spotList .spot')]
    .find(el => ((el.querySelector('.f') || {}).textContent || '').includes(ref + ' ')
             || ((el.querySelector('.f') || {}).textContent || '').endsWith(ref));
  if(!row) return null;
  // The tag sits on the callsign line (.c); text is the whole row, both lines.
  return {text: row.querySelector('.who').textContent, atno: !!row.querySelector('.c .atno')};
}"""
ANY_TAG = "() => [...document.querySelectorAll('#spotList .c .atno')].length > 0"

with sync_playwright() as p:
    br = p.chromium.launch()
    errs = []

    ctx = br.new_context(service_workers="block", viewport={"width": 420, "height": 860})
    base_routes(ctx)
    ctx.route(re.compile(r".*data/wwff-activity\.json"), lambda r: r.fulfill(
        status=200, content_type="application/json", body=json.dumps({"refs": WORLD})))
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE, wait_until="load")
    pg.wait_for_function("() => document.querySelectorAll('#spotList .spot').length >= 6", timeout=15000)
    pg.wait_for_function(ANY_TAG, timeout=10000)
    r = {ref: pg.evaluate(ROW, ref) for ref in REFS}

    print("\n[1] a real count, from the worldwide file")
    ok(r["PAFF-0001"] and "42 QSOs" in r["PAFF-0001"]["text"], f"PAFF-0001 shows 42 QSOs ({r['PAFF-0001']})")

    print("\n[2] never activated: ATNO, in its own class for the red")
    ok(r["PAFF-0002"] and r["PAFF-0002"]["atno"] and "0 QSO" not in r["PAFF-0002"]["text"],
       f"PAFF-0002 shows ATNO ({r['PAFF-0002']})")
    ok(r["ONFF-0962"] and r["ONFF-0962"]["atno"],
       f"[2b] a home-country reference missing from the home table is still ATNO ({r['ONFF-0962']})")

    print("\n[3] nothing to go on: silent")
    ok(r["PAFF-0003"] and "QSO" not in r["PAFF-0003"]["text"] and not r["PAFF-0003"]["atno"],
       f"PAFF-0003 stays silent ({r['PAFF-0003']})")
    ok(r["ONFF-0005"] and "QSO" not in r["ONFF-0005"]["text"] and not r["ONFF-0005"]["atno"],
       f"activated but no count stays silent, not a false ATNO ({r['ONFF-0005']})")

    print("\n[4] the home country's own table wins over the worldwide file")
    ok(r["ONFF-0001"] and "3,675 QSOs" in r["ONFF-0001"]["text"], f"ONFF-0001 shows 3,675 ({r['ONFF-0001']})")

    print("\n[5] the agenda list gets the same treatment")
    pg.evaluate("() => document.querySelector('#spotTab .seg[data-tab=\"agenda\"]').click()")
    pg.wait_for_timeout(300)
    a = pg.evaluate("() => { const w = document.querySelector('#spotList .spot .who'); return w ? w.textContent : null; }")
    ok(bool(a) and "42 QSOs" in a, f"the agenda entry for PAFF-0001 shows its count ({a!r})")

    print("\n[6] the label follows the language, ATNO does not")
    pg.evaluate("() => document.querySelector('#spotTab .seg[data-tab=\"spots\"]').click()")
    pg.evaluate("() => { lang = 'nl'; applyLang(); }")
    nl = pg.evaluate(ROW, "PAFF-0001")
    nl2 = pg.evaluate(ROW, "PAFF-0002")
    ok(nl and "42 QSO's" in nl["text"], f"Dutch: 42 QSO's ({nl})")
    ok(nl2 and "ATNO" in nl2["text"], f"and ATNO stays ATNO ({nl2})")
    ctx.close()

    print("\n[7] a failed download is tried again later, not given up for the session")
    calls = {"n": 0}

    def flaky(route):
        calls["n"] += 1
        if calls["n"] <= 2:          # both URLs fetchFirst() tries, first attempt
            route.fulfill(status=503, body="")
        else:
            route.fulfill(status=200, content_type="application/json", body=json.dumps({"refs": WORLD}))

    ctx2 = br.new_context(service_workers="block", viewport={"width": 420, "height": 860})
    base_routes(ctx2)
    ctx2.route(re.compile(r".*data/wwff-activity\.json"), flaky)
    pg2 = ctx2.new_page()
    pg2.on("pageerror", lambda e: errs.append(str(e)))
    pg2.goto(BASE, wait_until="load")
    pg2.wait_for_function("() => document.querySelectorAll('#spotList .spot').length >= 6", timeout=15000)
    pg2.wait_for_function("() => worldActivityFailedAt > 0", timeout=10000)
    pg2.evaluate("() => renderSpots()")
    pg2.wait_for_timeout(300)
    ok(calls["n"] == 2, f"no new attempt within the minute ({calls['n']} requests)")
    before = pg2.evaluate(ROW, "PAFF-0002")
    ok(before and not before["atno"], f"meanwhile no tag rather than a guess ({before})")
    pg2.evaluate("() => { worldActivityFailedAt -= 61000; renderSpots(); }")
    pg2.wait_for_function("""() => [...document.querySelectorAll('#spotList .c .atno')].length > 0""", timeout=10000)
    t = pg2.evaluate(ROW, "PAFF-0002")
    ok(calls["n"] >= 3 and t and t["atno"], f"after a minute it tries again and the tags appear ({calls['n']} requests, {t})")
    ctx2.close()


    print("\n[9] on a narrow phone the tag is never cut off")
    # A first version put the tag at the end of the reference line, which is
    # one line with an ellipsis: at 390 px the count was cut, at 360 px ATNO
    # too. With a GPS position the right-hand column (bearing, distance) is
    # at its widest, so that is the case to test.
    for width in (360, 390):
        ctx3 = br.new_context(service_workers="block", viewport={"width": width, "height": 800})
        base_routes(ctx3)
        ctx3.route(re.compile(r".*data/wwff-activity\.json"), lambda r: r.fulfill(
            status=200, content_type="application/json", body=json.dumps({"refs": WORLD})))
        pg3 = ctx3.new_page()
        pg3.on("pageerror", lambda e: errs.append(str(e)))
        pg3.goto(BASE, wait_until="load")
        pg3.evaluate("() => { const b = document.querySelector('[data-view=\"viewSpots\"]'); if(b) b.click(); }")
        pg3.wait_for_function(ANY_TAG, timeout=15000)
        pg3.evaluate("() => { here = {lat: 50.85, lon: 4.35}; renderSpots(); }")
        pg3.wait_for_timeout(200)
        bad = pg3.evaluate("""() => [...document.querySelectorAll('#spotList .spot')].map(row => {
            const tag = row.querySelector('.c .qso, .c .atno');
            if(!tag) return null;
            const t = tag.getBoundingClientRect(), r = row.getBoundingClientRect(), who = row.querySelector('.who').getBoundingClientRect();
            const clipped = t.width === 0 || t.right > who.right + 0.5 || t.right > r.right + 0.5
                          || tag.scrollWidth > tag.clientWidth + 0.5;
            return clipped ? row.querySelector('.who').textContent.trim() : null;
          }).filter(Boolean)""")
        shown = pg3.evaluate("() => document.querySelectorAll('#spotList .c .qso, #spotList .c .atno').length")
        vis = pg3.evaluate("() => { const l = document.getElementById('spotList'); return !!(l && l.offsetParent); }")
        ok(shown >= 5 and not bad,
           f"{width} px: all {shown} tags fully visible{' (list on screen)' if vis else ''} (clipped: {bad})")
        ctx3.close()

    print("\n[8] no JS errors")
    real = [e for e in errs if "Failed to load resource" not in e]
    ok(not real, "no page errors: " + (real[0][:160] if real else "ok"))

    br.close()

print("\n" + ("ALL OK" if not fails else f"{len(fails)} PROBLEMS: " + " | ".join(fails)))
sys.exit(1 if fails else 0)
