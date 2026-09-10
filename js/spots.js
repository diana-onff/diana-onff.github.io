/* ------------------------------------------------------------------ *
 * Spots — WWFF Spotline. Step 4 of the plan.
 * Spotline's static JSON files, refreshed every 30 s as they themselves
 * recommend, paused as soon as the tab is not visible.
 * ------------------------------------------------------------------ */
const SPOTS_URL  = 'https://spots.wwff.co/static/spots.json';
const AGENDA_URL = 'https://spots.wwff.co/static/agendas_active.json';
const AGENDA_ALL = 'https://spots.wwff.co/static/agendas.json';
const REFRESH_MS = 30000;

let spots = [], agenda = [], spotsAt = null, spotsError = null;
// 'all' (worldwide), 'onff', or a programme code such as 'PAFF' (one country).
// Worldwide is the factory setting; anyone who once chose something else gets
// that back on every subsequent start — see Settings → Spots filter.
// The key was deliberately renamed from 'arcs' to 'arcs2': the lines should be
// on by default, and anyone who once switched them off back when the button
// worked the other way round would otherwise be stuck with a choice they never
// meant to make.
let showArcs = recall('arcs2') !== '0';
let showSpots = recall('spots') !== '0', spotFilter = recall('spotFilter2') || 'all', spotTab = 'spots', spotTimer = null, here = null;

// Bring the menu switches in line right after reading the preferences.
// applyVisibility() does this too, but it bails out as long as the map layers
// are not there — and precisely when the style fails to load you don't want a
// menu claiming the opposite.
syncSwitch('spots', showSpots);
syncSwitch('arcs',  showArcs);
let agendaSkipped = 0;

function startSpots(){
  if(spotTimer) return;
  fetchSpots();
  spotTimer = setInterval(()=>{ if(!document.hidden) fetchSpots(); }, REFRESH_MS);
}
async function fetchSpots(){
  try{
    // Spotline makes three files available; we use all three of them.
    const [s,a,all] = await Promise.all([
      fetch(SPOTS_URL,{cache:'no-store'}).then(r=>r.json()),
      fetch(AGENDA_URL,{cache:'no-store'}).then(r=>r.json()).catch(()=>[]),
      fetch(AGENDA_ALL,{cache:'no-store'}).then(r=>r.json()).catch(()=>[])
    ]);
    spots = Array.isArray(s) ? s : [];
    // Activations under way first, then the announced ones still to come.
    const active = Array.isArray(a) ? a : [];
    const later  = (Array.isArray(all) ? all : []).filter(x =>
      !active.some(y => String(y.id) === String(x.id)));
    agenda = active.concat(later);
    spotsAt = new Date(); spotsError = null;
  }catch(err){
    // A TypeError with no status code almost always means: blocked by CORS.
    spotsError = (err instanceof TypeError)
      ? 'Spotline weigert de rechtstreekse verbinding (CORS). Hiervoor is de proxy uit het plan nodig.'
      : ('Spots ophalen mislukt: ' + err.message);
  }
  paintSpots(); renderSpots();
}

const isONFF = r => typeof r === 'string' && r.toUpperCase().startsWith('ONFF');
// A WWFF reference is always "<PROGRAMME>-<number>" and the programme itself
// already ends in "FF" (ONFF, PAFF, VKFF, …) — so the part before the first
// hyphen is the programme code, worldwide, with no separate table needed.
const refProgram = r => (typeof r === 'string' ? r.toUpperCase().split('-')[0] : '');
function spotVisible(ref){
  if(spotFilter === 'all') return true;
  if(spotFilter === 'onff') return isONFF(ref);
  return refProgram(ref) === spotFilter;         // one specific country
}
const visibleSpots = () => spots
  .filter(s => s.latitude && s.longitude)
  .filter(s => spotVisible(s.reference))
  .filter(s => ageMin(s) < 60);

function ageMin(s){ return (Date.now()/1000 - (s.spot_time||0)) / 60; }
function agoText(s){
  const m = Math.max(0, Math.round(ageMin(s)));
  return m < 1 ? t('spot.justnow') : t('spot.minago').replace('{n}', m);
}

/* Where am I? GPS if it is available, otherwise the locator from the settings.
   Without either of the two we draw no arc lines — there is no starting point. */
