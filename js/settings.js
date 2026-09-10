/* ================================================================== *
 * Settings — everything in the localStorage of this device
 * ================================================================== */
const GRID_RE = /^[A-R]{2}[0-9]{2}([A-X]{2})?$/i;

const cfg = {
  call:  recall('call'),
  callp: recall('callp'),
  grid:  recall('grid'),
  // 'gps' is the factory setting: wherever you are standing right now. For a
  // field application that is nearly always the answer to "where should the map
  // open". If the browser says no, or takes too long, homeView() moves on to
  // your locator, then your country prefix, then the whole area — so the map
  // never starts out on an empty globe.
}

function saveSettings(){
  remember('call',  cfg.call);
  remember('callp', cfg.callp);
  remember('grid',  cfg.grid);
  remember('lang',  langPref);      // 'auto' or a language code — not the resolved language
}

function loadSettingsUI(){
  $('setCall').value  = cfg.call;
  $('setCallP').value = cfg.callp;
  $('setGrid').value  = cfg.grid;
  syncSpotFilterUI();
  syncWorldFilterUI();
  [...$('setLang').children].forEach(b => b.classList.toggle('on', b.dataset.lang === langPref));
  checkGrid();
}

$('setLang').addEventListener('click', e => {
  const b = e.target.closest('.seg[data-lang]'); if(!b) return;
  langPref = b.dataset.lang;
  lang = langPref === 'auto' ? browserLang() : langPref;
  [...$('setLang').children].forEach(c => c.classList.toggle('on', c === b));
  [...$('langPick').children].forEach(c => c.classList.toggle('on', c.dataset.lang === lang));
  saveSettings();
  applyLang();
});

function checkGrid(){
  const v = $('setGrid').value.trim().toUpperCase();
  const fb = $('fbGrid');
  if(!v){ fb.textContent=''; fb.className='fb'; $('setGrid').className=''; return true; }
  const ok = GRID_RE.test(v);
  fb.textContent = ok ? '' : t('set.gridbad');
  fb.className = 'fb' + (ok ? '' : ' bad');
  $('setGrid').className = ok ? 'good' : 'bad';
  return ok;
}

['setCall','setCallP','setGrid'].forEach(id => $(id).addEventListener('input', e => {
  const pos = e.target.selectionStart;
  e.target.value = e.target.value.toUpperCase();
  e.target.setSelectionRange(pos,pos);
  cfg.call  = $('setCall').value.trim();
  cfg.callp = $('setCallP').value.trim();
  cfg.grid  = $('setGrid').value.trim();
  checkGrid();
  saveSettings();
}));
$('setGridGps').onclick = () => {
  if(!navigator.geolocation) return;
  navigator.geolocation.getCurrentPosition(pos => {
    cfg.grid = locator(pos.coords.latitude, pos.coords.longitude);
    $('setGrid').value = cfg.grid; checkGrid(); saveSettings();
  });
};

/* ---------- locator → coordinates ---------- */
function gridToLatLon(g){
  g = (g||'').toUpperCase();
  if(!GRID_RE.test(g)) return null;
  const A = 'A'.charCodeAt(0);
  let lon = (g.charCodeAt(0)-A)*20 - 180;
  let lat = (g.charCodeAt(1)-A)*10 - 90;
  lon += parseInt(g[2],10)*2;
  lat += parseInt(g[3],10)*1;
  if(g.length >= 6){
    lon += (g.charCodeAt(4)-A)*(5/60);
    lat += (g.charCodeAt(5)-A)*(2.5/60);
    lon += 2.5/60; lat += 1.25/60;
  } else { lon += 1; lat += 0.5; }
  return [lon, lat];
}

/* Callsign prefix → rough country position. Enough to open the map on the right
   country; not meant as a DXCC table. Extendable when Diana goes European. */
