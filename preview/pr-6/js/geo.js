/* ---------- GPS: am I inside the zone? ---------- */
function pointInRing(x,y,ring){
  let inside=false;
  for(let i=0,j=ring.length-1;i<ring.length;j=i++){
    const [xi,yi]=ring[i], [xj,yj]=ring[j];
    if(((yi>y)!==(yj>y)) && (x < (xj-xi)*(y-yi)/(yj-yi)+xi)) inside=!inside;
  }
  return inside;
}
function pointInGeom(x,y,geom){
  for(const poly of geom.coordinates){
    if(pointInRing(x,y,poly[0])){
      let inHole=false;
      for(let h=1;h<poly.length;h++) if(pointInRing(x,y,poly[h])) inHole=true;
      if(!inHole) return true;
    }
  }
  return false;
}
function haversine(lat1,lon1,lat2,lon2){
  const R=6371000, t=Math.PI/180;
  const a=Math.sin((lat2-lat1)*t/2)**2 +
          Math.cos(lat1*t)*Math.cos(lat2*t)*Math.sin((lon2-lon1)*t/2)**2;
  return 2*R*Math.asin(Math.sqrt(a));
}
function distanceToZone(lat,lon,f){
  // Shortest distance to an edge point. Plenty good enough for "how far are you from the boundary".
  let best=Infinity;
  for(const poly of f.geometry.coordinates)
    for(const [x,y] of poly[0]){
      const d=haversine(lat,lon,y,x);
      if(d<best) best=d;
    }
  return best;
}
/* ---------- getting a position that can be trusted ----------
 *
 * Asking the browser where you are is not one question with one answer. A GPS
 * chip that has just woken up has no satellites yet, and the browser answers
 * in the meantime from wifi networks and cell masts — a position that can be
 * hundreds of metres out, handed over with exactly the same air of confidence
 * as a real one. That is what made Diana report "you are outside" while
 * standing in the middle of a reserve: the boundary check was right, the
 * position was wrong. Opening another app that forces a proper fix and coming
 * back made it correct, which is the tell.
 *
 * getCurrentPosition() takes whatever that first answer happens to be, and
 * maximumAge made it worse by allowing a fix from seconds ago to count.
 *
 * So: watch instead of ask. Fixes arrive in waves and the reported accuracy
 * falls as satellites come in — 1500 m, 400 m, 60 m, 12 m. The marker follows
 * along, but the question "are you inside this reference" is not answered
 * until the accuracy is good enough, or until we have waited long enough and
 * answer with the sharpest fix we got (which, being honestly ±400 m, comes out
 * of evaluate() as "too close to call" rather than a confident lie).
 *
 * That was not enough, and a report from the field showed why. Indoors, a
 * phone often never gets a satellite lock at all: the browser answers from the
 * wifi network, within a second, claiming twenty metres — because that is how
 * accurate the wifi database thinks it is, not how accurate this answer is. If
 * the router is registered at an old address, you get a confident position a
 * few hundred metres away. One operator landed in the cemetery beside his
 * house, with every number in the app claiming it was right.
 *
 * You cannot tell those apart at the moment they arrive. So we stopped trying:
 * the first good-looking fix still answers straight away, but the watch keeps
 * running for the rest of the budget and the answer is revised as more readings
 * come in. Outdoors, where the first fix is already the real one, nothing
 * changes and you notice nothing. Indoors, the answer corrects itself a few
 * seconds later instead of quietly being wrong.
 *
 * Which reading wins is NOT decided by the accuracy it claims for itself —
 * that was the next thing to fail, and it failed on the same phone that
 * reported ±5 m while its answers stood fifty metres apart. The readings are
 * judged against each other instead; see "what the readings TOGETHER say"
 * below.
 *
 * And an accuracy the browser will not state is never treated as a good one.
 * "Unknown" used to come out of evaluate() as nought metres — which reads as
 * perfect, and switched off the very doubt it should have raised.
 */
const FIX_GOOD_M  = 25;      // sharp enough to answer on
const FIX_WAIT_MS = 12000;   // and never keep anyone waiting longer than this
/* Past this, a poor fix stops reading as ordinary outdoor GPS noise and
   starts reading as a permission problem: a browser can be told to share
   only an "approximate" location — for itself, or for one site specifically
   — deliberately fuzzed into an area the size of a small town. No amount of
   waiting or pressing ◎ fixes that; only the browser's own location setting
   does. A field report showed exactly this: a comparison app on the same
   phone, at the same spot, held a steady 15 m while Diana sat at 98 and then
   136 m on two separate tries. See accHint below and set.fixhint.
   Deliberately well above FIX_GOOD_M: ordinary outdoor scatter or a slow
   satellite lock can land in between and is not what this is warning about. */
