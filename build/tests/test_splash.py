import re, json, sys
from playwright.sync_api import sync_playwright
BASE="http://localhost:8011/web/"
fails=[]
def ok(c,m):
    print(("  ✓ " if c else "  ✗ ")+m)
    if not c: fails.append(m)
def routes(ctx):
    ctx.route(re.compile(r"https://tiles\.openfreemap\.org/.*"), lambda r: r.fulfill(
        status=200, content_type="application/json",
        body=json.dumps({"version":8,"sources":{},"layers":[{"id":"bg","type":"background","paint":{"background-color":"#e8e4d8"}}]})))
    ctx.route(re.compile(r"https://spots\.wwff\.co/.*"), lambda r: r.fulfill(status=200, content_type="application/json", body="[]"))
    ctx.route(re.compile(r"https://docs\.google\.com/.*"), lambda r: r.abort())

with sync_playwright() as p:
    br=p.chromium.launch()
    ctx=br.new_context(service_workers="block", viewport={"width":390,"height":844}); routes(ctx)
    pg=ctx.new_page(); errs=[]
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE, wait_until="commit")

    print("\n[1] the splash screen is there straight away")
    pg.wait_for_selector("#splash", timeout=3000)
    pg.wait_for_timeout(450)
    vis = pg.evaluate("() => { const e=document.getElementById('splash'); if(!e) return null; const s=getComputedStyle(e); return {disp:s.display, op:s.opacity, bg:s.backgroundImage.slice(0,60)}; }")
    print("   ", vis)
    ok(vis and vis["disp"]!="none" and float(vis["op"])>0.5, "visible while loading")
    ok(vis and "start.jpg" in vis["bg"], "the drawing is on it")
    ok(pg.evaluate("() => (document.getElementById('splashVer')||{}).textContent||''").startswith("v"),
       "version number is on it: " + pg.evaluate("() => (document.getElementById('splashVer')||{}).textContent||''"))
    txt = pg.evaluate("() => (document.getElementById('splashTxt')||{}).textContent||''")
    ok(len(txt)>3, f"loading text: “{txt}”")
    anim = pg.evaluate("""() => { const s=document.querySelector('.splash .sweep'); const t=document.querySelector('.splash .tx i');
        return {sweep:getComputedStyle(s).animationName, tx:getComputedStyle(t).animationName}; }""")
    ok(anim["sweep"]=="dsweep" and anim["tx"]=="dtx", f"the signal animations are running: {anim}")
    pg.screenshot(path="/tmp/shot_splash.png")
    pg.wait_for_timeout(1200); pg.screenshot(path="/tmp/shot_splash2.png")

    print("\n[2] disappears by itself once the map is up")
    pg.wait_for_function("() => !document.getElementById('splash')", timeout=12000)
    ok(True, "splash screen is gone")
    ms = pg.evaluate("() => performance.now()")
    print(f"    (after {ms/1000:.1f}s)")
    ok(ms < 11000, "within a reasonable time")
    ok(pg.evaluate("() => !!map.getLayer('onff-fill')"), "and the map layer really is there by then")

    print("\n[3] the points from the WWFF directory with no boundary in the KMZ")
    # How many there are depends on the KMZ release; meta.json from the same build
    # is the only honest yardstick.
    import urllib.request, json as _json
    verwacht = _json.load(urllib.request.urlopen("http://localhost:8011/data/meta.json")).get("points_no_polygon", 0)
    n = pg.evaluate("() => noPoly.features.length")
    ok(n==verwacht, f"{verwacht} points loaded (got {n})")
    ok(pg.evaluate("() => index.filter(z=>z.nopoly).length")==verwacht, f"all {verwacht} in the search index")
    dup = pg.evaluate("""() => { const seen={}, dups=[];
        for(const z of index){ if(seen[z.ref]) dups.push(z.ref); seen[z.ref]=1; } return dups; }""")
    ok(not dup, f"no duplicate references in the index ({dup[:4]})")
    proef = pg.evaluate("() => noPoly.features[0] ? "
                        "{ref:noPoly.features[0].properties.ref, naam:noPoly.features[0].properties.name||''} : null")
    if proef:
        pg.evaluate(f"() => select({proef['ref']!r})"); pg.wait_for_timeout(500)
        getoond = pg.evaluate("() => document.getElementById('zoneName').textContent")
        ok((proef['naam'] or proef['ref']) in getoond, f"name from the directory ({getoond[:40]})")

    print("\n[4] bottom bar: all labels at the same height")
    tops = pg.evaluate("""() => [...document.querySelectorAll('#nav button')].filter(b => b.offsetParent).map(b => {
        const lab = b.querySelector('span:last-child');
        return {v:b.dataset.view, top:Math.round(lab.getBoundingClientRect().top),
                ic:Math.round(b.querySelector('.ic').getBoundingClientRect().top)}; })""")
    for t in tops: print("   ", t)
    labtops = {t["top"] for t in tops}
    ictops  = {t["ic"] for t in tops}
    ok(len(labtops)==1, f"labels on one line ({sorted(labtops)})")
    ok(len(ictops)==1, f"icons on one line ({sorted(ictops)})")
    pg.screenshot(path="/tmp/shot_nav.png", clip={"x":0,"y":770,"width":390,"height":74})

    print("\n[5] no JS errors")
    real=[e for e in errs if "Failed to load resource" not in e]
    ok(not real, "no page errors: "+(real[0][:130] if real else "ok"))
    br.close()
print("\n"+("ALL OK" if not fails else f"{len(fails)} PROBLEMS: "+" | ".join(fails)))
sys.exit(1 if fails else 0)
