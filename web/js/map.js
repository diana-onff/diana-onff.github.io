/* ---------- map ---------- */
const map = new maplibregl.Map({
  container:'map',
  style: STYLE_URL(currentStyle),
  center:[4.47,50.85], zoom:7.2,
  attributionControl:{compact:true}
});
map.addControl(new maplibregl.NavigationControl({showCompass:false}),'bottom-right');

function paintZones(){
  if (!zones || !map.isStyleLoaded()) return;
  if (map.getSource('onff')) return;
  
  // generateId gives every feature an ascending id, in the same order as the array —
  // that is what feature-state (the selection highlight) needs.
  map.addSource('onff',{type:'geojson',data:zones,generateId:true});

  map.addLayer({
    id:'onff-fill', type:'fill', source:'onff',
    paint:{
      'fill-color':'#2d6a4f',
      // 'zoom' is only allowed at the top of an interpolate, so the selection sits inside it.
      'fill-opacity':['interpolate',['linear'],['zoom'],
        7,  ['case',['boolean',['feature-state','sel'],false],0.42,0.20],
        12, ['case',['boolean',['feature-state','sel'],false],0.45,0.28]]
    }
  });
  map.addLayer({
    id:'onff-line', type:'line', source:'onff',
    paint:{
      'line-color':['case',['boolean',['feature-state','sel'],false],'#d97706','#1b4332'],
      'line-width':['interpolate',['linear'],['zoom'],
        7,  ['case',['boolean',['feature-state','sel'],false],2.4,0.5],
        12, ['case',['boolean',['feature-state','sel'],false],3.2,1.6]],
      'line-opacity':0.9
    }
  });
  // Labels come from a separate point source: one point per reference. Put them
  // on the fill layer and MapLibre draws a label per polygon part — and an area
  // like ONFF-0329 consists of 67 separate parcels.
  map.addSource('onff-pts',{type:'geojson',data:labelFeatures()});
  if (map.getStyle().glyphs) map.addLayer({
    id:'onff-label', type:'symbol', source:'onff-pts',
    layout:{
      'text-field':['get','ref'],
      'text-font':['Noto Sans Regular'],
      'text-size':11, 'text-allow-overlap':false, 'text-padding':6,
      'visibility': showLabels ? 'visible' : 'none'
    },
    paint:{'text-color':'#1b4332','text-halo-color':'#f6f4ee','text-halo-width':1.6}
  });

  paintNoPoly();

  map.on('click','onff-fill', e => {
    // Zones can overlap — show everything under the finger, not just the topmost one.
    const hits = map.queryRenderedFeatures(e.point,{layers:['onff-fill']});
    select(hits[0].properties.ref, hits.map(h=>h.properties.ref));
  });
  map.on('mouseenter','onff-fill',()=>map.getCanvas().style.cursor='pointer');
  map.on('mouseleave','onff-fill',()=>map.getCanvas().style.cursor='');
}

/* ---------- references without a boundary ----------
 *
 * A dotted ring, not a filled area. You should be able to see that difference on
 * the map without reading the legend: a boundary is a boundary, a point is a
 * guess from ONFF's own list. The icon is drawn on canvas — no external file.
 */
function addNoPolyIcon(){
  if(map.hasImage('diana-nopoly')) return;
  const d = 44, r = 15, c = d/2, dpr = 2, cv = document.createElement('canvas');
  cv.width = cv.height = d*dpr;
  const x = cv.getContext('2d');
  x.scale(dpr,dpr);

  x.beginPath(); x.arc(c,c,r+3,0,Math.PI*2);
  x.fillStyle = 'rgba(246,244,238,.85)'; x.fill();       // readable on every map style

  x.setLineDash([4,3.2]); x.lineWidth = 2.4; x.strokeStyle = '#1b4332';
  x.beginPath(); x.arc(c,c,r,0,Math.PI*2); x.stroke();

  x.setLineDash([]); x.beginPath(); x.arc(c,c,3.6,0,Math.PI*2);
  x.fillStyle = '#d97706'; x.fill();                      // amber = "approximate"

  map.addImage('diana-nopoly', {width:d*dpr, height:d*dpr, data:x.getImageData(0,0,d*dpr,d*dpr).data},
               {pixelRatio:dpr});
}

