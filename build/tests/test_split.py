"""The app is cut into web/js/*.js, and that cut has to stay sound.

    python3 build/tests/test_split.py

These files were one app.js of nearly 5800 lines until Fase 6. They are plain
scripts, not modules: they share one global scope and run in the order the
<script> tags give them. Nothing enforces that by itself, so this file does.

What it guards, and why each one is here rather than obvious:

  1. Every file under js/ is actually loaded. Add a file, forget the tag, and
     nothing complains — the functions in it simply never exist.
  2. Every loaded file is in SHELL_FILES in sw.js. Forget that one and the app
     works perfectly online and is broken offline, which you discover in a wood
     with no signal and no way to fix it.
  3. Nothing throws at load. A function declaration is hoisted only inside its
     own file now; a load-time reference to something declared in a later file
     used to work as one file and would now be undefined.
  4. Things declared in one file are visible in the others, which is the whole
     premise of using plain scripts instead of modules.
  5. The build stamp placeholder still sits in exactly one file, or site.sh
     will refuse to build.
"""
import re, json, os, sys, pathlib
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8011/web/"
WEB = pathlib.Path(__file__).resolve().parents[2] / "web"
fails = []


def ok(c, m):
    print(("  ✓ " if c else "  ✗ ") + m)
    if not c:
        fails.append(m)


html = (WEB / "index.html").read_text(encoding="utf-8")
tags = re.findall(r'<script src="js/([^"]+)"', html)
on_disk = sorted(p.name for p in (WEB / "js").glob("*.js"))

print("\n[1] every file on disk is loaded, and every tag points at a real file")
ok(sorted(tags) == on_disk,
   f"index.html loads exactly the {len(on_disk)} files in js/ "
   f"(missing tag: {sorted(set(on_disk) - set(tags))}, "
   f"tag without file: {sorted(set(tags) - set(on_disk))})")
ok(len(tags) == len(set(tags)), "no file is loaded twice")

print("\n[2] the service worker can take the whole app offline")
sw = (WEB / "sw.js").read_text(encoding="utf-8")
shell = re.search(r"SHELL_FILES = \[(.*?)\]", sw, re.S).group(1)
cached = set(re.findall(r"'\./js/([^']+)'", shell))
ok(cached == set(on_disk),
   f"SHELL_FILES lists all of js/ (not cached: {sorted(set(on_disk) - cached)})")

print("\n[3] the build stamp is findable exactly once")
hits = [p.name for p in (WEB / "js").glob("*.js")
        if "'__DIANA_BUILD__'" in p.read_text(encoding="utf-8")]
ok(len(hits) == 1, f"exactly one file holds the placeholder ({hits})")

with sync_playwright() as p:
    exe = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
    br = p.chromium.launch(executable_path=exe if os.path.exists(exe) else None)
    ctx = br.new_context(service_workers="block", viewport={"width": 420, "height": 860})
    ctx.route(re.compile(r"https://tiles\.openfreemap\.org/.*"), lambda r: r.fulfill(
        status=200, content_type="application/json",
        body=json.dumps({"version": 8, "sources": {}, "layers": [
            {"id": "bg", "type": "background", "paint": {"background-color": "#e8e4d8"}}]})))
    ctx.route(re.compile(r"https://spots\.wwff\.co/static/.*"), lambda r: r.fulfill(
        status=200, content_type="application/json", body="[]"))
    ctx.route(re.compile(r"https://docs\.google\.com/.*"), lambda r: r.abort())
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE, wait_until="load")
    pg.wait_for_timeout(2500)

    print("\n[4] the split app boots clean")
    ok(not errs, f"no page errors at load: {errs[:3] if errs else 'none'}")
    n = pg.evaluate("() => document.querySelectorAll('script[src^=\"js/\"]').length")
    ok(n == len(on_disk), f"the browser really loaded all {len(on_disk)} scripts ({n})")

    print("\n[5] one global scope: each file can see the others")
    #      name            declared in            used by
    for name, home in [("$", "core.js"), ("remember", "core.js"), ("t", "i18n.js"),
                       ("STR", "i18n-strings.js"), ("map", "map.js"), ("toggle", "map.js"),
                       ("syncSwitch", "map.js"), ("refLookup", "self-spot.js"),
                       ("agendaOpen", "agenda.js"), ("prefetchArea", "offline.js"),
                       ("haversine", "geo.js"), ("showStatus", "geo.js")]:
        ok(pg.evaluate(f"() => typeof {name} !== 'undefined'"), f"{name} (from {home}) is reachable")
    ok(pg.evaluate("() => Object.keys(STR).length === 7"), "all seven languages survived the cut")

    print("\n[6] the one line the split had to change is still wired up")
    ok(pg.evaluate("() => typeof document.getElementById('btnOffline').onclick === 'function'"),
       "btnOffline has a handler — prefetchArea lives in a later file")

    print("\n[7] every screen still opens, with nothing thrown")
    for view in ["viewSpots", "viewSelf", "viewAgendaNew", "viewSession",
                 "viewSet", "viewHeat", "viewRules"]:
        b = pg.query_selector(f'[data-view="{view}"]')
        if not b:
            continue
        pg.evaluate(f"() => document.querySelector('[data-view=\"{view}\"]').click()")
        pg.wait_for_timeout(180)
        ok(pg.is_visible(f"#{view}"), f"{view} opens")
    ok(not errs, f"still nothing thrown after visiting every screen: {errs[:3] if errs else 'none'}")

    br.close()

print()
if fails:
    print(f"FAILED — {len(fails)} check(s):")
    for f in fails:
        print("  - " + f)
    sys.exit(1)
print("ALL OK")
