
let zones = null;          // FeatureCollection
let index = null;          // lightweight index
let currentStyle = 'liberty';
let showLabels = true;
let showZones = true;
let showNoPoly = true;
let selected = null;
let watchId = null;

/* References that are on the ONFF list but have no boundary in the KMZ. They
   are shown as a point — visible, but emphatically not a boundary: the
   "am I inside it" test skips them for that reason. */
let noPoly = {type:'FeatureCollection', features:[]};
const noPolyByRef = new Map();

/* Worldwide WWFF programmes → country, for the spots filter. Empty until
   loadData() has fetched it; a single country and "worldwide" work without this
   list too, only "one specific country" needs it. */
let wwffPrograms = [];

/* Which countries Diana has boundaries for, and which of those are in memory.
   Diana began as a Belgian app with one pair of data files; it now reads a
   manifest instead, so that a second country is a file in data/ rather than a
   change to the code. */
let countries = [];        // what data/countries.json offers
let loadedPrograms = [];   // what is actually in zones/index right now
let activity = {};

/* Activity for a single reference, ready to display. The directory contains one
   impossible date (year 1059); we leave that out rather than present it as
   fact. The Nearby screen reads this same function, so the rule lives here
   only. */
function activityOf(ref){
  const a = activity[ref];
  if(!a) return null;
  const year = a.last ? parseInt(a.last.slice(0,4), 10) : null;
  const now = new Date().getFullYear();
  const date = (year && year >= 1990 && year <= now + 1) ? a.last : null;
  if(!date && !a.q) return null;
  return {qso: a.q || 0, date};
}

/* The two activity boxes, shared by the area panel and the panel for a
   reference without a boundary. */
function activityFacts(ref){
  const a = activityOf(ref);
  if(!a) return '';
  return (a.qso ? `<div class="fact"><div class="k">${t('zone.qso')}</div>`
                + `<div class="v">${a.qso.toLocaleString(locale())}</div></div>` : '')
       + (a.date ? `<div class="fact"><div class="k">${t('zone.lastact')}</div>`
                 + `<div class="v">${a.date}</div></div>` : '');
}

/* QSO counts worldwide, for the spots screen (spots.js): data/wwff-activity.json,
   ref -> count for every active WWFF reference, any programme, not only the
   one country whose boundaries happen to be loaded. 0 means the directory has
   no activation on record (ATNO). Lazy, because it runs to about a megabyte and
   the spots list itself has nothing to wait for it to show; ensureWorldActivity()
   below loads it on first use and spots.js repaints once it lands, the same
   shape as ensureRadioZones() in nearinfo.js. Deliberately not in the service
   worker's precache: that would make every visitor fetch it again on every
   release, nightly data commits included, while the ordinary data cache
   (versEerst() in sw.js) already keeps a copy once it has been fetched, and
   its 3.5 s timeout only covers waiting for the response to start, not the
   download itself. A failed load is tried again, at most
   once a minute, on a later repaint of the spots list: the list refreshes
   every 30 s anyway, and a field connection that failed once often comes back. */
let worldActivity = {}, worldActivityLoaded = false, worldActivityLoading = null, worldActivityFailedAt = 0;
function ensureWorldActivity(){
  if(worldActivityLoaded || worldActivityLoading) return worldActivityLoading;
  if(worldActivityFailedAt && Date.now() - worldActivityFailedAt < 60000) return null;
  worldActivityLoading = (async () => {
    try{
      const doc = await fetchFirst(dataURL('wwff-activity.json'));
      worldActivity = doc.refs || {};
      worldActivityLoaded = true;
    }catch{ worldActivityFailedAt = Date.now(); }
    worldActivityLoading = null;
    if(worldActivityLoaded && typeof renderSpots === 'function') renderSpots();
  })();
  return worldActivityLoading;
}

/* The QSO count for one reference, for spots.js: a number (0 = never activated,
   ATNO) or null when there is nothing to go on. Prefers the home country's own
   `activity` table when the reference is in it, and falls back to the
   worldwide file otherwise (the same fallback refPosition() uses for a pin's
   own position).

   Why not activityOf(): that one hides "no count, no date" so the area panel
   shows no empty box, and the per-country table leaves a never-activated
   reference out altogether (the directory gives it an empty count, never a
   literal 0). Either way the very case this is for would come back as "no
   data". So a reference missing from `activity` is looked up in the worldwide
   file, which does carry it, as 0. */