const PREFIX_HOME = {
  ON:[4.47,50.85,7.2], OO:[4.47,50.85,7.2], OP:[4.47,50.85,7.2], OQ:[4.47,50.85,7.2],
  OR:[4.47,50.85,7.2], OS:[4.47,50.85,7.2], OT:[4.47,50.85,7.2],
  PA:[5.3,52.2,7], PB:[5.3,52.2,7], PC:[5.3,52.2,7], PD:[5.3,52.2,7], PE:[5.3,52.2,7],
  PH:[5.3,52.2,7], PI:[5.3,52.2,7],
  DA:[10.4,51.2,6], DB:[10.4,51.2,6], DC:[10.4,51.2,6], DD:[10.4,51.2,6], DF:[10.4,51.2,6],
  DG:[10.4,51.2,6], DH:[10.4,51.2,6], DJ:[10.4,51.2,6], DK:[10.4,51.2,6], DL:[10.4,51.2,6],
  DM:[10.4,51.2,6], DO:[10.4,51.2,6],
  F:[2.4,46.6,5.5], TM:[2.4,46.6,5.5],
  G:[-2.0,53.5,5.6], M:[-2.0,53.5,5.6], '2E':[-2.0,53.5,5.6],
  EI:[-8.0,53.3,6.5], EJ:[-8.0,53.3,6.5],
  LX:[6.1,49.8,9], HB:[8.2,46.8,7.4], OE:[13.3,47.6,6.8],
  OZ:[10.0,56.0,6.4], '5Q':[10.0,56.0,6.4], OU:[10.0,56.0,6.4],
  SM:[15.5,62.0,4.6], SA:[15.5,62.0,4.6], LA:[9.0,64.5,4.4], OH:[26.0,64.5,4.6],
  I:[12.5,42.5,5.3], IK:[12.5,42.5,5.3], IZ:[12.5,42.5,5.3], IW:[12.5,42.5,5.3],
  EA:[-3.7,40.2,5.5], EB:[-3.7,40.2,5.5], EC:[-3.7,40.2,5.5],
  CT:[-8.0,39.5,6.2], SP:[19.3,52.0,5.8], OK:[15.5,49.8,6.5], OM:[19.5,48.7,6.8],
  HA:[19.4,47.2,6.6], YO:[25.0,45.9,6.2], LZ:[25.3,42.7,6.6], SV:[23.7,38.5,5.8],
  YL:[24.6,56.9,6.5], ES:[25.5,58.7,6.6], LY:[23.9,55.3,6.6],
};

/* Where the map sits until the GPS position comes in. There is nothing left to
   choose here — the map always opens where you are (see applyHomeView) — but a
   GPS fix takes seconds and can be refused, and until then this beats an empty
   globe: your locator, else your country prefix, else all the areas. */
function homeView(){
  if(here) return {center:[here.lon, here.lat], zoom:12};
  {
    const ll = gridToLatLon(cfg.grid);
    if(ll) return {center:ll, zoom:10};
  }
  const call = (cfg.call || cfg.callp || '').toUpperCase().split('/')[0];
  for(const len of [3,2,1]){
    const key = call.slice(0,len);
    if(PREFIX_HOME[key]){
      const [lon,lat,z] = PREFIX_HOME[key];
      return {center:[lon,lat], zoom:z};
    }
  }
  const ll = gridToLatLon(cfg.grid);
  if(ll) return {center:ll, zoom:10};
  return null;   // unknown → dataBounds() decides
}

/* If we don't know the country, we show not the globe but exactly the area that
   we do have data for. Right now that is Belgium; if Diana goes European, this
   moves along by itself with nothing to adjust. */
function dataBounds(){
  // Points without a boundary have no bbox — they don't count here.
  const boxed = (index || []).filter(z => z.bbox);
  if(!boxed.length) return null;
  return boxed.reduce((a,z) => [Math.min(a[0],z.bbox[0]), Math.min(a[1],z.bbox[1]),
                                Math.max(a[2],z.bbox[2]), Math.max(a[3],z.bbox[3])],
                      [180,90,-180,-90]);
}

function applyHomeView(){
  // First put something sensible up, so that there is never an empty globe
  // sitting there waiting on a GPS fix.
  const v = homeView();
  if(v) map.jumpTo(v);
  else {
    const b = dataBounds();
    if(b) map.fitBounds([[b[0],b[1]],[b[2],b[3]]], {padding:30, duration:0});
  }
  // And then do the same as the ◎ button: determine the position, place the
  // marker, move there and check whether you are inside an area. Quietly,
  // because this was not asked for by a tap on the button: no "finding
  // location…" panel at startup, and a refused permission passes without a word.
  locate(true);
}