const FIX_HINT_M = 75;
let fixRun = null;           // the locate() in progress, or null
/* The last position we committed to, for the readout in Settings: there is no
   other way to tell a sharp fix from a coarse one after the fact, and "it put
   me in the wrong place" is not something you can debug from a screenshot. */
let lastFix = null;
/* Where the marker is standing at this moment, with the accuracy that came
   with it. Drives the ring on the map; see fixApply() for why it is not the
   same thing as lastFix. */
let ringFix = null;
/* Whether the readings behind the current answer contradicted each other. Set
   where the verdict is made, read where the verdict is worded. */
let fixScattered = false;

/* How far apart two fixes are, in metres. */
function fixApart(a, b){
  return haversine(a.coords.latitude, a.coords.longitude,
                   b.coords.latitude, b.coords.longitude);
}

/* ---------- what the readings TOGETHER say ----------
 *
 * Five readings from one spot in Hoboken, two minutes apart at most: 773 m
 * ±6, 820 m ±11, 768 m ±10, 776 m ±8, 767 m ±5 to the same reference. Four of
 * those ten pairs are mutually impossible — 820 ±11 against 767 ±5 differ by
 * 53 m where their own margins allow 16. The phone was not a little
 * optimistic; it claimed ±8 while scattering over fifty metres.
 *
 * No rule that reads the stated accuracy can catch that, because the stated
 * accuracy is the thing that is wrong. But the readings catch each other: if
 * several of them, taken seconds apart, land further apart than they claim to
 * be able to, then that claim is refuted by the phone's own evidence. So the
 * margin Diana reports is the larger of what the phone says and what its
 * answers actually do.
 *
 * Two things keep this from overreacting:
 *   - only fixes of comparable quality are weighed against each other. A wifi
 *     fix claiming 20 m and a satellite fix claiming 8 m do not "disagree" —
 *     one is simply better, and the coarse one is dropped rather than allowed
 *     to inflate the margin to the distance between them.
 *   - the position becomes the most central of the readings rather than the
 *     first or the last, which is what makes a single wild outlier harmless.
 */
const FIX_WINDOW_MS = 45000;   // readings older than this say nothing about now
const FIX_CREDIBLE  = 2;       // within 2x of the best stated accuracy counts
const FIX_WALK_MPS  = 1.4;     // you could honestly have walked this far meanwhile
const FIX_SCATTER   = 1.5;     // beyond this much of the stated margin: scattered

/* Every reading of the last minute, across taps — not per run. Those five
   readings were five separate presses of the ◎ button, so a history that
   started fresh each time would never see them disagree. */
let fixLog = [];

function fixRemember(lat, lon, acc, at){
  fixLog.push({lat, lon, acc, at: at || Date.now()});
  const cut = Date.now() - FIX_WINDOW_MS;
  fixLog = fixLog.filter(f => f.at >= cut).slice(-16);
}

/* The readings worth weighing against each other: recent, and not obviously
   worse than the best one in hand. */
function fixCredible(now){
  const fresh = fixLog.filter(f => now - f.at <= FIX_WINDOW_MS);
  if(!fresh.length) return [];
  const best = Math.min(...fresh.map(f => f.acc));
  return fresh.filter(f => f.acc <= Math.max(best * FIX_CREDIBLE, best + 5));
}

/* Where the readings agree you are, and how far out that can be.
   Returns {lat, lon, acc, scattered} or null. */
function fixVerdict(now){
  now = now == null ? Date.now() : now;
  const set = fixCredible(now);
  if(!set.length) return null;
  const sharp = set.reduce((a, b) => (b.acc < a.acc ? b : a));
  if(set.length === 1) return {lat:sharp.lat, lon:sharp.lon, acc:sharp.acc, scattered:false};

  // The medoid: the reading with the least total distance to the others. Not an
  // average — averaging two clusters puts you in the street between them, where
  // no reading ever said you were.
  let mid = set[0], midSum = Infinity;
  for(const a of set){
    let sum = 0;
    for(const b of set) sum += haversine(a.lat, a.lon, b.lat, b.lon);
    if(sum < midSum){ midSum = sum; mid = a; }
  }
  // How far the readings stand apart beyond what they could honestly explain:
  // their own margins, plus the walking you might have done in between. What is
  // left over is scatter, and scatter is error the phone did not own up to.
  let reach = mid.acc;
  for(const b of set){
    const walked = FIX_WALK_MPS * Math.abs(b.at - mid.at) / 1000;
    const onverklaard = haversine(mid.lat, mid.lon, b.lat, b.lon) - walked;
    if(onverklaard > reach) reach = onverklaard;
  }
  // Consistent readings leave the sharpest one to speak for itself; only when
  // they genuinely contradict each other does the middle of the cloud become
  // the better answer, with the width of the cloud as the margin.
  if(reach <= sharp.acc * FIX_SCATTER)
    return {lat:sharp.lat, lon:sharp.lon, acc:sharp.acc, scattered:false};
  return {lat:mid.lat, lon:mid.lon, acc:Math.round(reach), scattered:true};
}

