const CACHE_NAME = "rescue-net-app-v7";
const APP_SHELL = [
  "./",
  "index.html",
  "manifest.webmanifest",
  "src/app.js",
  "src/styles.css",
  "src/logo.svg"
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))))
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  // API answers (logged-in data) are never put in the shared cache; the app
  // keeps its own offline copy in localStorage
  if (new URL(request.url).pathname.includes("/api/method/")) return;
  event.respondWith(
    fetch(request).then((response) => {
      const copy = response.clone();
      caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
      return response;
    }).catch(() => caches.match(request).then((cached) => cached || caches.match("./")))
  );
});

