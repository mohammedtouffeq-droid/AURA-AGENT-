const AURA_CACHE_NAME = 'aura-core-shell-v24';
const AURA_PHOTO_CACHE = 'aura-wallpaper-photos-v1';
const AURA_PRECACHE_URLS = [
  '/',
  '/index.html',
  '/aura_wallpapers.js',
  '/aura_offline_mobile.js',
  '/aura_work_ide.js',
  '/aura_cinematic_intro.js',
  '/aura_ultra_100.js',
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
          keys.filter((k) => k !== AURA_CACHE_NAME && k !== AURA_PHOTO_CACHE).map((k) => caches.delete(k))
        )
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);

  // Cache-First for curated 4K Unsplash wallpaper photos so viewed backdrops load 100% offline!
  if (url.hostname === 'images.unsplash.com') {
    event.respondWith(
      caches.open(AURA_PHOTO_CACHE).then(async (cache) => {
        const hit = await cache.match(req);
        if (hit) return hit;
        try {
          const net = await fetch(req);
          if (net && (net.status === 200 || net.type === 'opaque')) {
            cache.put(req, net.clone()).catch(() => {});
          }
          return net;
        } catch (_) {
          return new Response('', { status: 504 });
        }
      })
    );
    return;
  }

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
