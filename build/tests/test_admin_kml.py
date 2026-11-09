# The admin panel and a .kml, a wrong file type, and an upload resumed after a
# restart (since 2.2.9).
#
#     python3 build/tests/test_admin_kml.py
#
# What happened: a Portuguese release arrived as a loose .kml. The panel sent
# it, a pull request came, and the conversion skipped it without a word (it
# only reads .kmz). The second try, as .kmz, was converted fine, but the app
# restarted while it ran and the follow-up was gone: an older pull request the
# app still remembered made hervatUpload() throw the new upload away.
#
# Checked here, with GitHub replaced by a stub (no network, no token):
#   [1] a .kml is wrapped into a real .kmz on the device, read back by the
#       panel's own check, and the zip itself is valid (Python unzips it to
#       the very same KML);
#   [2] the upload sends that .kmz, into the country's folder;
#   [3] any other extension is refused before anything is sent;
#   [4] after a restart, an older remembered pull request no longer blocks the
#       new upload: its pull request is made and followed;
#   [5] while the conversion runs, the card says so instead of showing nothing;
#   [6] "Live now" lists every country in countries.json;
#   [7] when making the .kmz goes wrong, the panel says automatic conversion did
#       not work and asks for a .kmz, and sends nothing: a deflate that comes
#       out garbled falls back on a plain zip that still checks out; a zip that
#       cannot be read back, and an empty .kml, are refused.
import base64, io, json, pathlib, re, sys, tempfile, zipfile
from playwright.sync_api import sync_playwright
import preconsent  # noqa: F401  answered welcome screen, see preconsent.py

BASE = "http://localhost:8011/web/"
ROOT = pathlib.Path(__file__).resolve().parents[2]
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
    ctx.route(re.compile(r"https://(spots\.wwff\.co|raw\.githubusercontent\.com|api\.github\.com|docs\.google\.com)/.*"),
              lambda r: r.abort())


KML = ('<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
       + "".join(f"<Placemark><name>ONFF-{i:04d} Gebied {i}</name><Point><coordinates>4.{i},50.8,0</coordinates>"
                 "</Point></Placemark>" for i in range(1, 400))
       + "</Document></kml>")

STUB = """
window.__calls = [];
window.__branchExists = true;
gh = async (path, opts) => {
  const method = (opts && opts.method) || 'GET';
  window.__calls.push({path, method, body: opts && opts.body ? JSON.parse(opts.body) : null});
  if (/\\/pulls\\?state=open/.test(path))              return [];
  if (/\\/pulls$/.test(path) && method === 'POST')      return {number: 99, html_url: 'https://github.com/x/y/pull/99',
                                                              title: 't', head: {ref: JSON.parse(opts.body).head, sha: 's'}};
  if (/\\/pulls\\/\\d+$/.test(path))                    return {number: 99, state: 'open', html_url: 'u', title: 't', head: {sha: 's', ref: 'b'}};
  if (/\\/git\\/ref\\/heads\\/diana-data-/.test(path)) { if (!window.__branchExists) throw new Error('404'); return {object: {sha: 'x'}}; }
  if (/\\/git\\/ref\\/heads\\//.test(path))             return {object: {sha: 'base-sha'}};
  if (/\\/git\\/commits\\/base-sha/.test(path))         return {tree: {sha: 'tree-sha'}};
  if (/\\/git\\/trees\\/tree-sha/.test(path))           return {tree: []};
  if (/\\/git\\/trees$/.test(path))                     return {sha: 'new-tree'};
  if (/\\/git\\/commits$/.test(path))                   return {sha: 'new-commit'};
  if (/\\/actions\\/runs/.test(path))                   return {workflow_runs: []};
  if (/\\/issues\\/\\d+\\/comments/.test(path))         return [];
  return {};
};
ghRuw = async () => '';
wachtOpBranch = async () => true;
"""

