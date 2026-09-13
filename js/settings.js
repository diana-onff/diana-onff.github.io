/* ================================================================== *
 * Settings — everything in the localStorage of this device
 * ================================================================== */
const GRID_RE = /^[A-R]{2}[0-9]{2}([A-X]{2})?$/i;

/* The five words under the remark field on the spot screen. These are only
   what Diana starts with — they are yours to overwrite in Settings, and an
   empty field simply gives no button. */
const CHIP_DEFAULTS = ['5W', 'QRP', 'EFHW', 'QSY soon', 'Vertical'];

/* The radii the Nearby screen offers. A fixed set rather than a free number:
   four taps beat a number pad in the field, and it keeps the list from being
   asked to draw half of Belgium. */
const NEAR_KM = [10, 25, 50, 100];

/* Stored as one JSON list rather than five separate keys, so that a field you
   deliberately cleared stays cleared: with five keys an empty one is
   indistinguishable from one that was never set, and the default would come
   creeping back on the next start. */
function readChips(){
  try{
    const raw = recall('chips');
    if(raw){
      const a = JSON.parse(raw);
      if(Array.isArray(a)) return CHIP_DEFAULTS.map((d,i) => typeof a[i] === 'string' ? a[i] : d);
    }
  }catch{}
  return CHIP_DEFAULTS.slice();
}

const cfg = {
  call:  recall('call'),
  callp: recall('callp'),
  grid:  recall('grid'),
  // Which band list the announce screen offers: 'full' is every amateur band
  // from 160m to 23cm, 'short' only the six that carry nearly every ONFF
  // activation. Neither is more correct than the other — the long one is
  // complete, the short one fits on a phone without scrolling.
  bands: recall('bands') === 'short' ? 'short' : 'full',
  chips: readChips(),
  // How far around you the Nearby screen looks, in kilometres. 25 is about an
  // hour on a bicycle and a comfortable afternoon by car — far enough to plan
  // with, close enough that the list stays a list.
  nearkm: NEAR_KM.includes(parseInt(recall('nearkm'), 10)) ? parseInt(recall('nearkm'), 10) : 25,
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
  remember('bands', cfg.bands);
  remember('nearkm', cfg.nearkm);
  remember('chips', JSON.stringify(cfg.chips));
  remember('lang',  langPref);      // 'auto' or a language code — not the resolved language
}

function loadSettingsUI(){
  $('setCall').value  = cfg.call;
  $('setCallP').value = cfg.callp;
  $('setGrid').value  = cfg.grid;
  cfg.chips.forEach((v,i) => { $('setChip'+(i+1)).value = v; });
  [...$('setBands').children].forEach(b => b.classList.toggle('on', b.dataset.bands === cfg.bands));
  [...$('setNearKm').children].forEach(b => b.classList.toggle('on', +b.dataset.km === cfg.nearkm));
  syncSpotFilterUI();
  syncWorldFilterUI();
  [...$('setLang').children].forEach(b => b.classList.toggle('on', b.dataset.lang === langPref));
  checkGrid();
}

/* Both of these live in later files (agenda.js, self-spot.js) and are only ever
   reached from a click — by then everything has loaded. Calling them from the
   top level of this file would not work; see docs/DEVELOPER.md. */
$('setBands').addEventListener('click', e => {
  const b = e.target.closest('.seg[data-bands]'); if(!b) return;
  cfg.bands = b.dataset.bands;
  [...$('setBands').children].forEach(c => c.classList.toggle('on', c === b));
  saveSettings();
  fillBandOptions();
});

$('setNearKm').addEventListener('click', e => {
  const b = e.target.closest('.seg[data-km]'); if(!b) return;
  cfg.nearkm = +b.dataset.km;
  [...$('setNearKm').children].forEach(c => c.classList.toggle('on', c === b));
  saveSettings();
  nearShown = NEAR_MAX_ROWS;
  renderNearby();
});

[1,2,3,4,5].forEach(i => $('setChip'+i).addEventListener('input', () => {
  cfg.chips[i-1] = $('setChip'+i).value.trim();
  saveSettings();
  renderChips();
}));

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
/* Same trap as the ◎ button had: a locator square is only a few kilometres
   across, and a first fix off a wifi network can be further out than that. So
   this waits for a real one too — bestFix lives in geo.js, which loads later,
   but this only ever runs from a click. */
