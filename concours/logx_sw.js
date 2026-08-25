/* Service worker LogX AI — installabilité (PWA) + shell hors-ligne.
   Ne touche JAMAIS aux écritures (POST /log/add…) ni aux données live (/data,
   /config, /agent) : réseau normal. Ne met en cache que le shell statique. */
const CACHE = 'logx-v2';   // v2 : précache des libs vendorisées (Leaflet/Chart.js)
const SHELL = [
  '/logx_logbook.html', '/logx_logbook.js',
  '/logx_mobile.html',
  '/logx_statusbar.js', '/logx_i18n.js',
  '/logx_icon.svg', '/manifest.webmanifest',
  // Libs vendorisées localement (zone blanche) : précachées pour que la carte
  // (Leaflet) et les stats (Chart.js) tiennent au 1er chargement hors-ligne,
  // sans attendre une visite en ligne préalable. Cf. vendor/ + tests.
  '/vendor/leaflet/leaflet.min.css', '/vendor/leaflet/leaflet.min.js',
  '/vendor/chartjs/chart.umd.min.js',
];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE)
    .then(c => c.addAll(SHELL).catch(() => {}))
    .then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(caches.keys()
    .then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;                 // écritures : jamais interceptées
  const url = new URL(req.url);
  // Données live : laisser le réseau (pas de cache périmé sur le log/scores)
  if (/^\/(data|log|config|agent|proxy|coach|rig|rotor|cluster|activation|countries|departments)(\/|$)/.test(url.pathname)) return;
  // Shell statique : RÉSEAU D'ABORD (les mises à jour arrivent tout de suite),
  // le cache ne sert QUE de repli hors-ligne.
  e.respondWith(fetch(req).then(res => {
    if (res.ok && /\.(js|css|html|svg|webmanifest)$/.test(url.pathname)) {
      const copy = res.clone();
      caches.open(CACHE).then(c => c.put(req, copy));
    }
    return res;
  }).catch(() => caches.match(req).then(hit => hit || (req.mode === 'navigate' ? caches.match('/logx_logbook.html') : undefined))));
});
