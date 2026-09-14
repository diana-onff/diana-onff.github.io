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
import json, pathlib, re, sys, tempfile, zipfile
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8011/web/"
fails = []


def ring(lon, lat, d=0.01):
    pts = [(lon, lat), (lon + d, lat), (lon + d, lat + d), (lon, lat + d), (lon, lat)]
    return " ".join(f"{x},{y},0" for x, y in pts)


def kmz(path, program, gebieden):
    """A real KMZ — a zip with a KML in it — because the check in the panel
    unpacks the file itself. A made-up four-byte file would only exercise the
    "cannot read this" branch."""
    pms = "".join(
        f"<Placemark><name>{program}-{num} Gebied {num}</name><Polygon><outerBoundaryIs>"
        f"<LinearRing><coordinates>{ring(lon, lat)}</coordinates></LinearRing>"
        f"</outerBoundaryIs></Polygon></Placemark>" for num, lon, lat in gebieden)
    kml = ('<?xml version="1.0" encoding="UTF-8"?>'
           '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
           f'<name>{program}</name><Folder><name>{program}</name>{pms}</Folder>'
           '</Document></kml>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("doc.kml", kml)

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
    pg.wait_for_timeout(600)
    ok(not pg.evaluate("() => document.getElementById('admSend').disabled"),
       "with a country chosen it opens")

    print("\n[2b] the file is read before it is sent, and may say it is the wrong one")
    # The mistake that actually happens: the right file, the wrong country in
    # the list. The panel used to take that on trust and find out from a failed
    # build twenty-five megabytes later.
    tmp = pathlib.Path(tempfile.mkdtemp())
    kmz(tmp / "DLFF 2026.kmz", "DLFF", [("0001", 13.2, 48.9), ("0002", 12.9, 47.5)])
    kmz(tmp / "OZFF 2026.kmz", "OZFF", [("0001", 11.0, 57.2), ("0002", 10.5, 56.2)])
    (tmp / "geenzip.kmz").write_bytes(b"this is not a zip at all")

    def keur(bestand, program):
        pg.set_input_files("#admFile", str(tmp / bestand))
        pg.select_option("#admProgram", program)
        pg.wait_for_function(
            "() => { const e = document.getElementById('admCheck');"
            "        return !e.hidden && !e.textContent.includes('…'); }", timeout=20000)
        return (pg.evaluate("() => document.getElementById('admCheck').className"),
                pg.evaluate("() => document.getElementById('admCheck').textContent"),
                pg.evaluate("() => document.getElementById('admSend').disabled"))

    cls, txt, dicht = keur("DLFF 2026.kmz", "OZFF")
    ok("bad" in cls, f"a German file sent as Danish is flagged ({cls})")
    ok("DLFF" in txt and "OZFF" in txt, f"naming both countries: {txt!r}")
    ok(dicht, "and the send button stays shut — this one we are sure about")

    cls, txt, dicht = keur("OZFF 2026.kmz", "OZFF")
    ok("good" in cls, f"the matching file passes ({cls})")
    ok(not dicht, "and can be sent")

    cls, txt, dicht = keur("geenzip.kmz", "OZFF")
    ok("bad" not in cls, f"a file the check cannot read is not called wrong ({cls})")
    ok(not dicht, "and is not blocked either — a check that may be wrong may not say no")

    # Back to a state the rest of the file expects.
    pg.set_input_files("#admFile", str(tmp / "DLFF 2026.kmz"))
    pg.select_option("#admProgram", "DLFF")
    pg.wait_for_timeout(800)

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
