// DMS (Ming Ming 2026-11-23): halaman pertama = login. Tamu yang membuka pusat kendali dialihkan ke dms-login.html.
// Bila backend tidak terjangkau, halaman tetap tampil (status API ditampilkan oleh window manager).
(() => {
  "use strict";
  const html = document.documentElement;
  html.classList.add("dms-auth-check");
  const reveal = () => html.classList.remove("dms-auth-check");
  const timer = setTimeout(reveal, 5000);
  const toLogin = () => {
    const here = location.pathname.split("/").pop() + location.search + location.hash;
    location.replace("dms-login.html?next=" + encodeURIComponent(here));
  };
  window.RNDmsToLogin = toLogin;
  fetch("/rescue-net-frappe/api/method/rescue_net.api_auth.session_info", {
    credentials: "include", headers: { Accept: "application/json" }, cache: "no-store"
  }).then((r) => (r.ok ? r.json() : Promise.reject(new Error("HTTP " + r.status))))
    .then((p) => {
      const user = (p && p.message && p.message.user) || "Guest";
      if (user === "Guest") return toLogin();
      clearTimeout(timer); reveal();
    })
    .catch(() => { clearTimeout(timer); reveal(); });
})();
