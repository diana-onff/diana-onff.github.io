/* ================================================================== *
 * Nearby > Info: where you are standing, in radio terms.
 *
 * The second tab of the Nearby screen. Everything on it is worked out on
 * the device from data shipped with Diana: the clock, the position geo.js
 * already has (no second GPS request), the zone file in geo/, and the WWFF
 * references the map has already loaded. No third party is asked anything,
 * and it works offline.
 *
 * Each block on the tab is a card in INFO_CARDS: an id, a title, where its
 * numbers come from, and a render function that turns one shared context
 * into HTML. Adding a card later (the same information for a selected area,
 * say) means adding an entry, not touching the others; a card that throws
 * shows "not available" on its own and leaves the rest standing.
 * ================================================================== */
const RADIO_ZONES_URL = 'geo/radio-zones.json';
const INFO_MOVE_M = 100;          // recompute zones and nearest only past this

/* 'areas' is the list that was always there; 'info' is this tab. */
let nearTab = recall('near.tab') === 'info' ? 'info' : 'areas';
function nearInfoActive(){ return nearTab === 'info'; }

function syncNearTab(){
  [...$('nearTab').children].forEach(c => c.classList.toggle('on', c.dataset.neartab === nearTab));
  $('nearAreas').hidden = nearTab !== 'areas';
  $('nearInfoWrap').hidden = nearTab !== 'info';
}
$('nearTab').addEventListener('click', e => {
  const b = e.target.closest('.seg[data-neartab]'); if(!b) return;
  nearTab = b.dataset.neartab;
  remember('near.tab', nearTab);
  syncNearTab();
  renderNearby();                 // nearby.js hands over to renderNearInfo() on this tab
});
syncNearTab();

/* escHtml() comes from self-spot.js. */

/* ---------- the zone file ----------
   Loaded the first time the tab is shown, then kept (and cached by the
   service worker for offline use). A failed load is retried at most every
   30 seconds, not on every position update. */