function paintNoPoly(){
  if(!map.isStyleLoaded()) return;
  if(!noPoly || !noPoly.features.length) return;
  if(map.getSource('onff-np')) return;

  addNoPolyIcon();
  map.addSource('onff-np',{type:'geojson',data:noPoly});
  map.addLayer({
    id:'np-dot', type:'symbol', source:'onff-np',
    layout:{'icon-image':'diana-nopoly','icon-allow-overlap':true,
            'icon-size':['interpolate',['linear'],['zoom'],7,0.6,12,1],
            'visibility': (showZones && showNoPoly) ? 'visible':'none'}
  });
  if(map.getStyle().glyphs) map.addLayer({
    id:'np-label', type:'symbol', source:'onff-np',
    layout:{'text-field':['get','ref'],'text-font':['Noto Sans Regular'],'text-size':11,
            'text-offset':[0,1.4],'text-anchor':'top','text-allow-overlap':false,'text-padding':6,
            'visibility': (showZones && showNoPoly && showLabels) ? 'visible':'none'},
    paint:{'text-color':'#1b4332','text-halo-color':'#f6f4ee','text-halo-width':1.6}
  });

  if(!npBound){          // layers are re-added after every style switch, handlers are not
    npBound = true;
    map.on('click','np-dot', e => select(e.features[0].properties.ref));
    map.on('mouseenter','np-dot',()=>map.getCanvas().style.cursor='pointer');
    map.on('mouseleave','np-dot',()=>map.getCanvas().style.cursor='');
  }
}
let npBound = false;

/* ---------- other WWFF areas worldwide (from the same CSV) ----------
   Never a boundary — only a point, just like an ONFF reference without a
   polygon. With thousands of points they get clustered (MapLibre's built-in
   cluster option), otherwise the map is unreadable at a world-level zoom. */
let showWorld = true;
let worldFilter = recall('worldFilter') || 'all';
let worldPoints = {type:'FeatureCollection', features:[]};
let worldLoaded = false, worldLoading = null;
let worldBound = false;

async function loadWorldPoints(){
  if(worldLoaded || worldLoading) return worldLoading;
  worldLoading = (async () => {
    try{
      worldPoints = await fetchFirst(['./data/wwff-world.geojson','../data/wwff-world.geojson']);
    }catch{ worldPoints = {type:'FeatureCollection', features:[]}; }
    worldLoaded = true;
    const optW = $('optWorld');
    if(optW) optW.hidden = worldPoints.features.length === 0;
    paintWorld();
  })();
  return worldLoading;
}

function worldFilteredData(){
  if(worldFilter === 'all') return worldPoints;
  const feats = worldPoints.features.filter(f => refProgram(f.properties.ref) === worldFilter);
  return {type:'FeatureCollection', features:feats};
}