with sync_playwright() as p:
    br = p.chromium.launch()
    ctx = br.new_context(service_workers="block", viewport={"width": 420, "height": 900})
    routes(ctx)
    ctx.add_init_script("""
        localStorage.setItem('diana.lang', 'en');
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
    pg.evaluate("() => document.querySelector('#nav button[data-view=\"viewAdmin\"]').click()")
    pg.wait_for_timeout(400)
    pg.evaluate("() => vulProgrammas()")
    tmp = pathlib.Path(tempfile.mkdtemp())
    (tmp / "onff_20261110.kml").write_text(KML, encoding="utf-8")
    (tmp / "onff_20261110.gpx").write_text("<gpx/>", encoding="utf-8")

    def verdict():
        pg.wait_for_function("() => { const e = $('admCheck'); return !e.hidden && !e.textContent.includes('…'); }",
                             timeout=20000)
        return pg.evaluate("() => [$('admCheck').className, $('admCheck').textContent, $('admSend').disabled]")

    print("\n[1] a .kml is wrapped into a .kmz on the device")
    pg.set_input_files("#admFile", str(tmp / "onff_20261110.kml"))
    pg.select_option("#admProgram", "ONFF")
    cls, txt, dicht = verdict()
    ok("onff_20261110.kmz" in txt, f"the line says it goes out as .kmz ({txt[:70]})")
    ok("good" in cls and "ONFF" in txt, f"and the panel's own check reads that .kmz: {cls}")
    ok(not dicht, "the send button opens")
    b64 = pg.evaluate("""async () => { const f = await teVersturen();
        const b = new Uint8Array(await f.arrayBuffer()); let s = '';
        for (let i = 0; i < b.length; i += 0x8000) s += String.fromCharCode.apply(null, b.subarray(i, i + 0x8000));
        return [f.name, btoa(s)]; }""")
    raw = base64.b64decode(b64[1])
    z = zipfile.ZipFile(io.BytesIO(raw))
    ok(z.testzip() is None and z.namelist() == ["doc.kml"], f"a valid zip with doc.kml in it ({z.namelist()})")
    ok(z.read("doc.kml").decode("utf-8") == KML, "that unpacks to exactly the KML chosen")
    ok(len(raw) < len(KML.encode()), f"and smaller than the KML ({len(raw)} < {len(KML.encode())} bytes)")

    print("\n[2] the upload sends the .kmz into the country's folder")
    pg.evaluate("() => { window.__calls = []; }")
    pg.click("#admSend")
    pg.wait_for_function("() => window.__calls.some(c => c.path.endsWith('/pulls') && c.method === 'POST')", timeout=15000)
    trees = pg.evaluate("() => window.__calls.filter(c => c.path.endsWith('/git/trees'))")
    paths = [e["path"] for e in trees[0]["body"]["tree"]] if trees else []
    ok(paths == ["incoming/ONFF/onff_20261110.kmz"], f"into incoming/ONFF/ as .kmz ({paths})")
    blobs = pg.evaluate("() => window.__calls.filter(c => c.path.endsWith('/git/blobs'))")
    sent = base64.b64decode(blobs[0]["body"]["content"]) if blobs else b""
    ok(sent[:4] == b"PK\x03\x04", "the blob sent is the zip, not the bare KML")
    ok(pg.evaluate("() => huidigePr() && huidigePr().number") == 99, "and its pull request is followed")

    print("\n[3] any other file type is refused before anything is sent")
    pg.evaluate("() => { window.__calls = []; }")
    pg.set_input_files("#admFile", str(tmp / "onff_20261110.gpx"))
    pg.wait_for_timeout(300)
    r = pg.evaluate("() => [$('admCheck').className, $('admCheck').textContent, $('admSend').disabled, $('admCheck').hidden]")
    ok("bad" in r[0] and ".gpx" in r[1] and not r[3], f"an error under the file ({r[1][:60]})")
    ok(r[2], "the send button stays shut, with the country still chosen")
    pg.evaluate("() => { $('admSend').disabled = false; $('admSend').click(); }")
    pg.wait_for_timeout(600)
    ok(not pg.evaluate("() => window.__calls.filter(c => c.method !== 'GET').length"),
       "even a forced press sends nothing")

    print("\n[4] after a restart an older pull request no longer blocks the upload under way")
    pg.evaluate("""() => { window.__calls = []; window.__branchExists = true;
        bewaarPr({number: 18, head: {ref: 'diana-data-202611091556'}, html_url: 'u'}, 'oud.kml', 'CTFF');
        bewaarBezig({branch: 'diana-data-202611091637', file: 'ctff_20261110.kmz', program: 'CTFF', at: new Date().toISOString()}); }""")
    pg.evaluate("() => hervatUpload()")
    pg.wait_for_timeout(500)
    made = pg.evaluate("() => window.__calls.find(c => c.path.endsWith('/pulls') && c.method === 'POST')")
    ok(made is not None and made["body"]["head"] == "diana-data-202611091637",
       "the pull request for the new branch is made")
    ok(pg.evaluate("() => huidigePr().branch") == "diana-data-202611091637" and pg.evaluate("() => huidigBezig()") is None,
       "and followed instead of the old #18")

    print("\n[5] while the conversion still runs, the card says so")
    pg.evaluate("""() => { window.__calls = []; window.__branchExists = false; bewaarPr(null);
        bewaarBezig({branch: 'diana-data-202611091700', file: 'ctff_20261110.kmz', program: 'CTFF', at: new Date().toISOString()}); }""")
    pg.evaluate("() => hervatUpload()")
    pg.wait_for_timeout(800)
    card = pg.evaluate("() => [$('admPrCard').hidden, $('admPrHead').textContent]")
    ok(not card[0] and "ctff_20261110.kmz" in card[1] and "running" in card[1], f"visible: {card[1][:70]}")
    ok(pg.evaluate("() => hervatTimer !== null"), "and Diana tries again by itself")
    pg.evaluate("() => { window.__branchExists = true; clearTimeout(hervatTimer); hervatTimer = null; return hervatUpload(); }")
    pg.wait_for_timeout(500)
    ok(pg.evaluate("() => huidigePr() && huidigePr().branch") == "diana-data-202611091700",
       "once the branch is there, its pull request follows")
    pg.evaluate("""() => { bewaarPr(null);
        bewaarBezig({branch: 'diana-data-202611090100', file: 'x.kmz', program: 'CTFF', at: '2026-11-09T01:00:00Z'});
        window.__branchExists = false; return toonPr(); }""")
    pg.wait_for_timeout(400)
    ok("an hour" in pg.evaluate("() => $('admPrHead').textContent") and pg.evaluate("() => !!$('admRunForget')"),
       "after an hour: said so, with a button to forget it")
    pg.click("#admRunForget")
    pg.wait_for_timeout(400)
    ok(pg.evaluate("() => huidigBezig()") is None and pg.evaluate("() => $('admPrCard').hidden"), "which clears it")

    print("\n[6] Live now lists every country")
    want = [c["program"] for c in json.loads((ROOT / "data" / "countries.json").read_text())["countries"]]
    pg.evaluate("() => loadMeta()")
    pg.wait_for_timeout(600)
    shown = pg.evaluate("() => [...document.querySelectorAll('#admCurrent .admland b')].map(b => b.textContent)")
    ok(shown == want, f"{shown}")

    print("\n[7] when the conversion on the device goes wrong")
    (tmp / "leeg.kml").write_text("", encoding="utf-8")
    pg.evaluate("() => { bewaarPr(null); bewaarBezig(null); window.__calls = []; }")

    def kies(naam):
        pg.set_input_files("#admFile", str(tmp / naam))
        pg.select_option("#admProgram", "ONFF")
        pg.wait_for_function("() => { const e = $('admCheck'); return !e.hidden && !e.textContent.includes('…'); }", timeout=20000)
        return pg.evaluate("() => [$('admCheck').className, $('admCheck').textContent, $('admSend').disabled]")

    # (a) the compressor hands back garbage that is smaller than the input
    pg.evaluate("""() => { window.__CS = window.CompressionStream;
        window.CompressionStream = class { constructor(){ const ts = new TransformStream({
          transform(c, ctl){ ctl.enqueue(new Uint8Array([1, 2, 3, 4, 5, 6, 7, 8])); } });
          this.readable = ts.readable; this.writable = ts.writable; } }; }""")
    pg.set_input_files("#admFile", str(tmp / "leeg.kml"))   # a different choice, so it is made afresh
    pg.wait_for_timeout(300)
    cls, txt, dicht = kies("onff_20261110.kml")
    ok("good" in cls and not dicht, f"a garbled deflate is caught and a plain zip is used instead ({cls})")
    raw = base64.b64decode(pg.evaluate("""async () => { const f = await teVersturen();
        const b = new Uint8Array(await f.arrayBuffer()); let s = '';
        for (let i = 0; i < b.length; i += 0x8000) s += String.fromCharCode.apply(null, b.subarray(i, i + 0x8000));
        return btoa(s); }"""))
    z = zipfile.ZipFile(io.BytesIO(raw))
    ok(z.read("doc.kml").decode("utf-8") == KML and z.infolist()[0].compress_type == 0,
       "which unpacks to exactly the KML, stored")
    pg.evaluate("() => { window.CompressionStream = window.__CS; }")

    # (b) the zip cannot be read back at all
    pg.evaluate("() => { window.__KE = kmzEntry; kmzEntry = async () => null; }")
    pg.set_input_files("#admFile", str(tmp / "leeg.kml"))
    pg.wait_for_timeout(300)
    cls, txt, dicht = kies("onff_20261110.kml")
    ok("bad" in cls and "automatically" in txt and ".kmz" in txt, f"automatic conversion did not work, upload a .kmz: {txt[:80]}")
    ok(dicht, "and the send button stays shut")
    pg.evaluate("() => { window.__calls = []; $('admSend').disabled = false; $('admSend').click(); }")
    pg.wait_for_timeout(800)
    ok(not pg.evaluate("() => window.__calls.filter(c => c.method !== 'GET').length"), "even a forced press sends nothing")
    pg.evaluate("() => { kmzEntry = window.__KE; }")

    # (c) an empty .kml
    pg.set_input_files("#admFile", str(tmp / "onff_20261110.kml"))
    pg.wait_for_timeout(300)
    cls, txt, dicht = kies("leeg.kml")
    ok("bad" in cls and "automatically" in txt and dicht, f"an empty .kml is refused the same way ({txt[:50]})")

    ok(not errs, f"no page errors ({errs[:2]})")
    br.close()

print("\n" + ("ALL OK" if not fails else f"{len(fails)} PROBLEMS: " + " | ".join(fails)))
sys.exit(1 if fails else 0)
