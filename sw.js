/* Rescue-Net web app service worker (phase 5 option B: the website is the
 * installable app). Scope /rescue-net/.
 *  - pages: network first, cached copy when offline, else pages/offline.html
 *  - JS / CSS / images: cached per exact URL (the ?v= cache-buster decides
 *    the version); offline, any cached version of the file is used
 *  - API calls (/api/method/, /rescue-net-frappe/) and non-GET requests are
 *    never cached — logged-in data stays out of the shared cache; offline
 *    writes go through the page's own queue (rn-sync-engine.js).
 */
const CACHE = "rescue-net-web-v25"; // v25 2026-11-24: thumbnail RAB/PDF + penampil dokumen. v24 2026-11-24: Program Khusus tampilan publik dulu utk simulasi terbuka, RAB terbaca, form pengelola hanya pengelola. v23 2026-11-24: Pengaturan dipisah 3 (Akun / Organisasi / Sistem RN) + Verifikasi Pengelola Donasi. v22 2026-11-24: menu Posko/Modul hanya untuk pengelola (publik: Daftarkan Posko; halaman donasi: grup Donasi saja); QRIS di samping rekening. v21 2026-11-24: rencana pengungsian riil hanya angka untuk tamu/non-pengelola. v20 2026-11-24: nominal donasi min 1000 step 1 (dulu step 1000 + min 1 = semua nominal bulat ditolak browser). v19 2026-11-24: Program Donasi detail publik di atas, tombol pengelola disembunyikan, HP gulir ke detail. v18 2026-11-24: 2FA wajib pemilik org tertutup (pengalihan ke Pengaturan Akun). v17 2026-11-24: menu HP (laci) tidak lagi menimpa menu publik, grup tampil tanpa menunggu server. v16: dua menu pengaturan. v15 2026-11-23: blok Pengaturan Posko paling atas; v14 Pengaturan dan booking armada; v13 2026-11-24: banner BMKG ringkas; v12 2026-11-23: peta risiko CC tanpa bencana riil; v11 2026-11-23: lapisan InaRISK + cuaca BMKG; v10 rincian Bencana Aktif.
const PRECACHE = [
 "/rescue-net/index.html",
 "/rescue-net/pages/laporan-masyarakat.html",
 "/rescue-net/pages/posko-logistik.html",
 "/rescue-net/pages/registrasi-posko.html",
 "/rescue-net/pages/shelter-detail.html",
 "/rescue-net/pages/bencana-aktif.html",
 "/rescue-net/pages/offline.html",
 "/rescue-net/pages/posko-detail.html",
 "/rescue-net/pages/posko-medis-detail.html",
 "/rescue-net/pages/dapur-umum.html",
 "/rescue-net/pages/alat-kerja.html",
 "/rescue-net/pages/kehadiran-relawan.html",
 "/rescue-net/pages/kartu-keluarga.html",
 "/rescue-net/pages/scan.html",
 "/rescue-net/pages/posko-distribusi.html",
 "/rescue-net/assets/js/rn-offline-outbox.js",
 "/rescue-net/assets/js/posko-detail.js",
 "/rescue-net/assets/js/posko-medis-detail.js",
 "/rescue-net/assets/js/dapur-umum.js",
 "/rescue-net/assets/js/alat-kerja.js",
 "/rescue-net/assets/js/recovery-alat.js",
 "/rescue-net/assets/js/kehadiran-relawan.js",
 "/rescue-net/assets/js/kartu-keluarga.js",
 "/rescue-net/assets/js/scan.js",
 "/rescue-net/assets/js/rn-posko-contact.js",
 "/rescue-net/assets/js/rn-kpi-go.js",
 "/rescue-net/assets/js/rn-drill-banner.js",
 "/rescue-net/assets/js/rn-pwa.js",
 "/rescue-net/assets/js/posko-distribusi.js",
 "/rescue-net/pages/install.html",
 "/rescue-net/pages/manual.html",
 "/rescue-net/pages/manual-teknis.html",
 "/rescue-net/pages/cetak-label.html",
 "/rescue-net/assets/css/rn-lightbox.css",
 "/rescue-net/assets/css/rn-mobile-drawer.css?v=warna-20261122",
 "/rescue-net/assets/css/rn-navigation-v2.css",
 "/rescue-net/assets/css/style.css?v=warna-20261122",
 "/rescue-net/assets/js/api.js",
 "/rescue-net/assets/js/bencana-aktif.js?v=lengkap-inarisk-20261123",
 "/rescue-net/assets/js/rn-inarisk-layers.js?v=inarisk-20261123",
 "/rescue-net/assets/css/rn-ba-compact.css?v=lengkap-20261123",
 "/rescue-net/assets/js/community-report.js",
 "/rescue-net/assets/js/logistik.js",
 "/rescue-net/assets/js/registrasi-posko.js",
 "/rescue-net/assets/js/rn-frappe-client.js",
 "/rescue-net/assets/js/rn-icons.js",
 "/rescue-net/assets/js/rn-item-groups.js",
 "/rescue-net/assets/js/rn-layout-mode.js",
 "/rescue-net/assets/js/rn-lightbox.js",
 "/rescue-net/assets/js/rn-logistik-info.js",
 "/rescue-net/assets/js/rn-mobile-drawer.js?v=hp-20261124",
 "/rescue-net/assets/js/rn-navigation-v2.js",
 "/rescue-net/assets/js/rn-posko-picker.js",
 "/rescue-net/assets/js/rn-posko-scope.js",
 "/rescue-net/assets/js/rn-posko-settings.js",
 "/rescue-net/assets/js/rn-posko-events-settings.js",
 "/rescue-net/assets/js/rn-account-tabs.js",
 "/rescue-net/assets/js/rn-public-header.js?v=warna-20261122",
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