function paintWorld(tries){
  if(!worldLoaded) return;
  // The data can arrive sooner than the map style does (the file is large).
  // In that case just try again in a moment — otherwise the layer lies there
  // quietly until something else happens to call redrawOverlays().
  if(!map.isStyleLoaded()){
    tries = tries || 0;
    if(tries > 100) return;    // ~8 s, then we give up
    setTimeout(()=>paintWorld(tries+1), 80);
    return;
  }
  const data = worldFilteredData();
  const src = map.getSource('wwff-world');
  if(src){ src.setData(data); applyVisibility(); return; }
  if(!worldPoints.features.length) return;
  map.addSource('wwff-world', { type:'geojson', data, cluster:true, clusterRadius:50, clusterMaxZoom:9 });
  // Its own colour, and deliberately not green or orange: those are already
  // taken by the areas, the spots and the agenda. Blue reads immediately as
  // "another country".
  map.addLayer({ id:'world-clusters', type:'circle', source:'wwff-world', filter:['has','point_count'],
    paint:{ 'circle-color':'#2563eb', 'circle-opacity':0.7,
            'circle-radius':['step',['get','point_count'],13, 50,17, 500,22, 5000,27],
            'circle-stroke-width':1.5, 'circle-stroke-color':'#fff' } });
  if(map.getStyle().glyphs) map.addLayer({
    id:'world-cluster-count', type:'symbol', source:'wwff-world', filter:['has','point_count'],
    layout:{'text-field':['get','point_count_abbreviated'],'text-font':['Noto Sans Regular'],'text-size':11},
    paint:{'text-color':'#fff'} });
  // Growing with the zoom: zoomed out there are thousands of them and they have
  // to stay small, zoomed in there is a handful and you shouldn't have to hunt
  // for them.
  map.addLayer({ id:'world-point', type:'circle', source:'wwff-world', filter:['!',['has','point_count']],
    paint:{ 'circle-radius':['interpolate',['linear'],['zoom'], 4,3.5, 8,5, 12,7.5, 16,10],
            'circle-color':'#2563eb', 'circle-opacity':0.95,
            'circle-stroke-width':['interpolate',['linear'],['zoom'], 4,1, 12,2],
            'circle-stroke-color':'#fff' } });
  // Only from zoom 11 on: below that it is a cloud of text, above it it is
  // exactly what you want to know without having to tap.
  if(map.getStyle().glyphs) map.addLayer({
    id:'world-label', type:'symbol', source:'wwff-world', filter:['!',['has','point_count']],
    minzoom:11,
    layout:{'text-field':['get','ref'],'text-font':['Noto Sans Regular'],'text-size':11,
            'text-offset':[0,1.1],'text-anchor':'top','text-allow-overlap':false,'text-padding':6},
    paint:{'text-color':'#1e3a8a','text-halo-color':'#fff','text-halo-width':2} });
  if(!worldBound){
    worldBound = true;
    map.on('click','world-clusters', e => {
      const f = map.queryRenderedFeatures(e.point, {layers:['world-clusters']})[0];
      const clusterId = f.properties.cluster_id;
      map.getSource('wwff-world').getClusterExpansionZoom(clusterId, (err, zoom) => {
        if(err) return;
        map.easeTo({center: f.geometry.coordinates, zoom});
      });
    });
    map.on('click','world-point', e => {
      const f = e.features[0];
      new maplibregl.Popup({closeButton:true, maxWidth:'240px'})
        .setLngLat(f.geometry.coordinates)
        .setHTML(`<b>${f.properties.ref}</b><br>${f.properties.name||''}`)
        .addTo(map);
    });
    map.on('mouseenter','world-clusters',()=>map.getCanvas().style.cursor='pointer');
    map.on('mouseleave','world-clusters',()=>map.getCanvas().style.cursor='');
    map.on('mouseenter','world-point',()=>map.getCanvas().style.cursor='pointer');
    map.on('mouseleave','world-point',()=>map.getCanvas().style.cursor='');
  }
  applyVisibility();
}

function setWorldFilter(value){
  worldFilter = value;
  remember('worldFilter', worldFilter);
  syncWorldFilterUI();
  if(worldLoaded) paintWorld();
}

function syncWorldFilterUI(){
  const sel = $('setWorldCountry');
  if(sel) sel.value = (worldFilter!=='all') ? worldFilter : '';
}

function populateWorldCountries(){
  const sel = $('setWorldCountry'); if(!sel) return;
  const current = sel.value;
  sel.innerHTML = `<option value="" data-i18n="set.worldcountrynone">${t('set.worldcountrynone')}</option>`
    + wwffPrograms.map(p => `<option value="${p.program}">${p.country}</option>`).join('');
  sel.value = current;
  syncWorldFilterUI();
}

/* The data stands apart from the map. If the background map drops out — no
   network, nothing in the cache yet — then search, session, rules and heatmap
   all keep working. Only the tiles are missing. */
$('splashVer').textContent = 'v' + APP_VERSION;
$('setVer').textContent = `${APP_VERSION} · ${BUILD_TXT}`;
$('verBadge').textContent = `v${APP_VERSION} · ${BUILD_TXT}`;
// Tapping the badge takes you to Settings, where the dataset and the "Check for
// updates" button live. That is where you want to go anyway the moment you
// start paying attention to a version number.
$('verBadge').onclick = () =>
  document.querySelector('#nav button[data-view="viewSet"]').click();
loadMeta();
splashStep(22, 'splash.data');
// An iframe has no business showing a splash screen: that is someone else's frame.
if(new URLSearchParams(location.search).get('embed') === '1') splashDone();

