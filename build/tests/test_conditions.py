# Veldinfo > Condities: space weather from NOAA SWPC, via the "conditions" branch.
#
#     python3 build/tests/test_conditions.py
#
# [1] build/conditions.py on the NOAA text and JSON formats (fixtures in
#     build/tests/conditions/): every value read; a source that fails falls
#     back (Kp from the 3-hourly values, or the previous file); nothing at
#     all is an error. No network: this sandbox cannot reach NOAA, the first
#     real run is the workflow on GitHub.
# [2] the bottom bar says Veldinfo, with three tabs, and Condities draws the
#     Kp dial, the numbers, the band strip and sunrise/sunset, with real taps
#     on a 390 px phone.
# [3] the rules: band levels for a few fixed SFI/Kp pairs, Kp words, sunrise
#     and sunset against an independent almanac (astral), polar day/night.
# [4] offline: the last good copy, with its age; never fetched: says so.
import json, os, re, subprocess, sys, tempfile
from playwright.sync_api import sync_playwright
import preconsent  # noqa: F401  answered welcome screen, see preconsent.py

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
FIX = os.path.join(HERE, "conditions")
BASE = "http://localhost:8011/web/?lang=nl"
COND = re.compile(r"https://raw\.githubusercontent\.com/.*/conditions/conditions\.json")
fails = []


def ok(c, m):
    print(("  ✓ " if c else "  ✗ ") + m)
    if not c:
        fails.append(m)


print("[1] build/conditions.py")
sys.path.insert(0, os.path.join(ROOT, "build"))
import conditions as C  # noqa: E402

import datetime as _dt  # noqa: E402
RUN = _dt.datetime(2026, 10, 2, 3, 30, tzinfo=_dt.timezone.utc)   # half an hour after the fixtures
out, probs = C.build(FIX, now=RUN)
ok(out["kp"] == {"value": 1.33, "time": "2026-10-02T06:00:00Z"}, f"Kp: the official 3-hourly value, its time the end of its three hours ({out['kp']})")
ok(out["kp_now"] == {"value": 1.0, "time": "2026-10-02T02:04:00Z"}, f"and the minute estimate beside it ({out['kp_now']})")
objs = json.dumps([{"time_tag": "2026-10-02T00:00:00", "Kp": 2.67}, {"time_tag": "2026-10-02T03:00:00", "Kp": 3.0}])
ok(C.parse_kp3h(objs, RUN) == {"value": 3.0, "time": "2026-10-02T06:00:00Z"}, "the 3-hourly file also read as a list of objects")
try:
    C.parse_kp3h(objs, RUN + _dt.timedelta(hours=20))
    ok(False, "a 3-hourly file stuck for half a day is not trusted")
except ValueError:
    ok(True, "a 3-hourly file stuck for half a day is not trusted")
ok(out["a"] == {"value": 4, "date": "2026-10-01"}, f"A of the last complete day, not today's partial row ({out['a']})")
ok(out["sfi"] == {"value": 92, "date": "2026-10-01"} and out["ssn"] == {"value": 38, "date": "2026-10-01"},
   f"SFI and sunspots of the newest day ({out['sfi']}, {out['ssn']})")
ok(out["source"] == "NOAA SWPC" and not probs, f"source named, no problems ({probs})")

