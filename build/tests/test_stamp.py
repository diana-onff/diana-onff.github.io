# A night with only new data is not a new release of the app (since 2.2.12).
#
#     python3 build/tests/test_stamp.py
#
# The version stamp used to be the commit hash. Every nightly data refresh is a
# commit, so every night sw.js came out different and every phone took that for
# a new app: it fetched the whole app again at the first start of the day and
# said "new version". Now the stamp is a fingerprint of the app files only.
#
# What must hold, and is checked here:
#   [1] two publications that differ only in data/: sw.js, js/core.js and
#       index.html, and every other app file, are byte for byte the same;
#   [2] a publication with one app file changed gets a new stamp, so a real
#       package still arrives as a new version;
#   [3] a phone with the app installed, while the server gets new data: no new
#       service worker, no "new version", and the new data IS shown;
#   [4] offline: the app still starts, with the newest data it had;
#   [5] after a real app change on the server, the phone does see a new version.
import functools, http.server, json, pathlib, re, shutil, subprocess, sys, tempfile, threading
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[2]
fails = []


def ok(c, m):
    print(("  ✓ " if c else "  ✗ ") + m)
    if not c:
        fails.append(m)


def publiceer(repo, out):
    r = subprocess.run(["bash", "build/site.sh", str(out)], cwd=repo, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-500:])
    return r.returncode == 0


def app_files(site):
    return {p.relative_to(site).as_posix(): p.read_bytes() for p in site.rglob("*")
            if p.is_file() and p.relative_to(site).parts[0] != "data"}


def stamp(site):
    sw = (site / "sw.js").read_text(encoding="utf-8")
    return re.search(r"const VERSION\s*=\s*'([^']*)'", sw).group(1)


def bump_meta(repo, zones):
    m = repo / "data" / "meta.json"
    d = json.loads(m.read_text(encoding="utf-8"))
    d["zones"] = zones
    d["generated"] = f"2026-11-{10 + zones % 10:02d}T02:17:00Z"
    m.write_text(json.dumps(d, indent=2), encoding="utf-8")


