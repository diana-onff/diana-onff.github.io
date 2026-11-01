# The remembered admin token is stored encrypted (since 2.2.2).
#
#     python3 build/tests/test_tokencrypt.py
#
# "Remember the token on this device" used to put the token itself in
# localStorage. It now stores only an AES-GCM ciphertext, keyed from a
# passphrase of at least ten characters, and the panel asks for that
# passphrase once per page load. A token left in plain text by an older
# version is taken into memory and deleted from storage at once. While the
# panel is locked a pending upload is shown as waiting, and nothing is sent to
# GitHub; after unlocking, the same follow-up runs as before. Also checked:
# the embed generator writes spots=0 when the spots box is unticked.
import re, json, sys
from playwright.sync_api import sync_playwright
import preconsent  # noqa: F401  answered welcome screen, see preconsent.py

BASE = "http://localhost:8011/web/"
TOKEN = "github_pat_TESTTOKEN_1234567890abcdef"
PASS = "groene specht in het bos"
fails = []


def ok(c, m):
    print(("  ✓ " if c else "  ✗ ") + m)
    if not c:
        fails.append(m)


gh_calls = []


def routes(ctx):
    ctx.route(re.compile(r"https://tiles\.openfreemap\.org/.*"), lambda r: r.fulfill(
        status=200, content_type="application/json",
        body=json.dumps({"version": 8, "sources": {}, "layers": [
            {"id": "bg", "type": "background", "paint": {"background-color": "#e8e4d8"}}]})))
    ctx.route(re.compile(r"https://spots\.wwff\.co/.*"), lambda r: r.fulfill(
        status=200, content_type="application/json", body="[]"))
    ctx.route(re.compile(r"https://docs\.google\.com/.*"), lambda r: r.abort())
    ctx.route(re.compile(r"https://raw\.githubusercontent\.com/.*"), lambda r: r.abort())

    def gh(route):
        gh_calls.append((route.request.url, route.request.headers.get("authorization", "")))
        route.fulfill(status=404, content_type="application/json", body='{"message":"Not Found"}')
    ctx.route(re.compile(r"https://api\.github\.com/.*"), gh)


STORE = "() => Object.keys(localStorage).filter(k => k.startsWith('diana.adm')).reduce((o,k) => (o[k]=localStorage.getItem(k), o), {})"
VIS = """() => ({
  pass: !document.getElementById('admPassBox').hidden,
  unlock: !document.getElementById('admUnlockBox').hidden,
  tokenDisabled: document.getElementById('admToken').disabled,
  remember: document.getElementById('admRemember').checked,
  token: adm.token,
})"""


def open_admin(pg):
    pg.click('#nav button[data-view="viewAdmin"]')
    pg.wait_for_timeout(400)


def leaks(store):
    return [k for k, v in store.items() if TOKEN in (v or "")]