function myPos(){
  if(here) return [here.lon, here.lat];
  const ll = gridToLatLon(cfg.grid);
  return ll || null;
}

/* Great-circle arc between two points, as a series of intermediate points.
   Straight lines on a Mercator map are not real bearings; over 2000 km the
   difference is visible. Splits cleanly at the date line. */
function greatCircle(from, to, steps){
  const rad = Math.PI/180, deg = 180/Math.PI;
  const [lon1,lat1] = from.map(v=>v*rad), [lon2,lat2] = to.map(v=>v*rad);
  const d = 2*Math.asin(Math.sqrt(
    Math.sin((lat2-lat1)/2)**2 + Math.cos(lat1)*Math.cos(lat2)*Math.sin((lon2-lon1)/2)**2));
  if(!isFinite(d) || d === 0) return [[from, to]];
  const n = steps || Math.max(16, Math.min(128, Math.round(d*deg)));
  const pts = [];
  for(let i=0;i<=n;i++){
    const f = i/n;
    const A = Math.sin((1-f)*d)/Math.sin(d), B = Math.sin(f*d)/Math.sin(d);
    const x = A*Math.cos(lat1)*Math.cos(lon1) + B*Math.cos(lat2)*Math.cos(lon2);
    const y = A*Math.cos(lat1)*Math.sin(lon1) + B*Math.cos(lat2)*Math.sin(lon2);
    const z = A*Math.sin(lat1) + B*Math.sin(lat2);
    pts.push([Math.atan2(y,x)*deg, Math.atan2(z, Math.sqrt(x*x+y*y))*deg]);
  }
  // Cut the line into pieces at the date line, otherwise it stretches right across the map.
  const parts = [[]];
  for(let i=0;i<pts.length;i++){
    if(i && Math.abs(pts[i][0] - pts[i-1][0]) > 180) parts.push([]);
    parts[parts.length-1].push(pts[i]);
  }
  return parts.filter(pp => pp.length > 1);
}

/* An agenda item has no coordinates in the Spotline file. For ONFF references
   we know the centre point from our own data; for the rest we don't, and those
   we leave off the map rather than making them up. */
function refPosition(ref){
  if(!ref || !zones) return null;
  const f = zones.features.find(x => x.properties.ref === String(ref).toUpperCase());
  if(!f) return null;
  const b = bboxOf(f.geometry);
  return [(b[0]+b[2])/2, (b[1]+b[3])/2];
}

/* The little icon: a green disc with an antenna on it, as a map image. After a
   style switch images are gone, so this gets called again. */
function addSpotIcon(){
  if(map.hasImage('diana-spot')) return;
  const S = 48, c = document.createElement('canvas');
  c.width = c.height = S;
  const g = c.getContext('2d');
  // White ring around the outside: that is the difference between "a green dot
  // among the other dots" and "this is an active spot". Inside it a bright green
  // instead of the dark ink green, which sank away on a light map.
  g.fillStyle = '#fff';
  g.beginPath(); g.arc(S/2, S/2, S/2 - 1, 0, Math.PI*2); g.fill();
  g.fillStyle = '#16a34a';
  g.beginPath(); g.arc(S/2, S/2, S/2 - 4.5, 0, Math.PI*2); g.fill();
  g.strokeStyle = '#fff'; g.lineWidth = 3; g.lineCap = 'round';
  g.beginPath(); g.moveTo(S/2, S*0.72); g.lineTo(S/2, S*0.34); g.stroke();       // mast
  g.beginPath(); g.moveTo(S*0.34, S*0.44); g.lineTo(S*0.66, S*0.44); g.stroke(); // dipole
  g.lineWidth = 2.4;
  g.beginPath(); g.arc(S/2, S*0.34, S*0.16, Math.PI*1.15, Math.PI*1.85); g.stroke(); // radiation
  g.beginPath(); g.arc(S/2, S*0.34, S*0.26, Math.PI*1.2, Math.PI*1.8); g.stroke();
  map.addImage('diana-spot', {width:S, height:S, data:g.getImageData(0,0,S,S).data});
}

let pulsePhase = 0, pulseTimer = null;

