/* rn-pwa.js — the website is the installable Rescue-Net app (phase 5, option B).
 * Registers /rescue-net/sw.js, keeps the browser's install prompt for the
 * "Install App" button ([data-pwa-install]) and marks <html> with
 * .rn-offline while the device has no connection. Loaded by every page. */
(function () {
  "use strict";
  if (window.RNPWA) return;
  var deferred = null;

  if ("serviceWorker" in navigator && (location.protocol === "https:" || location.hostname === "localhost")) {
    window.addEventListener("load", function () {
      navigator.serviceWorker.register("/rescue-net/sw.js", { scope: "/rescue-net/" }).catch(function () {});
    });
  }

  function installed() {
    return window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone === true;
  }

  function refreshButtons() {
    document.querySelectorAll("[data-pwa-install]").forEach(function (b) {
      b.hidden = installed() || !deferred;
    });
    document.querySelectorAll("[data-pwa-installed]").forEach(function (el) { el.hidden = !installed(); });
  }

  window.addEventListener("beforeinstallprompt", function (e) {
    e.preventDefault();
    deferred = e;
    refreshButtons();
  });
  window.addEventListener("appinstalled", function () { deferred = null; refreshButtons(); });

  document.addEventListener("click", function (e) {
    var b = e.target.closest("[data-pwa-install]");
    if (!b || !deferred) return;
    deferred.prompt();
    deferred.userChoice.finally(function () { deferred = null; refreshButtons(); });
  });

  // the notice styles itself: not every page loads style.css (Control Centre)
  function noticeStyle() {
    if (document.getElementById("rn-offline-style")) return;
    var st = document.createElement("style");
    st.id = "rn-offline-style";
    st.textContent = 'html.rn-offline body::after{content:"Offline \\2014  menampilkan salinan terakhir; ' +
      'laporan disimpan di perangkat dan terkirim saat online.";position:fixed;left:12px;right:12px;bottom:12px;' +
      'z-index:99999;padding:8px 12px;border-radius:10px;font:13px/1.4 system-ui,sans-serif;text-align:center;' +
      'background:#2d211b;color:#fff;box-shadow:0 8px 24px rgba(0,0,0,.2)}';
    document.head.appendChild(st);
  }
  function net() { noticeStyle(); document.documentElement.classList.toggle("rn-offline", !navigator.onLine); }
  window.addEventListener("online", net);
  window.addEventListener("offline", net);
  document.addEventListener("DOMContentLoaded", function () { net(); refreshButtons(); });

  window.RNPWA = { installed: installed, canPrompt: function () { return !!deferred; } };
})();