with sync_playwright() as p:
    br = p.chromium.launch()
    ctx = br.new_context(service_workers="block", viewport={"width": 420, "height": 900}, locale="en-GB")
    ctx.add_init_script("try{localStorage.setItem('diana.lang','en');localStorage.setItem('diana.wizard.done','1');}catch(e){}")
    routes(ctx)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE, wait_until="load")
    pg.evaluate(f"""() => {{
      localStorage.setItem('diana.adm.repo', 'diana-onff/diana-onff.github.io');
      localStorage.setItem('diana.adm.src', 'diana-onff/diana-source');
      localStorage.setItem('diana.adm.token', '{TOKEN}');
    }}""")

    print("\n[1] a token remembered in plain text by an older version")
    pg.reload(wait_until="load")
    pg.wait_for_timeout(1200)
    open_admin(pg)
    st = pg.evaluate(STORE)
    v = pg.evaluate(VIS)
    ok("diana.adm.token" not in st, "the plain-text token is gone from storage at load")
    ok(v["token"] == TOKEN, "but still in memory for this page, so nothing running breaks")
    ok(v["remember"] and v["pass"] and not v["unlock"], "remember stays ticked and the passphrase box asks for one")
    ok("unencrypted" in pg.evaluate("() => $('admPassLead').textContent"), "and says why")

    print("\n[2] choosing the passphrase")
    pg.fill("#admPass1", "kort"); pg.fill("#admPass2", "kort"); pg.click("#admPassSave")
    ok("10" in pg.evaluate("() => $('admPassFb').textContent"), "under 10 characters is refused")
    pg.fill("#admPass1", PASS); pg.fill("#admPass2", PASS + "x"); pg.click("#admPassSave")
    ok("match" in pg.evaluate("() => $('admPassFb').textContent"), "two different passphrases are refused")
    ok("diana.adm.tokenenc" not in pg.evaluate(STORE), "nothing stored after a refusal")
    pg.fill("#admPass2", PASS); pg.click("#admPassSave")
    pg.wait_for_function("() => !!localStorage.getItem('diana.adm.tokenenc')", timeout=15000)
    st = pg.evaluate(STORE)
    enc = json.loads(st["diana.adm.tokenenc"])
    ok(enc.get("v") == 1 and enc.get("n") == 600000 and enc.get("ct") and enc.get("iv") and enc.get("salt"),
       "stored as {v, n: 600000, salt, iv, ct}")
    ok(not leaks(st), f"the token appears nowhere in storage in readable form ({leaks(st)})")
    ok(not pg.evaluate(VIS)["pass"], "the passphrase box closes")
    ok(pg.evaluate("() => $('admPass1').value === '' && $('admPass2').value === ''"), "and the passphrase fields are emptied")

    print("\n[3] the next start asks for the passphrase")
    pg.evaluate("""() => localStorage.setItem('diana.adm.pr', JSON.stringify({
        number: 9, branch: 'diana-data-test', url: 'https://example/pr/9',
        file: 'ONFF_2026.kmz', program: 'ONFF', at: new Date().toISOString()}))""")
    gh_calls.clear()
    pg.reload(wait_until="load")
    pg.wait_for_timeout(1500)
    open_admin(pg)
    v = pg.evaluate(VIS)
    ok(v["unlock"] and not v["pass"] and v["tokenDisabled"] and v["token"] == "", "locked: unlock box, token field shut, nothing in memory")
    ok(pg.evaluate("() => !$('admPrCard').hidden && $('admPrHead').textContent.includes('Unlock')"),
       "the pending upload says it waits for unlocking")
    ok(pg.evaluate("() => $('admPrMerge').disabled && $('admPrClose').disabled"), "publish and reject are shut while locked")
    ok(not [c for c in gh_calls if "Bearer" in c[1] and TOKEN in c[1]], "nothing went to GitHub with the token while locked")

    pg.fill("#admPassIn", "verkeerde wachtzin hier"); pg.click("#admUnlockBtn")
    pg.wait_for_function("() => $('admUnlockFb').textContent.includes('Wrong')", timeout=15000)
    ok(pg.evaluate("() => adm.token") == "", "a wrong passphrase unlocks nothing")

    pg.fill("#admPassIn", PASS); pg.press("#admPassIn", "Enter")
    pg.wait_for_function("() => adm.token !== ''", timeout=15000)
    pg.wait_for_timeout(800)
    v = pg.evaluate(VIS)
    ok(v["token"] == TOKEN and not v["unlock"] and not v["tokenDisabled"], "the right one gives the token back, field open again")
    ok(pg.evaluate("() => $('admToken').value") == TOKEN, "and fills in the token field")
    ok([c for c in gh_calls if c[1] == "Bearer " + TOKEN and "/pulls/9" in c[0]],
       "the pending upload is followed up again, with the token")
    ok(not leaks(pg.evaluate(STORE)), "still no readable token in storage after unlocking")

    print("\n[4] a changed token, forgetting, unticking")
    pg.fill("#admToken", TOKEN + "NEW")
    v = pg.evaluate(VIS)
    ok("diana.adm.tokenenc" not in pg.evaluate(STORE) and v["pass"], "a changed token drops the stale copy and asks to save again")
    pg.fill("#admPass1", PASS); pg.fill("#admPass2", PASS); pg.click("#admPassSave")
    pg.wait_for_function("() => !!localStorage.getItem('diana.adm.tokenenc')", timeout=15000)
    pg.uncheck("#admRemember")
    ok("diana.adm.tokenenc" not in pg.evaluate(STORE), "unticking remember deletes the encrypted copy")
    pg.check("#admRemember")
    pg.fill("#admPass1", PASS); pg.fill("#admPass2", PASS); pg.click("#admPassSave")
    pg.wait_for_function("() => !!localStorage.getItem('diana.adm.tokenenc')", timeout=15000)
    pg.reload(wait_until="load")
    pg.wait_for_timeout(1200)
    open_admin(pg)
    pg.click("#admForget")
    v = pg.evaluate(VIS)
    ok("diana.adm.tokenenc" not in pg.evaluate(STORE) and not v["remember"] and not v["unlock"] and not v["tokenDisabled"],
       "'Enter the token again' clears it and opens the token field")

    print("\n[5] the embed code")
    code = pg.evaluate("() => $('embCode').textContent")
    ok("spots=" not in code, "spots on (the default) adds nothing")
    pg.uncheck("#embSpots")
    ok("spots=0" in pg.evaluate("() => $('embCode').textContent"), "spots off writes spots=0")
    pg.check("#embWorld")
    ok("world=1" in pg.evaluate("() => $('embCode').textContent"), "other WWFF areas still writes world=1")

    ok(not errs, f"no page errors ({errs[:2]})")
    br.close()

print("\nOK" if not fails else f"\n{len(fails)} failure(s)")
sys.exit(1 if fails else 0)