/* A verdict dressed as a Position, so that everything downstream — fixApply,
   evaluate, the ring — keeps taking one kind of thing. */
function fixAsPos(v){
  return {coords:{latitude:v.lat, longitude:v.lon, accuracy:v.acc}, timestamp:Date.now()};
}

/* Worth telling the user about again? A metre of drift is not. */
function fixMoved(a, b){
  if(!a) return true;
  return haversine(a.lat, a.lon, b.lat, b.lon) > 5 ||
         Math.abs(a.acc - b.acc) > Math.max(5, a.acc * 0.25);
}

/* Everything that follows from a new position. `final` separates following
   along on the map (every wave) from committing to an answer (once). */
function fixApply(pos, final){
  const {latitude:lat, longitude:lon} = pos.coords;
  const accuracy = fixAcc(pos);
  here = {lat, lon};
  // Two different things, deliberately kept apart. lastFix is what Diana
  // committed to and is what Settings reports; ringFix is simply where the
  // marker is standing right now, final or not, because the ring has to follow
  // the marker — a circle drawn around a position the marker has already left
  // is worse than none at all. While it is still searching, that ring shrinking
  // is also the clearest sign that anything is happening.
  ringFix = {lat, lon, acc: accuracy};
  if(final){
    lastFix = {lat, lon, acc: accuracy, at: Date.now()};
    if(typeof syncFixUI === 'function') syncFixUI();
    if(typeof syncAccHint === 'function') syncAccHint();
  }
  if(typeof paintFixAcc === 'function') paintFixAcc();
  marker.setLngLat([lon,lat]).addTo(map);
  if(final) map.easeTo({center:[lon,lat], zoom:Math.max(map.getZoom(),12)});
  renderSpots();
  // Nearby was drawn from the centre of your locator square until now, or not
  // at all — a real fix changes every distance on it. A new position is a new
  // list, so it starts at the first pageful again.
  nearShown = NEAR_MAX_ROWS;
  if($('viewNearby').classList.contains('on')) renderNearby();
  // The arc lines were drawn from the locator square too; redraw them, or they
  // stay skewed until you happen to switch tabs.
  if(showSpots) paintSpots();
  if(final) evaluate(lat, lon, accuracy);
}

/* The reported accuracy in metres, or null when the browser did not give a
   usable one. Zero is a number, not a missing value — reading it as "unknown"
   is how you end up waiting the full budget for a fix that was already perfect
   by the browser's own account. */
function fixAcc(pos){
  const a = pos && pos.coords ? pos.coords.accuracy : null;
  return (typeof a === 'number' && isFinite(a) && a >= 0) ? a : null;
}

/* The one way to get a position in Diana. onFinal gets the sharpest fix we
   could get within the budget; onFail only fires when there is nothing at all.
   Used by the ◎ button, by the map at startup, and by "take my locator from
   the GPS" in Settings — the same trap catches all three. */
