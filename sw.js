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
 */
const VERSION   = 'diana-ed6bb09';
const SHELL     = `${VERSION}-shell`;
const TILES     = `${VERSION}-tiles`;
const TILE_MAX  = 3000;               // roughly 60 MB of vector tiles

// Both the published layout (data next to index.html) and the repo layout (data
// one level up) are listed. Whatever does not exist is skipped: addAll() fails as
// a whole on a single 404, so we cache them one by one.
const SHELL_FILES = [
  './', './index.html', './app.css', './app.js', './manifest.webmanifest',
  './icon-192.png', './icon-512.png', './apple-touch-icon.png', './start.jpg', './logo.png',
  './vendor/maplibre-gl.js', './vendor/maplibre-gl.css',
  './data/onff.geojson', './data/onff-index.json', './data/meta.json',
  './data/onff-points.geojson', './data/onff-activity.json', './data/wwff-programs.json',
  './data/wwff-world.geojson',
  '../data/onff.geojson', '../data/onff-index.json', '../data/meta.json',
  '../data/onff-points.geojson', '../data/onff-activity.json', '../data/wwff-programs.json',
  '../data/wwff-world.geojson',
];

self.addEventListener('install', e => {
  e.waitUntil((async () => {
    const cache = await caches.open(SHELL);
    await Promise.all(SHELL_FILES.map(u =>
      cache.add(u).catch(() => {})     // layout not present: just skip it
    ));
    // Deliberately no skipWaiting here. The new release stays ready and waiting
    // until the page asks for it itself (SKIP_WAITING), so that nobody gets an
    // unannounced reload in the middle of their work. Fresh data does not need
    // this: the page and everything under data/ come in network-first.
  })());
});

self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys =>
    Promise.all(keys.filter(k => !k.startsWith(VERSION)).map(k => caches.delete(k)))
  ).then(()=>self.clients.claim()));
});

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
      const hit = await cache.match(event.request);
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
  if (url.origin === location.origin && /\/data\/[^/]+\.(geojson|json)$/.test(url.pathname)) {
    event.respondWith(versEerst(event.request));
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
