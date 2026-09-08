import re, json, sys
from playwright.sync_api import sync_playwright
BASE="http://localhost:8011/web/"
fails=[]
def ok(c,m):
    print(("  ✓ " if c else "  ✗ ")+m)
    if not c: fails.append(m)
def routes(ctx, sheet):
    ctx.route(re.compile(r"https://tiles\.openfreemap\.org/.*"), lambda r: r.fulfill(
        status=200, content_type="application/json",
        body=json.dumps({"version":8,"sources":{},"layers":[{"id":"bg","type":"background","paint":{"background-color":"#e8e4d8"}}]})))
    ctx.route(re.compile(r"https://spots\.wwff\.co/.*"), lambda r: r.fulfill(status=200, content_type="application/json", body="[]"))
    ctx.route(re.compile(r"https://docs\.google\.com/.*"), sheet)

CSV = ("Activity Date,ACTIVATING Station Callsign,QSO's,ONFF Ref\n"
       "2026-05-01,ON3VZ/P,44,ONFF-0104\n2026-06-02,ON4XX/P,60,ONFF-0002\n")

with sync_playwright() as p:
    br=p.chromium.launch()

    print("\n[1] sheet reachable → the year tables are used")
    ctx=br.new_context(service_workers="block", viewport={"width":390,"height":844})
    routes(ctx, lambda r: r.fulfill(status=200, content_type="text/csv", body=CSV))
    pg=ctx.new_page(); pg.goto(BASE, wait_until="load"); pg.wait_for_timeout(2500)
    pg.evaluate("() => document.querySelector('#nav button[data-view=\"viewHeat\"]').click()")
    pg.wait_for_timeout(1500)
    ok(pg.evaluate("() => heatSource")=="sheet", f"source = sheet (got {pg.evaluate('() => heatSource')})")
    ok(pg.evaluate("() => Object.keys(heat||{}).length")==2, "two areas from the mocked sheet")
    ctx.close()

    print("\n[2] sheet blocked (CORS) → fallback to the WWFF directory")
    ctx=br.new_context(service_workers="block", viewport={"width":390,"height":844})
    routes(ctx, lambda r: r.abort())
    pg=ctx.new_page(); errs=[]; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE, wait_until="load"); pg.wait_for_timeout(2500)
    pg.evaluate("() => document.querySelector('#nav button[data-view=\"viewHeat\"]').click()")
    pg.wait_for_timeout(2000)
    src = pg.evaluate("() => heatSource")
    ok(src=="wwff", f"source = wwff (got {src})")
    n = pg.evaluate("() => Object.keys(heat||{}).length")
    ok(n>800, f"{n} areas with activity from the directory")
    box = pg.evaluate("() => document.getElementById('heatBox').innerText")
    ok("WWFF" in box, "the user sees where it came from")
    ok("activated" in box.lower() or "geactiveerd" in box.lower(), "the plain summary is there too")
    buckets = pg.evaluate("""() => { const pp = map.getPaintProperty('onff-fill','fill-color');
        if(!Array.isArray(pp)) return 0;
        return pp.filter(x => typeof x === 'string' && x.startsWith('#')).length; }""")
    ok(buckets >= 4, f"the map is divided into {buckets} colour classes")
    rf = pg.evaluate("""() => { let n=0; for(const v of Object.values(heat)) if(v.date && +v.date.slice(0,4) < 1990) n++; return n; }""")
    ok(rf==0, f"impossible dates from the source filtered out ({rf} left)")
    neg = pg.evaluate("() => document.getElementById('negList').innerText")
    ok(len(neg)>20, "list of neglected areas filled in")
    ok(not [e for e in errs if 'Failed to load resource' not in e], "no JS errors")
    pg.screenshot(path="/tmp/shot_heat.png")
    br.close()
print("\n"+("ALL OK" if not fails else f"{len(fails)} PROBLEMS: "+" | ".join(fails)))
sys.exit(1 if fails else 0)
