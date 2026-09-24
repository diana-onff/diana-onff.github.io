# Agenda pins on the map, for a reference outside your own country.
#
#     python3 build/tests/test_agenda_place.py
#
# A field report: on Worldwide, the map only ever showed the green on-air
# spots, never the orange planned ones, even though the agenda list itself
# had entries. Traced to refPosition() in spots.js: an agenda item carries no
# coordinates of its own in Spotline's files, so its position was worked out
# from `zones`, the full boundary polygons of whichever one country is
# loaded (yours, by default). Any reference from another country was not in
# there, so it came back with no position and was silently left off the map,
# counted only in the "unplaced" total. Almost every entry in a worldwide
# agenda is not your own country, so almost nothing ever showed.
#
# The fix falls back to worldPoints, the same worldwide point file the map's
# own blue dots already use for every country besides the loaded one. This
# test plants one agenda item in the home country (ONFF, placeable from
# `zones` as before), one in another real country (PAFF, placeable only from
# the fallback) and one with a made-up reference that is in neither, and
# checks the map source and the "unplaced" count agree on which is which.
#
# ONFF is the real, on-disk boundary data (like test_worldpoints.py, not
# mocked), and PAFF-0001 is a real reference from the shipped
# data/wwff-world.geojson, so this exercises the actual fallback lookup
# rather than a fixture built to match it.
import re, json, sys
from playwright.sync_api import sync_playwright
import preconsent  # noqa: F401  answered welcome screen, see preconsent.py

BASE = "http://localhost:8011/web/"
fails = []


def ok(c, m):
    print(("  ✓ " if c else "  ✗ ") + m)
    if not c:
        fails.append(m)


NOW = None  # filled in once "now" is known, see below


def agenda_fixture():
    return [
        {"id": 1, "reference": "ONFF-0001", "activator_call": "ON4AA",
         "band": "40m", "mode": "SSB", "utc_start": NOW["past"], "utc_end": NOW["future"]},
        {"id": 2, "reference": "PAFF-0001", "activator_call": "PA1BB",
         "band": "20m", "mode": "CW", "utc_start": NOW["past"], "utc_end": NOW["future"]},
        {"id": 3, "reference": "ZZFF-9999", "activator_call": "ZZ1CC",
         "band": "15m", "mode": "SSB", "utc_start": NOW["past"], "utc_end": NOW["future"]},
    ]


def routes(ctx):
    ctx.route(re.compile(r"https://tiles\.openfreemap\.org/.*"), lambda r: r.fulfill(
        status=200, content_type="application/json",
        body=json.dumps({"version": 8, "sources": {}, "layers": [
            {"id": "bg", "type": "background", "paint": {"background-color": "#e8e4d8"}}]})))
    ctx.route(re.compile(r"https://spots\.wwff\.co/static/spots\.json"), lambda r: r.fulfill(
        status=200, content_type="application/json", body="[]"))
    ctx.route(re.compile(r"https://spots\.wwff\.co/static/agendas_active\.json"), lambda r: r.fulfill(
        status=200, content_type="application/json", body=json.dumps(agenda_fixture())))
    ctx.route(re.compile(r"https://spots\.wwff\.co/static/agendas\.json"), lambda r: r.fulfill(
        status=200, content_type="application/json", body="[]"))
    ctx.route(re.compile(r"https://docs\.google\.com/.*"), lambda r: r.abort())


READ = """() => {
  const pts = map.getSource('agenda-pts')._data.features
    .map(f => f.properties.ref)
    .sort();
  return {placed: pts, skipped: agendaSkipped};
}"""

with sync_playwright() as p:
    import datetime
    now = datetime.datetime.utcnow()
    NOW = {
        "past": (now - datetime.timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S"),
        "future": (now + datetime.timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S"),
    }

    br = p.chromium.launch()
    ctx = br.new_context(service_workers="block", viewport={"width": 420, "height": 860})
    routes(ctx)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE, wait_until="load")
    pg.wait_for_timeout(3000)   # the real wwff-world.geojson is ~9 MB, give it a moment
    pg.wait_for_function("() => worldLoaded === true", timeout=15000)
    pg.wait_for_function("() => !!map.getSource('agenda-pts')", timeout=15000)
    pg.wait_for_timeout(300)

    print("\n[1] the home-country entry places as before (from `zones`)")
    st = pg.evaluate(READ)
    ok("ONFF-0001" in st["placed"], f"ONFF-0001 is on the map ({st})")

    print("\n[2] an entry from another real country now places too (from `worldPoints`)")
    ok("PAFF-0001" in st["placed"], f"PAFF-0001 is on the map ({st})")

    print("\n[3] a reference in neither file is still left off, honestly")
    ok("ZZFF-9999" not in st["placed"], f"the made-up reference is not on the map ({st})")
    ok(st["skipped"] == 1, f"exactly the one unplaceable entry is counted (got {st['skipped']})")

    print("\n[4] the agenda list itself shows all three regardless of placeability")
    pg.evaluate("() => document.querySelector('#spotTab .seg[data-tab=\"agenda\"]').click()")
    pg.wait_for_timeout(200)
    rows = pg.evaluate("() => document.querySelectorAll('#spotList .spot').length")
    ok(rows == 3, f"all 3 announced activations are listed (got {rows})")

    print("\n[5] no JS errors")
    real = [e for e in errs if "Failed to load resource" not in e]
    ok(not real, "no page errors: " + (real[0][:160] if real else "ok"))

    br.close()

print("\n" + ("ALL OK" if not fails else f"{len(fails)} PROBLEMS: " + " | ".join(fails)))
sys.exit(1 if fails else 0)
