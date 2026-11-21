const AURA_CACHE_NAME = 'aura-core-shell-v20';
const AURA_PRECACHE_URLS = [
  '/',
  '/index.html',
  '/aura_wallpapers.js',
  '/aura_offline_mobile.js',
  '/manifest.json',
  '/api/pwa/icon.svg',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(AURA_CACHE_NAME)
      .then((cache) => cache.addAll(AURA_PRECACHE_URLS).catch(() => {}))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) =>
        Promise.all(
          keys.filter((k) => k !== AURA_CACHE_NAME).map((k) => caches.delete(k))
        )
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith('/api/') && url.pathname !== '/api/pwa/icon.svg') {
    return;
  }
  if (url.pathname.startsWith('/media/')) {
    return;
  }

  // Network-First with Instant Cache Fallback so Mobile PWA loads cleanly in Airplane Mode
  event.respondWith(
    fetch(req)
      .then((networkRes) => {
        if (networkRes && networkRes.status === 200) {
          const clone = networkRes.clone();
          caches.open(AURA_CACHE_NAME).then((cache) => cache.put(req, clone)).catch(() => {});
        }
        return networkRes;
      })
      .catch(async () => {
        const cached = await caches.match(req);
        if (cached) return cached;
        if (req.mode === 'navigate') {
          return (await caches.match('/')) || (await caches.match('/index.html'));
        }
        return new Response('Offline resource unavailable', { status: 503 });
      })
  );
});