function paintSpots(){
  if(!map.isStyleLoaded() || !zones){ redrawOverlays(); return; }
  addSpotIcon();

  const mine = myPos();
  const live = visibleSpots();

  // ---- spots under way ----
  const spotFC = {type:'FeatureCollection', features: live.map(s => ({
    type:'Feature',
    properties:{ id:s.id, call:s.activator||'?', ref:s.reference||'',
                 khz:s.frequency_khz||'', mode:s.mode||'', stale: ageMin(s) > 30 },
    geometry:{type:'Point', coordinates:[s.longitude, s.latitude]}
  }))};

  // ---- announced activations, only the ones we can place ----
  const nowUTC = new Date().toISOString().slice(0,19).replace('T',' ');
  const agendaPlaced = [];
  agendaSkipped = 0;
  for(const a of agenda){
    if(!spotVisible(a.reference)) continue;
    if(a.utc_end && a.utc_end < nowUTC) continue;
    const pos = refPosition(a.reference);
    if(!pos){ agendaSkipped++; continue; }
    agendaPlaced.push({...a, _pos:pos});
  }
  const agFC = {type:'FeatureCollection', features: agendaPlaced.map(a => ({
    type:'Feature',
    properties:{ call:a.activator_call||'?', ref:a.reference||'',
                 band:a.band||'', when:(a.utc_start||'').slice(5,16) },
    geometry:{type:'Point', coordinates:a._pos}
  }))};

  // ---- arc lines from your own position ----
  const arcs = (kind, items) => ({type:'FeatureCollection', features: mine ? items.flatMap(it => {
    const to = kind === 'spot' ? [it.longitude, it.latitude] : it._pos;
    if(!to || (Math.abs(to[0]-mine[0]) < 1e-6 && Math.abs(to[1]-mine[1]) < 1e-6)) return [];
    return greatCircle(mine, to).map(line => ({
      type:'Feature', properties:{}, geometry:{type:'LineString', coordinates:line}
    }));
  }) : []});

  const sources = {
    'spots':      spotFC,
    'agenda-pts': agFC,
    'spot-arcs':  arcs('spot', live),
    'agenda-arcs':arcs('agenda', agendaPlaced),
  };
  for(const [id, data] of Object.entries(sources)){
    if(map.getSource(id)) map.getSource(id).setData(data);
    else map.addSource(id, {type:'geojson', data});
  }

  if(!map.getLayer('spot-arcs-line')){
    // Two kinds of line, deliberately different in weight. A planned activation
    // is an appointment you act on: dashes, solid enough to see. A live spot is
    // here now and gone again in a moment: dots, light, so that twenty at once
    // don't smear over the map underneath.
    map.addLayer({ id:'agenda-arcs-line', type:'line', source:'agenda-arcs',
      layout:{'line-cap':'butt'},
      paint:{'line-color':'#e8873a','line-width':2.4,'line-opacity':0.9,'line-dasharray':[2,1.5]}});
    // Round ends on a dash of almost nothing: that is how you draw a real dotted
    // line in MapLibre instead of short dashes.
    map.addLayer({ id:'spot-arcs-line', type:'line', source:'spot-arcs',
      layout:{'line-cap':'round'},
      paint:{'line-color':'#16a34a','line-width':2.2,'line-opacity':0.95,'line-dasharray':[0.1,1.9]}});

    map.addLayer({ id:'agenda-dot', type:'circle', source:'agenda-pts',
      paint:{'circle-radius':7,'circle-color':'#fff','circle-opacity':1,
             'circle-stroke-color':'#e8873a','circle-stroke-width':2.2}});

    // The blinking "radiation" underneath the little icon.
    map.addLayer({ id:'spots-pulse', type:'circle', source:'spots',
      filter:['!',['get','stale']],
      paint:{'circle-radius':12,'circle-color':'#22c55e','circle-opacity':0.5,'circle-blur':0.35}});

    map.addLayer({ id:'spots-icon', type:'symbol', source:'spots',
      layout:{'icon-image':'diana-spot','icon-allow-overlap':true,
              'icon-size':['interpolate',['linear'],['zoom'],4,0.42,10,0.66]},
      paint:{'icon-opacity':['case',['get','stale'],0.45,1]}});

    if(map.getStyle().glyphs){
      map.addLayer({ id:'agenda-label', type:'symbol', source:'agenda-pts',
        layout:{'text-field':['format',['get','call'],{'font-scale':1.2},
                              '\n',{}, ['get','when'],{'font-scale':0.85}],
                'text-font':['Noto Sans Regular'],'text-size':13,'text-line-height':1.15,
                'text-offset':[0,1.3],'text-anchor':'top','text-padding':4},
        paint:{'text-color':'#7c3510','text-halo-color':'#fff','text-halo-width':2.6,
               'text-halo-blur':0.2}});
      map.addLayer({ id:'spots-call', type:'symbol', source:'spots',
        // Who is on there is the answer you are looking for; frequency and mode
        // are secondary. Hence one label in two sizes instead of three lines of
        // equally small grey.
        layout:{'text-field':['case',['==',['get','khz'],''],
                              ['format',['get','call'],{'font-scale':1.25}],
                              ['format',['get','call'],{'font-scale':1.25},
                                        '\n',{},
                                        ['concat',['to-string',['get','khz']],' ',['get','mode']],{'font-scale':0.85}]],
                'text-font':['Noto Sans Regular'],'text-size':13,'text-line-height':1.15,
                'text-offset':[0,1.5],'text-anchor':'top','text-allow-overlap':false,'text-padding':4},
        paint:{'text-color':'#0b3d1f','text-halo-color':'#fff','text-halo-width':2.6,
               'text-halo-blur':0.2}});
    }

    if(!paintSpots._bound){
      paintSpots._bound = true;
      map.on('click','spots-icon', e => openSpot(e.features[0].properties.id));
      map.on('mouseenter','spots-icon',()=>map.getCanvas().style.cursor='pointer');
      map.on('mouseleave','spots-icon',()=>map.getCanvas().style.cursor='');
    }
  }

  startPulse();
  applyVisibility();
}

