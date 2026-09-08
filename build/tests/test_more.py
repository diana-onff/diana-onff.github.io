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

    print("\n[A] the default language is English, even with a Dutch browser")
    ctx=br.new_context(service_workers="block", locale="nl-BE", viewport={"width":420,"height":860}); routes(ctx)
    pg=ctx.new_page(); pg.goto(BASE, wait_until="load"); pg.wait_for_timeout(1500)
    ok(pg.evaluate("() => lang")=="en", "starts in English despite locale nl-BE")
    ok(pg.evaluate("() => langPref")=="en", "preference is set to 'en'")

    print("\n[B] setting the language in Settings stays saved")
    pg.evaluate("() => document.querySelector('#nav button[data-view=\"viewSet\"]').click()")
    pg.wait_for_timeout(300)
    pg.evaluate("() => document.querySelector('#setLang .seg[data-lang=\"nl\"]').click()")
    pg.wait_for_timeout(400)
    ok(pg.evaluate("() => lang")=="nl", "language switched to NL")
    ok(pg.evaluate("() => localStorage.getItem('diana.lang')")=="nl", "choice saved")
    ok("Instellingen" in pg.evaluate("() => document.querySelector('#viewSet h1').textContent"), "the screen really is translated too")
    pg.reload(wait_until="load"); pg.wait_for_timeout(1500)
    ok(pg.evaluate("() => lang")=="nl", "choice survives a reload")

    print("\n[C] 'Follow the browser' does what it says")
    pg.evaluate("() => document.querySelector('#nav button[data-view=\"viewSet\"]').click()")
    pg.evaluate("() => document.querySelector('#setLang .seg[data-lang=\"auto\"]').click()")
    pg.wait_for_timeout(400)
    ok(pg.evaluate("() => lang")=="nl", "follows the browser language nl-BE")
    ok(pg.evaluate("() => localStorage.getItem('diana.lang')")=="auto", "'auto' saved, not the resolved language")
    ctx.close()

    print("\n[D] an unknown browser language with 'auto' falls back to English")
    ctx=br.new_context(service_workers="block", locale="pl-PL"); routes(ctx)
    pg=ctx.new_page()
    pg.add_init_script("localStorage.setItem('diana.lang','auto')")
    pg.goto(BASE, wait_until="load"); pg.wait_for_timeout(1200)
    ok(pg.evaluate("() => lang")=="en", "Polish is not supported → English")
    ctx.close()

    print("\n[E] installing: the button only appears once the browser offers it")
    ctx=br.new_context(service_workers="block", viewport={"width":420,"height":860}); routes(ctx)
    pg=ctx.new_page(); pg.goto(BASE, wait_until="load"); pg.wait_for_timeout(1500)
    pg.evaluate("() => document.querySelector('#nav button[data-view=\"viewSet\"]').click()")
    pg.wait_for_timeout(200)
    ok(pg.evaluate("() => document.getElementById('instBtn').hidden"), "no button without an offer from the browser")
    how = pg.evaluate("() => document.getElementById('instHow').innerText")
    ok(len(how)>10, f"but there is an explanation per platform: “{how[:60]}…”")
    ok(pg.evaluate("() => document.getElementById('instBar').hidden"), "no bar without an offer")

    print("\n[F] installing: with an offer both button and bar appear, and the prompt runs")
    pg.evaluate("""() => {
      window.__prompted = 0; window.__choice = null;
      const e = new Event('beforeinstallprompt');
      e.prompt = () => { window.__prompted++; };
      e.userChoice = Promise.resolve({outcome:'accepted', platform:'web'});
      dispatchEvent(e);
    }""")
    pg.wait_for_timeout(300)
    ok(not pg.evaluate("() => document.getElementById('instBtn').hidden"), "button appears")
    ok(not pg.evaluate("() => document.getElementById('instBar').hidden"), "bar appears")
    pg.evaluate("() => document.getElementById('instBtn').click()")
    pg.wait_for_timeout(400)
    ok(pg.evaluate("() => window.__prompted")==1, "prompt() called exactly once")
    ok(pg.evaluate("() => localStorage.getItem('diana.installed')")=="1", "installed state remembered")
    ok("✓" in pg.evaluate("() => document.getElementById('instHow').innerText"), "now shows 'is installed'")

    print("\n[G] 'not now' does not ask again")
    pg.evaluate("() => { localStorage.removeItem('diana.installed'); localStorage.removeItem('diana.inst.asked'); }")
    pg.reload(wait_until="load"); pg.wait_for_timeout(1200)
    pg.evaluate("""() => { const e=new Event('beforeinstallprompt'); e.prompt=()=>{}; e.userChoice=Promise.resolve({outcome:'dismissed'}); dispatchEvent(e); }""")
    pg.wait_for_timeout(200)
    ok(not pg.evaluate("() => document.getElementById('instBar').hidden"), "bar is there")
    pg.evaluate("() => document.getElementById('instBarNo').click()")
    pg.wait_for_timeout(200)
    ok(pg.evaluate("() => document.getElementById('instBar').hidden"), "dismissed")
    pg.reload(wait_until="load"); pg.wait_for_timeout(1200)
    pg.evaluate("""() => { const e=new Event('beforeinstallprompt'); e.prompt=()=>{}; e.userChoice=Promise.resolve({outcome:'dismissed'}); dispatchEvent(e); }""")
    pg.wait_for_timeout(300)
    ok(pg.evaluate("() => document.getElementById('instBar').hidden"), "does not come back after a reload")

    print("\n[H] iOS: no dead button but the Safari steps")
    ctx2=br.new_context(service_workers="block",
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
        viewport={"width":390,"height":844}); routes(ctx2)
    pg2=ctx2.new_page(); pg2.goto(BASE, wait_until="load"); pg2.wait_for_timeout(1500)
    ok(pg2.evaluate("() => platform()")=="ios", "platform recognised as iOS/Safari")
    pg2.evaluate("() => document.querySelector('#nav button[data-view=\"viewSet\"]').click()")
    pg2.wait_for_timeout(200)
    txt = pg2.evaluate("() => document.getElementById('instHow').innerText")
    ok("Home Screen" in txt or "Add to" in txt, f"shows the Share→Add-to-Home-Screen steps: “{txt[:70]}…”")
    ok(pg2.evaluate("() => document.getElementById('instBtn').hidden"), "no button that could not do anything anyway")
    ctx2.close()

    print("\n[I] the manifest and icons really are reachable")
    r1 = pg.request.get("http://localhost:8011/web/manifest.webmanifest")
    r2 = pg.request.get("http://localhost:8011/web/icon-192.png")
    r3 = pg.request.get("http://localhost:8011/web/icon-512.png")
    r4 = pg.request.get("http://localhost:8011/web/apple-touch-icon.png")
    ok(r1.status==200 and r2.status==200 and r3.status==200 and r4.status==200,
       f"manifest {r1.status}, icons {r2.status}/{r3.status}/{r4.status}")
    mf = r1.json()
    ok(any(i["sizes"]=="512x512" for i in mf["icons"]), "the 512 icon is in the manifest")
    ok(any(i.get("purpose")=="maskable" for i in mf["icons"]), "maskable variant present")

    br.close()
print("\n"+("ALL OK" if not fails else f"{len(fails)} PROBLEMS: "+" | ".join(fails)))
sys.exit(1 if fails else 0)
