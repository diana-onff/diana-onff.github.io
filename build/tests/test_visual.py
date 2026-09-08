import re, json, sys
from playwright.sync_api import sync_playwright
BASE="http://localhost:8011/web/"
fails=[]
def ok(c,m):
    print(("  ✓ " if c else "  ✗ ")+m); 
    if not c: fails.append(m)
def routes(ctx):
    ctx.route(re.compile(r"https://tiles\.openfreemap\.org/.*"), lambda r: r.fulfill(
        status=200, content_type="application/json",
        body=json.dumps({"version":8,"sources":{},"layers":[{"id":"bg","type":"background","paint":{"background-color":"#e8e4d8"}}]})))
    ctx.route(re.compile(r"https://spots\.wwff\.co/.*"), lambda r: r.fulfill(status=200, content_type="application/json", body="[]"))
    ctx.route(re.compile(r"https://docs\.google\.com/.*"), lambda r: r.abort())

with sync_playwright() as p:
    br=p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
                          if __import__('os').path.exists("/opt/pw-browsers/chromium-1194/chrome-linux/chrome") else None)
    ctx=br.new_context(service_workers="block", viewport={"width":390,"height":844}, has_touch=True); routes(ctx)
    pg=ctx.new_page(); pg.goto(BASE, wait_until="load"); pg.wait_for_timeout(2000)

    print("\n[1] the icon really does get drawn (count pixels, do not hope)")
    # Do not aim at a fixed coordinate: which reference has no boundary changes
    # with every KMZ release, and then nothing gets drawn here any more.
    # We take the first point the dataset itself hands us.
    coord = pg.evaluate("() => noPoly.features[0] ? noPoly.features[0].geometry.coordinates : null")
    ok(bool(coord), f"a boundary-less point to look at: {coord}")
    pg.evaluate(f"() => map.jumpTo({{center:{coord}, zoom:11}})"); pg.wait_for_timeout(1200)
    pt = pg.evaluate(f"() => {{ const p = map.project({coord}); return [Math.round(p.x), Math.round(p.y)]; }}")
    shot = pg.screenshot(clip={"x":max(0,pt[0]-30),"y":max(0,pt[1]-30),"width":60,"height":60})
    open("/tmp/np_icon.png","wb").write(shot)
    from PIL import Image
    im = Image.open("/tmp/np_icon.png").convert("RGB")
    px = list(im.getdata())
    def near(c, t, tol=26): return all(abs(c[i]-t[i])<=tol for i in range(3))
    green = sum(1 for c in px if near(c,(27,67,50)))
    amber = sum(1 for c in px if near(c,(217,119,6)))
    print(f"    green ring pixels: {green} · amber core: {amber}")
    ok(green>40, "dotted green ring visible")
    ok(amber>4, "amber-coloured core visible")

    print("\n[2] the install bar does not overlap the bottom bar")
    pg.evaluate("""() => { const e=new Event('beforeinstallprompt'); e.prompt=()=>{}; 
                           e.userChoice=Promise.resolve({outcome:'dismissed'}); dispatchEvent(e); }""")
    pg.wait_for_timeout(400)
    box = pg.evaluate("""() => { const b=document.getElementById('instBar').getBoundingClientRect();
                                 const n=document.getElementById('nav').getBoundingClientRect();
                                 return {bBottom:b.bottom, nTop:n.top, bTop:b.top, w:b.width}; }""")
    print("   ", box)
    ok(box["bBottom"] <= box["nTop"]+1, f"bar ends above the nav ({box['bBottom']:.0f} ≤ {box['nTop']:.0f})")
    ok(box["bTop"] > 0 and box["w"] > 200, "bar is fully in view")
    pg.screenshot(path="/tmp/shot_bar.png")

    print("\n[3] panel of a boundary-less point")
    pg.evaluate("() => document.getElementById('instBarNo').click()")
    pg.evaluate("() => select('ONFF-0011')"); pg.wait_for_timeout(800)
    pg.screenshot(path="/tmp/shot_point.png")
    ok(True, "screenshot taken")

    print("\n[4] settings screen with language + install")
    pg.evaluate("() => closeSheet()")
    pg.evaluate("() => document.querySelector('#nav button[data-view=\"viewSet\"]').click()")
    pg.wait_for_timeout(400)
    pg.screenshot(path="/tmp/shot_settings.png", full_page=True)
    ok(True, "screenshot taken")
    br.close()
print("\n"+("ALL OK" if not fails else f"{len(fails)} PROBLEMS: "+" | ".join(fails)))
sys.exit(1 if fails else 0)