/* Blinking: one timer, only while the layer is visible and the tab is open. */
function startPulse(){
  if(pulseTimer) return;
  pulseTimer = setInterval(() => {
    if(!showSpots || document.hidden || !map.getLayer('spots-pulse')) return;
    pulsePhase = (pulsePhase + 1) % 20;
    const f = pulsePhase / 20;
    map.setPaintProperty('spots-pulse','circle-radius', 10 + f*18);
    map.setPaintProperty('spots-pulse','circle-opacity', 0.55 * (1 - f));
  }, 90);
}

/* Bring everything into view: your own position plus every visible spot. */
function fitSpots(){
  const pts = visibleSpots().map(s => [s.longitude, s.latitude]);
  const mine = myPos(); if(mine) pts.push(mine);
  if(!pts.length){ showStatus('out', t('spots.none'), ''); return; }
  const b = pts.reduce((a,[x,y]) => [Math.min(a[0],x),Math.min(a[1],y),Math.max(a[2],x),Math.max(a[3],y)],
                       [180,90,-180,-90]);
  map.fitBounds([[b[0],b[1]],[b[2],b[3]]], {padding:60, maxZoom:11, duration:800});
}

/* ---------- direction, distance, locator ---------- */
function bearing(lat1,lon1,lat2,lon2){
  const t=Math.PI/180, y=Math.sin((lon2-lon1)*t)*Math.cos(lat2*t);
  const x=Math.cos(lat1*t)*Math.sin(lat2*t)-Math.sin(lat1*t)*Math.cos(lat2*t)*Math.cos((lon2-lon1)*t);
  return (Math.atan2(y,x)/t+360)%360;
}
const COMPASS = ['N','NNO','NO','ONO','O','OZO','ZO','ZZO','Z','ZZW','ZW','WZW','W','WNW','NW','NNW'];
const compassName = d => COMPASS[Math.round(d/22.5)%16];

function locator(lat,lon){
  const A='A'.charCodeAt(0);
  let x=lon+180, y=lat+90;
  const f1=String.fromCharCode(A+Math.floor(x/20)), f2=String.fromCharCode(A+Math.floor(y/10));
  const s1=Math.floor((x%20)/2), s2=Math.floor(y%10);
  const t1=String.fromCharCode(A+Math.floor(((x%2)*60)/5)), t2=String.fromCharCode(A+Math.floor(((y%1)*60)/2.5));
  return `${f1}${f2}${s1}${s2}${t1.toLowerCase()}${t2.toLowerCase()}`.toUpperCase();
}
const fmtKm = m => m>=1000 ? `${(m/1000).toFixed(m<10000?1:0)} km` : `${Math.round(m)} m`;