function qsoCountAnywhere(ref){
  ref = String(ref || '').toUpperCase();   // as refPosition() does: both tables are keyed in capitals
  const a = activity[ref];
  if(a){
    if(a.q) return a.q;
    return a.last ? null : 0;   // activated but no count: say nothing, not ATNO
  }
  const w = worldActivity[ref];
  return typeof w === 'number' ? w : null;
}

/* ---------- loading data ---------- */
async function fetchFirst(urls){
  let lastErr;
  for(const u of urls){
    try{ const r = await fetch(u); if(r.ok) return await r.json(); lastErr = new Error(r.status+' '+u); }
    catch(e){ lastErr = e; }
  }
  throw lastErr;
}

/* Which dataset is actually in here? That is the question you ask when the map
   looks out of date, and until now the answer was only to be found in
   meta.json. Now it is in Settings, next to the version number. */
async function loadMeta(){
  const el = $('setData'), adminEl = $('admCurrent');
  try{
    const m = await fetchFirst(['./data/meta.json','../data/meta.json']);
    if(el) el.textContent = `${m.release || '?'} · ${m.zones || '?'} ${t('set.zones')}`;
    // In the admin screen, the full provenance: which file, which release, and
    // when the build ran. That last one is the only way to see from the outside
    // whether an upload really has been processed.
    if(adminEl){
      const gebouwd = m.generated ? m.generated.replace('T',' ').replace('Z',' UTC') : '?';
      adminEl.innerHTML =
        `<b>${m.source_file || '?'}</b><br>` +
        `release ${m.release || '?'} · ${m.zones || '?'} ${t('set.zones')}<br>` +
        `${t('adm.processed')} ${gebouwd}` +
        (m.directory_failed ? '<br>⚠ WWFF-directory was onbereikbaar' : '');
      adminEl.className = 'fb';
    }
    return m;
  }catch{
    if(el) el.textContent = '—';
    if(adminEl){ adminEl.textContent = '—'; adminEl.className = 'fb bad'; }
    return null;
  }
}

/* When published, the data sits next to index.html; in the repo it sits one
   level up. Both work, with no build step needed for local use. */
const dataURL = rel => ['./data/' + rel, '../data/' + rel];

/* The manifest the build writes: one entry per programme that has boundaries,
   with the files that belong to it. A data set from before the manifest
   existed does not have one, and then this stands in — the single pair of ONFF
   files Diana always loaded, under the names they had. So the app and the data
   can be updated in either order without a window in which the map is empty. */
const LEGACY_ONFF = {
  program: 'ONFF', country: 'Belgium', legacy: true,
  files: {zones: 'onff.geojson', points: 'onff-points.geojson', activity: 'onff-activity.json'},
};

async function loadCountries(){
  try{
    const doc = await fetchFirst(dataURL('countries.json'));
    const list = (doc.countries || []).filter(c => c.program && c.files && c.files.zones);
    if(list.length) return list;
  }catch{}
  return [LEGACY_ONFF];
}

/* ---------- your country, the one setting ----------
 *
 * Diana used to have three separate notions of "country" that knew nothing of
 * one another: which one the spots filter offered, which one the worldwide
 * points were narrowed to, and which one's boundaries were in memory. That
 * last one was never asked — it went by your callsign and nothing else, so
 * picking the Netherlands in Settings changed the spots and left the map
 * Belgian.
 *
 * One value now, and everything reads it: the spots and agenda filter, the
 * boundaries that get loaded, and the points of other countries on the map.
 * Kept apart from "which filter is on" on purpose — see homeProgram() in
 * spots.js: glancing at Worldwide does not mean you have stopped caring about
 * the Netherlands. */
function homeCountry(have){
  const saved = recall('homeprog');
  if(saved) return saved;
  // cfg first: a callsign just typed in Settings has not necessarily been
  // saved yet, and the country ought to follow along as you type.
  const call = (typeof cfg !== 'undefined' && cfg ? (cfg.call || cfg.callp) : '')
            || recall('call') || recall('callp');
  const mine = programForCall(call);
  if(mine) return mine;
  const list = have || (countries || []).map(c => c.program);
  // The map opens over Belgium and that is where this app was born, so it is
  // the honest default for someone who has not said who they are yet —
  // certainly more honest than whichever country happens to sort first.
  return list.includes('ONFF') ? 'ONFF' : (list[0] || 'ONFF');
}

