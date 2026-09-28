/*
 * Diana — service worker.
 *
 * The rule: anything that has to be fresh goes network-first with the cache as a
 * safety net; only what never changes within a version goes cache-first.
 *
 * The page itself and everything under data/ count as "has to be fresh". That is
 * a deliberate change: cache-first on those two meant that a visitor who had
 * already opened the app once kept seeing the old zones after a new dataset, until
 * the cache happened to expire. Offline still works, because the cache is still
 * the fallback — it is just no longer the first choice.
 *
 * Map tiles get a cache of their own with a rough LRU limit, so a downloaded area
 * stays put but storage does not grow without bound.
 *
 * Three caches, and only one of them belongs to a release. build/site.sh gives
 * VERSION a new value on every build, and every nightly data refresh is a build,
 * so a new service worker arrives nearly every night. On activation it deletes
 * the caches of the previous one. That is right for the app itself (SHELL), but
 * the map tiles and the data used to be in caches named after the version too,
 * so they went with it: download an area at home, let the app update itself
 * overnight, start it without signal in the field, and there was no basemap and
 * no boundaries. Tiles (TILES) and data (DATA) now live in caches whose names
 * never change; the data in them is kept fresh by dataVers() below, the tiles
 * are the ones you chose to download. The first worker with these names moves
 * whatever the old, versioned caches held into them before those are deleted.
 */
const VERSION   = 'diana-v6';
const SHELL     = `${VERSION}-shell`;
const TILES     = 'diana-tiles';      // never renamed: see above
const DATA      = 'diana-data';       // never renamed: see above
const TILE_MAX  = 3000;               // roughly 60 MB of vector tiles

// Which requests are data (dataVers(), cache DATA): everything under data/,
// subfolders included.
const DATA_RE = /\/data\/(?:[^/]+\/)*[^/]+\.(geojson|json)$/;

// Both the published layout (data next to index.html) and the repo layout (data
// one level up) are listed. Whatever does not exist is skipped: addAll() fails as
// a whole on a single 404, so we cache them one by one.
const SHELL_FILES = [
  './', './index.html', './css/app.css', './manifest.webmanifest',
  // The app itself, split per screen. Every one of these must be here: leave one
  // out and the app works online and is broken offline — which you find out in
  // the woods, with no signal. Keep in step with the <script> tags in index.html.
  './js/core.js', './js/radiogeo.js', './js/i18n-strings.js', './js/i18n.js', './js/map-data.js',
  './js/map.js', './js/spots.js', './js/install.js', './js/gestures.js',
  './js/nav.js', './js/settings.js', './js/privacy.js', './js/admin.js', './js/self-spot.js',
  './js/agenda.js', './js/session.js', './js/rules.js', './js/nearby.js', './js/nearinfo.js',
  './js/offline.js', './js/geo.js', './js/releases.js',
  './icon-192.png', './icon-512.png', './apple-touch-icon.png', './start.jpg', './logo.png',
  './vendor/maplibre-gl.js', './vendor/maplibre-gl.css',
  // CQ/ITU zones and ITU regions for Nearby > Info. Precached rather than
  // fetched on first use: the tab is meant for the field, where there may be
  // no signal the first time anyone opens it.
  './geo/radio-zones.json',
  // The files that are the same whatever country you carry. The per-country
  // files are NOT listed here on purpose: which countries you have is a choice,
  // and a shell that precached every one of them would drag Sweden down the
  // line to fetch two Belgian reserves. They are cached the moment they are
  // first fetched (every data response goes through dataVers() below, which
  // keeps a copy in DATA), so a country you have opened once is a country you
  // have offline, across releases too.
  './data/countries.json', './data/meta.json',
  './data/wwff-programs.json', './data/wwff-world.geojson',
  '../data/countries.json', '../data/meta.json',
  '../data/wwff-programs.json', '../data/wwff-world.geojson',
  // Belgium under the names it had before the manifest existed. A data set
  // older than this release still uses them; cache.add() skips whatever is not
  // there, so listing both layouts costs nothing.
  './data/onff.geojson', './data/onff-index.json',
  './data/onff-points.geojson', './data/onff-activity.json',
  '../data/onff.geojson', '../data/onff-index.json',
  '../data/onff-points.geojson', '../data/onff-activity.json',
];

self.addEventListener('install', e => {
  e.waitUntil((async () => {
    const cache = await caches.open(SHELL);
    const data = await caches.open(DATA);
    await Promise.all(SHELL_FILES.map(async u => {
      // The data files in this list go to DATA, and only when they are not
      // there yet: dataVers() keeps what is there fresh, so there is no need
      // to fetch the 9 MB world file again for every nightly release.
      if (DATA_RE.test(new URL(u, self.location).pathname)) {
        if (!(await data.match(u))) await addShellFile(data, u, true).catch(() => {});
        return;
      }
      await addShellFile(cache, u);
    }));
    // Deliberately no skipWaiting here. The new release stays ready and waiting
    // until the page asks for it itself (SKIP_WAITING), so that nobody gets an
    // unannounced reload in the middle of their work. Fresh data does not need
    // this: the page and everything under data/ come in network-first.
  })());
});

