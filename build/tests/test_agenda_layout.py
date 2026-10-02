# The announcement form: the Start and End fields stay inside the card.
#
#     python3 build/tests/test_agenda_layout.py
#
# Chrome gives a date-and-time field a fixed minimum width (about 212 px).
# In two plain 1fr columns that pushed End out of the card on a phone. Now:
# side by side when both fit, otherwise one under the other, and never
# outside the card. Checked at 360, 390 (stacked) and 800 px (side by side).
import sys
from playwright.sync_api import sync_playwright
import preconsent  # noqa: F401  answered welcome screen, see preconsent.py

BASE = "http://localhost:8011/web/?lang=nl"
fails = []


def ok(c, m):
    print(("  ✓ " if c else "  ✗ ") + m)
    if not c:
        fails.append(m)


BOXES = """() => {
  const box = id => { const r = document.getElementById(id).getBoundingClientRect(); return [r.left, r.right, r.top, r.bottom]; };
  const card = document.getElementById('agStart').closest('.card').getBoundingClientRect();
  return {s: box('agStart'), e: box('agEnd'), c: [card.left, card.right], page: document.documentElement.scrollWidth, vw: innerWidth};
}"""

with sync_playwright() as p:
    br = p.chromium.launch()
    for w, stacked in ((360, True), (390, True), (800, False)):
        print(f"\n[{w} px]")
        ctx = br.new_context(viewport={"width": w, "height": 800}, is_mobile=w < 600, has_touch=True, service_workers="block")
        ctx.route("**/spots.wwff.co/**", lambda r: r.fulfill(status=200, body="[]", content_type="application/json"))
        pg = ctx.new_page()
        pg.goto(BASE, wait_until="load")
        pg.wait_for_timeout(2500)
        pg.tap('#nav button[data-view="viewAgendaNew"]')
        pg.wait_for_timeout(400)
        b = pg.evaluate(BOXES)
        inside = all(b["c"][0] - 0.5 <= f[0] and f[1] <= b["c"][1] + 0.5 for f in (b["s"], b["e"]))
        ok(inside, f"Begin and Einde inside the card (card {b['c']}, begin {b['s'][:2]}, einde {b['e'][:2]})")
        ok(b["page"] <= b["vw"], f"nothing sticks out of the page ({b['page']} <= {b['vw']})")
        below = b["e"][2] >= b["s"][3]
        ok(below == stacked, ("one under the other" if stacked else "side by side") + f" (begin bottom {b['s'][3]:.0f}, einde top {b['e'][2]:.0f})")
        ctx.close()
    br.close()

print("\n" + ("ALL OK" if not fails else f"{len(fails)} PROBLEMS: " + " | ".join(fails)))
sys.exit(1 if fails else 0)
