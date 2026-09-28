# The service worker and the data files: fresh when possible, never worse
# offline or on one bar of signal.
#
#     python3 build/tests/test_sw_data.py
#
# Every other browser test runs with the service worker blocked. This one runs
# it for real, over a site built by build/site.sh and served by a server in
# this test that can change files underneath it (the way a nightly data
# refresh changes them on GitHub Pages), answer slowly, trickle a file out,
# break a download halfway, or be unreachable altogether.
#
# Background (Package 7): sw.js used to take only the files directly in data/
# network-first, so data/zones/ (boundaries, points, QSO counts per country)
# and data/sites/ (website links) stayed on the phone as they were until the
# user tapped "new version". Every data file now goes through dataVers():
# no copy yet -> network, however slow; a copy -> the fresh file only if it
# arrives complete within 3.5 s, else the copy at once, with the download
# finishing in the background for the next start. A half-downloaded file is
# never stored or shown.
#
#   [1] a changed QSO count in data/zones/ reaches the app on the next start
#   [2] so does a changed link in data/sites/
#   [3] and a file directly in data/ (that already worked)
#   [4] server unreachable: the app starts with the last copies
#   [5] the app's own scripts stay cache-first (they change with a release)
#   [6] first reply slower than 3.5 s: the copy, without waiting
#   [7] boundary file trickling in: the copy at once, the new file stored in
#       the background and used on the next start
#   [8] download breaking halfway: the copy, and the copy stays good
#   [9] no copy on the phone and a slow server: wait for it, do not give up
# With the sw.js from before Package 7 every check that expects the new data
# fails (the zones and sites files never refresh); a first version of this
# change failed [7], [8] and [9] instead, which is why they are here.
import http.server, json, os, pathlib, re, shutil, socket, subprocess, sys, tempfile, threading, time
from playwright.sync_api import sync_playwright
import preconsent  # noqa: F401  answered welcome screen, see preconsent.py

ROOT = pathlib.Path(__file__).resolve().parents[2]
fails = []


def ok(c, m):
    print(("  ✓ " if c else "  ✗ ") + m)
    if not c:
        fails.append(m)


def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def touch_json(path, change):
    """Rewrite a JSON file with `change` applied and move its modification time
    on, so the server really serves it as a new version."""
    doc = json.loads(path.read_text(encoding="utf-8"))
    change(doc)
    before = path.stat().st_mtime
    path.write_text(json.dumps(doc), encoding="utf-8")
    os.utime(path, (before + 5, before + 5))


def rename_first(name):
    def change(doc):
        f = next(x for x in doc["features"] if x["properties"].get("ref") == "ONFF-0001")
        f["properties"]["name"] = name
    return change


# Per path, how the server misbehaves: ("head", seconds) waits before the
# first reply; ("trickle", bytes per second) sends the body slowly;
# ("drop", n) sends n bytes of the body and then hangs up.
MODE = {}
STATE = {"down": False, "down_hits": 0}

