# Regels (since 1.30.0): two tabs, Regels and Bandplan, and the WWFF rules text.
#
#     python3 build/tests/test_rules.py
#
# A tap on Regels in the bottom bar opens the Regels tab; Bandplan is one tap
# away and shows the band plan as before. The text: seven WWFF rules in three
# groups, in all eight languages, the 6.8 file name as an example box, the
# links, and in every language but English the note that the translation is
# Diana's own. Also: Sessie is gone from the bottom bar, and nothing sticks out
# of a 360 px screen.
import sys
from playwright.sync_api import sync_playwright
import preconsent  # noqa: F401  answered welcome screen, see preconsent.py

BASE = "http://localhost:8011/web/?lang=nl"
fails = []


def ok(c, m):
    print(("  ✓ " if c else "  ✗ ") + m)
    if not c:
        fails.append(m)


with sync_playwright() as p:
    br = p.chromium.launch()
    ctx = br.new_context(viewport={"width": 360, "height": 740}, is_mobile=True, has_touch=True, service_workers="block")
    ctx.route("**/spots.wwff.co/**", lambda r: r.fulfill(status=200, body="[]", content_type="application/json"))
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE, wait_until="load")
    pg.wait_for_timeout(2500)

    print("[1] the bottom bar")
    views = pg.eval_on_selector_all("#nav button[data-view]", "b => b.map(x => x.dataset.view)")
    ok("viewSession" not in views and not pg.query_selector("#viewSession"), f"no Sessie any more ({views})")

    print("\n[2] Regels opens on Regels")
    pg.tap('#nav button[data-view="viewRules"]')
    pg.wait_for_timeout(300)
    st = pg.evaluate("""() => ({tabs: [...document.querySelectorAll('#rulesTab .seg')].map(b => [b.textContent, b.classList.contains('on')]),
        text: !document.getElementById('rulesText').hidden, band: !document.getElementById('bandWrap').hidden,
        nums: [...document.querySelectorAll('#rulesText .rule .rnum')].map(n => n.textContent),
        groups: [...document.querySelectorAll('#rulesText .rgroup')].map(n => n.textContent),
        ex: (document.querySelector('.rulex') || {}).textContent || '',
        links: [...document.querySelectorAll('#rulesText a')].map(a => a.getAttribute('href')),
        note: document.querySelector('.rsrc').textContent, wide: document.documentElement.scrollWidth, vw: innerWidth})""")
    ok(st["tabs"] == [["Regels", True], ["Bandplan", False]] and st["text"] and not st["band"], f"two tabs, Regels shown first ({st['tabs']})")
    ok(st["nums"] == ["3.5", "3.6", "4.4", "4.7", "6.8", "6.9", "6.11"], f"the seven rules, 3.5 only once ({st['nums']})")
    ok(st["groups"] == ["Het gebied", "QSO's", "Logs"], f"in three groups ({st['groups']})")
    ok("ON3VZ" in st["ex"] and "ONFF-0104" in st["ex"] and "20261002" in st["ex"] and ".adi" in st["ex"] and "datum (JJJJMMDD)" in st["ex"],
       f"the 6.8 file name as a labelled example ({st['ex'].split()!r})")
    ok("https://wwff.co/logsearch/" in st["links"] and "mailto:wwfflogs@winqsl.de" in st["links"] and any("Global-Rules" in h for h in st["links"]),
       "links: Logsearch, the mail address, the official rules")
    ok("Vertaling door Diana. De Engelse tekst van WWFF geldt." in st["note"], f"the translation note ({st['note']!r})")
    ok(st["wide"] <= st["vw"], f"nothing sticks out of a 360 px screen ({st['wide']} <= {st['vw']})")
    if pg.evaluate("() => !!document.querySelector('.rulex')"):
        gap = pg.evaluate("() => { const p = [...document.querySelectorAll('.rulex .rxp')]; return p.map(x => x.className.split(' ')[1]); }")
        ok(gap == ["c", "at", "r", "sp", "d", "x"], f"with the space before the date shown as its own part ({gap})")

    print("\n[3] Bandplan, and back")
    pg.tap("#rulesTab .seg[data-rtab='band']")
    pg.wait_for_timeout(200)
    ok(pg.evaluate("() => document.getElementById('rulesText').hidden && !document.getElementById('bandWrap').hidden && document.querySelectorAll('#bandBox .band').length >= 8"),
       "Bandplan shows the band plan, the rules hidden")
    pg.tap('#nav button[data-view="viewSpots"]')
    pg.tap('#nav button[data-view="viewRules"]')
    pg.wait_for_timeout(200)
    ok(pg.evaluate("() => rulesTab") == "rules" and pg.evaluate("() => !document.getElementById('rulesText').hidden"),
       "leaving and coming back: Regels again")

    print("\n[4] every language")
    langs = pg.evaluate("""() => Object.fromEntries(Object.entries(RULES_TEXT).map(([k, L]) => [k,
        {n: L.groups.flatMap(g => g.rules.map(r => r.n)).join(','), note: !!L.note, ex: L.groups.some(g => g.rules.some(r => r.body.includes('%EXAMPLE%'))),
         dash: JSON.stringify(L).includes('\\u2014')}]))""")
    ok(sorted(langs) == sorted(["en", "nl", "fr", "de", "da", "it", "es", "pt"]), f"all eight languages ({sorted(langs)})")
    ok(all(v["n"] == "3.5,3.6,4.4,4.7,6.8,6.9,6.11" and v["ex"] for v in langs.values()), "each with the same seven rules and the example")
    ok(all(v["note"] == (k != "en") for k, v in langs.items()), "the translation note everywhere but in the English original")
    ok(not any(v["dash"] for v in langs.values()), "no long dashes in any language")
    pg.evaluate("() => { lang = 'en'; renderRules(); }")
    ok(pg.text_content("#rulesText .rule[data-rule='6.8'] h4") == "Naming of logs" and pg.text_content(".rsrc").startswith("Full official"),
       "English: the WWFF text, no translation note")
    ok(not errs, f"no page errors ({errs[:2]})")
    br.close()

print("\n" + ("ALL OK" if not fails else f"{len(fails)} PROBLEMS: " + " | ".join(fails)))
sys.exit(1 if fails else 0)