const dataReady = loadData().then(()=>{
  splashStep(70, 'splash.draw');
  applyLang();
  [...$('langPick').children].forEach(b=>b.classList.toggle('on', b.dataset.lang===lang));
  redrawOverlays();
  loadSettingsUI();
  applyHomeView();
  try{ applyEmbed(); }catch(err){ console.error('embed-parameters:', err); }
  if(showSpots) startSpots();
  if(showWorld) loadWorldPoints();
  whenDrawn();
}).catch(err=>{
  $('counts').textContent = t('map.datafail');
  console.error('data:', err);
  splashDone();              // an error is no reason to be stuck on the splash screen
});

/* The splash screen goes away once the zones are genuinely drawn — not once the
   data has arrived. Otherwise you see an empty map still filling itself in. If
   there are references without a boundary, their layer counts too: otherwise the
   screen would disappear while those dots still have to appear. */
function whenDrawn(tries){
  tries = tries || 0;
  const needsPoints = noPoly && noPoly.features && noPoly.features.length > 0;
  const drawn = map.isStyleLoaded() && map.getLayer('onff-fill')
    && (!needsPoints || map.getLayer('np-dot'));
  if(drawn || tries > 100){    // ~10 s, then we just show whatever is there
    splashStep(100, 'splash.ready');
    setTimeout(splashDone, 260);
    return;
  }
  if(tries === 12) splashStep(88, 'splash.map');
  setTimeout(()=>whenDrawn(tries+1), 100);
}

map.on('load', () => dataReady.then(redrawOverlays));
map.on('error', e => {
  // A missing background map must not drag the rest of the app down with it.
  if(String(e.error||'').match(/style|tile|glyph/i)) return;
  console.warn('kaart:', e.error);
});

$('langPick').addEventListener('click', e=>{
  const b=e.target.closest('.seg[data-lang]'); if(!b) return;
  lang = langPref = b.dataset.lang;     // via the buttons at the top it is always a fixed choice
  [...$('langPick').children].forEach(c=>c.classList.toggle('on',c===b));
  [...$('setLang').children].forEach(c=>c.classList.toggle('on',c.dataset.lang===langPref));
  saveSettings();
  applyLang();
});

/* ---------- embed mode: ?embed=1&prov=…&ref=…&lang=…&spots=1&world=1 ----------
   An <iframe> that is already sitting somewhere must not suddenly start showing
   spots or world points because the default in the app changed — so in an embed
   both layers stay off unless the parameter is explicitly there. */
function applyEmbed(){
  const q = new URLSearchParams(location.search);
  // Spots are on everywhere, in an embed too — ?spots=0 is the way out for
  // anyone who wants a bare map. The world-points layer does stay opt-in in an
  // embed: it is big, and an already published iframe has no business suddenly
  // pulling down 9 MB.
  if(q.get('spots')==='0') showSpots = false;
  if(q.get('embed')==='1') showWorld = q.get('world')==='1';
  if(q.get('world')==='1'){ showWorld=true; loadWorldPoints();
    const o=document.querySelector('[data-layer="world"]'); if(o){o.classList.add('on');o.querySelector('.sw').classList.add('on');} }
  if(q.get('ref')) select(q.get('ref').toUpperCase());
  if(q.get('prov')){
    const p=q.get('prov').toLowerCase();
    const sel = index.filter(z=>z.bbox && (z.prov||'').toLowerCase().includes(p));
    if(sel.length){
      const b=[Math.min(...sel.map(z=>z.bbox[0])),Math.min(...sel.map(z=>z.bbox[1])),
               Math.max(...sel.map(z=>z.bbox[2])),Math.max(...sel.map(z=>z.bbox[3]))];
      map.fitBounds([[b[0],b[1]],[b[2],b[3]]],{padding:30});
    }
  }
  if(q.get('embed')==='1'){
    document.body.classList.add('embed');
    document.body.classList.remove('has-nav');
  }
}