/* ---------- list ---------- */
function renderSpots(){
  const list=$('spotList'), meta=$('spotMeta');
  if(spotTab==='agenda') return renderAgenda(list, meta);
  if(spotsError){
    list.innerHTML = `<p class="hint" style="color:#b45309">${spotsError}</p>`;
    meta.textContent = spotsAt ? `${t('spots.updated')} ${spotsAt.toLocaleTimeString(locale(),{hour:'2-digit',minute:'2-digit'})}` : '';
    return;
  }
  const rows = visibleSpots().sort((a,b)=>{
    if(here) return dist(a)-dist(b);
    return (b.spot_time||0)-(a.spot_time||0);
  });
  list.innerHTML = rows.length ? rows.map(s=>{
    const d = here ? `<b>${Math.round(bearing(here.lat,here.lon,s.latitude,s.longitude))}°</b>${fmtKm(dist(s))}`
                   : `<b>${Math.max(0,Math.round(ageMin(s)))}′</b>${s.mode||''}`;
    return `<div class="spot${ageMin(s)>30?' stale':''}" data-id="${s.id}">
      <span class="sig">((·))</span>
      <span class="who"><div class="c">${s.activator||'?'}</div>
        <div class="f">${s.frequency_khz||'?'} kHz · ${s.mode||'?'} · ${s.reference||''}</div></span>
      <span class="d">${d}</span></div>`;
  }).join('') : `<p class="hint">${t('spots.none')}</p>`;
  meta.textContent = spotsAt
    ? `${rows.length} spots · ${t('spots.updated')} ${spotsAt.toLocaleTimeString(locale(),{hour:'2-digit',minute:'2-digit'})}`
    : t('spots.loading');
}
function dist(s){ return here ? haversine(here.lat,here.lon,s.latitude,s.longitude) : Infinity; }

/* Announced activations. Spotline supplies utc_start/utc_end as text; we show
   what is running and what is still to come, with "on air now" marked separately. */
function renderAgenda(list, meta){
  if(spotsError){
    list.innerHTML = `<p class="hint" style="color:#b45309">${spotsError}</p>`;
    meta.textContent=''; return;
  }
  const rows = agenda
    .filter(a => spotVisible(a.reference))
    .sort((a,b)=>String(a.utc_start).localeCompare(String(b.utc_start)));
  const nowUTC = new Date().toISOString().slice(0,19).replace('T',' ');
  list.innerHTML = rows.length ? rows.map(a=>{
    const running = a.utc_start <= nowUTC && nowUTC <= a.utc_end;
    return `<div class="spot${running?'':' stale'}">
      <span class="sig" style="${running?'':'background:var(--paper);color:var(--ink-3)'}">${running?'●':'○'}</span>
      <span class="who"><div class="c">${a.activator_call||'?'}</div>
        <div class="f">${a.reference||''} · ${a.band||'?'} · ${a.mode||'?'}</div></span>
      <span class="d"><b>${running?t('spots.now'):(a.utc_start||'').slice(5,10)}</b>${
        running ? t('spots.until')+' '+(a.utc_end||'').slice(11,16) : (a.utc_start||'').slice(11,16)+' UTC'}</span>
    </div>`;
  }).join('') : `<p class="hint">${t('spots.noagenda')}</p>`;
  meta.textContent = (spotsAt
    ? `${rows.length} ${t('spots.announced')} · ${t('spots.updated')} ${spotsAt.toLocaleTimeString(locale(),{hour:'2-digit',minute:'2-digit'})}`
    : '')
    + (agendaSkipped ? ` · ${agendaSkipped} ${t('spots.unplaced')}` : '');
}