function bestFix(onFinal, onProgress, onFail, onEnd){
  if(!navigator.geolocation){ if(onFail) onFail(null); return null; }
  const run = {watch:null, timer:null, best:null, answered:null, done:false};
  run.stop = () => {
    if(run.done) return;
    run.done = true;
    if(run.watch != null) navigator.geolocation.clearWatch(run.watch);
    if(run.timer != null) clearTimeout(run.timer);
    run.watch = run.timer = null;
    if(onEnd) onEnd();
  };
  // The budget is up: answer with the sharpest thing we have, if we have not
  // answered already, and close the watch either way — one left running costs
  // battery all afternoon.
  run.timer = setTimeout(() => {
    const best = run.best;
    const alwaar = run.answered;
    run.stop();
    if(!alwaar){
      // Nothing was good enough to answer on. Whatever we did collect still
      // has to be judged together — a reading with no stated accuracy, or one
      // too coarse to commit to, is exactly the case where the readings as a
      // whole know more than any one of them.
      const verdict = fixVerdict();
      if(verdict){ fixScattered = verdict.scattered; onFinal(fixAsPos(verdict)); }
      else if(best) onFinal(best);
      else if(onFail) onFail(null);
    }
  }, FIX_WAIT_MS);

  run.watch = navigator.geolocation.watchPosition(pos => {
    if(run.done) return;
    const acc = fixAcc(pos), best = fixAcc(run.best);
    // Keep the sharpest fix so far, not the most recent one: accuracy does not
    // only improve, it wanders. A fix without a stated accuracy never displaces
    // one that has it — unknown is not better than known.
    if(!run.best || (acc != null && (best == null || acc < best))) run.best = pos;
    // Following along is for while we are still searching. Once there is an
    // answer, the only thing allowed to move the marker is a fix good enough to
    // overturn it — otherwise the next wifi wave drags it back to the wrong
    // place, after the satellites had just put it right.
    if(onProgress && !run.answered) onProgress(pos);

    // No stated accuracy: usable as a position to follow along with, never as
    // grounds to commit to an answer. Keep looking; the deadline will take it
    // if nothing better turns up, and evaluate() will then say out loud that it
    // does not know how good it is.
    if(acc == null) return;

    // Into the log, and then let ALL the recent readings decide together —
    // this one included. That is what turns "the phone says ±5 m" into "the
    // phone's last four answers stand 50 m apart, so ±5 m is not true".
    fixRemember(pos.coords.latitude, pos.coords.longitude, acc);
    const verdict = fixVerdict();
    if(!verdict) return;

    if(!run.answered){
      // Still as quick as before: one usable reading is enough to answer on.
      if(verdict.acc <= FIX_GOOD_M || acc <= FIX_GOOD_M){
        run.answered = verdict;
        fixScattered = verdict.scattered;
        onFinal(fixAsPos(verdict));
      }
      return;
    }
    // Answered already, and now there is more evidence. Re-answer whenever the
    // picture has really changed — the position moved, or the margin turned out
    // to be wider or narrower than we said. No test on this single fix being
    // "better": the whole point is that a fix cannot be trusted to rate itself.
    if(fixMoved(run.answered, verdict)){
      run.answered = verdict;
      fixScattered = verdict.scattered;
      onFinal(fixAsPos(verdict));
    }
  }, err => {
    if(run.done) return;
    // A wobble after we already have something usable is not a failure.
    if(run.answered){ run.stop(); return; }
    if(run.best){ const best = run.best; run.stop(); onFinal(best); return; }
    run.stop();
    if(onFail) onFail(err);
  }, {enableHighAccuracy:true, timeout:FIX_WAIT_MS, maximumAge:0});
  return run;
}