/* On a style switch all of our own layers disappear — draw them again. */
let styleSwitching = false;
function setStyle(name){
  currentStyle = name;
  // setStyle is asynchronous. Right after it, isStyleLoaded() still reports true
  // for the old style; if we drew then, the new style would wipe it straight
  // back off. 'idle' only fires once the new style is really in place.
  styleSwitching = true;
  map.setStyle(STYLE_URL(name));
  map.once('idle', () => { styleSwitching = false; redrawOverlays(); });
  map.once('styledata', () => setTimeout(() => { styleSwitching = false; redrawOverlays(); }, 400));
}

/* One single place that rebuilds everything we put on the map ourselves.
 *
 * Two things used to make this unreliable. 'styledata' fires before the style is
 * really ready — addLayer then does nothing and the areas vanish. And if the
 * spots layer was switched on before the map had loaded (via ?spots=1, for
 * instance), paintSpots quietly bailed out without ever trying again.
 *
 * So this function waits until both the style and the data are there, and
 * anyone who wants to draw something simply calls this. */
let redrawPending = false;
function redrawOverlays(){
  if(redrawPending) return;
  redrawPending = true;
  (function attempt(tries){
    if(styleSwitching || !map.isStyleLoaded() || !zones){
      if(tries > 100){ redrawPending = false; return; }   // ~8 s, then we give up
      return void setTimeout(() => attempt(tries+1), 80);
    }
    redrawPending = false;
    try{
      paintZones();
      // Called separately, not only from paintZones: that one stops right away
      // if the source already exists, and the points are loaded after the zones.
      // Otherwise they never get added — the same trap as with the spots earlier.
      paintNoPoly();
      if(showSpots) paintSpots();
      if(showWorld) paintWorld();
      applyVisibility();
      reselect();
      if(heatOnMap) applyHeatPaint(true);
    }catch(err){ console.warn('hertekenen kaart:', err); }
  })(0);
}

function syncSwitch(laag, aan){
  const opt = document.querySelector(`[data-layer="${laag}"]`);
  if(!opt) return;
  opt.classList.toggle('on', aan);
  const sw = opt.querySelector('.sw');
  if(sw) sw.classList.toggle('on', aan);
}

function applyVisibility(){
  // The menu first, then the map. The switches describe a preference, not a
  // layer: without a loaded map style the button would otherwise not match the
  // actual setting.
  syncSwitch('spots', showSpots);
  syncSwitch('arcs',  showArcs);
  if(!map.getLayer('onff-fill')) return;
  const v = showZones ? 'visible':'none';
  ['onff-fill','onff-line'].forEach(l=>map.setLayoutProperty(l,'visibility',v));
  if(map.getLayer('onff-label'))
    map.setLayoutProperty('onff-label','visibility',(showZones&&showLabels)?'visible':'none');
  if(map.getLayer('np-dot'))
    map.setLayoutProperty('np-dot','visibility',(showZones&&showNoPoly)?'visible':'none');
  if(map.getLayer('np-label'))
    map.setLayoutProperty('np-label','visibility',(showZones&&showNoPoly&&showLabels)?'visible':'none');
  const sv = showSpots ? 'visible' : 'none';
  ['spots-pulse','spots-icon','spots-call','agenda-dot','agenda-label']
    .forEach(l=>{ if(map.getLayer(l)) map.setLayoutProperty(l,'visibility',sv); });
  // The arc lines to your own QTH can be switched separately: with a lot of
  // spots it otherwise turns into a spider's web across the map.
  const av = (showSpots && showArcs) ? 'visible' : 'none';
  ['spot-arcs-line','agenda-arcs-line']
    .forEach(l=>{ if(map.getLayer(l)) map.setLayoutProperty(l,'visibility',av); });
  const wv = showWorld ? 'visible' : 'none';
  ['world-clusters','world-cluster-count','world-point','world-label']
    .forEach(l=>{ if(map.getLayer(l)) map.setLayoutProperty(l,'visibility',wv); });
}

/* ---------- selection & detail panel ---------- */
function featureIdOf(ref){ return zones.features.findIndex(f=>f.properties.ref===ref); }

function reselect(){ if(selected) markSelected(selected); }

function clearSelection(){
  if(map._lastSel!=null && map.getSource('onff')){
    map.setFeatureState({source:'onff',id:map._lastSel},{sel:false});
    map._lastSel = null;
  }
}