/* One file into a cache at installation. A file of the app itself that
   cannot be fetched (a dropped connection, one bar of signal, or missing
   from the release) is tried twice more, and if it still fails, the whole
   installation fails: the browser tries again at its next update check.
   Better than the old way, which skipped any failure alike: a release could
   install with half its scripts missing, and once it took over, the app
   would not start offline at all. Only data files may be missing (404): the
   list names them in both layouts, published and repository, and only one
   of the two exists. The caller ignores those failures. Every other entry in
   SHELL_FILES must exist in web/; test_sw_data.py checks that. */
async function addShellFile(cache, u, optional){
  for (let attempt = 0; ; attempt++) {
    try {
      const res = await fetch(u, {cache: 'no-cache'});
      if (res.status === 404 && optional) return;
      if (!res.ok) throw new Error(res.status + ' ' + u);
      await cache.put(u, res);
      return;
    } catch (err) {
      if (attempt >= 2) throw err;
      await new Promise(r => setTimeout(r, 1000 * (attempt + 1)));
    }
  }
}

self.addEventListener('activate', e => {
  e.waitUntil((async () => {
    const keep = [SHELL, TILES, DATA];
    const old = (await caches.keys()).filter(k => !keep.includes(k));
    // Before the old caches go: move the data and the downloaded tiles out of
    // them. Data first: it is a few dozen files and it is what the map cannot
    // do without; the tiles can run into thousands. Should this be cut short
    // (the phone kills a slow activation), nothing is lost: the old caches are
    // only deleted at the very end, dataVers() and the tile handler also look
    // in them, and the next release finishes the move.
    const tiles = await caches.open(TILES), data = await caches.open(DATA);
    for (const [target, wanted] of [
      [data,  u => u.origin === self.location.origin && DATA_RE.test(u.pathname)],
      [tiles, u => u.hostname === 'tiles.openfreemap.org'],
    ]) {
      for (const k of old) {
        try {
          const c = await caches.open(k);
          for (const req of await c.keys()) {
            if (!wanted(new URL(req.url))) continue;
            const res = await c.match(req);
            if (!res) continue;
            // Two copies of the same file: the newer one stays (by the date
            // the server sent it). The newest need not be the one already in
            // the new cache: that one may be from when this worker installed,
            // days before it took over.
            const have = await target.match(req);
            if (have && !isNewer(res, have)) continue;
            await target.put(req, res);
          }
        } catch {}
      }
    }
    await trim(tiles);
    await Promise.all(old.map(k => caches.delete(k)));
    await self.clients.claim();
  })());
});

/* Was response a fetched later than response b? By the Date header the server
   put on it; without one on either side, no. */
function isNewer(a, b){
  const ta = Date.parse(a.headers.get('date') || ''), tb = Date.parse(b.headers.get('date') || '');
  return !isNaN(ta) && (isNaN(tb) || ta > tb);
}

// Network first, cache as the safety net. With a short time limit: on a bad
// connection, waiting three seconds for fresh data is worse than showing the
// previous version — certainly with a map in your hand on a mountain.
async function versEerst(request, timeoutMs = 3500){
  const cache = await caches.open(SHELL);
  try{
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    const res = await fetch(request, {signal: controller.signal});
    clearTimeout(timer);
    if (res && res.ok) cache.put(request, res.clone()).catch(()=>{});
    return res;
  }catch{
    const hit = await cache.match(request) || await cache.match(new URL(request.url).pathname);
    if (hit) return hit;
    throw new Error('offline en niets in de cache');
  }
}