$('setGridGps').onclick = () => {
  if(!navigator.geolocation) return;
  $('setGridGps').disabled = true;
  const done = () => { $('setGridGps').disabled = false; };
  bestFix(pos => {
    cfg.grid = locator(pos.coords.latitude, pos.coords.longitude);
    $('setGrid').value = cfg.grid; checkGrid(); saveSettings(); done();
  }, null, done);
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

/* Callsign prefix → WWFF programme. Diana uses this for one thing: which
   country the spots filter offers first, so a Dutch operator does not have to
   tap past Belgium every time. One tap changes it, so a guess that misses
   costs nothing — which is why prefixes whose programme is genuinely
   ambiguous are left out rather than guessed at. Every code here was checked
   against data/wwff-programs.json (a test keeps it that way): WWFF lists
   England as GXFF and carries no separate Scottish or Welsh programme, so
   G/M/2E all land there. */
const PREFIX_PROGRAM = {
  ON:'ONFF', OO:'ONFF', OP:'ONFF', OQ:'ONFF', OR:'ONFF', OS:'ONFF', OT:'ONFF',
  PA:'PAFF', PB:'PAFF', PC:'PAFF', PD:'PAFF', PE:'PAFF', PF:'PAFF', PG:'PAFF',
  PH:'PAFF', PI:'PAFF',
  DA:'DLFF', DB:'DLFF', DC:'DLFF', DD:'DLFF', DE:'DLFF', DF:'DLFF', DG:'DLFF',
  DH:'DLFF', DJ:'DLFF', DK:'DLFF', DL:'DLFF', DM:'DLFF', DN:'DLFF', DO:'DLFF',
  DP:'DLFF', DQ:'DLFF', DR:'DLFF',
  F:'FFF', TM:'FFF', TK:'FFF',
  G:'GXFF', M:'GXFF', '2E':'GXFF',
  OZ:'OZFF', OU:'OZFF', '5P':'OZFF', '5Q':'OZFF',
  I:'IFF', IK:'IFF', IZ:'IFF', IW:'IFF', IU:'IFF',
  EA:'EAFF', EB:'EAFF', EC:'EAFF', ED:'EAFF',
  CT:'CTFF', CR:'CTFF',
  SP:'SPFF', SN:'SPFF', SO:'SPFF', SQ:'SPFF', '3Z':'SPFF',
  OK:'OKFF', OL:'OKFF', OM:'OMFF',
  HA:'HAFF', HG:'HAFF',
  SM:'SMFF', SA:'SMFF', SB:'SMFF', SC:'SMFF', SD:'SMFF', SE:'SMFF', SF:'SMFF',
  SG:'SMFF', SH:'SMFF', SI:'SMFF', SJ:'SMFF', SK:'SMFF', SL:'SMFF',
  LA:'LAFF', LB:'LAFF', LG:'LAFF', LN:'LAFF',
  OH:'OHFF', OF:'OHFF', OG:'OHFF',
  OE:'OEFF', HB:'HBFF', LX:'LXFF',
  EI:'EIFF', EJ:'EIFF',
  YO:'YOFF', YP:'YOFF', YQ:'YOFF', YR:'YOFF',
  LZ:'LZFF', S5:'S5FF', '9A':'9AFF',
  YU:'YUFF', YT:'YUFF',
  SV:'SVFF', SW:'SVFF', SX:'SVFF', SY:'SVFF', SZ:'SVFF',
  TA:'TAFF', TB:'TAFF', TC:'TAFF',
  ES:'ESFF', YL:'YLFF', LY:'LYFF', ER:'ERFF',
  UR:'URFF', UT:'URFF', UU:'URFF', UV:'URFF', UW:'URFF', UX:'URFF', UY:'URFF',
  UZ:'URFF', EM:'URFF', EO:'URFF',
  EW:'EWFF', EU:'EWFF', EV:'EWFF',
  Z3:'Z3FF', E7:'E7FF', ZA:'ZAFF', '4O':'4OFF',
  R:'RFF', UA:'RFF', UB:'RFF', UC:'RFF', UD:'RFF', UE:'RFF', UF:'RFF', UG:'RFF',
  UH:'RFF', UI:'RFF',
  K:'KFF', W:'KFF', N:'KFF',
  VE:'VEFF', VA:'VEFF', VO:'VEFF', VY:'VEFF',
  VK:'VKFF', ZL:'ZLFF',
  JA:'JAFF', JE:'JAFF', JF:'JAFF', JG:'JAFF', JH:'JAFF', JI:'JAFF', JJ:'JAFF',
  JK:'JAFF', JL:'JAFF', JM:'JAFF', JN:'JAFF', JO:'JAFF', JP:'JAFF', JQ:'JAFF',
  JR:'JAFF', JS:'JAFF',
};

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


