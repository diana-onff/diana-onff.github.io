"""The privacy package: the welcome screen, the statistics consent, the
privacy page, "clear everything", and the location permission and precision.

This is the one browser test that does NOT import preconsent: it is about
the very first visit, so it has to start from a device that has never
answered the welcome screen.

    python3 -m http.server 8011          # from the repo root
    python3 build/tests/test_privacy.py
"""
import re, json, sys
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8011/web/"
HOBOKEN = {"latitude": 51.1750, "longitude": 4.3450}
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
    ctx.route(re.compile(r"https://spots\.wwff\.co/.*"),
              lambda r: r.fulfill(status=200, content_type="application/json", body="[]"))
    ctx.route(re.compile(r"https://docs\.google\.com/.*"), lambda r: r.abort())
    # Never reach Umami for real; only whether the page asks for it matters.
    ctx.route(re.compile(r"https://cloud\.umami\.is/.*"),
              lambda r: r.fulfill(status=200, content_type="application/javascript", body="/* stub */"))


# Counts position requests, so "the startup request waits" can be checked.
SPY = """
window.__watchCalls = 0;
(() => {
  const g = navigator.geolocation;
  if (!g) return;
  const orig = g.watchPosition.bind(g);
  g.watchPosition = function () { window.__watchCalls++; return orig.apply(null, arguments); };
})();
"""

# A browser where this site has been refused location: the Permissions API
# says so, and every request comes back with code 1.
DENIED = """
(() => {
  const g = navigator.geolocation;
  g.watchPosition = function (ok, err) { window.__watchCalls = (window.__watchCalls || 0) + 1;
    setTimeout(() => err && err({code: 1, message: 'User denied Geolocation'}), 50); return 1; };
  g.clearWatch = function () {};
  const q = navigator.permissions.query.bind(navigator.permissions);
  navigator.permissions.query = d => d && d.name === 'geolocation'
    ? Promise.resolve({state: 'denied', onchange: null}) : q(d);
})();
"""


def fresh(br, granted=True, acc=8, extra=None, locale="en-US"):
    kw = dict(service_workers="block", locale=locale, viewport={"width": 420, "height": 860})
    if granted:
        kw.update(geolocation=dict(HOBOKEN, accuracy=acc), permissions=["geolocation"])
    ctx = br.new_context(**kw)
    routes(ctx)
    ctx.add_init_script(SPY)
    if extra:
        ctx.add_init_script(extra)
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(BASE, wait_until="load")
    pg.wait_for_timeout(1500)
    return ctx, pg, errors


def js(pg, expr):
    return pg.evaluate("() => " + expr)


def loc_text(pg, box="consentLocState"):
    return js(pg, f"document.getElementById('{box}').textContent")