with tempfile.TemporaryDirectory() as tmp:
    tmp = pathlib.Path(tmp)
    repo = tmp / "diana"
    repo.mkdir()
    shutil.copytree(ROOT / "web", repo / "web")
    shutil.copytree(ROOT / "build", repo / "build")
    shutil.copytree(ROOT / "data", repo / "data")

    print("\n[1] only the data changes")
    a, b = tmp / "a", tmp / "b"
    bump_meta(repo, 901)
    ok(publiceer(repo, a), "first publication")
    bump_meta(repo, 902)
    (repo / "data" / "zones" / "onff-activity.json").write_text(
        (repo / "data" / "zones" / "onff-activity.json").read_text(encoding="utf-8").replace('"generated"', '"generated_x"', 1),
        encoding="utf-8")
    ok(publiceer(repo, b), "second publication, other data")
    fa, fb = app_files(a), app_files(b)
    verschil = sorted(k for k in fa.keys() | fb.keys() if fa.get(k) != fb.get(k))
    ok(not verschil, f"every app file byte for byte the same ({verschil[:4]})")
    ok(stamp(a) == stamp(b), f"same service worker name ({stamp(a)})")
    ok((a / "data" / "meta.json").read_bytes() != (b / "data" / "meta.json").read_bytes(), "while the data did change")
    core = (a / "js" / "core.js").read_text(encoding="utf-8")
    ok(re.search(r"const BUILD = '[0-9a-f]{7} · \d\d/\d\d/\d{4}'", core) is not None,
       "the stamp in core.js: fingerprint and date (" + re.search(r"const BUILD = '([^']*)'", core).group(1) + ")")

    print("\n[2] an app file changes")
    c = tmp / "c"
    kaart = repo / "web" / "js" / "map.js"
    origineel = kaart.read_text(encoding="utf-8")
    kaart.write_text(origineel + "\n// a change in the app\n", encoding="utf-8")
    ok(publiceer(repo, c), "third publication, map.js changed")
    ok(stamp(c) != stamp(b), f"a new service worker name ({stamp(b)} -> {stamp(c)})")
    ok((c / "sw.js").read_bytes() != (b / "sw.js").read_bytes(), "so the phone sees a new version")
    kaart.write_text(origineel, encoding="utf-8")

    # ------------------------------------------------------------------ phone
    # One folder served over http, its contents swapped between publications,
    # just as GitHub Pages swaps the site. Service workers are on.
    live = tmp / "live"
    shutil.copytree(a, live)

    class Stil(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
        def end_headers(self):
            self.send_header("Cache-Control", "no-cache")
            super().end_headers()
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Stil, directory=str(live)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    URL = f"http://127.0.0.1:{srv.server_address[1]}/"

    def wissel(naar):
        for p in list(live.iterdir()):
            shutil.rmtree(p) if p.is_dir() else p.unlink()
        for p in naar.iterdir():
            (shutil.copytree if p.is_dir() else shutil.copy2)(p, live / p.name)

    STYLE = json.dumps({"version": 8, "sources": {}, "layers": [{"id": "bg", "type": "background", "paint": {"background-color": "#e8e4d8"}}]})
    with sync_playwright() as p:
        br = p.chromium.launch()
        ctx = br.new_context(viewport={"width": 412, "height": 900})
        ctx.add_init_script("try{localStorage.setItem('diana.lang','en');localStorage.setItem('diana.wizard.done','1');"
                            "localStorage.setItem('diana.consent','1');localStorage.setItem('diana.call','ON3VZ');}catch(e){}")
        ctx.route(re.compile(r"https://tiles\.openfreemap\.org/.*"), lambda r: r.fulfill(status=200, content_type="application/json", body=STYLE))
        ctx.route(re.compile(r"https://(spots\.wwff\.co|raw\.githubusercontent\.com|api\.github\.com|docs\.google\.com|cloud\.umami\.is)/.*"),
                  lambda r: r.fulfill(status=200, content_type="application/json", body="[]"))
        pg = ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))

        def start():
            pg.goto(URL, wait_until="load")
            pg.wait_for_function("() => navigator.serviceWorker.controller && $('setData') && /\\d/.test($('setData').textContent)", timeout=60000)
            pg.wait_for_timeout(2500)

        def toestand():
            return pg.evaluate("""async () => { const r = await navigator.serviceWorker.getRegistration();
              await r.update().catch(() => {}); await new Promise(z => setTimeout(z, 1500));
              return {waiting: !!(r.waiting || r.installing), data: $('setData').textContent,
                      sw: navigator.serviceWorker.controller.scriptURL,
                      status: ($('status') || {}).textContent || ''}; }""")

        print("\n[3] the phone, while the server gets new data")
        pg.goto(URL, wait_until="load")
        pg.wait_for_function("() => navigator.serviceWorker.controller", timeout=60000)
        start()
        t = toestand()
        ok("901" in t["data"], f"first start: the data of then ({t['data'].strip()})")
        wissel(b)
        start()
        t = toestand()
        ok(not t["waiting"], "no new service worker waiting")
        ok("new version" not in t["status"].lower(), "no 'new version' message")
        ok("902" in t["data"], f"and the new data is shown ({t['data'].strip()})")

        print("\n[4] offline")
        ctx.set_offline(True)
        pg.reload(wait_until="load")
        pg.wait_for_function("() => document.documentElement.classList.contains('js-ok') && /\\d/.test($('setData').textContent)", timeout=60000)
        ok("902" in pg.evaluate("() => $('setData').textContent"), "the app starts, with the newest data it had")
        ctx.set_offline(False)

        print("\n[5] a real app change on the server")
        wissel(c)
        start()
        t = toestand()
        ok(t["waiting"], "a new service worker is installed and waiting: the new version arrives")
        ok(not errs, f"no page errors ({errs[:2]})")
        br.close()
    srv.shutdown()

print("\n" + ("ALL OK" if not fails else f"{len(fails)} PROBLEMS: " + " | ".join(fails)))
sys.exit(1 if fails else 0)
