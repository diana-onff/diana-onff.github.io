import re, json, sys, subprocess, time
from playwright.sync_api import sync_playwright

BASE="http://localhost:8011/web/"
fails=[]
def ok(cond,msg):
    print(("  ✓ " if cond else "  ✗ ")+msg)
    if not cond: fails.append(msg)

def route_all(ctx):
    # geen net in deze container: alles wat naar buiten wil, onderscheppen
    ctx.route(re.compile(r"https://tiles\.openfreemap\.org/.*"), lambda r: r.fulfill(
        status=200, content_type="application/json",
        body=json.dumps({"version":8,"sources":{},"layers":[
            {"id":"bg","type":"background","paint":{"background-color":"#e8e4d8"}}]})))
    ctx.route(re.compile(r"https://spots\.wwff\.co/.*"), lambda r: r.fulfill(
        status=200, content_type="application/json", body="[]"))
    ctx.route(re.compile(r"https://docs\.google\.com/.*"), lambda r: r.abort())

with sync_playwright() as p:
    br = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
                           if __import__('os').path.exists("/opt/pw-browsers/chromium-1194/chrome-linux/chrome") else None)
    ctx = br.new_context(service_workers="block", viewport={"width":420,"height":860})
    route_all(ctx)
    pg = ctx.new_page()
    errs=[]
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append("console."+m.type+": "+m.text) if m.type=="error" else None)
    pg.goto(BASE, wait_until="load")
    pg.wait_for_timeout(2500)

    print("\n[1] geen JS-fouten bij het laden")
    real = [e for e in errs if "Failed to load resource" not in e]   # ./data 404 is de bedoelde terugval
    ok(not real, "geen page errors: "+ (real[0][:160] if real else "ok"))

    print("\n[2] punten zonder polygoon")
    # Hoeveel er zijn hangt af van het KMZ dat er ligt: een nieuwe release kan
    # grenzen toevoegen voor referenties die vorige keer nog een punt waren.
    # Vastpinnen op een getal maakt de test kapot bij elke databuild, dus we
    # vergelijken met wat meta.json van diezelfde build zegt.
    import urllib.request, json as _json
    meta = _json.load(urllib.request.urlopen("http://localhost:8011/data/meta.json"))
    verwacht = meta.get("points_no_polygon", 0)
    n = pg.evaluate("() => noPoly.features.length")
    ok(n==verwacht, f"{verwacht} punten geladen (kreeg {n})")
    inidx = pg.evaluate("() => index.filter(z=>z.nopoly).length")
    ok(inidx==verwacht, f"{verwacht} punten in de zoekindex (kreeg {inidx})")
    lay = pg.evaluate("() => !!map.getLayer('np-dot')")
    ok(lay, "laag np-dot bestaat")
    rendered = pg.evaluate("""() => { map.jumpTo({center:[4.5,50.9],zoom:6});
        return map.queryRenderedFeatures({layers:['np-dot']}).length; }""")
    pg.wait_for_timeout(1600)
    rendered = pg.evaluate("() => map.queryRenderedFeatures({layers:['np-dot']}).length")
    # Eentje kan buiten beeld liggen (er stond er ooit een op Antarctica), dus
    # we eisen niet alles, wel bijna alles van wat er in dit venster hoort.
    ok(rendered >= max(1, verwacht - 2),
       f"punten renderen echt op de kaart ({rendered} van {verwacht})")

    print("\n[3] klikken op een punt geeft het juiste paneel")
    # Welke referentie geen grens heeft, verandert met elke KMZ-release — een vast
    # nummer prikken maakt deze test na de volgende upload onterecht rood. We
    # nemen er eentje uit de dataset die er op dat moment echt is.
    proef = pg.evaluate("() => noPoly.features[0] ? "
                        "{ref: noPoly.features[0].properties.ref, naam: noPoly.features[0].properties.name} : null")
    ok(bool(proef), f"een referentie zonder grens om mee te testen: {proef}")
    pg.evaluate(f"() => select({proef['ref']!r})")
    pg.wait_for_timeout(400)
    ok(pg.locator("#sheet").get_attribute("class").find("open")>=0, "paneel opent")
    ok((proef['naam'] or proef['ref']) in pg.locator("#zoneName").inner_text(), "naam klopt")
    note = pg.locator("#zoneNote").inner_text()
    ok("no boundary" in note.lower() or "geen grens" in note.lower(), f"uitleg staat er: {note[:60]}…")
    ok(len(pg.locator("#badges").inner_text().strip())>0, "er staan kenmerken bij de referentie")
    ok("area" not in pg.locator("#facts").inner_text().lower() and " ha" not in pg.locator("#facts").inner_text(),
       "geen verzonnen oppervlakte")

    print("\n[4] GPS-test slaat punten over (mag niet crashen)")
    errs.clear()
    pg.evaluate("() => evaluate(50.84896, 4.90140, 12)")   # exact op een punt zonder polygoon
    pg.wait_for_timeout(300)
    ok(not errs, "geen fout bij evaluate() vlakbij een punt: "+(errs[0][:120] if errs else "ok"))
    st = pg.locator("#status").inner_text()
    ok("outside" in st.lower() or "buiten" in st.lower() or len(st)>0, f"status getoond: {st[:70]}…")

    print("\n[5] melding is wegklikbaar")
    ok(pg.locator("#status").get_attribute("class").find("show")>=0, "melding staat aan")
    pg.locator("#stClose").click()
    pg.wait_for_timeout(200)
    ok(pg.locator("#status").get_attribute("class").find("show")<0, "melding weggeklikt")

    print("\n[6] zoeken vindt een referentie zonder grens")
    pg.evaluate("() => { const s=document.getElementById('search'); s.classList.add('on'); s.style.display='block'; }")
    zoek = proef['ref'].split('-')[-1] if proef else '0961'
    pg.evaluate(f"() => {{ const i=document.getElementById('q'); i.value={zoek!r}; i.dispatchEvent(new Event('input',{{bubbles:true}})); }}")
    pg.wait_for_timeout(400)
    res = pg.evaluate("() => document.getElementById('results').innerText")
    ok(len(res.strip()) > 0, f"zoeken op {zoek!r} geeft resultaten")
    ok("◌" in res, "gemarkeerd als zonder grens")

    print("\n[7] laagknop voor de punten")
    ok(pg.evaluate("() => !document.getElementById('optNopoly').hidden"), "laagknop vrijgegeven zodra er punten zijn")
    pg.evaluate("""() => { const o=document.querySelector('[data-layer=\\"nopoly\\"]'); o.click(); }""")
    pg.wait_for_timeout(300)
    vis = pg.evaluate("() => map.getLayoutProperty('np-dot','visibility')")
    ok(vis=="none", f"uitzetten werkt (visibility={vis})")
    pg.evaluate("""() => document.querySelector('[data-layer=\\"nopoly\\"]').click()""")
    pg.wait_for_timeout(300)
    ok(pg.evaluate("() => map.getLayoutProperty('np-dot','visibility')")=="visible", "weer aan werkt")

    br.close()

print("\n"+("ALLES OK" if not fails else f"{len(fails)} PROBLEMEN: "+ " | ".join(fails)))
sys.exit(1 if fails else 0)
