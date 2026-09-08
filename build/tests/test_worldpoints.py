import re, json, sys
from playwright.sync_api import sync_playwright
BASE = "http://localhost:8011/web/"
fails = []


def ok(c, m):
    print(("  ✓ " if c else "  ✗ ") + m)
    if not c:
        fails.append(m)


def routes(ctx):
    ctx.route(re.compile(r"https://tiles\.openfreemap\.org/.*"), lambda r: r.fulfill(
        status=200, content_type="application/json",
        body=json.dumps({"version": 8, "sources": {}, "layers": [
            {"id": "bg", "type": "background", "paint": {"background-color": "#e8e4d8"}}]})))
    ctx.route(re.compile(r"https://spots\.wwff\.co/static/spots\.json"), lambda r: r.fulfill(
        status=200, content_type="application/json", body="[]"))
    ctx.route(re.compile(r"https://spots\.wwff\.co/static/agendas.*"), lambda r: r.fulfill(
        status=200, content_type="application/json", body="[]"))
    ctx.route(re.compile(r"https://docs\.google\.com/.*"), lambda r: r.abort())


with sync_playwright() as p:
    br = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
                            if __import__('os').path.exists("/opt/pw-browsers/chromium-1194/chrome-linux/chrome") else None)
    ctx = br.new_context(service_workers="block", viewport={"width": 420, "height": 860})
    routes(ctx)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE, wait_until="load")
    pg.wait_for_timeout(3000)   # the real wwff-world.geojson is ~9 MB, give it a moment

    print("\n[1] factory setting: the worldwide layer is on")
    default_on = pg.evaluate("() => showWorld")
    ok(default_on is True, f"showWorld default is true (got {default_on})")
    default_filter = pg.evaluate("() => worldFilter")
    ok(default_filter == "all", f"worldFilter default is 'all' (got '{default_filter}')")

    print("\n[2] the worldwide points layer is loaded and drawn")
    pg.wait_for_function("() => worldLoaded === true", timeout=15000)
    n = pg.evaluate("() => worldPoints.features.length")
    ok(n > 60000, f"more than 60.000 points loaded (got {n})")
    has_onff = pg.evaluate("() => worldPoints.features.some(f => f.properties.ref.startsWith('ONFF'))")
    ok(not has_onff, "no ONFF references in the worldwide layer (that is our own map layer)")
    src_exists = pg.evaluate("() => !!map.getSource('wwff-world')")
    ok(src_exists, "MapLibre source 'wwff-world' exists")
    # world-cluster-count is a text layer and needs glyphs — the mock test style
    # does not have those (no more than np-label, which has had the same
    # 'if(glyphs)' wait for a while now).
    layers_exist = pg.evaluate(
        "() => ['world-clusters','world-point'].every(l => !!map.getLayer(l))")
    ok(layers_exist, "the cluster and point layers exist")

    print("\n[3] filtering to one country narrows the source")
    pg.evaluate("""() => {
        const sel = document.getElementById('setWorldCountry');
        const opt = [...sel.options].find(o => o.textContent === 'Netherlands');
        sel.value = opt.value; sel.dispatchEvent(new Event('change'));
    }""")
    pg.wait_for_timeout(300)
    saved_filter = pg.evaluate("() => worldFilter")
    ok(saved_filter == "PAFF", f"worldFilter is 'PAFF' after choosing a country (got '{saved_filter}')")
    filtered_n = pg.evaluate("() => worldFilteredData().features.length")
    all_paff = pg.evaluate(
        "() => worldFilteredData().features.every(f => f.properties.ref.toUpperCase().split('-')[0] === 'PAFF')")
    ok(filtered_n > 0 and all_paff, f"only PAFF references in the filtered data ({filtered_n} of them)")

    print("\n[4] the choice survives a reload")
    stored = pg.evaluate("() => localStorage.getItem('diana.worldFilter')")
    ok(stored == "PAFF", f"'PAFF' saved in localStorage (got '{stored}')")
    pg.reload(wait_until="load")
    pg.wait_for_timeout(3000)
    pg.wait_for_function("() => worldLoaded === true", timeout=15000)
    after_reload = pg.evaluate("() => worldFilter")
    ok(after_reload == "PAFF", f"worldFilter still 'PAFF' after a reload (got '{after_reload}')")
    sel_after = pg.evaluate("() => document.getElementById('setWorldCountry').value")
    ok(sel_after == "PAFF", "the country dropdown shows the saved choice after a reload")

    print("\n[5] back to worldwide")
    pg.evaluate("""() => {
        const sel = document.getElementById('setWorldCountry');
        sel.value = ''; sel.dispatchEvent(new Event('change'));
    }""")
    pg.wait_for_timeout(300)
    back_to_all = pg.evaluate("() => worldFilter")
    ok(back_to_all == "all", f"worldFilter is 'all' again (got '{back_to_all}')")

    print("\n[6] the layer can be switched off and on from the layers panel")
    pg.evaluate("() => document.querySelector('.opt[data-layer=\"world\"]').click()")
    pg.wait_for_timeout(200)
    off_vis = pg.evaluate("() => map.getLayoutProperty('world-point','visibility')")
    ok(off_vis == 'none', f"layer hidden after switching off (got '{off_vis}')")
    pg.evaluate("() => document.querySelector('.opt[data-layer=\"world\"]').click()")
    pg.wait_for_timeout(200)
    on_vis = pg.evaluate("() => map.getLayoutProperty('world-point','visibility')")
    ok(on_vis == 'visible', f"layer visible again after switching on (got '{on_vis}')")

    print("\n[7] an embed without ?world=1 leaves the layer off")
    pg2 = ctx.new_page()
    pg2.on("pageerror", lambda e: errs.append(str(e)))
    pg2.goto(BASE + "?embed=1", wait_until="load")
    pg2.wait_for_timeout(2000)
    embed_off = pg2.evaluate("() => showWorld")
    ok(embed_off is False, f"showWorld is off in a bare embed (got {embed_off})")
    # Spots are precisely the exception: they always belong on it, in an embed too.
    embed_spots = pg2.evaluate("() => showSpots")
    ok(embed_spots is True, f"showSpots is on in an embed after all (got {embed_spots})")
    pg2.close()

    print("\n[8] an embed WITH ?world=1 does switch the layer on")
    pg3 = ctx.new_page()
    pg3.on("pageerror", lambda e: errs.append(str(e)))
    pg3.goto(BASE + "?embed=1&world=1", wait_until="load")
    pg3.wait_for_timeout(3000)
    embed_on = pg3.evaluate("() => showWorld")
    ok(embed_on is True, f"showWorld is on with ?world=1 (got {embed_on})")
    pg3.close()

    print("\n[9] no JS errors")
    real = [e for e in errs if "Failed to load resource" not in e]
    ok(not real, "no page errors: " + (real[0][:160] if real else "ok"))

    br.close()

print("\n" + ("ALL OK" if not fails else f"{len(fails)} PROBLEMS: " + " | ".join(fails)))
sys.exit(1 if fails else 0)
