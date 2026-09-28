# What's new: the release overview under Settings.
#
#     python3 build/tests/test_releases.py
#
# Kristof asked for a short overview of what each version added, newest on
# top, opened only from Settings (no message after an update), in Dutch and
# English (every other language shows the English text), with the early
# versions summed up in one block. Checked here:
#   [1] the list itself (no browser): newest entry = APP_VERSION in core.js,
#       versions strictly descending, the "earlier versions" block last, every
#       entry with Dutch and English lines, and no em dash anywhere in the text
#   [2] opening it from Settings on a phone, the current version marked, the
#       text in Dutch, and a long list that scrolls
#   [3] English, and French showing the English text under French labels
#   [4] back: the button at the bottom, the one at the top, and the phone's
#       own back button all return to Settings; afterwards back is no longer
#       tied to this screen, not even after a reload
#   [5] it never shows up by itself
import json, pathlib, re, subprocess, sys
from playwright.sync_api import sync_playwright
import preconsent  # noqa: F401  answered welcome screen, see preconsent.py

ROOT = pathlib.Path(__file__).resolve().parents[2]
BASE = "http://localhost:8011/web/?lang=nl"
fails = []


def ok(c, m):
    print(("  ✓ " if c else "  ✗ ") + m)
    if not c:
        fails.append(m)


print("\n[1] the list itself")
src = (ROOT / "web" / "js" / "releases.js").read_text(encoding="utf-8")
app_version = re.search(r"APP_VERSION = '([^']+)'", (ROOT / "web" / "js" / "core.js").read_text(encoding="utf-8")).group(1)
data = json.loads(subprocess.run(
    ["node", "-e", src.split("function renderReleases")[0] + "\nprocess.stdout.write(JSON.stringify(RELEASES));"],
    capture_output=True, text=True, check=True).stdout)
versions = [r["v"] for r in data if not r.get("earlier")]
ok(versions[0] == app_version, f"the newest entry is the app's own version ({versions[0]} / {app_version})")
key = lambda v: tuple(int(x) for x in v.split("."))
ok(all(key(a) > key(b) for a, b in zip(versions, versions[1:])), f"newest first, no duplicates ({versions})")
ok(data[-1].get("earlier") and not any(r.get("earlier") for r in data[:-1]), "the 'earlier versions' block comes last")
ok(all(r.get("nl") and r.get("en") for r in data), "every entry has Dutch and English lines")
ok(all(re.fullmatch(r"\d{4}-\d{2}-\d{2}", r["date"]) for r in data if not r.get("earlier")), "every version has a date")
text = json.dumps(data, ensure_ascii=False)
ok("\u2014" not in text and "\u2014" not in src, "no em dash in the text")