/* A reference without a boundary. The same panel, but without an area figure and
   without parcels, and with the reason alongside — otherwise a half-empty panel
   looks like a bug instead of a gap in the source data. */
function selectPoint(f){
  const p = f.properties;
  selected = p.ref;
  clearSelection();

  $('badges').innerHTML =
    `<span class="pill">${p.ref}</span>` +
    (p.prov ? `<span class="pill grey">${p.prov}</span>` : '') +
    `<span class="pill amber">${t('zone.nopoly')}</span>`;
  $('zoneName').textContent = p.name || p.ref;
  $('facts').innerHTML = (p.place
    ? `<div class="fact"><div class="k">${t('zone.place')}</div><div class="v">${p.place}</div></div>` : '')
    + activityFacts(p.ref);
  $('zoneNote').textContent = t('zone.nopolynote');

  openSheet();
  map.easeTo({center:f.geometry.coordinates, zoom:Math.max(map.getZoom(),12),
              padding:{top:90,bottom:260,left:40,right:40}});
}

function markSelected(ref){
  const id = featureIdOf(ref);
  if(id<0) return;
  if(map._lastSel!=null) map.setFeatureState({source:'onff',id:map._lastSel},{sel:false});
  map.setFeatureState({source:'onff',id},{sel:true});
  map._lastSel = id;
}

const FIELDS = [
  ['area_ha','zone.area', v=>`${v.toLocaleString(locale())} ha`],
  ['manager','zone.manager',   v=>v],
  ['desig',  'zone.desig',  v=>v],
  ['iucn',   'zone.iucn', v=>v],
  ['registration','zone.reg', v=>v],
  ['status_year','zone.since', v=>v],
];

function select(ref, alsoIn){
  const f = zones.features.find(x=>x.properties.ref===ref);
  if(!f){ const p = noPolyByRef.get(ref); if(p) selectPoint(p); return; }
  selected = ref;
  const p = f.properties;

  $('badges').innerHTML =
    `<span class="pill">${p.ref}</span>` +
    (p.prov ? `<span class="pill grey">${p.prov}</span>` : '') +
    (p.layer ? `<span class="pill grey">${p.layer}</span>` : '');
  $('zoneName').textContent = p.name;

  // Only show what is actually there. For nearly half the areas that is not
  // much — empty boxes full of dashes are worse than no box at all.
  const nParts = f.geometry.coordinates.length;
  $('facts').innerHTML = FIELDS
    .filter(([k])=>p[k]!==undefined && p[k]!==null && p[k]!=='')
    .map(([k,label,fmt])=>`<div class="fact"><div class="k">${t(label)}</div><div class="v">${fmt(p[k])}</div></div>`)
    .join('')
    + (nParts>1 ? `<div class="fact"><div class="k">${t('zone.parts')}</div><div class="v">${nParts}</div></div>` : '')
    + activityFacts(ref);

  const parts = f.geometry.coordinates.length;
  const notes = [];
  if(parts > 1) notes.push(t('zone.partsnote').replace('{n}', parts));
  const overlap = (alsoIn||[]).filter(r=>r!==ref);
  if(overlap.length) notes.push(t('zone.overlap').replace('{refs}', overlap.join(', ')));
  $('zoneNote').textContent = notes.join(' ');

  markSelected(ref);
  openSheet();

  const b = bboxOf(f.geometry);
  map.fitBounds([[b[0],b[1]],[b[2],b[3]]],{padding:{top:90,bottom:260,left:40,right:40},maxZoom:14});
}

function openSheet(){
  // Two panels at the bottom at once is unreadable on a phone.
  if($('viewHeat').classList.contains('on')) $('viewHeat').classList.add('tucked');
  const el = $('sheet');
  el.classList.add('open');
  // The height varies with the number of facts, so measure after rendering.
  requestAnimationFrame(()=>document.body.style.setProperty('--sheet-h', el.offsetHeight+'px'));
  document.body.classList.add('sheet-open');
}
function closeSheet(){
  $('sheet').classList.remove('open');
  document.body.classList.remove('sheet-open');
  $('viewHeat').classList.remove('tucked');
}
$('closeSheet').onclick = closeSheet;
$('zoneSpot').onclick = () => {
  closeSheet();
  document.querySelector('#nav button[data-view="viewSelf"]').click();
};
map.on('click', e => {                       // a click beside an area closes the panel
  if(!map.queryRenderedFeatures(e.point,{layers:map.getLayer('onff-fill')?['onff-fill']:[]}).length) closeSheet();
});

