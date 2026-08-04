/* SLN Meta Ads Analyzer – Service Worker (installability, geen offline-modus) */
const CACHE = 'sln-ads-v1';

const PRECACHE = [
  '/manifest.json',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE)
      .then(cache => Promise.all(PRECACHE.map(url => cache.add(url).catch(() => {}))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);

  // Alleen eigen statische bestanden cachen (icons, manifest) — cache-first.
  // Alle andere requests (data, HTML) gaan altijd via het netwerk: dit is
  // een live dashboard, geen content die zinvol offline te tonen is.
  if (url.origin === self.location.origin && url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(request).then(cached => {
        if (cached) return cached;
        return fetch(request).then(resp => {
          if (resp.ok) caches.open(CACHE).then(c => c.put(request, resp.clone()));
          return resp;
        });
      })
    );
  }
});
