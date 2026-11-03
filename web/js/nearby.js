/* ================================================================== *
 * Screen 7 — Nearby: what is within reach from where you are standing
 *
 * This replaces the activation heatmap. That screen read a published Google
 * Sheet with one tab per year and only went back seven years, so every
 * reference without a row in it — 741 of the 946 — was painted red and
 * labelled "never activated". Most of those have been activated many times;
 * they were simply never entered in that sheet. A number that is wrong in a
 * way you cannot see is worse than no number at all.
 *
 * The figures here come from data/onff-activity.json, built from the WWFF
 * directory along with every release: a QSO total and a last activation for
 * 926 of the 946 references. On the device, no third party, works offline.
 * Where the directory has nothing, this screen says so instead of guessing.
 * ================================================================== */
/* No loading of its own: map-data.js already fetches data/onff-activity.json
   at startup into `activity`, and activityOf() already drops the directory's
   one impossible date (year 1059). Two copies of that rule in two files is how
   they drift apart, so this screen asks that function and nothing else. */

/* 'dist' answers "what can I reach", the other two answer "what deserves a
   visit" — fewest QSOs first, longest untouched first. That is the planning
   question this screen exists for. */
let nearMetric = 'dist';

/* Everything within cfg.nearkm of you takes part — first the ring around you,
   then the ordering within it. Sorting by QSO count over all 946 references
   would otherwise put a neglected one 180 km away at the top, which is not
   what "nearby" means.

   The ceiling is what a phone can usefully show at once. Belgium is dense
   enough that it bites at the default already — 25 km around Brussels holds
   well over a hundred references — so when it does, the header says so
   ("100 / 217"). A list that quietly leaves things out is how the old heatmap
   went wrong; whatever is cut has to be visible. */
const NEAR_MAX_ROWS = 100;

/* How many are on screen right now. Grows by a pageful at a time, and resets
   the moment anything about the question changes — a different radius, a
   different ordering or a new position is a new list, not page three of the
   old one. */
let nearShown = NEAR_MAX_ROWS;

/* Distance and bearing from where you are to every reference we have a centre
   point for, nearest first, cut to NEAR_COUNT, and only then ordered by
   whatever the switch says. null means: we don't know where you are.

   Since 2.2.3 the list is not only the loaded country. Every other reference
   in the WWFF list (the blue dots of map.js) takes part too, so a Belgian at
   the Dutch border sees the Dutch references next door, and someone whose
   country has no boundaries in Diana (Spain, France ...) sees anything at
   all. Before, that last case had an empty list and the screen wrongly said
   it did not know where you were. For those references Diana has the QSO
   count (wwff-activity.json) but no date of the last activation: they say
   so, and sort last on "Last active", except a never-activated one (ATNO),
   which really is the longest untouched. `.loading` is set while the
   worldwide list is still on its way. */
function nearbyRows(){
  const p = myPos();
  if(!p) return null;
  const [lon, lat] = p;
  const km = cfg.nearkm || 25;
  const near = (index || [])
    .map(z => {
      // Only the handful of references without a boundary carry a lat/lon of
      // their own; everything with a polygon has a bbox instead. The middle of
      // that box is the same stand-in geo.js uses for "where is this area" —
      // good to a few hundred metres on a reserve, which is all a list of
      // distances needs. The distance to the boundary is what the map is for.
      const zlat = z.lat ?? (z.bbox ? (z.bbox[1] + z.bbox[3]) / 2 : null);
      const zlon = z.lon ?? (z.bbox ? (z.bbox[0] + z.bbox[2]) / 2 : null);
      if(zlat == null || zlon == null) return null;
      const a = activityOf(z.ref);
      return { ref: z.ref, name: z.name,
               d:    haversine(lat, lon, zlat, zlon),
               br:   bearing(lat, lon, zlat, zlon),
               qso:  a ? a.qso : 0,
               date: a ? a.date : null,
               known: !!a };
    })
    .filter(Boolean)
    .filter(r => r.d <= km * 1000);
  near.push(...nearbyWorldRows(lat, lon, km));
  near.sort((a,b) => a.d - b.d);
  const total = near.length;
  near.splice(nearShown);
  near.total = total;
  near.loading = !worldReady();

  // Unknown (null) after every number, so "fewest first" stays true for the ones we know.
  if(nearMetric === 'qso')     near.sort((a,b) =>
    ((a.qso == null) - (b.qso == null)) || (a.qso || 0) - (b.qso || 0) || a.d - b.d);
  if(nearMetric === 'recency') near.sort((a,b) =>
    // No date at all sorts as "longest ago": those are the ones worth a look.
    // A reference from another country has no date here at all: last, since
    // nothing is known about it, unless it was never activated.
    (recencyUnknown(a) - recencyUnknown(b)) ||
    String(a.date || '').localeCompare(String(b.date || '')) || a.d - b.d);
  return near;
}

let nearWaiting = false, nearActWaiting = false;   // one repaint per load, not one per render
const recencyUnknown = r => (r.world && r.qso !== 0) ? 1 : 0;

/* The worldwide list is in (map.js), and Field info asks for it itself if
   nothing else has yet: the "other WWFF areas" layer can be switched off. */
function worldReady(){
  if(typeof worldLoaded === 'undefined') return true;
  if(!worldLoaded && typeof loadWorldPoints === 'function'){
    const w = loadWorldPoints();
    if(w && !nearWaiting){
      nearWaiting = true;
      w.then(() => { nearWaiting = false; if($('viewNearby').classList.contains('on')) renderNearby(); });
    }
  }
  return worldLoaded;
}

