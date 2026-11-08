# The welcome screen says what the location permission is, and is not (since 2.2.6).
#
#     python3 build/tests/test_welcome_scope.py
#
# People hesitate over the location question. The two worries heard most (it
# opens the GPS to other websites, and it keeps the GPS running) are both
# untrue, and the welcome screen now says so in a box of its own, above the
# button. Checked: the box is there in all eight languages with both
# sentences, it stands above "Allow precise location", and on a small phone
# it is on screen without scrolling.
import re, json, sys
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8011/web/"
fails = []


def ok(c, m):
    print(("  ✓ " if c else "  ✗ ") + m)
    if not c:
        fails.append(m)


STYLE = json.dumps({"version": 8, "sources": {}, "layers": [{"id": "bg", "type": "background", "paint": {"background-color": "#e8e4d8"}}]})

with sync_playwright() as p:
    br = p.chromium.launch()
    errs = []
    for lang, w, h in (("nl", 360, 740), ("en", 390, 844), ("fr", 360, 740), ("de", 360, 740),
                       ("da", 390, 844), ("it", 390, 844), ("es", 390, 844), ("pt", 390, 844)):
        # A first visit: nothing answered yet, so the welcome screen comes up.
        ctx = br.new_context(service_workers="block", viewport={"width": w, "height": h})
        ctx.add_init_script(f"try{{localStorage.setItem('diana.lang','{lang}');}}catch(e){{}}")
        ctx.route(re.compile(r"https://tiles\.openfreemap\.org/.*"), lambda r: r.fulfill(
            status=200, content_type="application/json", body=STYLE))
        ctx.route(re.compile(r"https://(spots\.wwff\.co|raw\.githubusercontent\.com|api\.github\.com)/.*"), lambda r: r.abort())
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(BASE, wait_until="load")
        pg.wait_for_function("() => !document.getElementById('consent').hidden", timeout=20000)
        pg.wait_for_timeout(400)
        r = pg.evaluate("""l => {
          const box = document.getElementById('consentLocScope'), btn = document.getElementById('consentLoc');
          const b = box.getBoundingClientRect(), k = btn.getBoundingClientRect();
          return { t1: box.querySelector('b').textContent, t2: box.querySelector('span[data-i18n]').textContent,
                   want1: STR[l]['consent.locscope1'], want2: STR[l]['consent.locscope2'],
                   why: document.querySelector('[data-i18n="consent.locwhy"]').textContent, wantwhy: STR[l]['consent.locwhy'],
                   whyAbove: document.querySelector('[data-i18n="consent.locwhy"]').getBoundingClientRect().bottom <= b.top,
                   above: b.bottom <= k.top, visible: b.top >= 0 && b.bottom <= innerHeight && b.height > 30,
                   bg: getComputedStyle(box).backgroundColor };
        }""", lang)
        ok(r["t1"] == r["want1"] and r["t2"] == r["want2"] and len(r["t1"]) > 20 and len(r["t2"]) > 20,
           f"{lang}: both sentences ({r['t1'][:40]}…)")
        ok(r["why"] == r["wantwhy"] and len(r["why"]) > 60 and r["whyAbove"],
           f"{lang}: the line on what the location gives and that it works without, above the box")
        ok(any(w in r["t1"].lower() for w in ("programma", "program", "programme", "programm", "programmer", "programmi", "programas")),
           f"{lang}: the first sentence names other programs too")
        ok(r["above"] and r["visible"], f"{lang} at {w}x{h}: above the button and on screen without scrolling")
        ok(r["bg"] not in ("rgba(0, 0, 0, 0)", "transparent"), f"{lang}: in a tinted box of its own ({r['bg']})")
        ctx.close()
    ok(not errs, f"no page errors ({errs[:2]})")
    br.close()

print("\nOK" if not fails else f"\n{len(fails)} failure(s)")
sys.exit(1 if fails else 0)
