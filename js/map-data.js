
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
   loadData() has fetched it; "ONFF only" and "worldwide" work without this list
   too, only "one specific country" needs it. */
let wwffPrograms = [];
let activity = {};

/* Activity for a single reference, ready to display. The directory contains one
   impossible date (year 1059); we leave that out rather than present it as
   fact — the same check the heatmap was already doing. */
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

async function loadData(){
  if (window.DIANA_ZONES){            // baked into the standalone preview build
    zones = window.DIANA_ZONES;
  } else {
    // When published, the data sits next to index.html; in the repo it sits one
    // level up. Both work, with no build step needed for local use.
    zones = await fetchFirst(['./data/onff.geojson','../data/onff.geojson']);
  }
  index = zones.features.map(f => {
    const b = bboxOf(f.geometry);
    return {...f.properties, bbox:b};
  });

  // Points without a boundary live in a separate file. If it is missing (older
  // data, or a build without a reference list), the app simply carries on.
  if (window.DIANA_POINTS) noPoly = window.DIANA_POINTS;
  else {
    try{ noPoly = await fetchFirst(['./data/onff-points.geojson','../data/onff-points.geojson']); }
    catch{ noPoly = {type:'FeatureCollection', features:[]}; }
  }
  noPolyByRef.clear();
  for(const f of (noPoly.features||[])){
    noPolyByRef.set(f.properties.ref, f);
    // Into the index as well, so they turn up in the search box and can serve
    // as the position for an agenda item. Without a bbox — they don't have one.
    index.push({...f.properties, lon:f.geometry.coordinates[0], lat:f.geometry.coordinates[1]});
  }

  $('counts').innerHTML = `<b>${zones.features.length}</b> ${t('map.areas')}`
    + (noPoly.features.length ? ` · ${noPoly.features.length} ${t('map.nopolycount')}` : '');
  const optNp = $('optNopoly');
  if(optNp) optNp.hidden = noPoly.features.length === 0;

  // Programme → country, worldwide — for the spots filter (Settings: ONFF only
  // / one country / everywhere). If the file is missing (older data), then
  // "one specific country" simply stays empty; ONFF and Worldwide work anyway.
  try{
    const doc = await fetchFirst(['./data/wwff-programs.json','../data/wwff-programs.json']);
    wwffPrograms = (doc.programs || []).slice().sort((a,b)=>a.country.localeCompare(b.country));
  }catch{ wwffPrograms = []; }
  // Number of QSOs and the last activation per reference. Small file, and the
  // detail panel wants to be able to show it straight away — not only after
  // someone happens to open the heatmap, which until now was the only thing
  // that fetched it.
  try{
    const doc = await fetchFirst(['./data/onff-activity.json','../data/onff-activity.json']);
    activity = doc.refs || {};
  }catch{ activity = {}; }
  populateSpotCountries();
  populateWorldCountries();
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

