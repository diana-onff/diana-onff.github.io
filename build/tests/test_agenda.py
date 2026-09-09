"""Announcing an activation through the Worker (Fase 4): the date-range rules
that are new here, the Check/Send pattern reused from self-spotting, and the
pin saved locally afterwards.

    python3 build/tests/test_agenda.py

The Worker is stubbed, so this never touches the real proxy and never reaches
WWFF. Reference checking itself (refLookup) is already covered exhaustively
by test_spot.py — this file only re-touches it enough to prove the agenda
screen is wired to the same function, and spends its effort on what is new:
the month ceiling and the end-after-start rule, both enforced here even
though the Worker enforces them too, so a bad date never costs a request.
"""
import re, json, os, sys
from datetime import datetime, timedelta, timezone
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8011/web/"
WORKER = re.compile(r"https://diana-spotline\.diana-onff\.workers\.dev/agenda")
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


def local_dt(hours_from_now):
    """A datetime-local value string, computed the same way the browser's own
    `new Date()` would see "now" — this container and the browser both run in
    UTC, so the two clocks agree without needing to ask the page."""
    d = datetime.now(timezone.utc) + timedelta(hours=hours_from_now)
    return d.strftime("%Y-%m-%dT%H:%M")


def fill(pg, ref="ONFF-0001", act="ON3VZ/P", poster="ON3VZ", pin="1234",
         start_h=2, end_h=5):
    pg.fill("#agActivator", act)
    pg.fill("#agPoster", poster)
    pg.fill("#agReference", ref)
    pg.fill("#agStart", local_dt(start_h))
    pg.fill("#agEnd", local_dt(end_h))
    pg.fill("#agPin", pin)
    pg.wait_for_timeout(150)