with sync_playwright() as p:
    br = p.chromium.launch()
    ctx = br.new_context(service_workers="block", viewport={"width": 390, "height": 844},
                         is_mobile=True, has_touch=True)
    ctx.route(re.compile(r"https://tiles\.openfreemap\.org/.*"), lambda r: r.fulfill(
        status=200, content_type="application/json",
        body=json.dumps({"version": 8, "sources": {}, "layers": [
            {"id": "bg", "type": "background", "paint": {"background-color": "#dfe9df"}}]})))
    ctx.route(re.compile(r"https://spots\.wwff\.co/.*"), lambda r: r.fulfill(
        status=200, content_type="application/json", body="[]"))
    ctx.route(re.compile(r"https://docs\.google\.com/.*"), lambda r: r.abort())
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE, wait_until="load")
    pg.wait_for_function("() => zones && zones.features && zones.features.length > 0", timeout=20000)
    pg.wait_for_timeout(2500)

    print("\n[5] it never shows up by itself")
    ok(not pg.evaluate("() => document.getElementById('viewReleases').classList.contains('on')"),
       "not open after starting the app")

    print("\n[2] from Settings")
    pg.tap('#nav button[data-view="viewSet"]')
    pg.wait_for_timeout(300)
    pg.locator("#relOpenBtn").scroll_into_view_if_needed()
    ok(pg.locator("#relOpenBtn").inner_text().strip() == "Wat is er nieuw", "Settings has a 'Wat is er nieuw' button")
    pg.tap("#relOpenBtn")
    pg.wait_for_timeout(300)
    on = pg.evaluate("() => [...document.querySelectorAll('.view.on')].map(v => v.id)")
    ok(on == ["viewReleases"], f"it opens the overview ({on})")
    cards = pg.evaluate("() => [...document.querySelectorAll('#relList .rel')].map(c => ({head: c.querySelector('.relhead b').textContent, current: c.classList.contains('current'), items: c.querySelectorAll('li').length, first: (c.querySelector('li') || {}).textContent}))")
    ok(cards[0]["head"] == app_version and cards[0]["current"], f"the current version first, marked ({cards[0]['head']})")
    ok(len(cards) == len(data) and all(c["items"] > 0 for c in cards), f"every version with its lines ({len(cards)} cards)")
    ok(cards[-1]["head"].startswith("Eerdere versies"), f"'Eerdere versies' last ({cards[-1]['head']!r})")
    ok(cards[0]["first"] == data[0]["nl"][0], "the text in Dutch")
    sc = pg.evaluate("() => { const v = document.getElementById('viewReleases'); return {h: v.scrollHeight, c: v.clientHeight}; }")
    ok(sc["h"] > sc["c"], f"(the list is longer than the screen: {sc['h']} > {sc['c']} px)")
    pg.evaluate("() => { const v = document.getElementById('viewReleases'); v.scrollTop = v.scrollHeight; }")
    ok(pg.evaluate("() => document.getElementById('viewReleases').scrollTop") > 100, "and scrolls down to the end")
    ok(pg.evaluate("""() => { const b = document.getElementById('relBack').getBoundingClientRect();
        const e = document.elementFromPoint(b.left + b.width / 2, b.top + b.height / 2);
        return e && e.id === 'relBack'; }"""), "the back button at the end can be reached and tapped")

    print("\n[4] back to Settings, three ways")
    pg.tap("#relBack")
    pg.wait_for_timeout(300)
    ok(pg.evaluate("() => document.getElementById('viewSet').classList.contains('on')"), "the button at the bottom")
    ok(pg.evaluate("() => history.state") is None, "and the back entry went with it")
    pg.tap("#relOpenBtn"); pg.wait_for_timeout(200)
    pg.tap("#relBackTop"); pg.wait_for_timeout(300)
    ok(pg.evaluate("() => document.getElementById('viewSet').classList.contains('on')"), "the button at the top")
    pg.tap("#relOpenBtn"); pg.wait_for_timeout(200)
    ok(pg.evaluate("() => history.state && history.state.diana") == "back", "(opening it adds one back entry)")
    pg.go_back()
    pg.wait_for_timeout(400)
    ok(pg.evaluate("() => document.getElementById('viewSet').classList.contains('on')")
       and not pg.evaluate("() => document.getElementById('viewReleases').classList.contains('on')"),
       "the phone's back button: back in Settings, still inside Diana")
    ok(pg.url.startswith("http://localhost:8011/web/"), f"(still the same page: {pg.url})")

    # Reloaded with the overview open (the "new version" toast does that):
    # its back entry must not linger as a back press that does nothing.
    pg.tap("#relOpenBtn"); pg.wait_for_timeout(200)
    pg.reload(wait_until="load")
    pg.wait_for_timeout(1500)
    ok(pg.evaluate("() => history.state") is None, "after a reload no dead back entry is left")
    pg.tap('#nav button[data-view="viewSet"]'); pg.wait_for_timeout(300)

    print("\n[3] other languages")
    pg.evaluate("() => { lang = 'en'; applyLang(); }")
    pg.tap("#relOpenBtn"); pg.wait_for_timeout(300)
    en = pg.evaluate("() => ({title: document.querySelector('#viewReleases h1').textContent, first: document.querySelector('#relList li').textContent, earlier: [...document.querySelectorAll('#relList .relhead b')].pop().textContent})")
    ok(en["title"] == "What's new" and en["first"] == data[0]["en"][0] and en["earlier"].startswith("Earlier versions"),
       f"English ({en['title']!r})")
    pg.evaluate("() => { lang = 'fr'; applyLang(); }")
    pg.wait_for_timeout(200)
    fr = pg.evaluate("() => ({title: document.querySelector('#viewReleases h1').textContent, first: document.querySelector('#relList li').textContent})")
    ok(fr["title"] == "Nouveautés" and fr["first"] == data[0]["en"][0],
       f"French: French labels, English text, redrawn while open ({fr['title']!r})")
    ok(not errs, f"no page errors ({errs[:2]})")
    ctx.close()
    br.close()

print("\n" + ("ALL OK" if not fails else f"{len(fails)} PROBLEMS: " + " | ".join(fails)))
sys.exit(1 if fails else 0)
