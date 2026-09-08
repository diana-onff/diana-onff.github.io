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

def swipe(pg, sel, dy=140):
    """Real touch gestures, the way a finger sends them."""
    pg.evaluate("""([sel,dy]) => {
      const el = document.querySelector(sel);
      const r = el.getBoundingClientRect();
      const x = r.left + r.width/2, y = r.top + 14;
      const mk = (type, cy) => {
        const t = new Touch({identifier:1, target:el, clientX:x, clientY:cy});
        el.dispatchEvent(new TouchEvent(type,{bubbles:true, cancelable:true, touches:type==='touchend'?[]:[t], changedTouches:[t]}));
      };
      mk('touchstart', y);
      for(let i=1;i<=6;i++) mk('touchmove', y + dy*i/6);
      mk('touchend', y+dy);
    }""", [sel, dy])

with sync_playwright() as p:
    br=p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
                          if __import__('os').path.exists("/opt/pw-browsers/chromium-1194/chrome-linux/chrome") else None)
    ctx=br.new_context(service_workers="block", viewport={"width":390,"height":844},
                       has_touch=True, is_mobile=True); routes(ctx)
    pg=ctx.new_page()
    errs=[]; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE, wait_until="load"); pg.wait_for_timeout(2000)

    print("\n[1] area panel: swiping down closes it")
    pg.evaluate("() => select('ONFF-0104')"); pg.wait_for_timeout(500)
    ok("open" in pg.evaluate("() => document.getElementById('sheet').className"), "panel open")
    swipe(pg, "#sheet"); pg.wait_for_timeout(500)
    ok("open" not in pg.evaluate("() => document.getElementById('sheet').className"), "a downward swipe closes it")

    print("\n[2] swiping up does not close it")
    pg.evaluate("() => select('ONFF-0104')"); pg.wait_for_timeout(400)
    swipe(pg, "#sheet", dy=-120); pg.wait_for_timeout(400)
    ok("open" in pg.evaluate("() => document.getElementById('sheet').className"), "stays open on an upward swipe")

    print("\n[3] a short tap does not close it (otherwise you could not touch anything)")
    swipe(pg, "#sheet", dy=8); pg.wait_for_timeout(400)
    ok("open" in pg.evaluate("() => document.getElementById('sheet').className"), "stays open at 8 px")
    pg.evaluate("() => closeSheet()")

    print("\n[4] heatmap screen: swiping brings you back to the map")
    pg.evaluate("() => document.querySelector('#nav button[data-view=\"viewHeat\"]').click()")
    pg.wait_for_timeout(700)
    ok(pg.evaluate("() => document.getElementById('viewHeat').classList.contains('on')"), "heatmap open")
    swipe(pg, "#viewHeat"); pg.wait_for_timeout(600)
    # New behaviour: swiping down puts the panel away, but leaves the heatmap up.
    # The colours on the map are the whole point; only tapping Map closes it.
    ok(pg.evaluate("() => document.getElementById('viewHeat').classList.contains('minimized')"),
       "swipe down → panel put away")
    ok(pg.evaluate("() => document.getElementById('viewHeat').classList.contains('on')"),
       "the heatmap screen stays active")
    ok(pg.evaluate("() => heatOnMap === true"), "the areas keep their colour")
    pg.evaluate("() => document.getElementById('viewHeat').click()"); pg.wait_for_timeout(400)
    ok(not pg.evaluate("() => document.getElementById('viewHeat').classList.contains('minimized')"),
       "tapping the strip brings the panel back")
    pg.evaluate("() => document.querySelector('#nav button[data-view=\"map\"]').click()")
    pg.wait_for_timeout(400)
    ok(not pg.evaluate("() => document.getElementById('viewHeat').classList.contains('on')"),
       "only tapping Map brings you back to the ordinary map")
    ok(pg.evaluate("() => heatOnMap === false"), "and switches the colours off")
    ok(pg.evaluate("() => document.querySelector('#nav button[data-view=\"map\"]').classList.contains('on')"), "the map button is back on")

    print("\n[5] spot panel: same gesture")
    pg.evaluate("""() => { document.getElementById('spotSheet').classList.add('open');
                           document.body.classList.add('sheet-open'); }""")
    pg.wait_for_timeout(300)
    swipe(pg, "#spotSheet"); pg.wait_for_timeout(500)
    ok("open" not in pg.evaluate("() => document.getElementById('spotSheet').className"), "spot panel closes")

    print("\n[6] points survive a style switch (the old pitfall)")
    counts=[]
    for s in ["dark","positron","bright","liberty","dark","positron"]:
        pg.evaluate("(s) => setStyle(s)", s); pg.wait_for_timeout(1400)
        pg.evaluate("() => map.jumpTo({center:[4.5,50.9], zoom:6})"); pg.wait_for_timeout(700)
        counts.append(pg.evaluate("""() => ({
            zones: !!map.getLayer('onff-fill'),
            np: !!map.getLayer('np-dot'),
            rendered: map.queryRenderedFeatures({layers: map.getLayer('np-dot')?['np-dot']:[]}).length })"""))
    print("   ", counts)
    ok(all(c["zones"] and c["np"] for c in counts), "both zones and points present after each of the 6 style switches")
    ok(all(c["rendered"]>0 for c in counts), "points really rendered after every switch too")

    print("\n[7] no JS errors in this whole scenario")
    ok(not errs, "no page errors: "+(errs[0][:140] if errs else "ok"))
    br.close()
print("\n"+("ALL OK" if not fails else f"{len(fails)} PROBLEMS: "+" | ".join(fails)))
sys.exit(1 if fails else 0)