// Data files: fresh when that can be had quickly, the copy on the phone when
// not, and never a half-downloaded file. versEerst() above is not enough for
// these: its time limit only covers the wait for the server's first reply, so
// once a reply had started, a slow, stalled or broken download of a boundary
// file (Germany's is 13 MB) kept the map waiting, or empty, even with a good
// copy on the phone. Here:
//   - no copy on the phone yet: plain network, however slow, since there is
//     nothing better to show (a time limit would only turn slow into empty);
//   - a copy on the phone: the fresh file only if it arrives COMPLETE within
//     the time limit; otherwise the copy, straight away. The download carries
//     on in the background and is stored once complete, so the next start
//     has it. With no network at all the copy comes back at once.
// A file only goes into the cache after its last byte has arrived, and only
// when it differs from the copy (same ETag / Last-Modified: nothing to write).
async function dataVers(event, timeoutMs = 3500){
  const request = event.request;
  const cache = await caches.open(DATA);
  // DATA first; failing that, any cache: a move from the old, versioned caches
  // (see 'activate') that was cut short leaves files there that are still good.
  const inData = await cache.match(request) || await cache.match(new URL(request.url).pathname);
  const cached = inData || await caches.match(request);

  const network = (async () => {
    // A server that never answers at all is given up on after 30 s rather
    // than never; once it answers, the download may take as long as it takes.
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 30000);
    let res;
    try { res = await fetch(request, {signal: controller.signal}); }
    finally { clearTimeout(timer); }
    if (!res || !res.ok) throw new Error('status ' + (res && res.status));
    // Read once, in full (or this throws), then hand the same bytes to both
    // the page and the cache: one copy in memory, not three.
    const body = await res.blob();
    const headers = new Headers(res.headers);
    headers.delete('content-encoding');
    headers.delete('content-length');
    const make = () => new Response(body, {status: res.status, statusText: res.statusText, headers});
    const same = inData && ['etag', 'last-modified'].every(h =>
      inData.headers.get(h) && inData.headers.get(h) === res.headers.get(h));
    if (!same) {
      // Written in the background: the page does not wait for the disk.
      try { event.waitUntil(cache.put(request, make()).catch(() => {})); } catch {}
    }
    return make();
  })();

  if (!cached) return network;
  event.waitUntil(network.catch(() => {}));
  return Promise.race([
    network.catch(() => cached),
    new Promise(resolve => setTimeout(() => resolve(cached), timeoutMs)),
  ]);
}

self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if (event.request.method !== 'GET') return;

  // Live data: never serve it from the cache without saying so.
  if (url.hostname === 'spots.wwff.co' || url.hostname === 'docs.google.com') {
    event.respondWith(fetch(event.request).catch(() => caches.match(event.request)));
    return;
  }

  // Map tiles and fonts: cache-first with LRU.
  if (url.hostname === 'tiles.openfreemap.org') {
    event.respondWith(caches.open(TILES).then(async cache => {
      // TILES first; failing that, any cache (a move from an old, versioned
      // tile cache that was cut short, see 'activate').
      const hit = await cache.match(event.request) || await caches.match(event.request);
      if (hit) return hit;
      const res = await fetch(event.request);
      if (res.ok) { cache.put(event.request, res.clone()); trim(cache); }
      return res;
    }));
    return;
  }

  // The page itself: always the network first, otherwise someone opens the app
  // and is served the previous release with nothing to give that away.
  if (event.request.mode === 'navigate') {
    event.respondWith(versEerst(event.request).catch(() =>
      caches.match('./index.html').then(hit => hit || caches.match('./'))));
    return;
  }

  // The data layer: same again. This is exactly the case this service worker
  // used to get wrong — a new KMZ that never came through.
  //
  // Everything under data/, subfolders included. This used to match only the
  // files directly in data/ (countries.json, meta.json, the world files), so
  // the per-country files in data/zones/ (boundaries, points, QSO counts) and
  // the website links in data/sites/ fell through to the cache-first rule
  // below: once on the phone, they stayed as they were until the user tapped
  // "new version", however many nightly refreshes had passed. Now they are
  // asked for fresh on every start too, through dataVers() above: fresh if
  // it arrives complete within 3.5 s, otherwise the copy on the phone, with
  // the fresh one stored for next time.
  if (url.origin === location.origin && DATA_RE.test(url.pathname)) {
    event.respondWith(dataVers(event));
    return;
  }

  // The rest of the shell — vendor, icons, images — only changes along with
  // VERSION, so it may safely come from the cache.
  event.respondWith(caches.match(event.request).then(hit =>
    hit || fetch(event.request).then(res => {
      if (res.ok && url.origin === location.origin) {
        const copy = res.clone();
        caches.open(SHELL).then(c => c.put(event.request, copy));
      }
      return res;
    })
  ));
});

async function trim(cache){
  const keys = await cache.keys();
  if (keys.length <= TILE_MAX) return;
  for (const k of keys.slice(0, keys.length - TILE_MAX)) await cache.delete(k);
}

/* "Download this area for offline use": the page passes in a list of tile URLs. */
self.addEventListener('message', event => {
  if (event.data?.type === 'SKIP_WAITING') { self.skipWaiting(); return; }
  if (event.data?.type !== 'PREFETCH_TILES') return;
  event.waitUntil(caches.open(TILES).then(async cache => {
    let done = 0;
    for (const u of event.data.urls) {
      try { const r = await fetch(u); if (r.ok) await cache.put(u, r); } catch {}
      done++;
      if (done % 25 === 0) broadcast({type:'PREFETCH_PROGRESS', done, total:event.data.urls.length});
    }
    broadcast({type:'PREFETCH_DONE', done});
  }));
});
async function broadcast(msg){
  (await self.clients.matchAll()).forEach(c => c.postMessage(msg));
}
