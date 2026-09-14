# How Diana gets a position, as opposed to what it does with one.
#
# The bug this guards: standing inside a reserve, Diana said "you are outside".
# Not a boundary problem — the position itself was wrong. A GPS chip that has
# just woken up has no satellites, and the browser fills the gap with a fix off
# wifi and cell masts that can be hundreds of metres out. getCurrentPosition()
# takes that first answer and runs with it, and maximumAge:5000 even allowed a
# stale one. Opening another app that forced a real fix, then coming back, made
# Diana right again — which is exactly what you would expect if the first
# answer was the problem.
#
# So locate() now watches until the accuracy is good enough (or the budget runs
# out) before it answers. The real geolocation is replaced here by a stub that
# emits a coarse fix first and a sharp one later, in a place where the two land
# on opposite sides of a real ONFF boundary — so a premature answer is visibly
# the wrong answer.
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
    ctx.route(re.compile(r"https://spots\.wwff\.co/.*"), lambda r: r.fulfill(
        status=200, content_type="application/json", body="[]"))
    ctx.route(re.compile(r"https://docs\.google\.com/.*"), lambda r: r.abort())

# A stand-in for navigator.geolocation. Emits whatever window.__SEQ holds, on
# the timings given there, and records what was asked of it. getCurrentPosition
# throws on purpose: nothing in Diana may go back to asking once.
STUB = """
window.__GEO = {watches: 0, cleared: [], opts: [], usedGetCurrent: false};
const g = {
  watchPosition(ok, err, opts){
    const id = ++window.__GEO.watches;
    window.__GEO.opts.push(opts || {});
    (window.__SEQ || []).forEach(s => setTimeout(() => {
      if(window.__GEO.cleared.includes(id)) return;
      if(s.err) { if(err) err({code: 2, message: 'stub failure'}); return; }
      ok({coords: {latitude: s.lat, longitude: s.lon, accuracy: s.acc}, timestamp: Date.now()});
    }, s.t));
    return id;
  },
  clearWatch(id){ window.__GEO.cleared.push(id); },
  getCurrentPosition(){ window.__GEO.usedGetCurrent = true;
                        throw new Error('getCurrentPosition: Diana must watch, not ask'); },
};
Object.defineProperty(navigator, 'geolocation', {value: g, configurable: true});
"""