/* Which countries go into memory: yours, and only if we have boundaries for
   it. Never all of them — one country is megabytes, and there is no reason to
   carry Sweden around while you are standing in Flanders. A country we have no
   boundaries for loads nothing at all, and then the worldwide points are the
   only place its references exist; the map falls back to those by itself. */
function wantedPrograms(list){
  const have = list.map(c => c.program);
  // An explicit list wins, and nothing in the app writes it: this is how a
  // preview build — or a test — puts more than one country on board at once.
  try{
    const saved = JSON.parse(recall('countries') || '[]');
    const keep = Array.isArray(saved) ? saved.filter(p => have.includes(p)) : [];
    if(keep.length) return keep;
  }catch{}
  const mine = homeCountry(have);
  return have.includes(mine) ? [mine] : [];
}

/* Does your country have boundaries at all, or only points? The Settings
   screen says so out loud, because "only dots on the map" is otherwise
   indistinguishable from something being broken. */
function countryEntry(prog){
  return (countries || []).find(c => c.program === prog) || null;
}

async function loadCountry(c){
  const out = {zones: [], points: [], activity: {}};
  out.zones = (await fetchFirst(dataURL(c.files.zones))).features || [];
  // Points without a boundary, and the activity figures, are both allowed to be
  // missing — older data, or a build without a reference list. The boundaries
  // are what the country is for.
  if(c.files.points){
    try{ out.points = (await fetchFirst(dataURL(c.files.points))).features || []; }catch{}
  }
  if(c.files.activity){
    try{ out.activity = (await fetchFirst(dataURL(c.files.activity))).refs || {}; }catch{}
  }
  return out;
}

/* Put exactly these countries in memory, replacing whatever was there. Split
   off from loadData() because the country can now be changed while the app is
   running, and the second copy of this loop is precisely how the two would
   have drifted apart. */
/* Bumped every time what is in memory changes. The map compares against it so
   that an ordinary redraw costs nothing: handing a 3.8 MB source the same data
   again puts MapLibre's style back into "busy" for a moment, and a redraw that
   does that on every pass never lets it settle — which is how the points layer
   ended up never being built at all. */
let dataGen = 0;

async function loadPrograms(progs){
  zones  = {type:'FeatureCollection', features: []};
  noPoly = {type:'FeatureCollection', features: []};
  activity = {};
  loadedPrograms = [];
  for(const prog of progs){
    const c = countryEntry(prog);
    if(!c) continue;
    try{
      const got = await loadCountry(c);
      zones.features.push(...got.zones);
      noPoly.features.push(...got.points);
      Object.assign(activity, got.activity);
      loadedPrograms.push(prog);
    }catch(err){
      // One country that will not load must not take the others down with it.
      console.warn('country ' + prog + ' did not load:', err);
    }
  }
  dataGen++;
}

/* Everything that is derived from what is in memory: the search index, the
   points without a boundary, and the count under the map. */
function buildIndex(){
  index = zones.features.map(f => {
    const b = bboxOf(f.geometry);
    return {...f.properties, bbox:b};
  });

  noPolyByRef.clear();
  for(const f of (noPoly.features||[])){
    noPolyByRef.set(f.properties.ref, f);
    // Into the index as well, so they turn up in the search box and can serve
    // as the position for an agenda item. Without a bbox — they don't have one.
    index.push({...f.properties, lon:f.geometry.coordinates[0], lat:f.geometry.coordinates[1]});
  }

  updateCounts();
  const optNp = $('optNopoly');
  if(optNp) optNp.hidden = noPoly.features.length === 0;
}

/* The line under the map: what you are actually looking at. For a country
   without boundaries that is the worldwide points and nothing else — saying
   "0 areas" there would read as a fault rather than as the truth. */
function updateCounts(){
  const el = $('counts');
  if(!el) return;
  if(zones.features.length || noPoly.features.length){
    el.innerHTML = `<b>${zones.features.length}</b> ${t('map.areas')}`
      + (noPoly.features.length ? ` · ${noPoly.features.length} ${t('map.nopolycount')}` : '');
    return;
  }
  const wereld = (typeof worldFilteredData === 'function' && typeof worldLoaded !== 'undefined' && worldLoaded)
    ? worldFilteredData().features.length : 0;
  el.innerHTML = `<b>${wereld}</b> ${t('map.points')}`;
}