function locate(quiet){
  // quiet: called at startup instead of by a tap on ◎. No searching message and
  // no error message then — anyone who doesn't share their location ought to
  // simply see a map, not a complaint.
  if(!navigator.geolocation){ if(!quiet) showStatus('out', t('gps.none'), t('gps.nonesub')); return; }
  if(fixRun){
    // Still looking: a second tap should not open a second watch, only start
    // showing what the first one is doing. But once it has answered, tapping ◎
    // is asking again — and then it has to mean something, so that run is
    // closed and a fresh one starts.
    if(fixRun.run && fixRun.run.answered){ fixRun.run.stop(); }
    else { if(!quiet) fixRun.quiet = false; return; }
  }
  if(!quiet) showStatus('out', t('gps.searching'), '');

  // The token is claimed before the watch starts, so a fix that arrives
  // immediately cannot finish before we have something to compare against.
  const mine = {quiet: !!quiet};
  fixRun = mine;
  const loud = () => fixRun === mine && !mine.quiet;

  mine.run = bestFix(
    // Fires once when there is an answer, and again if a later fix overturns
    // it. Both are a full answer: marker, map and verdict.
    pos => fixApply(pos, true),
    pos => {
      const say = loud();
      fixApply(pos, false);
      const acc = fixAcc(pos);
      if(say) showStatus('out', t('gps.searching'),
        acc == null ? '' : t('gps.refining').replace('{a}', Math.round(acc)));
    },
    err => {
      const say = loud();
      if(say) showStatus('out', t('gps.failed'), err ? err.message : t('gps.nofix'));
    },
    // The watch is closed: only now is another one allowed to start.
    () => { if(fixRun === mine) fixRun = null; });
  if(!mine.run && fixRun === mine) fixRun = null;
}
function evaluate(lat,lon,accuracy){
  // Only real boundaries take part in "am I inside it". A point without a
  // polygon has no inside — you can't ask that question about it.
  const cand = index.filter(z => z.bbox &&
                                 lon>=z.bbox[0]-0.02 && lon<=z.bbox[2]+0.02 &&
                                 lat>=z.bbox[1]-0.02 && lat<=z.bbox[3]+0.02);
  const inside=[];
  for(const z of cand){
    const f = zones.features.find(x=>x.properties.ref===z.ref);
    if(pointInGeom(lon,lat,f.geometry)) inside.push(f);
  }
  // Unknown is not nought. This used to be `accuracy||0`, and nought metres is
  // read everywhere below as "no doubt whatsoever" — so a browser that would
  // not say how good its fix was got the most confident answer of all. Null
  // now, and every comparison below has to deal with it.
  const acc = (typeof accuracy === 'number' && isFinite(accuracy) && accuracy >= 0)
    ? Math.round(accuracy) : null;
  // How good the position was, said out loud, in every verdict — not only in
  // the one case where it happens to be about to flip the answer. Without it a
  // marker looks equally certain at ±6 m and at ±80 m, and a position that
  // wanders eighty metres between refreshes reads as a fault in the app rather
  // than as what the phone can manage indoors.
  const note = (acc == null ? ' · ' + t('gps.noacc')
                            : ' · ' + t('gps.accis').replace('{a}', acc))
             + (fixScattered ? ' · ' + t('gps.scatter') : '');
  if(inside.length){
    // Edge case: are you so close to the boundary that the GPS error could flip the answer?
    const edge = Math.min(...inside.map(f=>distanceToZone(lat,lon,f)));
    const names = inside.map(f=>`${f.properties.ref} ${f.properties.name}`).join(' · ');
    if(acc == null){
      // No margin to reason with. Say where the position puts you and say, in
      // the same breath, that there is nothing behind it — inventing a radius
      // here would be making up the very number that is missing.
      showStatus('near', t('gps.inone'), `${names}${note}`);
    } else if(edge < acc){
      showStatus('near', t('gps.nearedge').replace('{ref}', inside[0].properties.ref),
        t('gps.nearedgesub').replace('{d}', Math.round(edge)).replace('{a}', acc));
    } else {
      showStatus('in', inside.length>1 ? t('gps.inmany').replace('{n}', inside.length) : t('gps.inone'),
        `${names} — ${t('gps.toedge').replace('{d}', Math.round(edge))}${note}`);
    }
    select(inside[0].properties.ref, inside.map(f=>f.properties.ref));
  } else {
    // Same edge case as above, mirrored: the GPS point falls just outside a
    // real boundary, but not further outside than the GPS's own reported
    // error margin — so "outside" isn't something we can actually claim yet
    // either. `cand`'s bbox is padded by ~2.2 km, far more than any realistic
    // accuracy value, so a boundary within `acc` of this point — if one
    // exists — is already in `cand`.
    let nearEdgeF=null, nearEdgeD=Infinity;
    for(const z of cand){
      const f = zones.features.find(x=>x.properties.ref===z.ref);
      const d = distanceToZone(lat,lon,f);
      if(d<nearEdgeD){ nearEdgeD=d; nearEdgeF=f; }
    }
    if(nearEdgeF && acc != null && nearEdgeD < acc){
      showStatus('near', t('gps.nearedge').replace('{ref}', nearEdgeF.properties.ref),
        t('gps.nearedgesub').replace('{d}', Math.round(nearEdgeD)).replace('{a}', acc));
      select(nearEdgeF.properties.ref);
      return;
    }
    let best=null,bd=Infinity;
    for(const z of index){
      const zlat = z.lat ?? (z.bbox ? (z.bbox[1]+z.bbox[3])/2 : null);
      const zlon = z.lon ?? (z.bbox ? (z.bbox[0]+z.bbox[2])/2 : null);
      if(zlat==null || zlon==null) continue;
      const d=haversine(lat,lon,zlat,zlon);
      if(d<bd){bd=d;best=z;}
    }
    if(!best){ showStatus('out', t('gps.outside'), note.replace(/^ · /, '')); return; }
    // For a reference without a boundary there is no boundary to measure a
    // distance to; then the distance to the point is the most honest answer we
    // have.
    const f = zones.features.find(x=>x.properties.ref===best.ref);
    const edge = f ? distanceToZone(lat,lon,f) : bd;
    const dist = edge>1500 ? (edge/1000).toFixed(1)+' km' : Math.round(edge)+' m';
    showStatus('out', t('gps.outside'),
      `${t('gps.nearest')}: ${best.ref} ${best.name} — ${dist}${f?'':' ('+t('zone.nopoly')+')'}${note}`);
  }
}
/* ---------- what the last position actually was ----------
 *
 * "It put me in the wrong place" is not something anyone can debug from a
 * screenshot: a marker looks equally certain whether it came from a satellite
 * or from a wifi network that is registered at last year's address. So the
 * figures behind it are readable in Settings — how accurate, how old, and
 * whether there is a GPS position at all or whether the distances are coming
 * from the centre of your locator square, which for a six-character locator is
 * a box of some five kilometres.
 */