with sync_playwright() as p:
    br = p.chromium.launch()
    ctx = br.new_context(service_workers="block", viewport={"width": 420, "height": 860})
    routes(ctx)
    ctx.add_init_script(STUB)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE, wait_until="load")
    pg.wait_for_timeout(2500)

    # A point genuinely inside a real ONFF polygon, and a coarse "fix" a few
    # hundred metres away that falls outside it — the Waasmunster situation in
    # miniature.
    spot = pg.evaluate("""
      () => {
        const f = zones.features.find(x => x.geometry &&
          x.geometry.coordinates.length && x.geometry.coordinates[0][0].length > 200);
        // centre of the bbox, nudged until it really is inside
        const b = bboxOf(f.geometry);
        const lon = (b[0]+b[2])/2, lat = (b[1]+b[3])/2;
        if(!pointInGeom(lon, lat, f.geometry)){
          for(const [x,y] of f.geometry.coordinates[0][0]){
            // a vertex pulled a little towards the centre is inside
            const tx = x + (lon-x)*0.05, ty = y + (lat-y)*0.05;
            if(pointInGeom(tx, ty, f.geometry)) return {ref: f.properties.ref, lat: ty, lon: tx};
          }
          return null;
        }
        return {ref: f.properties.ref, lat, lon};
      }
    """)
    ok(spot is not None, f"found a point truly inside a real reference ({spot and spot['ref']})")
    ref, lat, lon = spot["ref"], spot["lat"], spot["lon"]
    coarse_lat, coarse_lon = lat + 0.006, lon + 0.006      # ≈ 800 m away
    # ... and it has to be genuinely outside the polygon, or "the wrong answer"
    # in [3b] is not wrong at all. Walk outwards until it really is.
    outside = pg.evaluate(f"""() => {{
        const f = zones.features.find(x => x.properties.ref === {ref!r});
        for(let k = 1; k < 60; k++){{
          const la = {lat} + 0.002*k, lo = {lon} + 0.002*k;
          if(!pointInGeom(lo, la, f.geometry)) return {{lat: la, lon: lo}};
        }}
        return null;
    }}""")
    ok(outside is not None, "found a point just outside that same reference")
    coarse_lat, coarse_lon = outside["lat"], outside["lon"]

    # The app locates itself once at startup, quietly. With no sequence set that
    # run just sits there until its budget expires, and locate() rightly refuses
    # to start a second watch next to it — so close it first.
    stop_run = "() => { if(fixRun && fixRun.run) fixRun.run.stop(); fixRun = null; }"

    print("\n[1] a coarse first fix does not get to answer")
    pg.evaluate(stop_run)   # closing it clears a watch too, so count from after
    base = pg.evaluate("() => ({w: window.__GEO.watches, c: window.__GEO.cleared.length})")
    pg.evaluate(f"""() => {{
      window.__SEQ = [
        {{t: 50,   lat: {coarse_lat}, lon: {coarse_lon}, acc: 1400}},
        {{t: 250,  lat: {coarse_lat}, lon: {coarse_lon}, acc: 380}},
        {{t: 1200, lat: {lat}, lon: {lon}, acc: 12}},
      ];
      hideStatus(); locate();
    }}""")
    pg.wait_for_timeout(500)     # the two coarse fixes are in, the sharp one is not
    txt = pg.evaluate("() => document.getElementById('stT1').textContent + ' / ' + document.getElementById('stT2').textContent")
    ok("380" in txt or "1400" in txt, f"it says it is still sharpening, with the accuracy ({txt.strip()[:60]})")
    cls = pg.evaluate("() => document.getElementById('status').className")
    ok("in" not in cls.split() and "near" not in cls.split(),
       "and has not yet claimed you are inside or outside anything")

    print("\n[2] the sharp fix is the one that answers")
    pg.wait_for_timeout(1200)
    cls = pg.evaluate("() => document.getElementById('status').className")
    ok("in" in cls.split(), f"once it is sharp, the verdict is 'inside' ({cls})")
    ok(ref in pg.evaluate("() => document.getElementById('stT2').textContent"),
       f"and names {ref}, the reference you are actually standing in")
    pos = pg.evaluate("() => here")
    ok(abs(pos["lat"] - lat) < 1e-6, "the position kept is the sharp one, not the coarse one")

    print("\n[3] the watch stays open after answering, and is asked for properly")
    # It used to close the moment it had an answer. It no longer does: indoors
    # the first good-looking fix is often a wifi position that is confidently
    # wrong, and the only way to find that out is to keep listening. It closes
    # on the budget instead — [4] is where that is checked.
    geo = pg.evaluate("() => window.__GEO")
    ok(geo["watches"] - base["w"] == 1, f"exactly one watch was opened (got {geo['watches'] - base['w']})")
    ok(len(geo["cleared"]) - base["c"] == 0,
       f"and is still open, listening for something better (cleared: {geo['cleared']})")
    ok(geo["opts"][-1].get("maximumAge") == 0,
       f"a cached fix is refused outright (maximumAge: {geo['opts'][-1].get('maximumAge')})")
    ok(geo["opts"][-1].get("enableHighAccuracy") is True, "and high accuracy is asked for")
    ok(not geo["usedGetCurrent"], "nothing went back to asking once with getCurrentPosition")
    pg.evaluate("() => { if(fixRun && fixRun.run) fixRun.run.stop(); }")
    ok(len(pg.evaluate("() => window.__GEO.cleared")) - base["c"] == 1,
       "and closing it really does clear the watch")

    print("\n[3b] a confident wifi fix is overturned by a sharper one that disagrees")
    # The report from the field: indoors, no satellite lock, and the browser
    # answers off the wifi network claiming twenty metres — because that is how
    # accurate the wifi DATABASE thinks it is, not this answer. The operator
    # landed in the cemetery beside his house. So: answer at once, keep
    # listening, and let a sharper fix that genuinely disagrees take over.
    pg.evaluate(f"""() => {{
      window.__SEQ = [
        {{t: 50,   lat: {coarse_lat}, lon: {coarse_lon}, acc: 20}},   // wifi, wrong, confident
        {{t: 1500, lat: {lat}, lon: {lon}, acc: 8}},                  // the satellites arrive
      ];
      hideStatus(); if(fixRun && fixRun.run) fixRun.run.stop(); locate();
    }}""")
    pg.wait_for_timeout(600)
    first = pg.evaluate("() => here")
    cls = pg.evaluate("() => document.getElementById('status').className")
    ok(abs(first["lat"] - coarse_lat) < 1e-6, "it answers straight away on the wifi fix")
    ok("in" not in cls.split(), "and that answer is the wrong one — outside the reference")
    pg.wait_for_timeout(1400)
    after = pg.evaluate("() => here")
    cls = pg.evaluate("() => document.getElementById('status').className")
    ok(abs(after["lat"] - lat) < 1e-6, "the sharper fix takes over the position")
    ok("in" in cls.split(), f"and the verdict is put right ({cls})")
    ok(ref in pg.evaluate("() => document.getElementById('stT2').textContent"),
       f"naming {ref} after all")

    print("\n[3c] ordinary jitter does not move the answer around")
    # A metre or two of wander is not a disagreement. If every wobble re-ran the
    # verdict the marker would dance and the message would flicker.
    pg.evaluate(f"""() => {{
      window.__SEQ = [
        {{t: 50,  lat: {lat}, lon: {lon}, acc: 12}},
        {{t: 700, lat: {lat + 0.00003}, lon: {lon}, acc: 10}},   // ~3 m away, ±10 m
      ];
      hideStatus(); if(fixRun && fixRun.run) fixRun.run.stop(); locate();
    }}""")
    pg.wait_for_timeout(1100)
    held = pg.evaluate("() => lastFix")
    ok(held and abs(held["lat"] - lat) < 1e-6,
       "a sharper fix within its own error margin leaves the answer alone")
    ok(abs(pg.evaluate("() => here")["lat"] - lat) < 1e-6,
       "and the marker does not wander off to it either")

    print("\n[3d] an accuracy the browser will not state is not treated as perfect")
    # This was real: evaluate() read the accuracy as `accuracy || 0`, so a fix
    # with no stated accuracy came out as nought metres — which every comparison
    # below reads as "no doubt whatsoever". Unknown got the most confident
    # answer of the lot.
    pg.evaluate(f"""() => {{
      window.__SEQ = [{{t: 50, lat: {lat}, lon: {lon}}}];   // no accuracy at all
      hideStatus(); if(fixRun && fixRun.run) fixRun.run.stop(); locate();
    }}""")
    pg.wait_for_timeout(600)
    cls = pg.evaluate("() => document.getElementById('status').className")
    ok("in" not in cls.split(),
       "it does not answer on a fix whose accuracy is unknown")
    pg.wait_for_timeout(12000)
    cls = pg.evaluate("() => document.getElementById('status').className")
    txt = pg.evaluate("() => document.getElementById('stT2').textContent")
    ok("show" in cls, f"after the budget it does answer ({cls})")
    ok("in" not in cls.split(), "but never with a confident 'you are inside'")
    ok(len(txt) > 20 and ref in txt,
       f"it names the reference and says the accuracy is missing ({txt[:80]!r})")

    print("\n[4] a fix that never sharpens still gets an answer — an honest one")
    # Only coarse fixes, and the budget cut short so the test does not sit for
    # twelve seconds. ±800 m against a boundary 300 m away is 'too close to
    # call', which is what evaluate() should say — not a confident verdict.
    was = pg.evaluate("() => window.__GEO.cleared.length")
    pg.evaluate(f"""() => {{
      window.__SEQ = [{{t: 50, lat: {coarse_lat}, lon: {coarse_lon}, acc: 800}}];
      hideStatus(); if(fixRun && fixRun.run) fixRun.run.stop(); fixRun = null;
      locate();
    }}""")
    pg.wait_for_timeout(400)
    mid = pg.evaluate("() => document.getElementById('status').className")
    ok("in" not in mid.split(), "still no verdict while the budget runs")
    pg.wait_for_timeout(12000)
    cls = pg.evaluate("() => document.getElementById('status').className")
    ok("show" in cls, f"after the budget it does answer ({cls})")
    ok("near" in cls.split() or "out" in cls.split(),
       "with the coarse accuracy carried into the verdict, not hidden")
    ok(pg.evaluate("() => window.__GEO.cleared.length") > was,
       "that watch was cleared too")

    print("\n[5] tapping twice does not start a second watch")
    before_taps = pg.evaluate("() => window.__GEO.watches")
    pg.evaluate(f"""() => {{
      window.__SEQ = [{{t: 400, lat: {lat}, lon: {lon}, acc: 10}}];
      if(fixRun && fixRun.run) fixRun.run.stop(); fixRun = null;
      locate(); locate(); locate();
    }}""")
    pg.wait_for_timeout(800)
    ok(pg.evaluate("() => window.__GEO.watches") == before_taps + 1,
       "three taps in a row open one watch, not three")

    print("\n[6] nothing thrown along the way")
    real = [e for e in errs if "getCurrentPosition" not in e]
    ok(not real, f"no page errors: {real or 'ok'}")

    print("\nALL OK" if not fails else f"\n{len(fails)} FAILED")
    br.close()
    sys.exit(1 if fails else 0)
