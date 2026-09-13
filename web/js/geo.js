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
 * of evaluate() as "too close to call" rather than a confident lie). Then the
 * watch is stopped, because one left running costs battery all afternoon.
 *
 * It costs a few seconds. An answer that holds is worth more than an instant
 * answer that is sometimes wrong.
 */
const FIX_GOOD_M  = 25;      // sharp enough to stop early and answer
const FIX_WAIT_MS = 12000;   // and never keep anyone waiting longer than this
let fixRun = null;           // the locate() in progress, or null

/* Everything that follows from a new position. `final` separates following
   along on the map (every wave) from committing to an answer (once). */
function fixApply(pos, final){
  const {latitude:lat, longitude:lon, accuracy} = pos.coords;
  here = {lat, lon};
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

/* The one way to get a position in Diana. onFinal gets the sharpest fix we
   could get within the budget; onFail only fires when there is nothing at all.
   Used by the ◎ button, by the map at startup, and by "take my locator from
   the GPS" in Settings — the same trap catches all three. */
/* The reported accuracy in metres, or null when the browser did not give a
   usable one. Zero is a number, not a missing value — reading it as "unknown"
   is how you end up waiting the full budget for a fix that was already perfect
   by the browser's own account. */
function fixAcc(pos){
  const a = pos && pos.coords ? pos.coords.accuracy : null;
  return (typeof a === 'number' && isFinite(a) && a >= 0) ? a : null;
}

function bestFix(onFinal, onProgress, onFail){
  if(!navigator.geolocation){ if(onFail) onFail(null); return null; }
  const run = {watch:null, timer:null, best:null, done:false};
  run.stop = () => {
    run.done = true;
    if(run.watch != null) navigator.geolocation.clearWatch(run.watch);
    if(run.timer != null) clearTimeout(run.timer);
    run.watch = run.timer = null;
  };
  const settle = () => {
    const best = run.best;
    run.stop();
    if(best) onFinal(best);
    else if(onFail) onFail(null);
  };
  run.timer = setTimeout(settle, FIX_WAIT_MS);
  run.watch = navigator.geolocation.watchPosition(pos => {
    if(run.done) return;
    const acc = fixAcc(pos), best = fixAcc(run.best);
    // Keep the sharpest fix so far, not the most recent one: accuracy does not
    // only improve, it wanders.
    if(!run.best || acc == null || best == null || acc < best) run.best = pos;
    if(onProgress) onProgress(pos);
    // A browser that will not say how accurate its fix is gives us nothing to
    // wait for, so waiting would only cost time.
    if(acc == null || acc <= FIX_GOOD_M) settle();
  }, err => {
    if(run.done) return;
    // A wobble after we already have something usable is not a failure.
    if(run.best){ settle(); return; }
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
  // A tap while one is already running should not start a second watch — it
  // should only start showing what the first one is doing.
  if(fixRun){ if(!quiet) fixRun.quiet = false; return; }
  if(!quiet) showStatus('out', t('gps.searching'), '');

  // The token is claimed before the watch starts, so a fix that arrives
  // immediately cannot finish before we have something to compare against.
  const mine = {quiet: !!quiet};
  fixRun = mine;
  const loud = () => fixRun === mine && !mine.quiet;
  const release = () => { if(fixRun === mine) fixRun = null; };

  mine.run = bestFix(
    pos => { release(); fixApply(pos, true); },
    pos => {
      const say = loud();
      fixApply(pos, false);
      if(say) showStatus('out', t('gps.searching'),
        t('gps.refining').replace('{a}', Math.round(fixAcc(pos) || 0)));
    },
    err => {
      const say = loud(); release();
      if(say) showStatus('out', t('gps.failed'), err ? err.message : t('gps.nofix'));
    });
  if(!mine.run) release();
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
  const acc = Math.round(accuracy||0);
  if(inside.length){
    // Edge case: are you so close to the boundary that the GPS error could flip the answer?
    const edge = Math.min(...inside.map(f=>distanceToZone(lat,lon,f)));
    const names = inside.map(f=>`${f.properties.ref} ${f.properties.name}`).join(' · ');
    if(edge < acc){
      showStatus('near', t('gps.nearedge').replace('{ref}', inside[0].properties.ref),
        t('gps.nearedgesub').replace('{d}', Math.round(edge)).replace('{a}', acc));
    } else {
      showStatus('in', inside.length>1 ? t('gps.inmany').replace('{n}', inside.length) : t('gps.inone'),
        `${names} — ${t('gps.toedge').replace('{d}', Math.round(edge))}`);
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
    if(nearEdgeF && nearEdgeD < acc){
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
    if(!best){ showStatus('out', t('gps.outside'), ''); return; }
    // For a reference without a boundary there is no boundary to measure a
    // distance to; then the distance to the point is the most honest answer we
    // have.
    const f = zones.features.find(x=>x.properties.ref===best.ref);
    const edge = f ? distanceToZone(lat,lon,f) : bd;
    const dist = edge>1500 ? (edge/1000).toFixed(1)+' km' : Math.round(edge)+' m';
    showStatus('out', t('gps.outside'),
      `${t('gps.nearest')}: ${best.ref} ${best.name} — ${dist}${f?'':' ('+t('zone.nopoly')+')'}.`);
  }
}
function showStatus(kind,t1,t2){
  const el=$('status');
  el.className='status show '+kind;
  $('stT1').textContent=t1; $('stT2').textContent=t2;
}
/* Every message has to be dismissable — it sits over the map. */
function hideStatus(){ $('status').className='status'; }
$('stClose').onclick = hideStatus;
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
