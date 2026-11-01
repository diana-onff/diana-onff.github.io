# Text from the area files and the admin screen is shown as text (since 2.2.1).
#
#     python3 build/tests/test_escape.py
#
# Spotline data (callsigns, remarks) was already escaped everywhere. Values
# that come out of a KMZ (province, managing authority, designation, ...), the
# provenance line in the admin screen and your own saved announcements went
# into innerHTML as they were. A tag in any of them would have run as code for
# everyone who opened that panel. Each is now escaped: a tag shows up as the
# literal characters, and the visible text of ordinary values is unchanged.
import re, json, sys
from playwright.sync_api import sync_playwright
import preconsent  # noqa: F401  answered welcome screen, see preconsent.py

BASE = "http://localhost:8011/web/?embed=1"
EVIL = '<img src=x onerror="window.__pwned=1">'
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
    ctx.route(re.compile(r"https://docs\.google\.com/.*"), lambda r: r.abort())


with sync_playwright() as p:
    br = p.chromium.launch()
    ctx = br.new_context(service_workers="block", viewport={"width": 420, "height": 860}, locale="en-GB")
    ctx.add_init_script("try{localStorage.setItem('diana.lang','en');"
                        "localStorage.setItem('diana.agendas', JSON.stringify([{reference:'ONFF-0001" + EVIL.replace('"', '\\"') +
                        "', utc_start:'2026-11-02T08:00', pin:'12" + EVIL.replace('"', '\\"') + "'}]));}catch(e){}")
    routes(ctx)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE, wait_until="load")
    pg.wait_for_function("() => typeof zones !== 'undefined' && zones && zones.features.length > 100", timeout=30000)

    print("\n[1] an area panel with a tag in every KMZ field")
    pg.evaluate("""evil => {
      const f = zones.features.find(x => x.properties.ref === 'ONFF-0685');
      Object.assign(f.properties, {prov: 'Antwerpen' + evil, layer: 'L' + evil, manager: 'Agentschap Natuur & Bos' + evil,
                                   desig: 'Reserve' + evil, iucn: 'IV' + evil, registration: 'R' + evil, status_year: '1998' + evil});
      select('ONFF-0685');
    }""", EVIL)
    pg.wait_for_timeout(500)
    r = pg.evaluate("""() => ({
      imgs: document.querySelectorAll('#sheet img').length,
      badges: document.getElementById('badges').textContent,
      facts: document.getElementById('facts').textContent,
      pwned: !!window.__pwned })""")
    ok(r["imgs"] == 0 and not r["pwned"], "no element and no script from the KMZ values")
    ok("Antwerpen<img" in r["badges"], "the tag shows up as text in the badge")
    ok("Agentschap Natuur & Bos<img" in r["facts"], "an ordinary '&' still reads '&', the tag as text")

    print("\n[2] a point without a boundary with a tag in its place and province")
    np_ref = pg.evaluate("""evil => { const f = noPoly.features[0]; if(!f) return null;
      f.properties.place = 'Gemeente' + evil; f.properties.prov = 'P' + evil; select(f.properties.ref); return f.properties.ref; }""", EVIL)
    if np_ref:
        pg.wait_for_timeout(400)
        ok(pg.evaluate("() => document.querySelectorAll('#sheet img').length === 0 && !window.__pwned"), f"{np_ref}: nothing runs")

    print("\n[3] your own saved announcements")
    pg.evaluate("() => renderAgendaSaved()")
    a = pg.evaluate("() => ({imgs: document.querySelectorAll('#agSavedList img').length, text: document.getElementById('agSavedList').textContent, pwned: !!window.__pwned})")
    ok(a["imgs"] == 0 and not a["pwned"], "no element and no script from a saved announcement")
    ok("ONFF-0001<img" in a["text"], "the stored text is shown as it was typed")

    ok(not errs, f"no page errors ({errs[:2]})")
    br.close()

print("\nOK" if not fails else f"\n{len(fails)} failure(s)")
sys.exit(1 if fails else 0)
