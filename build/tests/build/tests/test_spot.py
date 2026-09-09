"""Self-spotting through the Worker: checking, sending, and every way it can
fail.

    python3 build/tests/test_spot.py

The Worker is stubbed, so this never touches the real proxy and never reaches
WWFF. What it does exercise is the part that is easy to get wrong and
impossible to notice: that Send only opens after a check came back good, that
any edit closes it again, and that each kind of refusal produces the right
message and only offers the old route where the old route would actually
help.
"""
import re, json, os, sys
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8011/web/"
WORKER = re.compile(r"https://diana-spotline\.diana-onff\.workers\.dev/spot")
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
    ctx.route(re.compile(r"https://spots\.wwff\.co/static/.*"), lambda r: r.fulfill(
        status=200, content_type="application/json", body="[]"))
    ctx.route(re.compile(r"https://docs\.google\.com/.*"), lambda r: r.abort())


# What the stubbed Worker answers next, and what it was sent.
reply = {"status": 200, "body": {"dryrun": True}}
seen = []


def worker_route(r):
    try:
        seen.append(json.loads(r.request.post_data or "{}"))
    except Exception:
        seen.append({})
    if reply.get("abort"):
        r.abort()
        return
    r.fulfill(status=reply["status"], content_type="application/json",
              headers={"Access-Control-Allow-Origin": "*"},
              body=json.dumps(reply["body"]))


def fill(pg, ref="ONFF-0001", freq="14285", mode="SSB", act="ON3VZ/P", spotter="ON3VZ"):
    pg.fill("#spActivator", act)
    pg.fill("#spSpotter", spotter)
    pg.fill("#spReference", ref)
    pg.fill("#spFreq", freq)
    pg.select_option("#spMode", mode)
    pg.dispatch_event("#spMode", "input")
    pg.wait_for_timeout(120)