def open_agenda(pg):
    pg.evaluate("() => document.querySelector('[data-view=\"viewSpots\"]').click()")
    pg.wait_for_timeout(200)
    pg.click('.seg[data-tab="agenda"]')
    pg.wait_for_timeout(150)
    ok(not pg.is_hidden("#agNewOpen"), "the + Aankondigen button appears on the Agenda tab")
    pg.click("#agNewOpen")
    pg.wait_for_timeout(300)


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

    print("\n[1] the screen opens from the Agenda tab, prefilled and bounded")
    open_agenda(pg)
    ok(pg.is_visible("#viewAgendaNew"), "the agenda screen is showing")
    ok(pg.is_hidden("#viewSpots"), "and the Spots screen is not, underneath it")

    print("\n[2] the reference field uses the same local lookup as self-spotting")
    pg.fill("#agReference", "ONFF-9999")
    pg.wait_for_timeout(150)
    ok("bad" in pg.evaluate("() => document.getElementById('fbAgReference').className"),
       "an ONFF number we do not have is rejected")
    pg.fill("#agReference", "ONFF-0001")
    pg.wait_for_timeout(150)
    txt = pg.evaluate("() => document.getElementById('fbAgReference').textContent")
    ok("good" in pg.evaluate("() => document.getElementById('fbAgReference').className'"
                              if False else "() => document.getElementById('fbAgReference').className"),
       f"a real one is accepted, with a name ({txt[:44]})")

    print("\n[3] Send stays shut until a check has come back good")
    fill(pg)
    ok(pg.is_disabled("#agSend"), "Send is closed on a fresh, valid form")
    ok(not pg.is_disabled("#agCheck"), "Check is open once the form holds together")

    reply = {"status": 200, "body": {"dryrun": True, "ok": True}}
    seen.clear()
    pg.click("#agCheck")
    pg.wait_for_timeout(400)
    ok(len(seen) == 1 and seen[0].get("dryrun") is True, "the check goes out with dryrun: true")
    ok(seen[0].get("activator_call") == "ON3VZ/P" and seen[0].get("poster") == "ON3VZ",
       "and carries the activator and the poster separately")
    ok("utc_start" in seen[0] and "T" in seen[0]["utc_start"] and seen[0]["utc_start"].endswith("Z"),
       f"utc_start travels as real UTC, not the picker's local string ({seen[0].get('utc_start')})")
    ok(not pg.is_disabled("#agSend"), "Send opens after an accepted check")

    print("\n[4] any edit closes it again")
    pg.fill("#agBand", "20m")
    pg.wait_for_timeout(200)
    ok(pg.is_disabled("#agSend"), "Send is closed again once the form changes")

    print("\n[5] end before start is caught here, before it costs a request")
    fill(pg, start_h=5, end_h=2)
    ok(pg.is_disabled("#agCheck"), "Check does not open on a backwards range")
    msg = pg.evaluate("() => document.getElementById('fbAgWhen').textContent")
    ok(len(msg) > 0, f"and says why ({msg[:40]})")

    print("\n[6] more than a month out is caught the same way")
    fill(pg, start_h=40 * 24, end_h=40 * 24 + 2)
    ok(pg.is_disabled("#agCheck"), "Check does not open on a date over a month away")

    print("\n[7] a real send, and what happens to the pin afterwards")
    fill(pg, ref="ONFF-0002", pin="q1w2e3")
    reply = {"status": 200, "body": {"dryrun": True}}
    pg.click("#agCheck")
    pg.wait_for_timeout(300)
    reply = {"status": 201, "body": {"agenda_id": 777}}
    seen.clear()
    pg.click("#agSend")
    pg.wait_for_timeout(400)
    ok(len(seen) == 1 and "dryrun" not in seen[0], "the real send carries no dryrun")
    fb = pg.evaluate("() => document.getElementById('fbAgSend').textContent")
    ok("777" in fb, f"the agenda_id is shown ({fb[:48]})")
    ok(pg.evaluate("() => document.getElementById('agReference').value") == "",
       "the form clears, ready for the next announcement")
    saved = pg.evaluate("() => JSON.parse(localStorage.getItem('diana.agendas') || '[]')")
    ok(len(saved) == 1 and saved[0]["reference"] == "ONFF-0002" and saved[0]["pin"] == "q1w2e3",
       f"the reference and pin are kept locally ({saved[:1]})")
    ok(not pg.is_hidden("#agSavedCard"), "and the saved list becomes visible")

    print("\n[8] a duplicate is reassuring, not an error")
    fill(pg, ref="ONFF-0003")
    reply = {"status": 200, "body": {}}
    pg.click("#agCheck"); pg.wait_for_timeout(300)
    reply = {"status": 409, "body": {"error": "duplicate"}}
    pg.click("#agSend"); pg.wait_for_timeout(400)
    ok("good" in pg.evaluate("() => document.getElementById('fbAgSend').className"),
       "a 409 is shown as good news, same as for a spot")

    print("\n[9] a refusal by Spotline is shown as Spotline's own words")
    fill(pg, ref="ONFF-0004")
    reply = {"status": 400, "body": {"error": "no", "details": ["pin must be at least 4 characters"]}}
    pg.click("#agCheck"); pg.wait_for_timeout(400)
    fb = pg.evaluate("() => document.getElementById('fbAgSend').textContent")
    ok("pin must be at least 4 characters" in fb, f"the explanation comes through ({fb[:44]})")
    ok(pg.is_disabled("#agSend"), "and Send stays shut")

    print("\n[10] the daily ceiling reuses the same message as self-spotting")
    fill(pg, ref="ONFF-0005")
    reply = {"status": 503, "body": {"error": "daily", "limit": "day"}}
    pg.click("#agCheck"); pg.wait_for_timeout(400)
    fb = pg.evaluate("() => document.getElementById('fbAgSend').textContent")
    ok("gratis" in fb or "free" in fb, f"it explains the free tier ({fb[:52]})")

    print("\n[11] an unreachable Worker says so, with nothing to fall back to")
    fill(pg, ref="ONFF-0006")
    reply = {"abort": True, "status": 0, "body": {}}
    pg.click("#agCheck"); pg.wait_for_timeout(600)
    fb = pg.evaluate("() => document.getElementById('fbAgSend').textContent")
    ok(len(fb) > 0, f"a message is shown ({fb[:44]})")
    ok(pg.is_disabled("#agSend"), "and Send stays shut — there is no old route here")

    print("\n[12] the way back leaves no trace of the form")
    pg.click("#agBack")
    pg.wait_for_timeout(200)
    ok(pg.is_visible("#viewSpots"), "back on the Spots & agenda screen")
    ok(pg.is_hidden("#viewAgendaNew"), "and the agenda screen is gone")

    print("\n[13] there is a second door in, from the Meld screen — and it remembers")
    pg.evaluate("() => document.querySelector('[data-view=\"viewSelf\"]').click()")
    pg.wait_for_timeout(200)
    ok(pg.is_visible("#agFromSelf"), "the announce link is on the self-spot screen too")
    pg.click("#agFromSelf")
    pg.wait_for_timeout(300)
    ok(pg.is_visible("#viewAgendaNew"), "and it opens the same screen")
    pg.click("#agBack")
    pg.wait_for_timeout(200)
    ok(pg.is_visible("#viewSelf"), "← Terug returns to Meld, not always to Spots")
    ok(pg.is_hidden("#viewAgendaNew"), "and the agenda screen is gone")

    print("\n[14] a third door in: straight from the bottom nav")
    pg.evaluate("() => document.querySelector('[data-view=\"viewAgendaNew\"]').click()")
    pg.wait_for_timeout(300)
    ok(pg.is_visible("#viewAgendaNew"), "the nav button opens the same screen")
    ok(pg.evaluate("() => document.getElementById('agStart').min") != "",
       "and it's prefilled/bounded (agendaOpen ran) exactly as the other two doors do")

    print("\n[15] no JS errors along the way")
    ok(not errs, f"no page errors: {errs[:2] if errs else 'ok'}")

    br.close()

print()
if fails:
    print(f"FAILED — {len(fails)} check(s):")
    for f in fails:
        print("  - " + f)
    sys.exit(1)
print("ALL OK")