$('spotList').addEventListener('click', e=>{
  const row=e.target.closest('.spot[data-id]'); if(row) openSpot(Number(row.dataset.id));
});
$('spotTab').addEventListener('click', e=>{
  const b=e.target.closest('.seg[data-tab]'); if(!b) return;
  spotTab=b.dataset.tab;
  [...$('spotTab').children].forEach(c=>c.classList.toggle('on',c===b));
  $('agNewOpen').hidden = spotTab !== 'agenda';
  renderSpots();
});
/* Settings ↔ the quick filter above the Spots list share the same value
   ('all' | 'onff' | a programme code) — whatever you pick here is also the
   default for next time, and the other way round. */
function setSpotFilter(value){
  spotFilter = value;
  remember('spotFilter2', spotFilter);
  syncSpotFilterUI();
  paintSpots(); renderSpots();
}
function syncSpotFilterUI(){
  [...$('spotFilter').children].forEach(c=>c.classList.toggle('on', c.dataset.filter===spotFilter));
  const seg = $('setSpotFilter');
  if(seg) [...seg.children].forEach(c=>c.classList.toggle('on', c.dataset.filter===spotFilter));
  const sel = $('setSpotCountry');
  if(sel) sel.value = (spotFilter!=='all' && spotFilter!=='onff') ? spotFilter : '';
}
function populateSpotCountries(){
  const sel = $('setSpotCountry'); if(!sel) return;
  const current = sel.value;
  sel.innerHTML = `<option value="" data-i18n="set.spotscountrynone">${t('set.spotscountrynone')}</option>`
    + wwffPrograms.map(p => `<option value="${p.program}">${p.country}</option>`).join('');
  sel.value = current;
  syncSpotFilterUI();
}
$('spotFilter').addEventListener('click', e=>{
  const b=e.target.closest('.seg'); if(!b) return;
  setSpotFilter(b.dataset.filter);
});
$('setSpotFilter').addEventListener('click', e=>{
  const b=e.target.closest('.seg'); if(!b) return;
  setSpotFilter(b.dataset.filter);
});
$('setSpotCountry').addEventListener('change', e=>{
  setSpotFilter(e.target.value || 'all');
});
$('setWorldCountry').addEventListener('change', e=>{
  setWorldFilter(e.target.value || 'all');
});

/* ---------- spot detail ---------- */
function openSpot(id){
  const s = spots.find(x=>Number(x.id)===Number(id)); if(!s) return;
  closeSheet();
  if($('viewHeat').classList.contains('on')) $('viewHeat').classList.add('tucked');
  $('spCall').textContent = s.activator || '?';
  $('spAgo').textContent  = agoText(s) + (s.spotter ? ` door ${s.spotter}` : '');
  $('spRef').textContent  = s.reference || '';
  const facts = [
    [t('spot.freqmode'), `${s.frequency_khz||'?'} kHz · ${s.mode||'?'}`],
    [t('spot.area'), s.reference_name || s.reference || '—'],
    [t('spot.locthere'), locator(s.latitude,s.longitude)],
  ];
  if(here) facts.push([t('spot.locyou'), locator(here.lat,here.lon)]);
  if(s.remarks) facts.push([t('spot.remark'), s.remarks, true]);
  $('spFacts').innerHTML = facts.map(([k,v,wide])=>
    `<div class="fact${wide?' wide':''}"><div class="k">${k}</div><div class="v">${v}</div></div>`).join('');

  if(here){
    const br = bearing(here.lat,here.lon,s.latitude,s.longitude);
    $('spBearing').innerHTML =
      `<span class="compass"><span class="n">N</span><span class="needle" style="transform:translate(-50%,-100%) rotate(${br.toFixed(0)}deg)"></span></span>
       <span><div class="bg">${Math.round(br)}° · ${fmtKm(dist(s))}</div>
       <div class="bs">${compassName(br)} — ${t('spot.fromyou')}</div></span>`;
  } else {
    $('spBearing').innerHTML = `<span class="bs">${t('spot.nofix')}</span>`;
  }
  $('spotSheet').classList.add('open');
  document.body.classList.add('sheet-open');
  requestAnimationFrame(()=>document.body.style.setProperty('--sheet-h',$('spotSheet').offsetHeight+'px'));
  map.easeTo({center:[s.longitude,s.latitude], zoom:Math.max(map.getZoom(),9)});
}
$('closeSpot').onclick = ()=>{
  $('spotSheet').classList.remove('open');
  document.body.classList.remove('sheet-open');
  $('viewHeat').classList.remove('tucked');
};