with tempfile.TemporaryDirectory() as tmp:
    for f in os.listdir(FIX):
        with open(os.path.join(FIX, f)) as a, open(os.path.join(tmp, f), "w") as b:
            b.write(a.read())
    with open(os.path.join(tmp, "planetary_k_index_1m.json"), "w") as b:
        b.write("<html>changed format</html>")
    with open(os.path.join(tmp, "noaa-planetary-k-index.json"), "w") as b:
        b.write("[]")
    out2, probs2 = C.build(tmp, now=RUN)
    ok(out2["kp"] == {"value": 1.33, "time": "2026-10-02T06:00:00Z"} and "kp_now" not in out2 and any("kp1m" in p for p in probs2),
       f"3-hourly and minute files both broken: the 3-hourly Kp from the daily file, also from a row whose missing values run together ({out2['kp']})")
    stuck, probs_s = C.build(FIX, now=RUN + _dt.timedelta(hours=8))
    ok(stuck["kp"]["value"] == 1.33 and "kp_now" not in stuck and any("kp1m" in p for p in probs_s),
       f"minute file stuck for hours: no estimate shown, the 3-hourly Kp stays ({stuck['kp']})")
    for f in os.listdir(tmp):
        with open(os.path.join(tmp, f), "w") as b:
            b.write("garbage")
    prev = {"kp": {"value": 2.0, "time": "2026-10-01T21:00:00Z"}, "sfi": {"value": 99, "date": "2026-09-30"}}
    out3, probs3 = C.build(tmp, previous=prev, now=RUN)
    ok(out3.get("kp") == prev["kp"] and out3.get("sfi") == prev["sfi"] and "a" not in out3,
       f"all sources broken: the previous values stay, with their own time ({out3})")
    try:
        C.build(tmp, previous=["not", "a", "dict"], now=RUN)
        ok(False, "nothing now and nothing before: the run fails")
    except SystemExit:
        ok(True, "nothing now and nothing before (and a broken previous file): the run fails (red in Actions)")
r = subprocess.run([sys.executable, os.path.join(ROOT, "build", "conditions.py"), "--out", os.devnull, "--fixtures", FIX],
                   capture_output=True, text=True)
ok(r.returncode == 0 and '"sfi"' in r.stdout, "the command line the workflow uses works")
DATA = dict(out, updated="2026-10-02T12:23:00Z")


def routes(ctx, body):
    ctx.route(re.compile(r"https://tiles\.openfreemap\.org/.*"), lambda r: r.fulfill(
        status=200, content_type="application/json",
        body=json.dumps({"version": 8, "sources": {}, "layers": [{"id": "bg", "type": "background"}]})))
    ctx.route(re.compile(r"https://(spots\.wwff\.co|docs\.google\.com)/.*"), lambda r: r.fulfill(
        status=200, content_type="application/json", body="[]"))
    if body is None:
        ctx.route(COND, lambda r: r.abort())
    else:
        ctx.route(COND, lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(body)))