/* ---------- search ---------- */
function search(term){
  const t = term.trim().toLowerCase();
  if(t.length<2) return [];
  const digits = t.replace(/\D/g,'');
  return index.filter(z =>
      z.name.toLowerCase().includes(t) ||
      z.ref.toLowerCase().includes(t) ||
      (digits && z.ref.includes(digits.padStart(4,'0')))
    ).slice(0,40);
}
$('q').addEventListener('input', e => {
  const rows = search(e.target.value);
  $('results').innerHTML = rows.map(z =>
    `<div class="res" data-ref="${z.ref}"><span class="r">${z.ref.replace('ONFF-','')}</span>
     <span class="n">${z.name}${z.nopoly?` <span class="np">◌ ${t('zone.nopoly')}</span>`:''}</span>
     <span class="p">${z.prov||''}</span></div>`).join('')
    || (e.target.value.trim().length>1 ? '<div class="res"><span class="n">Niets gevonden</span></div>' : '');
});
$('results').addEventListener('click', e => {
  const row = e.target.closest('.res[data-ref]');
  if(row){ select(row.dataset.ref); toggle('search',false); }
});

/* ---------- panels ---------- */
function toggle(what, force){
  const map_ = {search:['search','btnSearch'], style:['popStyle','btnStyle'],
                layers:['popLayers','btnLayers']};
  for(const [k,[el,btn]] of Object.entries(map_)){
    const open = k===what ? (force!==undefined?force:!$(el).classList.contains('open')) : false;
    $(el).classList.toggle('open',open);
    $(btn).setAttribute('aria-expanded',open);
  }
  const searching = $('search').classList.contains('open');
  document.body.classList.toggle('searching', searching);
  if(searching) $('q').focus();
}
$('btnSearch').onclick = ()=>toggle('search');
$('btnStyle').onclick  = ()=>toggle('style');
$('btnLayers').onclick = ()=>toggle('layers');
/* Wrapped in an arrow rather than handed over directly, and that is the single
 * line the split into js/ actually changed. prefetchArea() lives in js/offline.js,
 * which loads after this file; as one big app.js the function declaration was
 * hoisted to the top and a bare reference worked. Across files it would be
 * undefined at this moment and the button would quietly do nothing. The arrow
 * looks the name up when the button is pressed, by which time every file has
 * run — the same idiom as the buttons above it. */
$('btnOffline').onclick = () => prefetchArea();
$('btnFit').onclick = () => { toggle(null); if(!showSpots){ showSpots = true;
  remember('spots','1'); syncSwitch('spots', true); startSpots(); applyVisibility(); }
  fitSpots(); };

$('popStyle').addEventListener('click', e => {
  const opt = e.target.closest('.opt'); if(!opt) return;
  [...$('popStyle').children].forEach(c=>c.classList?.remove('on'));
  opt.classList.add('on');
  setStyle(opt.dataset.style);
  toggle(null);            // style chosen — the panel can close
});
$('popLayers').addEventListener('click', e => {
  const opt = e.target.closest('.opt[data-layer]'); if(!opt) return;
  if(opt.dataset.layer==='onff') showZones = !showZones;
  if(opt.dataset.layer==='labels') showLabels = !showLabels;
  if(opt.dataset.layer==='nopoly') showNoPoly = !showNoPoly;
  if(opt.dataset.layer==='spots'){
    showSpots = !showSpots; remember('spots', showSpots ? '1' : '0');
    if(showSpots) startSpots();          // only fetch them once someone wants to see them
  }
  if(opt.dataset.layer==='arcs'){ showArcs = !showArcs; remember('arcs2', showArcs ? '1' : '0'); }
  if(opt.dataset.layer==='world'){ showWorld = !showWorld; if(showWorld) loadWorldPoints(); }
  opt.classList.toggle('on');
  opt.querySelector('.sw').classList.toggle('on');
  applyVisibility();
});


