# The admin panel's follow-up: does it actually keep checking on its own?
#
#     python3 build/tests/test_admin_poll.py
#
# Two things prompted this file. First: right after a push, GitHub's Actions
# API can take anywhere from a few seconds to close to a minute before it lists
# a run for it at all — toonPr() used to treat that gap as "nothing running"
# (bezig === false) and never armed its own poll, so the panel just sat on "in
# afwachting" until someone pressed "verversen" by hand. Second: a phone does
# not sit and wait — you switch to GitHub, or WhatsApp, or the screen locks,
# and the browser suspends its timers (this poll included) the moment the tab
# goes into the background. Coming back is now treated as a refresh in its own
# right: a visibilitychange listener re-runs toonPr() — which also renders the
# waiting-room cleanup list, its very first line, the one part of the panel
# that had no polling of its own at all.
#
# GitHub is replaced by a recorder, the same way test_adminupload.py does it:
# no network, no token, and the pull request is invented on the spot.
import json, re, sys
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8011/web/"
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


# window.__runsQueue is the test's current canned answer for .../actions/runs —
# set fresh before each step, so the test controls exactly what "not registered
# yet" versus "still running" looks like without any real waiting.
# window.__pullCalls counts how often toonPr() has actually asked GitHub for
# the pull request itself — the one call every pass through toonPr() makes,
# poll or visibilitychange alike — so the test can tell a real refresh
# happened apart from watching the DOM.
STUB = """
window.__pullCalls = 0;
window.__runsQueue = [];   // no runs listed yet at all
gh = async (path) => {
  if (/\\/pulls\\/7$/.test(path)) {
    window.__pullCalls++;
    return {number: 7, state: 'open', title: 'Nieuwe DLFF-release',
            html_url: 'https://example/pr/7', head: {sha: 'deadbeef'}};
  }
  if (/\\/actions\\/runs\\?/.test(path)) return {workflow_runs: window.__runsQueue};
  if (/\\/issues\\/7\\/comments/.test(path)) return [];
  return {};
};
"""

RUNNING = [{"name": "build-data", "status": "in_progress", "conclusion": None}]
DONE    = [{"name": "build-data", "status": "completed", "conclusion": "success"}]

with sync_playwright() as p:
    br = p.chromium.launch()
    ctx = br.new_context(service_workers="block", viewport={"width": 420, "height": 860})
    routes(ctx)
    # `diana.adm.pr` is deliberately NOT seeded here. adm.repo/src/token/path are
    # read once, synchronously, at script load — those have to be in place before
    # the page even starts. But unlockAdmin() also fires toonPr() once immediately
    # on load (its very own setTimeout(...,0)), using the REAL gh(), before this
    # test gets a chance to install the stub below — and a real fetch to
    # api.github.com fails here (no network, no valid token), which toonPr()
    # correctly reads as "this pull request is gone" and clears it right back out
    # of localStorage (bewaarPr(null)). Seeding the PR record up front just means
    # that very first, unstubbed call wipes the fixture before the test ever runs.
    # So: nothing to wipe going in — the PR record is written after the stub is
    # in place, exactly like a real one would be moments after a real upload.
    ctx.add_init_script("""
        localStorage.setItem('diana.adm.repo', 'diana-onff/diana-onff.github.io');
        localStorage.setItem('diana.adm.src', 'diana-onff/diana-source');
        localStorage.setItem('diana.adm.token', 'fake-token-for-the-stub');
        localStorage.setItem('diana.adm.path', 'incoming/');
    """)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE, wait_until="load")
    pg.wait_for_timeout(2500)
    pg.evaluate(STUB)
    pg.evaluate("""() => {
        localStorage.setItem('diana.adm.pr', JSON.stringify({
            number: 7, branch: 'diana-data-test', url: 'https://example/pr/7',
            file: 'DLFF/DLFF 2026.kmz', program: 'DLFF', at: new Date().toISOString()}));
    }""")
    ok(pg.evaluate("() => document.body.classList.contains('admin')"),
       "the admin panel unlocked itself from the saved repo (?admin=1 not even needed)")

    print("\n[1] a push with no run listed yet is not mistaken for 'nothing to wait for'")
    calls_before = pg.evaluate("() => window.__pullCalls")
    pg.evaluate("() => toonPr()")
    pg.wait_for_timeout(300)
    ok(pg.evaluate("() => window.__pullCalls") > calls_before, "toonPr() actually asked GitHub")
    ok(pg.evaluate("() => document.getElementById('admPrMerge').disabled"),
       "publishing stays shut while nothing is confirmed yet")
    ok(pg.evaluate("() => prPoll !== null && prPoll !== undefined"),
       "and — this was the bug — it keeps checking back on its own, not just while something is 'bezig'")

    print("\n[2] once a run is actually seen, the ordinary poll takes over the same way")
    pg.evaluate("(runs) => { window.__runsQueue = runs; }", RUNNING)
    pg.evaluate("() => toonPr()")
    pg.wait_for_timeout(300)
    ok(pg.evaluate("() => prPoll !== null"), "still polling — a run is genuinely running now")

    print("\n[3] and stops once there is nothing left to wait for")
    pg.evaluate("(runs) => { window.__runsQueue = runs; }", DONE)
    pg.evaluate("() => toonPr()")
    pg.wait_for_timeout(300)
    ok(not pg.evaluate("() => document.getElementById('admPrMerge').disabled"), "publishing opens up")
    ok(pg.evaluate("() => prPoll === null"), "and the poll lets go — nothing more will change on its own")

    print("\n[4] coming back to the app is treated as a refresh")
    # Simulate the phone-locked-and-came-back case directly: the point is not
    # to fake real OS-level backgrounding (Playwright cannot, and does not need
    # to) but to check that THIS listener, on THIS event, really does re-ask.
    pg.evaluate("(runs) => { window.__runsQueue = runs; }", RUNNING)  # something changed while "away"
    calls_before = pg.evaluate("() => window.__pullCalls")
    pg.evaluate("""() => {
        Object.defineProperty(document, 'visibilityState', {value: 'visible', configurable: true});
        document.dispatchEvent(new Event('visibilitychange'));
    }""")
    pg.wait_for_timeout(300)
    ok(pg.evaluate("() => window.__pullCalls") > calls_before,
       "becoming visible again re-ran toonPr() without anyone pressing 'verversen'")

    print("\n[5] the same tap also refreshes the waiting-room list, not only the pull request")
    # renderCleanup() is the very first line of toonPr() — this is what makes a
    # file left in incoming/ by a merge done outside the app (see ADMIN.md) show
    # up again without a manual tap on "opruimen" either.
    pg.evaluate("""() => {
        window.__cleanupCalls = (window.__cleanupCalls || 0);
        const orig = renderCleanup;
        renderCleanup = (...a) => { window.__cleanupCalls++; return orig(...a); };
    }""")
    pg.evaluate("""() => {
        document.dispatchEvent(new Event('visibilitychange'));
    }""")
    pg.wait_for_timeout(300)
    ok(pg.evaluate("() => window.__cleanupCalls") > 0, "renderCleanup() ran too")

    print("\n[6] nothing thrown along the way")
    ok(not errs, f"no page errors: {errs[:2] or 'ok'}")

    print("\n" + ("ALL OK" if not fails else f"{len(fails)} PROBLEMS"))
    br.close()
    sys.exit(1 if fails else 0)
