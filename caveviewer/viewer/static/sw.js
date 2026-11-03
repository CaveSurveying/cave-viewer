// The page, offline: a service worker that keeps everything the page needs,
// so once it has been opened with a signal it works underground. Written by
// caveviewer (offline.py), which fills in VERSION and FILES; a new build is a new
// version, which replaces the saved copy the next time the page is opened.
const VERSION = '__VERSION__';
const FILES = __FILES__;
const APP = `__ID__-${VERSION}`;
const TILES = '__ID__-tiles';      // satellite imagery, kept as it's seen
const DRAWN = '__ID__-drawn';      // the drawn survey, where there is one: kept as it's seen (the page asks for all of it)

self.addEventListener('install', e => {
  e.waitUntil((async () => {
    const c = await caches.open(APP);
    await c.addAll(FILES);
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', e => {
  e.waitUntil((async () => {
    for (const k of await caches.keys()) if (k.startsWith('__ID__-') && ![APP, TILES, DRAWN].includes(k)) await caches.delete(k);
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET') return;
  // imagery: the saved tile if there is one, else fetch and save it
  if (url.hostname === 'server.arcgisonline.com') {
    e.respondWith((async () => {
      const c = await caches.open(TILES);
      const hit = await c.match(e.request);
      if (hit) return hit;
      const r = await fetch(e.request);
      if (r.ok) c.put(e.request, r.clone());
      return r;
    })());
    return;
  }
  if (url.origin !== location.origin) return;
  // the drawn survey: its meta.json from the network if there is one (a new
  // build of it is a fresh start), the tiles saved, else fetched and saved
  const at = url.pathname.indexOf('/drawn/');
  if (at >= 0) {
    e.respondWith((async () => {
      const c = await caches.open(DRAWN);
      if (url.pathname.endsWith('/drawn/meta.json')) {
        let r;
        try { r = await fetch(e.request, { cache: 'no-cache' }); } catch { return (await c.match(e.request, { ignoreSearch: true })) || Response.error(); }
        if (!r.ok) return r;
        const old = await c.match(e.request, { ignoreSearch: true }), text = await r.clone().text();
        if (!old || await old.text() !== text) {
          await caches.delete(DRAWN);
          await (await caches.open(DRAWN)).put(e.request, new Response(text, { headers: { 'Content-Type': 'application/json' } }));
        }
        return r;
      }
      const hit = await c.match(e.request, { ignoreSearch: true });
      if (hit) return hit;
      const r = await fetch(e.request);
      if (r.ok) c.put(e.request, r.clone());
      return r;
    })());
    return;
  }
  // everything else: the saved copy, ignoring ?query and #hash
  e.respondWith((async () => {
    const hit = await caches.match(e.request, { ignoreSearch: true });
    return hit || fetch(e.request);
  })());
});
