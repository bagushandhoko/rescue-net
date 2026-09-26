/* Rescue-Net web app service worker (phase 5 option B: the website is the
 * installable app). Scope /rescue-net/.
 *  - pages: network first, cached copy when offline, else pages/offline.html
 *  - JS / CSS / images: cached per exact URL (the ?v= cache-buster decides
 *    the version); offline, any cached version of the file is used
 *  - API calls (/api/method/, /rescue-net-frappe/) and non-GET requests are
 *    never cached — logged-in data stays out of the shared cache; offline
 *    writes go through the page's own queue (rn-sync-engine.js).
 */
const CACHE = "rescue-net-web-v2";
const PRECACHE = [
 "/rescue-net/index.html",
 "/rescue-net/pages/laporan-masyarakat.html",
 "/rescue-net/pages/posko-logistik.html",
 "/rescue-net/pages/registrasi-posko.html",
 "/rescue-net/pages/shelter-detail.html",
 "/rescue-net/pages/bencana-aktif.html",
 "/rescue-net/pages/offline.html",
 "/rescue-net/pages/install.html",
 "/rescue-net/assets/css/rn-lightbox.css",
 "/rescue-net/assets/css/rn-mobile-drawer.css",
 "/rescue-net/assets/css/rn-navigation-v2.css",
 "/rescue-net/assets/css/style.css",
 "/rescue-net/assets/js/api.js",
 "/rescue-net/assets/js/bencana-aktif.js",
 "/rescue-net/assets/js/community-report.js",
 "/rescue-net/assets/js/logistik.js",
 "/rescue-net/assets/js/registrasi-posko.js",
 "/rescue-net/assets/js/rn-frappe-client.js",
 "/rescue-net/assets/js/rn-icons.js",
 "/rescue-net/assets/js/rn-item-groups.js",
 "/rescue-net/assets/js/rn-layout-mode.js",
 "/rescue-net/assets/js/rn-lightbox.js",
 "/rescue-net/assets/js/rn-logistik-info.js",
 "/rescue-net/assets/js/rn-mobile-drawer.js",
 "/rescue-net/assets/js/rn-navigation-v2.js",
 "/rescue-net/assets/js/rn-posko-picker.js",
 "/rescue-net/assets/js/rn-posko-scope.js",
 "/rescue-net/assets/js/rn-posko-settings.js",
 "/rescue-net/assets/js/rn-public-header.js",
 "/rescue-net/assets/js/rn-sync-engine.js",
 "/rescue-net/assets/js/rn-ui.js",
 "/rescue-net/assets/js/rn-verif-badge.js",
 "/rescue-net/assets/js/session-role.js",
 "/rescue-net/assets/js/shelter-detail.js",
 "/rescue-net/assets/vendor/leaflet/leaflet.css",
 "/rescue-net/assets/vendor/leaflet/leaflet.js",
 "/rescue-net/manifest.webmanifest",
 "/rescue-net/assets/img/pwa/icon-192.png",
 "/rescue-net/assets/img/rn-logo-web.png"
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => Promise.all(PRECACHE.map((u) => c.add(u).catch(() => null)))));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))));
  self.clients.claim();
});

function skip(url, request) {
  return request.method !== "GET" || url.origin !== self.location.origin ||
    url.pathname.includes("/api/method/") || url.pathname.startsWith("/rescue-net-frappe/") ||
    !url.pathname.startsWith("/rescue-net/");
}

self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);
  if (skip(url, request)) return;

  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request).then((res) => {
        if (res.ok) { const copy = res.clone(); caches.open(CACHE).then((c) => c.put(url.pathname, copy)); }
        return res;
      }).catch(() => caches.match(url.pathname, { ignoreSearch: true })
        .then((hit) => hit || caches.match("/rescue-net/pages/offline.html")))
    );
    return;
  }

  // exact URL (incl. ?v=) first, so a new cache-buster always fetches the new
  // file; any cached version only when the network is gone
  event.respondWith(
    caches.match(request).then((hit) => hit || fetch(request).then((res) => {
      if (res.ok) { const copy = res.clone(); caches.open(CACHE).then((c) => c.put(request, copy)); }
      return res;
    }).catch(() => caches.match(request, { ignoreSearch: true })))
  );
});