with sync_playwright() as p:
    exe = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
    br = p.chromium.launch(executable_path=exe if os.path.exists(exe) else None)
    ctx = br.new_context(service_workers="block", viewport={"width": 420, "height": 860})
    routes(ctx)
    ctx.route(WORKER, worker_route)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE, wait_until="load")
    pg.wait_for_timeout(2000)
    pg.evaluate("() => document.querySelector('[data-view=\"viewSelf\"]').click()")
    pg.wait_for_timeout(300)

    print("\n[1] references are checked against our own data, without the network")
    calls = []
    pg.on("request", lambda r: calls.append(r.url))
    for ref, want in [("ONFF-0001", "good"), ("ONFF-9999", "bad"),
                      ("XXFF-0001", "bad"), ("NONSENSE", "bad"), ("VKFF-0456", "good")]:
        pg.fill("#spReference", ref)
        pg.wait_for_timeout(150)
        cls = pg.evaluate("() => document.getElementById('fbReference').className")
        txt = pg.evaluate("() => document.getElementById('fbReference').textContent")
        got = "good" if "good" in cls else ("bad" if "bad" in cls else "")
        ok(got == want, f"{ref} → {want or 'neutral'} ({txt[:52]})")
    ok(not any("references/validate" in u for u in calls),
       "no call to the reference API was made at all")
    ok("Hautes Fagnes" in pg.evaluate(
        "() => { document.getElementById('spReference').value='ONFF-0001';"
        "checkReference(); return document.getElementById('fbReference').textContent }"),
       "an ONFF reference shows the name of the reserve, not just a tick")

    # With the world layer loaded — which it is by default — a foreign reference
    # can be judged outright. Without it we must not pretend to know: the
    # honest answer is the programme's country and an explicit "not checked
    # here", never a rejection. That branch is what an embed with the world
    # layer switched off actually runs, so it is worth proving.
    zonder = pg.evaluate("""() => {
      const bak = worldPoints;
      worldPoints = {type:'FeatureCollection', features:[]};
      document.getElementById('spReference').value = 'VKFF-0456';
      checkReference();
      const fb = document.getElementById('fbReference');
      const out = {text: fb.textContent, cls: fb.className};
      worldPoints = bak;
      return out;
    }""")
    ok("bad" not in zonder["cls"], "without the world layer a foreign reference is not rejected")
    ok("Australia" in zonder["text"], f"the country is named instead ({zonder['text'][:44]})")

    print("\n[2] Send stays shut until a check has come back good")
    fill(pg)
    ok(pg.is_disabled("#spSend"), "Send is closed on a fresh, valid form")
    ok(not pg.is_disabled("#spCheck"), "Check is open once the form holds together")

    reply = {"status": 200, "body": {"dryrun": True, "ok": True}}
    seen.clear()
    pg.click("#spCheck")
    pg.wait_for_timeout(400)
    ok(len(seen) == 1 and seen[0].get("dryrun") is True, "the check goes out with dryrun: true")
    ok(seen[0].get("reference") == "ONFF-0001" and seen[0].get("frequency_khz") == 14285,
       "and carries the form contents, frequency as a number")
    ok(not pg.is_disabled("#spSend"), "Send opens after an accepted check")

    print("\n[3] any edit closes it again")
    pg.fill("#spFreq", "14290")
    pg.wait_for_timeout(200)
    ok(pg.is_disabled("#spSend"), "Send is closed again after the frequency changes")
    ok("opnieuw" in pg.evaluate("() => document.getElementById('fbSend').textContent").lower()
       or "again" in pg.evaluate("() => document.getElementById('fbSend').textContent").lower(),
       "and it says so")

    print("\n[4] a real send, and what comes back")
    fill(pg)
    reply = {"status": 200, "body": {"dryrun": True}}
    pg.click("#spCheck")
    pg.wait_for_timeout(300)
    reply = {"status": 201, "body": {"spot_id": 4242}}
    seen.clear()
    pg.click("#spSend")
    pg.wait_for_timeout(400)
    ok(len(seen) == 1 and "dryrun" not in seen[0], "the real send carries no dryrun")
    fb = pg.evaluate("() => document.getElementById('fbSend').textContent")
    ok("4242" in fb, f"the spot_id is shown ({fb[:48]})")
    ok("good" in pg.evaluate("() => document.getElementById('fbSend').className"),
       "and it reads as a confirmation, not a warning")
    ok(pg.is_disabled("#spSend"), "Send closes again: sending the same spot twice is a new decision")

    print("\n[5] a duplicate is reassuring, not an error")
    fill(pg, freq="7130")
    reply = {"status": 200, "body": {}}
    pg.click("#spCheck"); pg.wait_for_timeout(300)
    reply = {"status": 409, "body": {"error": "duplicate"}}
    pg.click("#spSend"); pg.wait_for_timeout(400)
    ok("good" in pg.evaluate("() => document.getElementById('fbSend').className"),
       "a 409 is shown as good news")
    ok(pg.is_hidden("#spFallback"),
       "and the old route is not offered — the spot is already there")

    print("\n[6] a refusal by Spotline is shown as Spotline's own words")
    fill(pg, freq="14300")
    reply = {"status": 400, "body": {"error": "no", "details": ["frequency_khz 14300 is not in an amateur band"]}}
    pg.click("#spCheck"); pg.wait_for_timeout(400)
    fb = pg.evaluate("() => document.getElementById('fbSend').textContent")
    ok("not in an amateur band" in fb, f"the explanation comes through ({fb[:44]})")
    ok(pg.is_disabled("#spSend"), "and Send stays shut")
    ok(pg.is_hidden("#spFallback"),
       "no fallback offered: the old route would refuse it too, just silently")

    print("\n[7] the daily ceiling has its own message, in the user's language")
    fill(pg)
    reply = {"status": 503, "body": {"error": "daily", "limit": "day"}}
    pg.click("#spCheck"); pg.wait_for_timeout(400)
    fb = pg.evaluate("() => document.getElementById('fbSend').textContent")
    ok("gratis" in fb or "free" in fb, f"it explains the free tier ({fb[:52]})")
    ok("morgen" in fb or "tomorrow" in fb, "and says when to come back")
    ok(not pg.is_hidden("#spFallback"), "the old route is offered — it still works")

    print("\n[8] the kill switch is a different 503")
    reply = {"status": 503, "body": {"error": "off", "enabled": False}}
    fill(pg, freq="10120")
    pg.click("#spCheck"); pg.wait_for_timeout(400)
    fb = pg.evaluate("() => document.getElementById('fbSend').textContent")
    ok("gratis" not in fb and "free" not in fb, "it is not the daily-limit text")
    ok(len(fb) > 5, f"but it does say something ({fb[:44]})")
    ok(not pg.is_hidden("#spFallback"), "and offers the old route")

    print("\n[9] an unreachable Worker falls back instead of failing")
    fill(pg, freq="21200")
    reply = {"abort": True, "status": 0, "body": {}}
    pg.click("#spCheck"); pg.wait_for_timeout(600)
    ok(not pg.is_hidden("#spFallback"), "the old route appears when the Worker cannot be reached")
    ok(pg.is_disabled("#spSend"), "and Send stays shut")

    print("\n[10] classic mode skips the whole thing")
    pg.evaluate("() => document.querySelector('[data-view=\"viewSet\"]').click()")
    pg.wait_for_timeout(200)
    pg.check("#setClassic")
    pg.wait_for_timeout(200)
    pg.evaluate("() => document.querySelector('[data-view=\"viewSelf\"]').click()")
    pg.wait_for_timeout(300)
    fill(pg, freq="14285")
    ok(pg.is_hidden("#spCheck"), "the Check button is gone")
    ok(not pg.is_disabled("#spSend"), "and Send is open straight away")
    survives = pg.evaluate("() => localStorage.getItem('diana.self.classic')")
    ok(survives == "1", "the choice is remembered on this device")
    pg.evaluate("() => document.querySelector('[data-view=\"viewSet\"]').click()")
    pg.wait_for_timeout(150)
    pg.uncheck("#setClassic")
    pg.wait_for_timeout(150)

    print("\n[11] no JS errors along the way")
    ok(not errs, f"no page errors: {errs[:2] if errs else 'ok'}")

    br.close()

print()
if fails:
    print(f"FAILED — {len(fails)} check(s):")
    for f in fails:
        print("  - " + f)
    sys.exit(1)
print("ALL OK")
