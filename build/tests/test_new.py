import re, json, sys, subprocess, time
from playwright.sync_api import sync_playwright

BASE="http://localhost:8011/web/"
fails=[]
def ok(cond,msg):
    print(("  ✓ " if cond else "  ✗ ")+msg)
    if not cond: fails.append(msg)

def route_all(ctx):
    # no network in this container: intercept anything that wants to go out
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

    print("\n[1] no JS errors on loading")
    real = [e for e in errs if "Failed to load resource" not in e]   # the ./data 404 is the intended fallback
    ok(not real, "no page errors: "+ (real[0][:160] if real else "ok"))

    print("\n[2] points without a polygon")
    # How many there are depends on the KMZ that happens to be there: a new
    # release can add boundaries for references that were still a point last time.
    # Pinning this to a number breaks the test on every data build, so we compare
    # against what meta.json from that same build says.
    import urllib.request, json as _json
    meta = _json.load(urllib.request.urlopen("http://localhost:8011/data/meta.json"))
    verwacht = meta.get("points_no_polygon", 0)
    n = pg.evaluate("() => noPoly.features.length")
    ok(n==verwacht, f"{verwacht} points loaded (got {n})")
    inidx = pg.evaluate("() => index.filter(z=>z.nopoly).length")
    ok(inidx==verwacht, f"{verwacht} points in the search index (got {inidx})")
    lay = pg.evaluate("() => !!map.getLayer('np-dot')")
    ok(lay, "layer np-dot exists")
    rendered = pg.evaluate("""() => { map.jumpTo({center:[4.5,50.9],zoom:6});
        return map.queryRenderedFeatures({layers:['np-dot']}).length; }""")
    pg.wait_for_timeout(1600)
    rendered = pg.evaluate("() => map.queryRenderedFeatures({layers:['np-dot']}).length")
    # One of them may be off-screen (there was one in Antarctica at one point), so
    # we do not demand all of them, but we do demand nearly all of what belongs in
    # this viewport.
    ok(rendered >= max(1, verwacht - 2),
       f"points really do render on the map ({rendered} of {verwacht})")

    print("\n[3] clicking a point gives the right panel")
    # Which reference has no boundary changes with every KMZ release — pinning a
    # fixed number turns this test unfairly red after the next upload. We take one
    # from the dataset that really is there at that moment.
    proef = pg.evaluate("() => noPoly.features[0] ? "
                        "{ref: noPoly.features[0].properties.ref, naam: noPoly.features[0].properties.name} : null")
    ok(bool(proef), f"a boundary-less reference to test with: {proef}")
    pg.evaluate(f"() => select({proef['ref']!r})")
    pg.wait_for_timeout(400)
    ok(pg.locator("#sheet").get_attribute("class").find("open")>=0, "panel opens")
    ok((proef['naam'] or proef['ref']) in pg.locator("#zoneName").inner_text(), "name is right")
    note = pg.locator("#zoneNote").inner_text()
    ok("no boundary" in note.lower() or "geen grens" in note.lower(), f"the explanation is there: {note[:60]}…")
    ok(len(pg.locator("#badges").inner_text().strip())>0, "the reference has attributes listed with it")
    ok("area" not in pg.locator("#facts").inner_text().lower() and " ha" not in pg.locator("#facts").inner_text(),
       "no invented area")

    print("\n[4] the GPS test skips points (must not crash)")
    errs.clear()
    pg.evaluate("() => evaluate(50.84896, 4.90140, 12)")   # exactly on a point without a polygon
    pg.wait_for_timeout(300)
    ok(not errs, "no error from evaluate() close to a point: "+(errs[0][:120] if errs else "ok"))
    st = pg.locator("#status").inner_text()
    ok("outside" in st.lower() or "buiten" in st.lower() or len(st)>0, f"status shown: {st[:70]}…")

    print("\n[5] the message can be dismissed")
    ok(pg.locator("#status").get_attribute("class").find("show")>=0, "message is showing")
    pg.locator("#stClose").click()
    pg.wait_for_timeout(200)
    ok(pg.locator("#status").get_attribute("class").find("show")<0, "message dismissed")

    print("\n[6] search finds a reference without a boundary")
    pg.evaluate("() => { const s=document.getElementById('search'); s.classList.add('on'); s.style.display='block'; }")
    zoek = proef['ref'].split('-')[-1] if proef else '0961'
    pg.evaluate(f"() => {{ const i=document.getElementById('q'); i.value={zoek!r}; i.dispatchEvent(new Event('input',{{bubbles:true}})); }}")
    pg.wait_for_timeout(400)
    res = pg.evaluate("() => document.getElementById('results').innerText")
    ok(len(res.strip()) > 0, f"searching for {zoek!r} gives results")
    ok("◌" in res, "marked as having no boundary")

    print("\n[7] layer button for the points")
    ok(pg.evaluate("() => !document.getElementById('optNopoly').hidden"), "layer button released as soon as there are points")
    pg.evaluate("""() => { const o=document.querySelector('[data-layer=\\"nopoly\\"]'); o.click(); }""")
    pg.wait_for_timeout(300)
    vis = pg.evaluate("() => map.getLayoutProperty('np-dot','visibility')")
    ok(vis=="none", f"switching off works (visibility={vis})")
    pg.evaluate("""() => document.querySelector('[data-layer=\\"nopoly\\"]').click()""")
    pg.wait_for_timeout(300)
    ok(pg.evaluate("() => map.getLayoutProperty('np-dot','visibility')")=="visible", "switching back on works")

    br.close()

print("\n"+("ALL OK" if not fails else f"{len(fails)} PROBLEMS: "+ " | ".join(fails)))
sys.exit(1 if fails else 0)
