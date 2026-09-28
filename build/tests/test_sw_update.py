# A new release must not take the downloaded map and the data with it.
#
#     python3 build/tests/test_sw_update.py
#
# build/site.sh gives the service worker's cache a new name on every build, and
# every nightly data refresh is a build, so a new worker arrives nearly every
# night. On activation it deletes the previous worker's caches. The map tiles
# saved with "Download area" and the per-country data used to live in caches
# named after the version as well, so they went with it: download an area at
# home, let the app update overnight, start it without signal in the field,
# and there was no basemap and no boundaries.
#
# Tiles and data now live in caches with fixed names ('diana-tiles',
# 'diana-data'); only the app itself is versioned. Real service workers, over a
# site built by build/site.sh, served by a server that can be switched off.
# The server is switched off BEFORE each takeover, so whatever the app shows
# afterwards can only have come out of the caches on the device:
#   [0] today's worker, release to release, loses the downloaded tiles and the
#       boundaries (what this change fixes; shown, so the test keeps proving it)
#   [1] today's worker -> the new one: boundaries, QSO counts and tiles carried
#       over, offline; the old caches gone
#   [2] two copies of a file: the newer one is kept, whichever cache it is in
#       (a newer one fetched at installation; and a newer one the old worker
#       fetched while the new one was already waiting)
#   [3] a move that was cut short (old cache still there, file not yet moved):
#       still found, offline; the next release completes the move
#   [4] from then on a release only replaces the app's own cache
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


def old_sw():
    """The sw.js that is live today: the last committed one that still named its
    tile cache after the version."""
    for rev in ("HEAD", "HEAD~1", "HEAD~2", "HEAD~3", "HEAD~4", "HEAD~5"):
        r = subprocess.run(["git", "show", f"{rev}:web/sw.js"], cwd=ROOT, capture_output=True, text=True)
        if r.returncode == 0 and "`${VERSION}-tiles`" in r.stdout:
            return r.stdout
    return None


def stamp(source, name):
    out, n = re.subn(r"(const VERSION\s*=\s*')[^']*(')", lambda m: m.group(1) + name + m.group(2), source, count=1)
    assert n == 1
    return out


TILE = "https://tiles.openfreemap.org/planet/12/2100/1370.pbf"
STATE = {"down": False}

OLD = old_sw()
NEW = (ROOT / "web" / "sw.js").read_text(encoding="utf-8")
if OLD is None:
    print("No older sw.js with a versioned tile cache in the last commits: nothing to migrate from. Skipped.")
    sys.exit(0)