with sync_playwright() as p:
    br = p.chromium.launch()
    ctx = br.new_context(service_workers="block", viewport={"width": 390, "height": 844},
                         device_scale_factor=1, is_mobile=True, has_touch=True)
    ctx.add_init_script("try { localStorage.setItem('diana.grid', 'JO20SX'); } catch (e) {}")
    routes(ctx, DATA)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE, wait_until="load")
    pg.wait_for_function("() => typeof renderCond === 'function' && zones && zones.features", timeout=20000)
    pg.wait_for_timeout(1500)

    print("\n[2] Veldinfo with three tabs, Condities drawn")
    nav = pg.text_content('#nav button[data-view="viewNearby"]').strip()
    ok(nav.endswith("Veldinfo"), f"the bottom bar says Veldinfo ({nav!r})")
    pg.tap('#nav button[data-view="viewNearby"]')
    tabs = pg.eval_on_selector_all("#nearTab .seg", "b => b.map(x => x.textContent.trim())")
    ok(tabs == ["Gebieden", "Locatie", "Condities"], f"three tabs ({tabs})")
    ok(pg.text_content("#viewNearby h1").strip() == "Veldinfo", "the screen is called Veldinfo too")
    pg.tap("#nearTab .seg[data-neartab='cond']")
    pg.wait_for_selector("#condKp", timeout=5000)
    g = pg.evaluate("""() => ({kp: condKp.textContent, word: condKpWord.textContent, sfi: condSfi.textContent,
        a: condA.textContent, ssn: condSsn.textContent, gauge: !!document.querySelector('#nearCond svg.kpgauge line'),
        segs: document.querySelectorAll('#nearCond svg.kpgauge path').length,
        rise: (document.getElementById('condRise') || {}).textContent || '', age: condAge.textContent,
        nowcols: document.querySelectorAll('.condlabels span.now').length,
        nowcells: document.querySelectorAll('.condbar .condnow').length,
        visible: (() => { const r = nearCond.getBoundingClientRect(); return r.height > 200 && r.top < innerHeight; })()})""")
    ok(g["visible"] and g["gauge"] and g["segs"] == 9, f"the Kp dial with 9 steps and a needle, on screen ({g['segs']})")
    ok(g["kp"] == "1.33" and g["word"] == "rustig", f"Kp 1.33 (3-hourly), rustig ({g['kp']}, {g['word']})")
    now_txt = pg.text_content("#condKpNow")
    ok("per 3 uur" in now_txt and now_txt.endswith(": 1."), f"with the minute estimate small underneath ({now_txt!r})")
    ok((g["sfi"], g["a"], g["ssn"]) == ("92", "4", "38"), f"SFI 92, A 4, sunspots 38 ({g['sfi']}, {g['a']}, {g['ssn']})")
    ok("UTC" in g["rise"] and g["nowcols"] == 1 and g["nowcells"] == 5,
       f"sunrise in local time and UTC, the part of the day for now marked, a 'now' line on every bar ({g['rise']!r}, {g['nowcols']}, {g['nowcells']})")
    ok("Bron: NOAA SWPC" in g["age"], f"source and age said ({g['age']!r})")
    lvl = pg.evaluate("() => Object.fromEntries([...document.querySelectorAll('.condseg')].map(p => [p.dataset.band + '/' + p.dataset.part, p.dataset.level]))")
    labels = pg.eval_on_selector_all(".condlabels span", "s => s.map(x => x.textContent)")
    ok(labels == ["ochtend", "middag", "namiddag", "avond", "nacht"] and len(lvl) == 25,
       f"five bands, each a bar from ochtend to nacht ({labels})")
    ok((lvl["10/1"], lvl["15/1"], lvl["20/1"], lvl["80/4"]) == ("0", "1", "2", "2"),
       f"SFI 92, Kp 1: at midday 10 m poor, 15 m fair, 20 m good; 80 m good at night ({lvl['10/1']}, {lvl['15/1']}, {lvl['20/1']}, {lvl['80/4']})")
    words = pg.eval_on_selector_all(".condbar", "b => b.map(x => x.textContent.trim()).join('')")
    ok(words == "", "the bars carry colour only, no words")
    rows = pg.evaluate("""() => [...document.querySelectorAll('.condrow')].map(r => ({
        tag: r.querySelector('.condband small').textContent, now: (r.querySelector('.condnowword') || {}).textContent,
        bg: getComputedStyle(r.querySelector('.condbar')).backgroundImage}))""")
    ok([r["tag"] for r in rows] == ["NVIS, EU 's nachts", "NVIS en EU", "EU en DX", "DX", "DX"],
       f"next to each band what good means there, readable without a tap ({[r['tag'] for r in rows]})")
    ok(all(re.fullmatch(r"nu: (goed|matig|slecht)", r["now"] or "") for r in rows),
       f"and on the right what applies now, in words ({[r['now'] for r in rows]})")
    ok("rgb(82, 183, 136)" in rows[1]["bg"] and "rgb(155, 34, 38)" in rows[4]["bg"],
       "the bars use the Kp dial's colours: its green for good, its dark red for poor")
    pg.tap('.condseg[data-band="20"][data-part="3"]')
    tip = pg.text_content("#condTip")
    ok(tip == "20 m, avond: goed.", f"a tap on a bar says it in words ({tip!r})")
    cut = pg.evaluate("() => [...document.querySelectorAll('.condlabels span')].some(s => s.scrollWidth > s.clientWidth)")
    ok(not cut, "the five part-of-day labels fit, none cut off")
    if os.environ.get("DIANA_SHOTS"):
        pg.screenshot(path=os.path.join(os.environ["DIANA_SHOTS"], "condities.png"), full_page=False)
    pg.set_viewport_size({"width": 360, "height": 740})
    pg.wait_for_timeout(300)
    cut = pg.evaluate("() => [...document.querySelectorAll('.condlabels span')].some(s => s.scrollWidth > s.clientWidth)")
    ok(not cut, "also on a 360 px phone")
    pg.set_viewport_size({"width": 390, "height": 844})

    print("\n[3] the rules")
    lv = pg.evaluate("""() => ({
      high: bandOutlook(160, 1), storm: bandOutlook(160, 5.33), severe: bandOutlook(160, 7), k4: bandOutlook(160, 4),
      nosfi: bandOutlook(null, 1), mid: bandOutlook(135, 1),
      season: [bandOutlook(120, 1, 'winter')['10'][1], bandOutlook(120, 1, 'equinox')['10'][1], bandOutlook(120, 1, 'summer')['10'][1],
               bandOutlook(110, 1, 'winter')['20'][4], bandOutlook(110, 1, 'summer')['20'][4]],
      seasons: [['2026-01-15', 51], ['2026-07-01', 51], ['2026-01-15', -34], ['2026-01-15', 10], ['2026-10-02', 51]]
        .map(([d, lat]) => condSeason(new Date(d + 'T12:00:00Z'), lat)),
      w: [0, 2.67, 3, 4, 5, 6.33, 9].map(k => [kpClass(k).key, kpClass(k).g || 0]) })""")
    ok(lv["high"]["10"][1] == 2 and lv["high"]["15"][4] == 1 and lv["high"]["20"][4] == 1 and lv["mid"]["10"][1] == 2 and lv["mid"]["10"][0] == 1,
       "SFI 160, quiet: 10 m good at midday, 15 m and 20 m fair at night; at SFI 135 10 m opens later (fair in the morning)")
    ok(lv["storm"]["10"][1] == 1 and lv["storm"]["80"][4] == 1 and lv["severe"]["40"][1] == 0,
       "a storm costs every band a step, a severe one two")
    ok(lv["season"] == [2, 1, 1, 0, 1], f"season: at SFI 120, 10 m at midday good in winter only; at SFI 110, 20 m at night shut in winter, fair in summer ({lv['season']})")
    ok(lv["seasons"] == ["winter", "summer", "summer", "equinox", "equinox"], f"seasons by month and hemisphere, none in the tropics ({lv['seasons']})")
    ok(lv["k4"]["20"][1] == 1 and lv["k4"]["40"][1] == 2, "Kp 4 costs only the higher bands")
    ok(lv["nosfi"]["10"][1] is None and lv["nosfi"]["40"][4] == 2, "no SFI: unknown where it matters")
    ok(lv["w"] == [["cond.kp.quiet", 0], ["cond.kp.unsettled", 0], ["cond.kp.unsettled", 0], ["cond.kp.active", 0],
                   ["cond.kp.storm", 1], ["cond.kp.storm", 2], ["cond.kp.storm", 5]], f"Kp words and G1..G5, 2.67 being 3- ({lv['w']})")
    try:
        import datetime as dt
        from astral import LocationInfo
        from astral.sun import sun
        ref = []
        for lat, lon, d in [(50.85, 4.35, dt.date(2026, 10, 2)), (50.85, 4.35, dt.date(2026, 6, 21)), (38.7, -9.14, dt.date(2026, 1, 15))]:
            s = sun(LocationInfo("x", "x", "UTC", lat, lon).observer, date=d)
            ref.append([lat, lon, d.isoformat(), s["sunrise"].timestamp() * 1000, s["sunset"].timestamp() * 1000])
    except ImportError:
        # Without astral installed: its values for the first case (Brussels, 2 Oct 2026).
        ref = [[50.85, 4.35, "2026-10-02", 1790919881000, 1790961497000]]
    diffs = pg.evaluate("""(ref) => ref.map(([lat, lon, d, r, s]) => { const x = sunTimes(new Date(d + 'T12:00:00Z'), lat, lon);
        return [Math.abs(x.rise - r) / 60000, Math.abs(x.set - s) / 60000]; })""", ref)
    worst = max(max(d) for d in diffs)
    ok(worst < 2, f"sunrise and sunset within 2 minutes of an independent almanac (worst {worst:.1f} min, {len(ref)} cases)")
    polar = pg.evaluate("() => [sunTimes(new Date('2026-12-21T12:00:00Z'), 69.65, 18.96).polar, sunTimes(new Date('2026-06-21T12:00:00Z'), 69.65, 18.96).polar, ...['05:00', '08:00', '12:00', '15:00', '17:00', '22:00'].map(h => (periodAt(new Date('2026-10-02T' + h + ':00Z'), 50.85, 4.35) || {}).i), periodAt(new Date('2026-12-21T12:00:00Z'), 69.65, 18.96)]")
    ok(polar == ["night", "day", 4, 0, 1, 2, 3, 4, None],
       f"polar night and day; in Brussels on 2 Oct (sun 05:45 to 17:18 UTC) 05, 08, 12, 15, 17 and 22 UTC are night, morning, midday, afternoon, evening, night ({polar})")
    storm = dict(DATA, kp={"value": 6.33, "time": "2026-10-02T12:00:00Z"})
    pg.evaluate("(d) => { condData = d; renderCond(); }", storm)
    ok(pg.text_content("#condKpWord") == "storm G2", f"Kp 6.33 reads as storm G2 ({pg.text_content('#condKpWord')})")
    pg.evaluate("(d) => { condData = d; renderCond(); }", dict(DATA, kp={"value": 0.0, "time": "2026-10-02T15:00:00Z"}))
    dial = pg.evaluate("""() => { const s = document.querySelector('svg.kpgauge');
        const paths = [...s.querySelectorAll('path')].map(p => +p.getAttribute('opacity'));
        const l = s.querySelector('line'), len = Math.hypot(l.getAttribute('x2') - l.getAttribute('x1'), l.getAttribute('y2') - l.getAttribute('y1'));
        const zero = [...s.querySelectorAll('text')].find(t => t.textContent === '0');
        const dz = Math.hypot(zero.getAttribute('x') - l.getAttribute('x1'), zero.getAttribute('y') - 4 - l.getAttribute('y1'));
        return {first: paths[0], rest: Math.max(...paths.slice(1)), len, dz}; }""")
    ok(dial["first"] == 1 and dial["rest"] < 1, f"at Kp 0 the first green step lights up, the rest stays pale ({dial['first']}, {dial['rest']})")
    ok(dial["len"] < dial["dz"] - 6, f"and the needle stops short of the numbers ({dial['len']:.0f} < {dial['dz']:.0f})")
    thirds = pg.evaluate("() => [3.67, 4.67, 5.67].map(k => [kpClass(k).key, kpClass(k).g || 0, bandOutlook(160, k)['40'][4]])")
    ok(thirds == [["cond.kp.active", 0, 2], ["cond.kp.storm", 1, 1], ["cond.kp.storm", 2, 1]],
       f"Kp in thirds: 4- is active, 5- already G1 and costs a step, 6- is G2 ({thirds})")
    kept = dict(DATA, updated="2026-10-02T12:23:00Z", kp={"value": 2.0, "time": "2026-09-28T09:00:00Z"})
    pg.evaluate("(d) => { condData = d; renderCond(); }", kept)
    ok("Let op" in pg.text_content("#condAge") and "1 okt" in pg.text_content("#condDaily"),
       f"a value kept from an earlier run shows its own age, daily values their date ({pg.text_content('#condAge')!r}, {pg.text_content('#condDaily')!r})")
    ok(not errs, f"no page errors ({errs[:2]})")
    ctx.close()

    print("\n[4] offline")
    ctx = br.new_context(service_workers="block", viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    OLD = dict(DATA, updated="2026-10-01T06:00:00Z")     # well over six hours before any run of this test
    ctx.add_init_script("try { localStorage.setItem('diana.near.tab', 'cond'); localStorage.setItem('diana.cond.last', JSON.stringify({data: %s})); } catch (e) {}" % json.dumps(OLD))
    routes(ctx, None)
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE, wait_until="load")
    pg.wait_for_function("() => typeof renderCond === 'function'", timeout=20000)
    pg.wait_for_timeout(1000)
    pg.tap('#nav button[data-view="viewNearby"]')
    pg.wait_for_selector("#condKp", timeout=5000)
    pg.wait_for_timeout(800)
    ok(pg.text_content("#condSfi") == "92", "no connection: the last good copy is shown, on the tab you left it on")
    age = pg.text_content("#condAge")
    ok("Let op" in age and "condold" in (pg.get_attribute("#condAge", "class") or ""), f"with its age said out loud ({age!r})")
    pg.evaluate("() => { localStorage.removeItem('diana.cond.last'); condData = null; renderCond(); }")
    ok("Nog geen ruimteweergegevens" in pg.text_content("#nearCond"), "never fetched and offline: says so, no empty card")
    ok(not errs, f"no page errors ({errs[:2]})")
    br.close()

print("\n" + ("ALL OK" if not fails else f"{len(fails)} PROBLEMS: " + " | ".join(fails)))
sys.exit(1 if fails else 0)