with sync_playwright() as p:
    br = p.chromium.launch()

    print("\n[A] first visit: welcome screen, nothing pre-selected, no Umami, no position request yet")
    ctx, pg, errs = fresh(br, granted=False)
    ok(js(pg, "document.getElementById('consent').hidden") is False, "welcome screen is shown")
    ok(not js(pg, "document.getElementById('consentYes').classList.contains('on')")
       and not js(pg, "document.getElementById('consentNo').classList.contains('on')"),
       "neither statistics answer is pre-selected")
    ok(js(pg, "document.getElementById('umamiScript')") is None, "no Umami before any answer")
    ok(js(pg, "window.__watchCalls") == 0, "startup did not ask for the position behind the welcome screen")
    ok("Not asked yet" in loc_text(pg), f"location line says it has not been asked yet ({loc_text(pg)!r})")
    ok(len(errs) == 0, f"no page errors: {errs}")
    ctx.close()

    print("\n[B] answering without using the location button: the position request follows right after")
    ctx, pg, errs = fresh(br, granted=True, acc=8)
    ok(js(pg, "window.__watchCalls") == 0, "nothing asked while the screen is open")
    pg.click("#consentNo")
    pg.wait_for_timeout(1500)
    ok(js(pg, "document.getElementById('consent').hidden") is True, "screen closed")
    ok(js(pg, "window.__watchCalls") == 1, "exactly one position request, after the answer")
    ok(js(pg, "localStorage.getItem('diana.consent.stats')") == "0", "'no' recorded")
    ok(js(pg, "document.getElementById('umamiScript')") is None, "still no Umami")
    ok(len(errs) == 0, f"no page errors: {errs}")
    ctx.close()

    print("\n[C] the location button asks straight away, reports a sharp fix, and is not asked twice")
    ctx, pg, errs = fresh(br, granted=True, acc=8)
    ok("allowed" in loc_text(pg).lower(), f"already-granted permission is shown ({loc_text(pg)!r})")
    pg.click("#consentLoc")
    pg.wait_for_timeout(1500)
    ok(js(pg, "window.__watchCalls") == 1, "one position request from the tap")
    ok("±8 m" in loc_text(pg) and "Precise enough" in loc_text(pg), f"sharp fix reported ({loc_text(pg)!r})")
    ok(js(pg, "document.querySelector('#consentLocState .locmsg').classList.contains('good')"), "shown as good")
    pg.click("#consentYes")
    pg.wait_for_timeout(1000)
    ok(js(pg, "window.__watchCalls") == 1, "answering the screen does not start a second request")
    ok(js(pg, "!!document.getElementById('umamiScript')"), "'yes' loads Umami")
    ok(len(errs) == 0, f"no page errors: {errs}")
    ctx.close()

    print("\n[D] a fix that stays wide: says so, with the precise-location steps and the indoors note")
    ctx, pg, errs = fresh(br, granted=True, acc=300)
    pg.click("#consentLoc")
    pg.wait_for_timeout(13500)   # a coarse fix is only committed to when the 12 s budget runs out
    txt = loc_text(pg)
    ok("±300 m" in txt and "approximate" in txt, f"coarse fix explained ({txt[:90]!r}...)")
    ok("Indoors" in txt, "indoors note shown")
    ok(js(pg, "document.querySelectorAll('#consentLocState .locstep').length") == 2, "indoors note and steps")
    ok(js(pg, "document.querySelector('#consentLocState .locmsg').classList.contains('warn')"), "shown as a warning")
    ok(len(errs) == 0, f"no page errors: {errs}")
    ctx.close()

    print("\n[E] location refused for this site: says Diana cannot ask again, and how to allow it")
    ctx, pg, errs = fresh(br, granted=False, extra=DENIED)
    ok("blocked" in loc_text(pg), f"refusal shown before any tap ({loc_text(pg)[:60]!r})")
    pg.click("#consentLoc")
    pg.wait_for_timeout(800)
    ok("blocked" in loc_text(pg) and js(pg, "document.querySelectorAll('#consentLocState .locstep').length") == 1,
       "still refused after a tap, with the steps")
    ok(len(errs) == 0, f"no page errors: {errs}")
    ctx.close()

    print("\n[F] a returning visitor: no welcome screen, and the map locates itself at startup as before")
    ctx, pg, errs = fresh(br, granted=True, acc=8,
                          extra="localStorage.setItem('diana.consent.seen','1');localStorage.setItem('diana.consent.stats','0');")
    ok(js(pg, "document.getElementById('consent').hidden") is True, "no welcome screen")
    ok(js(pg, "window.__watchCalls") >= 1, "position requested at startup without a tap")
    ok(len(errs) == 0, f"no page errors: {errs}")
    ctx.close()

    print("\n[G] Settings: statistics toggle, privacy page in English by default and in the chosen language")
    ctx, pg, errs = fresh(br, granted=True, acc=8)
    pg.click("#consentNo")
    pg.wait_for_timeout(500)
    js(pg, "document.querySelector('#nav button[data-view=\"viewSet\"]').click()")
    pg.wait_for_timeout(300)
    ok(js(pg, "document.querySelector('#setStats .seg[data-stats=\"0\"]').classList.contains('on')"), "toggle shows 'no'")
    pg.click("#setStats .seg[data-stats='1']")
    pg.wait_for_timeout(300)
    ok(js(pg, "!!document.getElementById('umamiScript')"), "switching on loads Umami")
    pg.click("#setStats .seg[data-stats='0']")
    pg.wait_for_timeout(300)
    ok(js(pg, "document.getElementById('umamiScript')") is None, "switching off removes it")
    pg.click("#privOpenBtn")
    pg.wait_for_timeout(300)
    ok(js(pg, "document.querySelector('#viewPrivacy h1').textContent") == "Privacy", "privacy page in English")
    ok("±8 m" in loc_text(pg, "privLocState"), f"privacy page shows the location state ({loc_text(pg, 'privLocState')!r})")
    pg.click("#privBack")
    pg.wait_for_timeout(300)
    pg.click("#setLang .seg[data-lang='nl']")
    pg.wait_for_timeout(400)
    pg.click("#privOpenBtn")
    pg.wait_for_timeout(300)
    ok("Positie gevonden" in loc_text(pg, "privLocState"), "location line follows the language")
    ok(js(pg, "document.getElementById('privLocBtn').textContent") == "Controleer mijn locatie nu", "button translated")
    ok(len(errs) == 0, f"no page errors: {errs}")

    print("\n[H] clear everything: back to a first visit")
    pg.on("dialog", lambda d: d.accept())
    pg.click("#privClearBtn2")
    pg.wait_for_timeout(2500)
    ok(js(pg, "localStorage.getItem('diana.consent.seen')") is None, "answer forgotten")
    ok(js(pg, "document.getElementById('consent').hidden") is False, "welcome screen is back")
    ctx.close()

    print("\n[I] an embed never shows the welcome screen and locates as before")
    ctx = br.new_context(service_workers="block", geolocation=dict(HOBOKEN, accuracy=8), permissions=["geolocation"])
    routes(ctx)
    ctx.add_init_script(SPY)
    pg = ctx.new_page()
    pg.goto(BASE + "?embed=1", wait_until="load")
    pg.wait_for_timeout(1500)
    ok(js(pg, "document.getElementById('consent').hidden") is True, "no welcome screen in an iframe")
    ctx.close()

    br.close()

print("\n" + ("ALL OK" if not fails else f"{len(fails)} FAILED: " + "; ".join(fails)))
sys.exit(1 if fails else 0)
