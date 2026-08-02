// LevelEnAI service worker
// v2: eksik bir precache girdisi (icons/icon.svg) yüzünden install adımı
// tamamen düşüyordu — addAll tek bir 404'te reddediyor. Artık her girdi
// ayrı ayrı ekleniyor ve hata kurulumu bozmuyor.
const CACHE_NAME = 'levelenai-v2';
// Statik dosyalar üretimde hash'li isimlerle servis edildiği için sabit bir
// precache listesi tutmuyoruz; varlıklar ilk istekte runtime cache'e yazılır.
const PRECACHE = [
  '/static/manifest.json',
];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => Promise.all(
        PRECACHE.map(url => cache.add(url).catch(() => null))
      ))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  if (e.request.method !== 'GET') return;
  const url = new URL(e.request.url);

  // Aynı origin dışına karışma
  if (url.origin !== self.location.origin) return;

  // Arama motoru dosyaları hiçbir zaman önbellekten servis edilmemeli
  if (url.pathname === '/robots.txt' || url.pathname === '/sitemap.xml') return;

  // Statik varlıklar: cache-first (hash'li isimler zaten sürümlenmiş durumda)
  if (url.pathname.startsWith('/static/')) {
    e.respondWith(
      caches.match(e.request).then(cached => cached || fetch(e.request).then(res => {
        if (res.ok) {
          const copy = res.clone();
          caches.open(CACHE_NAME).then(c => c.put(e.request, copy));
        }
        return res;
      }))
    );
    return;
  }

  // HTML ve diğer her şey: network-first, çevrimdışıysa önbellek
  e.respondWith(
    fetch(e.request).catch(() => caches.match(e.request))
  );
});
