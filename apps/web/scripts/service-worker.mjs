import { readFile, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
const shell = await readFile('public/offline.html');
const digest = createHash('sha256').update(shell).update(await readFile('out/manifest.webmanifest'));
for (const size of [192,512]) digest.update(await readFile(`out/icons/${size}.png`));
const hash = digest.digest('hex').slice(0,12);
await writeFile('out/sw.js', `
const CACHE = 'app-shell-${hash}';
const ASSETS = ['/offline.html','/icons/192.png','/icons/512.png'];
self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(ASSETS)));
});
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key.startsWith('app-shell-') && key !== CACHE).map(key => caches.delete(key)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if(event.request.method !== 'GET' || url.origin !== self.location.origin) return;
  if(ASSETS.includes(url.pathname) && !url.search) {
    event.respondWith(caches.match(event.request).then(cached => cached || fetch(event.request)));
  } else if(event.request.mode === 'navigate') {
    event.respondWith(fetch(event.request).catch(() => caches.match('/offline.html')));
  }
});
`);
