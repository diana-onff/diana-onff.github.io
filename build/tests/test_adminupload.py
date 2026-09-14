# Where the admin panel writes in the source repo.
#
# A KMZ does not say which country it is for — the ONFF export carries its
# reference numbers in folder names, and nothing says another country's export
# does the same. So the panel asks, and until this release it did not: a file
# went into incoming/ with nothing to mark it, and a build reading a loose file
# takes it for ONFF. A German release would have been converted as Belgian.
#
# Every country now has its own folder, on the way in and on the way out, and
# that is what this file checks: which paths the panel builds. GitHub is
# replaced by a recorder — nothing here talks to a network, and no token is
# needed.
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

# Stands in for gh(): answers the handful of calls the move makes, and writes
# down every tree it is asked to create — that tree is where the paths live.
STUB = """
window.__calls = [];
gh = async (path, opts) => {
  window.__calls.push({path, body: opts && opts.body ? JSON.parse(opts.body) : null});
  if (/\\/git\\/ref\\/heads\\//.test(path))      return {object: {sha: 'base-sha'}};
  if (/\\/git\\/commits\\/base-sha/.test(path))  return {tree: {sha: 'tree-sha'}};
  if (/\\/git\\/trees\\/tree-sha/.test(path))    return {tree: [
        {type: 'blob', path: 'incoming/ONFF/ONFF 20260101.kmz', sha: 'blob-onff'},
        {type: 'blob', path: 'incoming/DLFF/DLFF 2026.kmz',     sha: 'blob-dlff'},
        {type: 'blob', path: 'incoming/los.kmz',                sha: 'blob-los'}]};
  if (/\\/git\\/trees$/.test(path))              return {sha: 'new-tree'};
  if (/\\/git\\/commits$/.test(path))            return {sha: 'new-commit'};
  return {};
};
"""

with sync_playwright() as p:
    br = p.chromium.launch()
    ctx = br.new_context(service_workers="block", viewport={"width": 420, "height": 860})
    routes(ctx)
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
    # The card lives on the admin screen, so open it — a select nobody can see
    # cannot be clicked, and clicking is the thing being tested.
    pg.evaluate("() => document.querySelector('#nav button[data-view=\"viewAdmin\"]').click()")
    pg.wait_for_timeout(400)

    print("\n[1] the country list is offered, with what Diana already has on top")
    pg.evaluate("() => vulProgrammas()")
    first = pg.evaluate("() => document.getElementById('admProgram').options[0].value")
    ok(first == "", "nothing is preselected — a wrong guess here overwrites a country")
    groups = pg.evaluate("() => [...document.querySelectorAll('#admProgram optgroup')].map(g => g.label)")
    ok(len(groups) == 2, f"two groups: what we have, and the rest ({groups})")
    has = pg.evaluate("() => [...document.querySelectorAll('#admProgram optgroup')][0].children[0].value")
    ok(has == "ONFF", f"the country on board comes first ({has})")
    n = pg.evaluate("() => document.getElementById('admProgram').options.length")
    ok(n > 150, f"and every WWFF programme is offered ({n} entries)")

    print("\n[2] nothing is sent until a country has been chosen")
    pg.evaluate("""() => {
        const dt = new DataTransfer();
        dt.items.add(new File([new Uint8Array([80,75,3,4])], 'DLFF 2026.kmz'));
        document.getElementById('admFile').files = dt.files;
        document.getElementById('admFile').dispatchEvent(new Event('change'));
    }""")
    ok(pg.evaluate("() => document.getElementById('admSend').disabled"),
       "a file on its own is not enough")
    pg.select_option("#admProgram", "DLFF")
    pg.wait_for_timeout(100)
    ok(not pg.evaluate("() => document.getElementById('admSend').disabled"),
       "with a country chosen it opens")

    print("\n[3] the upload lands in that country's folder")
    pg.evaluate("() => { window.__calls = []; }")
    pg.evaluate("() => document.getElementById('admSend').click()")
    pg.wait_for_timeout(600)
    trees = pg.evaluate("() => window.__calls.filter(c => c.path.endsWith('/git/trees'))")
    ok(bool(trees), "a tree was written")
    paths = [e["path"] for e in trees[0]["body"]["tree"]] if trees else []
    ok(paths == ["incoming/DLFF/DLFF 2026.kmz"],
       f"into incoming/DLFF/, not loose in incoming/ ({paths})")
    disp = pg.evaluate("() => window.__calls.find(c => c.path.includes('dispatches'))")
    ok(disp is not None, "and the conversion was started")

    print("\n[4] publishing moves it to that country's folder under source/")
    pg.evaluate("() => { window.__calls = []; }")
    pg.evaluate("() => verplaatsBron('ONFF/ONFF 20260101.kmz', true)")
    pg.wait_for_timeout(400)
    trees = pg.evaluate("() => window.__calls.filter(c => c.path.endsWith('/git/trees'))")
    changes = {e["path"]: e["sha"] for e in trees[0]["body"]["tree"]} if trees else {}
    ok(changes.get("source/ONFF/ONFF 20260101.kmz") == "blob-onff",
       f"it arrives in source/ONFF/ ({sorted(changes)})")
    ok("incoming/ONFF/ONFF 20260101.kmz" in changes
       and changes["incoming/ONFF/ONFF 20260101.kmz"] is None,
       "and leaves the waiting room")

    print("\n[5] a file from before the folders still moves correctly")
    pg.evaluate("() => { window.__calls = []; }")
    pg.evaluate("() => verplaatsBron('los.kmz', true)")
    pg.wait_for_timeout(400)
    trees = pg.evaluate("() => window.__calls.filter(c => c.path.endsWith('/git/trees'))")
    changes = {e["path"]: e["sha"] for e in trees[0]["body"]["tree"]} if trees else {}
    ok(changes.get("source/los.kmz") == "blob-los",
       f"a bare filename still goes straight to source/ ({sorted(changes)})")

    print("\n[6] the waiting room is listed through the country folders")
    listed = pg.evaluate("() => lijstWachtruimte()")
    paths = sorted(x["path"] for x in listed)
    ok(paths == ["DLFF/DLFF 2026.kmz", "ONFF/ONFF 20260101.kmz", "los.kmz"],
       f"everything waiting is found, at whatever depth ({paths})")

    print("\n[7] nothing thrown along the way")
    ok(not errs, f"no page errors: {errs[:2] or 'ok'}")

    print("\n" + ("ALL OK" if not fails else f"{len(fails)} PROBLEMS"))
    br.close()
    sys.exit(1 if fails else 0)
