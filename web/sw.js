// Service worker: deixa o app funcionando offline.
// Ao mudar qualquer arquivo do app, aumente a VERSAO para os celulares baixarem a nova versão.
const VERSAO = 'crescidoro-v1';
const ARQUIVOS = [
  './', 'index.html', 'style.css', 'manifest.webmanifest',
  'js/app.js', 'js/core.js', 'js/chart.js', 'js/heatmap.js',
  'sucesso.mp3', 'icon-192.png', 'icon-512.png', 'icon-maskable-512.png',
];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(VERSAO).then((c) => c.addAll(ARQUIVOS)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((ks) => Promise.all(ks.filter((k) => k !== VERSAO).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

// rede primeiro (pega atualizações), cache se estiver offline
self.addEventListener('fetch', (e) => {
  if (e.request.method !== 'GET' || new URL(e.request.url).origin !== location.origin) return;
  e.respondWith(
    fetch(e.request)
      .then((r) => {
        if (r.ok && r.status === 200) {
          const copia = r.clone();
          caches.open(VERSAO).then((c) => c.put(e.request, copia));
        }
        return r;
      })
      .catch(() => caches.match(e.request, { ignoreSearch: true })),
  );
});

self.addEventListener('notificationclick', (e) => {
  e.notification.close();
  e.waitUntil(self.clients.matchAll({ type: 'window' }).then((cs) => (cs[0] ? cs[0].focus() : self.clients.openWindow('./'))));
});