tmp = tempfile.mkdtemp()
try:
    site = pathlib.Path(tmp) / "_site"
    r = subprocess.run(["bash", "build/site.sh", str(site)], cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout[-400:], r.stderr[-400:]); sys.exit(1)
    swfile = site / "sw.js"
    meta = site / "data" / "meta.json"

    def set_release(name):
        m = json.loads(meta.read_text(encoding="utf-8")); m["release"] = name
        meta.write_text(json.dumps(m), encoding="utf-8")
        time.sleep(1.1)          # a later Date header than whatever came before

    class Server(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(site), **k)

        def do_GET(self):
            if STATE["down"]:
                self.close_connection = True
                return
            return super().do_GET()

        def end_headers(self):
            # Every answer fresh from the server, never the browser's own
            # HTTP cache: what is tested here is the service worker's caches.
            self.send_header("Cache-Control", "no-cache")
            super().end_headers()

        def log_message(self, fmt, *a):
            if os.environ.get("SWLOG"):
                with open(os.environ["SWLOG"], "a") as f:
                    f.write(("DOWN " if STATE["down"] else "") + (fmt % a) + "\n")

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

    READY = ("() => typeof activity !== 'undefined' && Object.keys(activity).length > 0"
             " && zones && zones.features && zones.features.length > 0")

    def new_context(br):
        ctx = br.new_context(service_workers="allow", viewport={"width": 420, "height": 860})
        ctx.route(re.compile(r"https://spots\.wwff\.co/.*"), lambda r: r.fulfill(
            status=200, content_type="application/json", body="[]"))
        ctx.route(re.compile(r"https://docs\.google\.com/.*"), lambda r: r.abort())
        return ctx

    def wait_js(pg, expr, timeout=30):
        """Poll until an async browser-side check comes back true. Not
        wait_for_function: that takes a returned Promise itself as "truthy" and
        stops at once, before the promise has even settled."""
        end = time.time() + timeout
        while True:
            try:
                if pg.evaluate(expr):
                    return
            except Exception:
                pass            # the page reloading itself in between (offline.js)
            if time.time() > end:
                raise TimeoutError(expr)
            time.sleep(0.2)

    def first_visit(pg, version_name, source):
        swfile.write_text(stamp(source, version_name), encoding="utf-8")
        pg.goto(BASE, wait_until="load")
        wait_js(pg, "() => navigator.serviceWorker.getRegistration().then(r => !!(r && r.active && r.active.state === 'activated'))")
        pg.reload(wait_until="load")
        pg.wait_for_function("() => !!navigator.serviceWorker.controller", timeout=15000)
        pg.wait_for_function(READY, timeout=30000)

    def publish(pg, version_name, source):
        """A new release on the server; the open app installs it, and it waits."""
        swfile.write_text(stamp(source, version_name), encoding="utf-8")
        pg.evaluate("() => navigator.serviceWorker.getRegistration().then(r => r.update())")
        wait_js(pg, "() => navigator.serviceWorker.getRegistration().then(r => !!(r && r.waiting))", 60)

    def take_over(pg, prev_name, version_name):
        """Tapping 'new version', with the server already unreachable: from here on
        nothing can come from the network."""
        STATE["down"] = True
        pg.evaluate("""() => navigator.serviceWorker.getRegistration().then(r => {
            const w = r.waiting || r.installing; if (w) w.postMessage({type: 'SKIP_WAITING'}); })""")
        wait_js(pg, "() => navigator.serviceWorker.getRegistration().then(r => !r.waiting && !r.installing"
                    " && !!r.active && r.active.state === 'activated')", 60)
        pg.wait_for_timeout(1500)            # the reload offline.js does by itself
        cold_start(pg)                       # a cold start, still offline

    def cold_start(pg):
        # The reload offline.js starts on its own can still be under way and
        # cancel this navigation; one more try settles it.
        for attempt in range(3):
            try:
                pg.goto(BASE, wait_until="load")
                return
            except Exception:
                pg.wait_for_timeout(1500)
        pg.goto(BASE, wait_until="load")

    def look(pg):
        try:
            pg.wait_for_function(READY, timeout=12000)
        except Exception:
            pass
        return pg.evaluate("""async (tile) => {
          const keys = await caches.keys();
          let tileHit = false;
          for (const k of keys) if (await (await caches.open(k)).match(tile)) tileHit = true;
          let served = false;
          try { await fetch(tile, {mode: 'no-cors'}); served = true; } catch {}
          let release = null;
          try { release = (await (await fetch('data/meta.json')).json()).release; } catch {}
          const full = [];
          for (const k of keys) if ((await (await caches.open(k)).keys()).length) full.push(k);
          return {
            areas: (typeof zones !== 'undefined' && zones && zones.features) ? zones.features.length : 0,
            qso: (typeof activity !== 'undefined' && activity['ONFF-0001']) ? activity['ONFF-0001'].q : null,
            tileHit, served, release, keys: full.sort() };
        }""", TILE)

    def download_area(pg, cache_name):
        """What 'Download area' leaves behind: a tile in the worker's tile cache
        (put there directly: the real tile server is not reachable here)."""
        pg.evaluate("""([name, url]) => caches.open(name).then(c =>
            c.put(url, new Response('TILE-DATA', {headers: {'content-type': 'application/x-protobuf'}})))""",
                    [cache_name, TILE])

    with sync_playwright() as p:
        br = p.chromium.launch()

        print("\n[0] today's worker, release to release")
        ctx = new_context(br); pg = ctx.new_page()
        first_visit(pg, "diana-old1", OLD)
        download_area(pg, "diana-old1-tiles")
        publish(pg, "diana-old2", OLD)
        take_over(pg, "diana-old1", "diana-old2")
        o = look(pg)
        STATE["down"] = False
        ok(not o["tileHit"] and o["areas"] == 0,
           f"(confirmed: afterwards offline no tiles and {o['areas']} areas; this is what gets fixed)")
        ctx.close()

        print("\n[1] today's worker -> the new one")
        set_release("R1")
        ctx = new_context(br); pg = ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        first_visit(pg, "diana-old1", OLD)
        download_area(pg, "diana-old1-tiles")
        before = pg.evaluate("() => ({areas: zones.features.length, qso: activity['ONFF-0001'].q})")
        # [2a] the new worker's installation fetches a newer meta.json than the one on the phone
        set_release("R2-at-install")
        publish(pg, "diana-new1", NEW)
        take_over(pg, "diana-old1", "diana-new1")
        o = look(pg)
        ok(o["areas"] == before["areas"] and o["qso"] == before["qso"],
           f"offline after the takeover: {o['areas']} areas and the QSO counts, moved from the old cache")
        ok(o["tileHit"] and o["served"], "the downloaded tiles came along and are served")
        ok(o["keys"] == ["diana-data", "diana-new1-shell", "diana-tiles"], f"the old caches are gone ({o['keys']})")

        print("\n[2] two copies of a file: the newer one stays")
        ok(o["release"] == "R2-at-install", f"a newer copy fetched at installation beats the old one ({o['release']})")
        STATE["down"] = False
        ctx.close()
        # [2b] the other way round: the new worker waits for days while the old
        # one keeps fetching newer copies.
        set_release("R3-first")
        ctx = new_context(br); pg = ctx.new_page()
        pg.on("pageerror", lambda e: errs.append(str(e)))
        first_visit(pg, "diana-old3", OLD)
        publish(pg, "diana-new3", NEW)          # installs, with R3-first in diana-data
        set_release("R4-while-waiting")
        pg.reload(wait_until="load")            # the old worker, still in charge, fetches R4
        pg.wait_for_function(READY, timeout=30000)
        pg.evaluate("() => fetch('data/meta.json').then(r => r.json())")
        take_over(pg, "diana-old3", "diana-new3")
        o = look(pg)
        ok(o["release"] == "R4-while-waiting",
           f"a newer copy the old worker fetched while the new one waited beats the one from installation ({o['release']})")
        STATE["down"] = False

        print("\n[3] a move that was cut short")
        # As if the takeover stopped halfway: an old cache is still there with the
        # boundaries and a tile in it, and neither has reached the new caches yet.
        pg.evaluate("""async (tile) => {
          const data = await caches.open('diana-data'), tiles = await caches.open('diana-tiles');
          const old = await caches.open('diana-cut-shell'), oldt = await caches.open('diana-cut-tiles');
          for (const req of await data.keys())
            if (req.url.includes('/data/zones/onff')) { await old.put(req, await data.match(req)); await data.delete(req); }
          await oldt.put(tile, new Response('TILE-DATA'));
          await tiles.delete(tile);
        }""", TILE)
        STATE["down"] = True
        cold_start(pg)
        o = look(pg)
        ok(o["areas"] == before["areas"] and o["served"],
           f"offline, boundaries ({o['areas']}) and the tile are still found in the old cache")
        STATE["down"] = False
        publish(pg, "diana-new4", NEW)
        take_over(pg, "diana-new3", "diana-new4")
        o = look(pg)
        ok(o["areas"] == before["areas"] and o["served"] and o["keys"] == ["diana-data", "diana-new4-shell", "diana-tiles"],
           f"the next release completes the move, offline ({o['areas']} areas, {o['keys']})")
        STATE["down"] = False

        print("\n[4] from now on, every night")
        download_area(pg, "diana-tiles")
        publish(pg, "diana-new5", NEW)
        take_over(pg, "diana-new4", "diana-new5")
        o = look(pg)
        ok(o["areas"] == before["areas"] and o["tileHit"] and o["served"],
           f"offline: boundaries ({o['areas']}) and tiles still there")
        ok(o["keys"] == ["diana-data", "diana-new5-shell", "diana-tiles"], f"only the app's own cache replaced ({o['keys']})")
        STATE["down"] = False
        ok(not errs, f"no page errors ({errs[:2]})")
        ctx.close()
        br.close()
    httpd.shutdown()
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("\n" + ("ALL OK" if not fails else f"{len(fails)} PROBLEMS: " + " | ".join(fails)))
sys.exit(1 if fails else 0)