tmp = tempfile.mkdtemp()
try:
    site = pathlib.Path(tmp) / "_site"
    r = subprocess.run(["bash", "build/site.sh", str(site)], cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout[-400:], r.stderr[-400:]); sys.exit(1)
    (site / "data" / "sites").mkdir(exist_ok=True)
    sites = site / "data" / "sites" / "onff.json"
    sites.write_text(json.dumps({"refs": {"ONFF-0001": "https://old.example.be/"}}), encoding="utf-8")
    act = site / "data" / "zones" / "onff-activity.json"
    zon = site / "data" / "zones" / "onff.geojson"
    meta = site / "data" / "meta.json"
    core = site / "js" / "core.js"
    ok(act.is_file() and zon.is_file() and meta.is_file(), "site built with its data files")
    # The worker now refuses to install when one of the app's own files cannot
    # be fetched (a 404 is only allowed for data files, listed in both
    # layouts). So a SHELL_FILES entry that no longer exists would block every
    # future update: each one must be in the published site.
    swsrc = (site / "sw.js").read_text(encoding="utf-8")
    listed = re.findall(r"'(\.{1,2}/[^']*)'", swsrc[swsrc.index("const SHELL_FILES"):swsrc.index("];", swsrc.index("const SHELL_FILES"))])
    app_files = [u for u in listed if u.startswith("./") and "/data/" not in u]
    missing = [u for u in app_files if not (site / (u[2:] or "index.html")).exists()]
    ok(len(app_files) > 20 and not missing, f"every app file sw.js precaches exists in the site ({len(app_files)} files, missing: {missing})")

    class Server(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(site), **k)

        def do_GET(self):
            if STATE["down"]:
                STATE["down_hits"] += 1
                self.close_connection = True
                return                       # no reply at all: a network error
            m = MODE.get(self.path.split("?")[0])
            if m and m[0] == "head":
                time.sleep(m[1])
            return super().do_GET()

        def copyfile(self, source, outputfile):
            m = MODE.get(self.path.split("?")[0])
            try:
                if not m or m[0] == "head":
                    super().copyfile(source, outputfile)
                elif m[0] == "trickle":
                    while True:
                        chunk = source.read(max(1, m[1] // 10))
                        if not chunk:
                            break
                        outputfile.write(chunk); outputfile.flush(); time.sleep(0.1)
                elif m[0] == "drop":
                    outputfile.write(source.read(m[1])); outputfile.flush()
                    self.close_connection = True
            except (BrokenPipeError, ConnectionResetError):
                pass

        def log_message(self, *a):
            pass

    class Threaded(http.server.ThreadingHTTPServer):
        # socketserver's default backlog is 5: a worker installing fetches some
        # forty files at once, and the rest were refused (net::ERR_FAILED),
        # leaving a half-filled cache that had nothing to do with the code
        # under test. GitHub Pages has no such limit.
        request_queue_size = 128

    httpd = Threaded(("127.0.0.1", free_port()), Server)
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    BASE = f"http://127.0.0.1:{httpd.server_address[1]}/"

    with sync_playwright() as p:
        br = p.chromium.launch()
        ctx = br.new_context(service_workers="allow", viewport={"width": 420, "height": 860})
        ctx.route(re.compile(r"https://tiles\.openfreemap\.org/.*"), lambda r: r.fulfill(
            status=200, content_type="application/json",
            body=json.dumps({"version": 8, "sources": {}, "layers": [
                {"id": "bg", "type": "background", "paint": {"background-color": "#e8e4d8"}}]})))
        ctx.route(re.compile(r"https://spots\.wwff\.co/.*"), lambda r: r.fulfill(
            status=200, content_type="application/json", body="[]"))
        ctx.route(re.compile(r"https://docs\.google\.com/.*"), lambda r: r.abort())
        pg = ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))

        READY = ("() => typeof activity !== 'undefined' && Object.keys(activity).length > 0"
                 " && zones && zones.features && zones.features.length > 0")

        def start(timeout=30000):
            """A fresh start of the app; returns the seconds until map and counts are there."""
            t0 = time.time()
            pg.goto(BASE, wait_until="load")
            pg.wait_for_function(READY, timeout=timeout)
            return time.time() - t0

        q = lambda: pg.evaluate("() => activity['ONFF-0001'] && activity['ONFF-0001'].q")
        link = lambda: pg.evaluate(
            "() => fetch('data/sites/onff.json').then(r => r.json()).then(d => d.refs['ONFF-0001'])")
        name = lambda: pg.evaluate(
            "() => zones.features.find(f => f.properties.ref === 'ONFF-0001').properties.name")
        areas = lambda: pg.evaluate("() => zones.features.length")

        # First visit installs the worker; from the second start it is in control.
        start()
        for _ in range(100):      # not wait_for_function: it takes a returned Promise as "true" at once
            if pg.evaluate("() => navigator.serviceWorker.getRegistration()"
                           ".then(r => !!(r && r.active && r.active.state === 'activated'))"):
                break
            time.sleep(0.2)
        pg.reload(wait_until="load")
        pg.wait_for_function("() => !!navigator.serviceWorker.controller", timeout=15000)
        start()
        ok(pg.evaluate("() => !!navigator.serviceWorker.controller"), "the service worker is in control")
        q0, link0, n0 = q(), link(), areas()
        ok(bool(q0) and link0 == "https://old.example.be/" and n0 > 900,
           f"first reading: QSO count {q0}, link {link0}, {n0} areas")

        print("\n[1] a nightly refresh changes a QSO count in data/zones/")
        touch_json(act, lambda d: d["refs"]["ONFF-0001"].update({"q": 987654}))
        start()
        ok(q() == 987654, f"the next start shows the new count ({q0} -> {q()})")

        print("\n[2] and a link in data/sites/")
        touch_json(sites, lambda d: d["refs"].update({"ONFF-0001": "https://new.example.be/"}))
        start()
        ok(link() == "https://new.example.be/", f"the new link comes through ({link()})")

        print("\n[3] a file directly in data/ (this already worked)")
        touch_json(meta, lambda d: d.update({"release": "TEST-RELEASE"}))
        start()
        rel = pg.evaluate("() => fetch('data/meta.json').then(r => r.json()).then(d => d.release)")
        ok(rel == "TEST-RELEASE", f"meta.json fresh too ({rel})")

        print("\n[4] server unreachable: the app starts with the last copies")
        STATE["down"] = True
        took = start()
        ok(STATE["down_hits"] > 0, f"(the server really refused everything: {STATE['down_hits']} attempts)")
        ok(q() == 987654 and link() == "https://new.example.be/" and areas() == n0,
           f"count, link and all {areas()} areas from the last start")
        ok(took < 5, f"without waiting for a time limit ({took:.1f} s)")
        STATE["down"] = False

        print("\n[5] the app's own scripts stay cache-first")
        original = core.read_text(encoding="utf-8")
        core.write_text(original.replace("const APP_VERSION", "window.__changedCore = 1;\nconst APP_VERSION", 1),
                        encoding="utf-8")
        before = core.stat().st_mtime
        os.utime(core, (before + 5, before + 5))
        start()
        ok(pg.evaluate("() => window.__changedCore") is None,
           "a changed script is not picked up outside a release (that is the job of 'new version')")
        core.write_text(original, encoding="utf-8")

        print("\n[6] first reply slower than 3.5 s")
        MODE["/data/zones/onff-activity.json"] = ("head", 6)
        touch_json(act, lambda d: d["refs"]["ONFF-0001"].update({"q": 111}))
        took = start()
        ok(q() == 987654, f"the app starts with the copy on the phone ({q()})")
        ok(took < 6, f"without waiting for the slow server ({took:.1f} s)")
        MODE.clear()
        time.sleep(3)                 # the slow reply finishes in the background
        start()
        ok(q() == 111, f"and the next start has the new count ({q()})")

        print("\n[7] a boundary file trickling in (3.8 MB at 300 kB/s)")
        touch_json(zon, rename_first("NAME-AFTER-REFRESH"))
        MODE["/data/zones/onff.geojson"] = ("trickle", 300_000)
        took = start()
        ok(areas() == n0 and name() != "NAME-AFTER-REFRESH",
           f"the map is there with the copy on the phone ({areas()} areas, {name()!r})")
        ok(took < 6.5, f"within the time limit, not after the whole download ({took:.1f} s)")
        time.sleep(16)                # let the background download finish
        MODE.clear()
        STATE["down"] = True          # prove the next start reads the cache, not the server
        start()
        ok(name() == "NAME-AFTER-REFRESH" and areas() == n0,
           f"the next start has the new file, stored in the background ({name()!r})")
        STATE["down"] = False

        print("\n[8] a boundary download breaking halfway")
        touch_json(zon, rename_first("NAME-NEVER-COMPLETE"))
        MODE["/data/zones/onff.geojson"] = ("drop", 200_000)
        took = start()
        ok(areas() == n0 and name() == "NAME-AFTER-REFRESH",
           f"the copy on the phone, all {areas()} areas ({name()!r})")
        ok(took < 6.5, f"at once ({took:.1f} s)")
        MODE.clear()
        STATE["down"] = True
        start()
        ok(areas() == n0 and name() == "NAME-AFTER-REFRESH",
           "and that copy is still whole afterwards: the broken download was not stored")
        STATE["down"] = False

        print("\n[9] no copy on the phone and a slow server")
        pg.evaluate("""async () => {
          for (const k of await caches.keys()) {
            const c = await caches.open(k);
            for (const req of await c.keys()) if (req.url.includes('/data/zones/onff')) await c.delete(req);
          }}""")
        MODE["/data/zones/onff.geojson"] = ("head", 6)
        took = start(timeout=40000)
        ok(areas() == n0, f"the boundaries still arrive ({areas()} areas after {took:.1f} s)")
        MODE.clear()

        ok(not errs, f"no page errors ({errs[:2]})")
        ctx.close()
        br.close()
    httpd.shutdown()
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("\n" + ("ALL OK" if not fails else f"{len(fails)} PROBLEMS: " + " | ".join(fails)))
sys.exit(1 if fails else 0)
