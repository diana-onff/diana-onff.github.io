# Fields side by side stay in line, in every language (since 2.2.10).
#
#     python3 build/tests/test_field_align.py
#
# Reported from Portugal: on the Spot form "Indicativo do ativador" ran over two
# lines and pushed its box down, out of line with "Spotter" next to it. A walk
# through all eight languages found the same on the Spot and Agenda forms in
# seven of them (Dutch included) and in Settings in three, on a small phone.
#
# Two changes, both checked here:
#   [1] the activator label is one short word in every language ("Ativador",
#       as asked);
#   [2] in every row of fields side by side, the boxes line up, also where a
#       label still runs over two lines: on a very narrow phone (320 px), a
#       small one (360 px) and a common one (412 px), in all eight languages,
#       on every screen that has such rows.
import re, json, sys
from playwright.sync_api import sync_playwright
import preconsent  # noqa: F401  answered welcome screen, see preconsent.py

BASE = "http://localhost:8011/web/"
LANGS = ["nl", "en", "fr", "de", "da", "it", "es", "pt"]
VIEWS = ["viewSelf", "viewAgendaNew", "viewSet"]
SHORT = {"nl": "Activator", "en": "Activator", "fr": "Activateur", "de": "Aktivierer",
         "da": "Aktivator", "it": "Attivatore", "es": "Activador", "pt": "Ativador"}
fails = []


def ok(c, m):
    print(("  ✓ " if c else "  ✗ ") + m)
    if not c:
        fails.append(m)


ROWS = r"""() => {
  const vis = e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const out = [];
  for (const g of document.querySelectorAll('.fgrid')) {
    if (!vis(g)) continue;
    const rows = {};
    for (const f of g.querySelectorAll(':scope > .fld')) {
      const inp = f.querySelector('input,select'); if (!inp || !vis(inp)) continue;
      const top = Math.round(f.getBoundingClientRect().top);
      (rows[top] = rows[top] || []).push({lbl: (f.querySelector('span') || {}).textContent || '?',
        bottom: inp.getBoundingClientRect().bottom, lines: Math.round(f.querySelector('span').getBoundingClientRect().height / 14)});
    }
    for (const r of Object.values(rows)) if (r.length > 1) out.push(r);
  }
  return out;
}"""

with sync_playwright() as p:
    br = p.chromium.launch()
    errs = []
    print("\n[1] the activator label is one short word")
    print("\n[2] the boxes in every row of fields side by side line up")
    wrapped = 0
    for lang in LANGS:
        bad = []
        for w in (320, 360, 412):
            ctx = br.new_context(service_workers="block", viewport={"width": w, "height": 800})
            ctx.add_init_script(f"try{{localStorage.setItem('diana.lang','{lang}');localStorage.setItem('diana.wizard.done','1');"
                                "localStorage.setItem('diana.call','CT7AOV');}catch(e){}")
            ctx.route(re.compile(r"https://tiles\.openfreemap\.org/.*"), lambda r: r.fulfill(
                status=200, content_type="application/json",
                body=json.dumps({"version": 8, "sources": {}, "layers": [{"id": "bg", "type": "background", "paint": {"background-color": "#e8e4d8"}}]})))
            ctx.route(re.compile(r"https://(spots\.wwff\.co|raw\.githubusercontent\.com|api\.github\.com|docs\.google\.com)/.*"), lambda r: r.abort())
            pg = ctx.new_page()
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.goto(BASE, wait_until="load")
            pg.wait_for_timeout(1500)
            if w == 360:
                got = pg.evaluate("() => [...document.querySelectorAll('[data-i18n=\"self.activator\"]')].map(e => e.textContent)")
                ok(got and all(x == SHORT[lang] for x in got), f"{lang}: {got[:1]}")
            n = 0
            for v in VIEWS:
                pg.evaluate(f"() => document.querySelector('#nav button[data-view=\"{v}\"]').click()")
                pg.wait_for_timeout(300)
                for row in pg.evaluate(ROWS):
                    n += 1
                    # The bottoms: a select is a hair lower than a text box
                    # (45 against 47 px), so their tops differ by that much
                    # whatever the labels do. Lined up means: on one baseline.
                    bots = [x["bottom"] for x in row]
                    if max(bots) - min(bots) > 1:
                        bad.append(f"{w}px {v}: " + " | ".join(x["lbl"] for x in row))
                    if len(set(x["lines"] for x in row)) > 1:
                        wrapped += 1
            ctx.close()
        ok(not bad and n > 0, f"{lang}: every row in line at 320, 360 and 412 px ({n} rows at 412 px)" + (f" {bad[:2]}" if bad else ""))
    print(f"  (rows where one label still takes more lines than its neighbour, and the boxes line up anyway: {wrapped})")
    ok(not errs, f"no page errors ({errs[:2]})")
    br.close()

print("\n" + ("ALL OK" if not fails else f"{len(fails)} PROBLEMS: " + " | ".join(fails)))
sys.exit(1 if fails else 0)
