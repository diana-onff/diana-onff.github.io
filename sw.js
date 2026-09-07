/*
 * Diana — service worker.
 *
 * Regel: alles wat vers moet zijn komt network-first met de cache als vangnet;
 * alleen wat nooit verandert binnen een versie komt cache-first.
 *
 * De pagina zelf en alles onder data/ vallen onder "moet vers zijn". Dat is een
 * bewuste wijziging: cache-first op die twee betekende dat een bezoeker die de
 * app al eens geopend had, na een nieuwe dataset gewoon de oude gebieden bleef
 * zien tot de cache toevallig verliep. Offline blijft werken, want de cache is
 * nog altijd de terugval — alleen niet langer de eerste keuze.
 *
 * Kaarttegels krijgen een eigen cache met een ruwe LRU-limiet, zodat een
 * gedownload gebied blijft staan maar de opslag niet ongelimiteerd groeit.
 */
const VERSION   = 'diana-8a9f885';
const SHELL     = `${VERSION}-shell`;
const TILES     = `${VERSION}-tiles`;
const TILE_MAX  = 3000;               // ruwweg 60 MB aan vectortegels

// Zowel de gepubliceerde indeling (data naast index.html) als de repo-indeling
// (data een niveau hoger) staat erin. Wat niet bestaat, wordt overgeslagen:
// addAll() faalt in zijn geheel bij één 404, dus we cachen stuk voor stuk.
const SHELL_FILES = [
  './', './index.html', './manifest.webmanifest',
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
      cache.add(u).catch(() => {})     // ontbrekende indeling: gewoon overslaan
    ));
    // Bewust géén skipWaiting hier. De nieuwe uitgave blijft klaarstaan tot de
    // pagina er zelf om vraagt (SKIP_WAITING), zodat niemand midden in het werk
    // een onaangekondigde herlaadbeurt krijgt. Verse data heeft dit niet nodig:
    // de pagina en alles onder data/ komen network-first binnen.
  })());
});

self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys =>
    Promise.all(keys.filter(k => !k.startsWith(VERSION)).map(k => caches.delete(k)))
  ).then(()=>self.clients.claim()));
});

// Netwerk eerst, cache als vangnet. Met een korte tijdslimiet: op een slechte
// verbinding is drie seconden wachten op verse data erger dan de vorige versie
// tonen, zeker met een kaart in de hand op een berg.
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

  // Live data: nooit uit de cache serveren zonder het te melden.
  if (url.hostname === 'spots.wwff.co' || url.hostname === 'docs.google.com') {
    event.respondWith(fetch(event.request).catch(() => caches.match(event.request)));
    return;
  }

  // Kaarttegels en lettertypen: cache-first met LRU.
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

  // De pagina zelf: altijd eerst het netwerk, anders opent iemand de app en
  // krijgt hij de vorige uitgave voorgeschoteld zonder dat iets dat verraadt.
  if (event.request.mode === 'navigate') {
    event.respondWith(versEerst(event.request).catch(() =>
      caches.match('./index.html').then(hit => hit || caches.match('./'))));
    return;
  }

  // De datalaag: idem. Dit is precies het geval waarvoor deze service worker
  // eerder de verkeerde keuze maakte — een nieuwe KMZ die nooit doorkwam.
  if (url.origin === location.origin && /\/data\/[^/]+\.(geojson|json)$/.test(url.pathname)) {
    event.respondWith(versEerst(event.request));
    return;
  }

  // De rest van de shell — vendor, iconen, afbeeldingen — verandert alleen mee
  // met VERSION, dus die mag gerust uit de cache komen.
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

/* "Gebied downloaden voor offline": de pagina stuurt een lijst tegel-URL's door. */
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