/* The references around you that are not the loaded country's own, from the
   worldwide list. A cheap latitude/longitude box first, so that only the
   handful nearby get the real distance. */
function nearbyWorldRows(lat, lon, km){
  if(typeof worldPoints === 'undefined' || !worldPoints || !worldPoints.features.length) return [];
  const have = new Set((index || []).map(z => z.ref));
  const own = new Set(loadedPrograms);
  const dLat = km / 111 + 0.01;
  const dLon = km / (111 * Math.max(Math.cos(lat * Math.PI / 180), 0.01)) + 0.01;
  if(!worldActivityLoaded){
    const w = ensureWorldActivity();
    if(w && !nearActWaiting){
      nearActWaiting = true;
      w.then(() => { nearActWaiting = false; if($('viewNearby').classList.contains('on')) renderNearby(); });
    }
  }
  const out = [];
  for(const f of worldPoints.features){
    const c = f.geometry && f.geometry.coordinates;
    if(!c) continue;
    if(Math.abs(c[1] - lat) > dLat) continue;
    let dl = Math.abs(c[0] - lon); if(dl > 180) dl = 360 - dl;
    if(dl > dLon) continue;
    const ref = String(f.properties.ref || '').toUpperCase();
    if(!ref || have.has(ref) || own.has(refProgram(ref))) continue;
    const d = haversine(lat, lon, c[1], c[0]);
    if(d > km * 1000) continue;
    out.push({ ref, name: f.properties.name || '', d, br: bearing(lat, lon, c[1], c[0]),
               qso: qsoCountAnywhere(ref), date: null, known: false, world: true });
  }
  return out;
}

function lastActiveText(r){
  if(r.world) return r.qso === 0 ? t('spots.atno') : t('near.nodate');
  if(!r.known) return t('near.nodata');
  if(!r.date)  return t('near.nodate');
  const d = new Date(r.date);
  const shown = isNaN(d) ? r.date
    : d.toLocaleDateString(locale(), {year:'numeric', month:'short', day:'numeric'});
  return t('near.lastactive').replace('{date}', shown);
}

function renderNearby(){
  // The Info tab (nearinfo.js) shares this entry point, so every place that
  // already redraws Nearby (opening it, a new position, a language change)
  // redraws whichever tab is showing.
  if(typeof nearInfoActive === 'function' && nearInfoActive()){ renderNearInfo(); return; }
  if(typeof nearCondActive === 'function' && nearCondActive()){ showCond(); return; }
  const box = $('nearBox'), list = $('nearList');
  if(!box || !list) return;
  const rows = nearbyRows();

  // The card around the list only when there is a list: empty, it showed as
  // a bare white bar under the message.
  list.parentElement.hidden = !(rows && rows.length);

  if(rows === null){
    // No GPS fix and no locator either. Say what is missing and where to fix it
    // rather than showing an empty list that looks broken.
    box.innerHTML = `<p class="hint">${t('near.nopos')}</p>`;
    list.innerHTML = '';
    $('nearMore').hidden = true;
    return;
  }

  const km = (cfg.nearkm || 25) + ' km';
  const from = here ? t('near.viagps')
                    : t('near.vialocator').replace('{grid}', (cfg.grid||'').toUpperCase());
  if(!rows.length){
    // Possible at 10 km in an empty corner of the country: say so, rather than
    // leaving a header claiming nought references above an empty card.
    // Or, while the worldwide list is still loading, nothing yet.
    box.innerHTML = `<p class="hint">${rows.loading ? t('near.loading') : t('near.none').replace('{d}', km)}</p>`;
    list.innerHTML = '';
    $('nearMore').hidden = true;
    return;
  }
  // "100 / 217" when the ceiling bit, plain "61" when it did not.
  const count = rows.total > rows.length ? `${rows.length} / ${rows.total}` : String(rows.length);
  box.innerHTML = `
    <div class="srow"><span><b>${count}</b> ${t('near.within').replace('{d}', km)}</span>
      <span class="r">${from}</span></div>`;

  $('nearMore').hidden = rows.total <= rows.length;
  $('nearMore').textContent = t('near.more').replace('{n}', Math.min(NEAR_MAX_ROWS, rows.total - rows.length));

  list.innerHTML = rows.map(r => `
    <div class="spot" data-ref="${escH(r.ref)}">
      <span class="sig">◎</span>
      <span class="who"><div class="c">${escH(r.ref)} · ${escH(r.name)}</div>
        <div class="f">${(r.known || (r.world && r.qso > 0)) ? `${r.qso.toLocaleString(locale())} QSO · ` : ''}${lastActiveText(r)}</div></span>
      <span class="d"><b>${fmtKm(r.d)}</b>${Math.round(r.br)}°</span>
    </div>`).join('');
}

$('nearMetric').addEventListener('click', e => {
  const b = e.target.closest('.seg[data-metric]'); if(!b) return;
  nearMetric = b.dataset.metric;
  [...$('nearMetric').children].forEach(c => c.classList.toggle('on', c === b));
  nearShown = NEAR_MAX_ROWS;
  renderNearby();
});

/* Appends the next hundred rather than navigating to a page of them: on a
   phone, in a field, paging away from what you were reading and having to find
   your place again is worse than a longer scroll. */
$('nearMore').onclick = () => { nearShown += NEAR_MAX_ROWS; renderNearby(); };

/* Tapping a reference does what tapping it on the map does: opens the zone
   panel, with everything in it — including the button to go and spot yourself
   there. So the map has to come back up first. */
$('nearList').addEventListener('click', e => {
  const row = e.target.closest('.spot[data-ref]'); if(!row) return;
  document.querySelector('#nav button[data-view="map"]').click();
  select(row.dataset.ref);
});