const GRID_KM = {4: 110, 6: 5, 8: 0.5};

function syncFixUI(){
  const el = $('setFixState');
  if(!el) return;
  if(lastFix){
    const min = Math.floor((Date.now() - lastFix.at) / 60000);
    const when = min < 1 ? t('spot.justnow') : t('spot.minago').replace('{n}', min);
    el.textContent = (lastFix.acc == null
        ? t('set.fixnoacc')
        : t('set.fixacc').replace('{a}', Math.round(lastFix.acc)))
      .replace('{when}', when)
      + ((lastFix.acc == null || lastFix.acc > FIX_GOOD_M) ? ' ' + t('set.fixcoarse') : '')
      // The one line in Settings that never goes away, whatever happened to the
      // banner on the other screens — dismissing that banner only says "stop
      // interrupting me elsewhere", not "stop telling me this at all".
      + (lastFix.acc != null && lastFix.acc > FIX_HINT_M ? ' ' + t('set.fixhint') : '');
    el.className = 'hint' + ((lastFix.acc != null && lastFix.acc <= FIX_GOOD_M) ? ' good' : ' warn');
    return;
  }
  const grid = (cfg.grid || '').trim().toUpperCase();
  el.className = 'hint';
  el.textContent = t('set.fixnone') + ' ' + (grid
    ? t('set.fixlocator').replace('{grid}', grid)
        .replace('{km}', GRID_KM[grid.length] || GRID_KM[6])
    : t('set.fixnolocator'));
}

/* top: this message is not about the map but about the app, so it has to be
   readable from whatever screen you are standing on. Everything else stays
   under the screens — see .status.top in the stylesheet. */
function showStatus(kind,t1,t2,top){
  const el=$('status');
  el.className='status show '+kind+(top?' top':'');
  $('stT1').textContent=t1; $('stT2').textContent=t2;
}
/* Every message has to be dismissable — it sits over the map. */
function hideStatus(){ $('status').className='status'; }
$('stClose').onclick = hideStatus;

/* ---------- "check your location permission" banner ----------
 * Same contract as the install bar just above it in index.html: it appears
 * on its own, and dismissing it makes it gone for good, everywhere except
 * Settings — which keeps saying the same thing (see set.fixhint above)
 * because turning off an interruption is not the same as no longer wanting
 * to know. Recomputed on every final fix, so it also disappears by itself,
 * without anyone dismissing anything, the moment the position genuinely
 * sharpens up again.
 */
function accHintOff(){ return recall('acc.hintoff') === '1'; }
function syncAccHint(){
  const el = $('accHint');
  if(!el) return;
  const show = !accHintOff() && lastFix && lastFix.acc != null && lastFix.acc > FIX_HINT_M;
  el.hidden = !show;
  if(show) $('accHintTxt').textContent = t('gps.hintacc').replace('{a}', Math.round(lastFix.acc));
}
$('accHintClose').onclick = () => { remember('acc.hintoff', '1'); $('accHint').hidden = true; };
const marker = new maplibregl.Marker({color:'#1b4332'});

/* our own locate button, down at the bottom with the zoom buttons */
class LocateControl{
  onAdd(){ const d=document.createElement('div');
    d.className='maplibregl-ctrl maplibregl-ctrl-group';
    d.innerHTML='<button type="button" title="Waar sta ik?" style="font-size:15px">◎</button>';
    d.onclick=()=>locate(); return d; }
  onRemove(){}
}
map.addControl(new LocateControl(),'bottom-right');

/* Esc closes everything */
addEventListener('keydown', e=>{ if(e.key==='Escape'){ toggle(null); closeSheet(); $('closeSpot').onclick(); }});