/* Your country changed in Settings. The boundaries of the old one go out of
   memory and the new one's come in — while the app is running, because sending
   someone off to restart for a setting they just changed is not an answer.
   What is drawn follows: the areas, the labels, the points without a boundary,
   and the worldwide dots (which leave out whatever country is on board). */
async function switchCountry(prog){
  await loadPrograms(prog ? [prog] : []);
  buildIndex();
  // A reference from the country that just left cannot stay selected.
  if(typeof clearSelection === 'function') clearSelection();
  if(typeof closeSheet === 'function') closeSheet();
  if(typeof updateCountrySources === 'function') updateCountrySources();
  // Nearby is a list of distances to what is in memory, so it is a different
  // list now, from the first page.
  if(typeof nearShown !== 'undefined') nearShown = NEAR_MAX_ROWS;
  if(typeof renderNearby === 'function' && $('viewNearby').classList.contains('on')) renderNearby();
  syncCountryUI();
}

async function loadData(){
  countries = await loadCountries();
  loadedPrograms = [];

  if (window.DIANA_ZONES){            // baked into the standalone preview build
    zones = window.DIANA_ZONES;
    if (window.DIANA_POINTS) noPoly = window.DIANA_POINTS;
  } else {
    await loadPrograms(wantedPrograms(countries));
  }
  if(!loadedPrograms.length){
    loadedPrograms = [...new Set((zones.features || [])
      .map(f => refProgram(f.properties && f.properties.ref)).filter(Boolean))];
  }

  buildIndex();

  // Programme → country, worldwide — for the spots filter (Settings: ONFF only
  // / one country / everywhere). If the file is missing (older data), then
  // "one specific country" simply stays empty; ONFF and Worldwide work anyway.
  try{
    const doc = await fetchFirst(dataURL('wwff-programs.json'));
    wwffPrograms = (doc.programs || []).slice().sort((a,b)=>a.country.localeCompare(b.country));
  }catch{ wwffPrograms = []; }
  // The QSO counts and last activations came in with each country above —
  // the detail panel and the Nearby screen both want them straight away.
  populateSpotCountries();
  syncCountryUI();
}

/* What Settings says about your country: which one it is, and whether Diana
   has boundaries for it or only points. That second line matters — a map with
   nothing but dots on it is otherwise indistinguishable from a map that is
   broken. */
function syncCountryUI(){
  const el = $('setCountryState');
  if(!el) return;
  const prog = homeCountry();
  const c = countryEntry(prog);
  if(!countries.length){
    el.textContent = '';
    return;
  }
  if(c && loadedPrograms.includes(prog)){
    el.textContent = t('set.countryzones')
      .split('{n}').join(zones.features.length)
      .split('{prog}').join(prog);
    el.className = 'hint good';
  }else if(c){
    el.textContent = t('set.countryloading').split('{prog}').join(prog);
    el.className = 'hint';
  }else{
    el.textContent = t('set.countrypoints').split('{prog}').join(prog);
    el.className = 'hint';
  }
}

/* One label point per reference, on the largest sub-area — where you are most
   likely to be standing out in the field. */
function labelFeatures(){
  return {type:'FeatureCollection', features: zones.features.map(f=>{
    let best=null, bestArea=-1;
    for(const poly of f.geometry.coordinates){
      let x1=180,y1=90,x2=-180,y2=-90;
      for(const [x,y] of poly[0]){ if(x<x1)x1=x; if(x>x2)x2=x; if(y<y1)y1=y; if(y>y2)y2=y; }
      const a=(x2-x1)*(y2-y1);
      if(a>bestArea){ bestArea=a; best=[(x1+x2)/2,(y1+y2)/2]; }
    }
    return {type:'Feature',
      properties:{ref:f.properties.ref, name:f.properties.name, parts:f.geometry.coordinates.length},
      geometry:{type:'Point', coordinates:best}};
  })};
}

function bboxOf(geom){
  let x1=180,y1=90,x2=-180,y2=-90;
  for (const poly of geom.coordinates)
    for (const ring of poly)
      for (const [x,y] of ring){
        if(x<x1)x1=x; if(x>x2)x2=x; if(y<y1)y1=y; if(y>y2)y2=y;
      }
  return [x1,y1,x2,y2];
}

