# The start screen when a script blocker stops every script (since 2.2.11).
#
#     python3 build/tests/test_scripts_blocked.py
#
# Reported: with a strict script blocker Diana stayed on the start screen for
# good, even after "Trust" was clicked (the page was not reloaded). Nothing in
# the app can run then, so the start screen now carries a box that needs no
# script: the stylesheet shows it after 20 s, and core.js hides it the moment
# the app's own scripts run (and the map library came in).
#   [1] every script blocked: the box appears, with F5 / Ctrl+R in it, readable
#       on a small phone;
#   [2] only the map library blocked: our own scripts notice, so the box shows
#       at once and the start screen stays;
#   [3] a normal start: the box never shows;
#   [4] a very slow connection (the map library takes 14 s to arrive): the
#       box does not show either. That is why it waits 20 s and not 10.
import re, json, sys, time
from playwright.sync_api import sync_playwright
import preconsent  # noqa: F401  answered welcome screen, see preconsent.py

BASE = "http://localhost:8011/web/"
fails = []


def ok(c, m):
    print(("  ✓ " if c else "  ✗ ") + m)
    if not c:
        fails.append(m)


def run(br, block):
    ctx = br.new_context(service_workers="block", viewport={"width": 360, "height": 740}, java_script_enabled=True)
    ctx.add_init_script("try{localStorage.setItem('diana.lang','en');localStorage.setItem('diana.wizard.done','1');}catch(e){}")
    ctx.route(re.compile(r"https://tiles\.openfreemap\.org/.*"), lambda r: r.fulfill(
        status=200, content_type="application/json",
        body=json.dumps({"version": 8, "sources": {}, "layers": [{"id": "bg", "type": "background", "paint": {"background-color": "#e8e4d8"}}]})))
    ctx.route(re.compile(r"https://(spots\.wwff\.co|raw\.githubusercontent\.com|api\.github\.com|docs\.google\.com|cloud\.umami\.is)/.*"), lambda r: r.abort())
    if block:
        ctx.route(re.compile(block), lambda r: r.abort())
    pg = ctx.new_page()
    pg.goto(BASE, wait_until="load")
    return ctx, pg


def box(pg):
    return pg.evaluate("""() => { const b = document.getElementById('splashHelp');
      if (!b) return {gone: true};
      const r = b.getBoundingClientRect(), cs = getComputedStyle(b);
      return {shown: cs.visibility === 'visible' && cs.display !== 'none' && +cs.opacity > 0.9,
              inview: r.top >= 0 && r.bottom <= innerHeight && r.width > 250, text: b.textContent}; }""")


with sync_playwright() as p:
    br = p.chromium.launch()

    print("\n[1] every script of the site blocked")
    ctx, pg = run(br, r".*diana.*\.js$|localhost:8011/web/.*\.js$")
    pg.wait_for_timeout(15000)
    ok(not box(pg)["shown"], "not at 15 s: a slow start on a weak connection is not a blocked one")
    pg.wait_for_timeout(6500)
    b = box(pg)
    ok(b.get("shown"), "after 20 s the box is there")
    ok(b.get("inview"), "and fully on a 360 x 740 screen")
    ok("F5" in b.get("text", "") and "Ctrl+R" in b.get("text", "") and "Cmd+R" in b.get("text", ""), "it says to reload with F5 or Ctrl+R (Mac: Cmd+R)")
    ok("diana-onff.github.io" in b.get("text", ""), "and which site to allow")
    ok(pg.evaluate("() => !document.documentElement.classList.contains('js-ok')"), "no script ran")
    ctx.close()

    print("\n[2] only the map library blocked")
    ctx, pg = run(br, r".*/vendor/maplibre-gl\.js$")
    pg.wait_for_timeout(3000)
    ok(box(pg).get("shown"), "our own scripts know at once: the box shows straight away")
    pg.wait_for_timeout(13000)
    ok(box(pg).get("shown"), "and the start screen stays, also after the usual 12 s")
    ctx.close()

    print("\n[3] a normal start")
    ctx, pg = run(br, None)
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.wait_for_timeout(1500)
    ok(pg.evaluate("() => document.documentElement.classList.contains('js-ok')"), "the app marks that its scripts run")
    seen = False
    for _ in range(22):
        b = box(pg)
        if b.get("shown"):
            seen = True
        pg.wait_for_timeout(1000)
    ok(not seen, "the box never shows, also not after 20 s")
    ok(not errs, f"no page errors ({errs[:2]})")
    ctx.close()

    print("\n[4] a very slow first visit: the scripts take 14 s to arrive")
    ctx, pg = run(br, None)
    def slow(route):
        time.sleep(14)
        route.continue_()
    pg.route(re.compile(r".*/vendor/maplibre-gl\.js$"), slow)
    pg.goto(BASE, wait_until="commit")
    seen = False
    for _ in range(24):
        if box(pg).get("shown"):
            seen = True
        pg.wait_for_timeout(1000)
    ok(pg.evaluate("() => document.documentElement.classList.contains('js-ok')"), "the app started in the end")
    ok(not seen, "and the box never showed")
    ctx.close()
    br.close()

print("\n" + ("ALL OK" if not fails else f"{len(fails)} PROBLEMS: " + " | ".join(fails)))
sys.exit(1 if fails else 0)