let radioZones = null, radioZonesLoading = null, radioZonesFailedAt = 0;
function ensureRadioZones(){
  if(radioZones || radioZonesLoading) return;
  if(radioZonesFailedAt && Date.now() - radioZonesFailedAt < 30000) return;
  radioZonesLoading = fetch(RADIO_ZONES_URL)
    .then(r => { if(!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
    .then(d => { radioZones = d; radioZonesFailedAt = 0; })
    .catch(err => { console.warn('radio-zones:', err); radioZonesFailedAt = Date.now(); })
    .finally(() => {
      radioZonesLoading = null;
      if(infoVisible()) renderNearInfo();
      // The map's own zone panel (map.js) shows the same four numbers for
      // whichever area is selected, and can be open before this tab ever
      // was; give it a chance to fill in its CQ/ITU/region tile too.
      if(typeof refreshSelectedRadioFacts === 'function') refreshSelectedRadioFacts();
    });
}

/* ---------- the WWFF references to search ----------
   The worldwide list when the map has it (it does by default), otherwise the
   references of the country on board. The grid is built once per list. */
let wwffGrid = null, wwffGridOf = null;
function wwffSource(){
  if(typeof worldPoints !== 'undefined' && worldPoints.features.length) return worldPoints;
  if(typeof index !== 'undefined' && index && index.length) return index;
  return null;
}
function wwffGridFor(src){
  if(wwffGridOf === src) return wwffGrid;
  const pts = src === worldPoints
    ? src.features.map(f => ({ref: f.properties.ref, name: f.properties.name,
                              lon: f.geometry.coordinates[0], lat: f.geometry.coordinates[1]}))
    : src.map(z => ({ref: z.ref, name: z.name,
                     lat: z.lat ?? (z.bbox ? (z.bbox[1] + z.bbox[3]) / 2 : NaN),
                     lon: z.lon ?? (z.bbox ? (z.bbox[0] + z.bbox[2]) / 2 : NaN)}));
  wwffGrid = gridIndex(pts);
  wwffGridOf = src;
  return wwffGrid;
}

/* ---------- where "here" is ----------
   The GPS position when there is one, with the margin the marker is showing
   right now; otherwise the middle of the locator from Settings, said out
   loud, because a six-character square is several kilometres across. */
function infoPosition(){
  if(here){
    const acc = (typeof ringFix !== 'undefined' && ringFix && ringFix.acc != null) ? ringFix.acc : null;
    return {lat: here.lat, lon: here.lon, acc, from: 'gps'};
  }
  const ll = gridToLatLon(cfg.grid);
  if(ll) return {lat: ll[1], lon: ll[0], acc: null, from: 'grid', grid: (cfg.grid || '').toUpperCase()};
  return null;
}

/* The expensive part (zones with their boundary check, nearest references),
   redone only when it could have changed: moved more than INFO_MOVE_M, the
   margin changed a lot, or the zone file / reference list arrived since. */
let infoCache = null;
function infoResults(pos){
  const src = wwffSource();
  const c = infoCache;
  const fresh = c && c.zonesReady === !!radioZones && c.src === src
    && haversine(c.lat, c.lon, pos.lat, pos.lon) <= INFO_MOVE_M
    && Math.abs((c.acc || 0) - (pos.acc || 0)) <= Math.max(25, (c.acc || 0) * 0.5);
  if(fresh) return c;
  const out = {lat: pos.lat, lon: pos.lon, acc: pos.acc, src, zonesReady: !!radioZones, zones: null, wwff: null};
  if(radioZones){
    out.zones = {
      cq:     zoneAround(radioZones.cq,     pos.lat, pos.lon, pos.acc),
      itu:    zoneAround(radioZones.itu,    pos.lat, pos.lon, pos.acc),
      region: zoneAround(radioZones.region, pos.lat, pos.lon, pos.acc),
    };
  }
  if(src) out.wwff = nearestIn(wwffGridFor(src), pos.lat, pos.lon, 3);
  return infoCache = out;
}

/* ---------- the cards ---------- */
function utcOffsetText(d){
  const m = -d.getTimezoneOffset();
  if(!m) return 'UTC';
  const a = Math.abs(m);
  return `UTC${m > 0 ? '+' : '−'}${Math.floor(a / 60)}${a % 60 ? ':' + String(a % 60).padStart(2, '0') : ''}`;
}
function clockValues(now){
  let tz = '';
  try{ tz = Intl.DateTimeFormat().resolvedOptions().timeZone || ''; }catch{}
  return {
    utc:   now.toISOString().slice(11, 19),
    utcd:  now.toLocaleDateString(locale(), {timeZone: 'UTC', day: 'numeric', month: 'short', year: 'numeric'}),
    local: now.toLocaleTimeString(locale(), {hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false}),
    tz:    [...new Set([tz.replace(/_/g, ' '), utcOffsetText(now)].filter(Boolean))].join(' · '),
  };
}
function cardTime(){
  const v = clockValues(new Date());
  return `<div class="infotiles">
    <div class="fact"><div class="k">UTC</div><div class="v big" id="infoUtc">${v.utc}</div><div class="s" id="infoUtcDate">${escHtml(v.utcd)}</div></div>
    <div class="fact"><div class="k">${t('info.local')}</div><div class="v big" id="infoLocal">${escHtml(v.local)}</div><div class="s" id="infoTz">${escHtml(v.tz)}</div></div>
  </div>`;
}

function cardPlace(ctx){
  const p = ctx.pos;
  const loc6 = p.from === 'grid' && p.grid ? p.grid.slice(0, 6) : maidenhead(p.lat, p.lon, 3);
  const loc8 = p.from === 'grid' ? '' : maidenhead(p.lat, p.lon, 4);
  const acc = p.from === 'gps'
    ? `<div class="v big">${p.acc != null ? '±' + escHtml(fmtKm(p.acc)) : '…'}</div><div class="s">GPS</div>`
    : `<div class="v">${t('info.unknown')}</div><div class="s">${t('info.fromgrid')}</div>`;
  return `<div class="infotiles">
    <div class="fact"><div class="k">Locator</div><div class="v big" id="infoLoc">${loc6}</div><div class="s">${loc8}</div></div>
    <div class="fact"><div class="k">${t('info.accuracy')}</div>${acc}</div>
  </div>
  <p class="infocoord">${fmtLatLon(p.lat, p.lon)}<br><span>${fmtDMS(p.lat, p.lon)}</span></p>`;
}

function zoneTile(label, z, id){
  const v = z.here.length ? z.here.join(' / ') : t('info.unknown');
  const also = z.also.length ? `<div class="s edge">${t('info.edge').replace('{z}', z.also.join(', '))}</div>` : '';
  return `<div class="fact"><div class="k">${label}</div><div class="v big" id="${id}">${v}</div>${also}</div>`;
}
function cardZones(ctx){
  const r = ctx.results;
  if(!r.zones){
    return `<p class="hint" style="margin:0">${t(radioZonesFailedAt ? 'info.zonesfail' : 'info.zonesloading')}</p>`;
  }
  const z = r.zones;
  const edge = [z.cq, z.itu, z.region].some(x => x.also.length || x.here.length > 1);
  const d = fmtKm(Math.max(ZONE_EDGE_M, ctx.pos.acc || 0));
  return `<div class="infotiles three">
    ${zoneTile(t('info.cq'), z.cq, 'infoCq')}
    ${zoneTile(t('info.itu'), z.itu, 'infoItu')}
    ${zoneTile(t('info.region'), z.region, 'infoRegion')}
  </div>${edge ? `<p class="infonote">${t('info.edgenote').replace('{d}', escHtml(d))}</p>` : ''}`;
}

function cardWwff(ctx){
  const list = ctx.results.wwff;
  if(!list || !list.length) return `<p class="hint" style="margin:0">${t('info.wwffnone')}</p>`;
  return `<div id="infoWwff" style="margin:0 -4px">${list.map(r => `
    <div class="spot" data-ref="${escHtml(r.ref)}" data-lat="${r.lat}" data-lon="${r.lon}" data-name="${escHtml(r.name || '')}">
      <span class="sig">◎</span>
      <span class="who"><div class="c">${escHtml(r.ref)}</div><div class="f">${escHtml(r.name || '')}</div></span>
      <span class="d"><b>${fmtKm(r.d)}</b>${Math.round(bearing(ctx.pos.lat, ctx.pos.lon, r.lat, r.lon))}°</span>
    </div>`).join('')}</div>`;
}

const INFO_CARDS = [
  {id: 'time',  title: 'info.time',  render: cardTime},
  {id: 'place', title: 'info.place', render: cardPlace, needsPos: true},
  {id: 'zones', title: 'info.zones', render: cardZones, needsPos: true, src: 'info.src.zones'},
  {id: 'wwff',  title: 'info.wwff',  render: cardWwff,  needsPos: true, src: 'info.src.wwff'},
];

function infoCardHtml(card, ctx){
  let body;
  if(card.needsPos && !ctx.pos){
    body = `<p class="hint" style="margin:0">${t('near.nopos')}</p>`;
  } else {
    try{ body = card.render(ctx); }
    catch(err){
      console.warn('info ' + card.id + ':', err);
      body = `<p class="hint" style="margin:0">${t('info.unavailable')}</p>`;
    }
  }
  return `<div class="card infocard" data-card="${card.id}">
    <h4 class="ch">${t(card.title)}</h4>${body}${card.src ? `<p class="hint infosrc">${t(card.src)}</p>` : ''}
  </div>`;
}

function infoVisible(){
  return nearInfoActive() && $('viewNearby').classList.contains('on');
}

function renderNearInfo(){
  const box = $('nearInfo');
  if(!box) return;
  ensureRadioZones();
  const pos = infoPosition();
  const ctx = {pos, results: pos ? infoResults(pos) : null};
  box.innerHTML = INFO_CARDS.map(c => infoCardHtml(c, ctx)).join('');
  startInfoClock();
}

/* ---------- the clock: ticks only while the tab is on screen ---------- */
let infoClock = null;
function startInfoClock(){
  if(!infoClock) infoClock = setInterval(tickInfoClock, 1000);
}
function tickInfoClock(){
  if(!infoVisible()){ clearInterval(infoClock); infoClock = null; return; }
  const v = clockValues(new Date());
  const set = (id, s) => { const el = $(id); if(el && el.textContent !== s) el.textContent = s; };
  set('infoUtc', v.utc); set('infoUtcDate', v.utcd); set('infoLocal', v.local); set('infoTz', v.tz);
}

/* ---------- a nearest reference, on the map ----------
   One from the country on board opens its panel, exactly like tapping it on
   the map. One from elsewhere has no panel, so the map goes there and shows
   the same small label a tap on a worldwide point shows. */
$('nearInfo').addEventListener('click', e => {
  const row = e.target.closest('.spot[data-ref]'); if(!row) return;
  const ref = row.dataset.ref;
  document.querySelector('#nav button[data-view="map"]').click();
  const own = (zones && zones.features.some(f => f.properties.ref === ref)) || noPolyByRef.has(ref);
  if(own){ select(ref); return; }
  const lon = +row.dataset.lon, lat = +row.dataset.lat;
  map.easeTo({center: [lon, lat], zoom: Math.max(map.getZoom(), 11)});
  new maplibregl.Popup({closeButton: true, maxWidth: '240px'})
    .setLngLat([lon, lat])
    .setHTML(`<b>${escHtml(ref)}</b><br>${escHtml(row.dataset.name || '')}`)
    .addTo(map);
});
