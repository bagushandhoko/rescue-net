// DMS di disastermanagement.online (owner 23 Nov 2026): halaman pertama = login DMS; sesudah login memakai
// halaman RN apa adanya, hanya warnanya tema DMS (biru tua + oranye, assets/css/rn-dms-tema.css).
// Bingkai lama (edisi-tertutup.html: peta tengah + jendela) tidak dipakai lagi.
(() => {
  "use strict";
  if (!["disastermanagement.online", "www.disastermanagement.online"].includes(location.hostname) && !window.RN_DMS_FORCE) return;
  const script = document.currentScript;
  const html = document.documentElement;
  html.classList.add("rn-dms-tema");
  if (!document.querySelector('link[href*="rn-dms-tema.css"]')) {
    const theme = document.createElement("link");
    theme.rel = "stylesheet";
    theme.href = new URL("../css/rn-dms-tema.css?v=tema-20261123c", script.src).href;
    document.head.append(theme);
  }
  // Nama komersial DMS (keputusan owner 22 Nov): ganti nama merek di header & judul tab.
  const brand = () => {
    document.querySelectorAll(".rn-public-brand-name").forEach((n) => { if (n.textContent.trim() !== "DMS") n.textContent = "DMS"; });
    if (/Rescue-?Net/i.test(document.title)) document.title = document.title.replace(/Rescue-?Net/gi, "DMS");
  };
  document.addEventListener("DOMContentLoaded", () => {
    brand();
    const header = document.querySelector(".rn-public-header") || document.body;
    new MutationObserver(brand).observe(header, { childList: true, subtree: true });
  });
  const page = (location.pathname.split("/").pop() || "").toLowerCase();
  // Halaman yang boleh dibuka tanpa login.
  const open = ["auth.html", "dms-login.html", "offline.html", "kebijakan-privasi.html", "install.html"];
  if (open.includes(page)) return;
  html.classList.add("dms-auth-check");
  const style = document.createElement("style");
  style.textContent = "html.dms-auth-check body{visibility:hidden}html.dms-auth-check{background:#090e1a}";
  document.head.append(style);
  const reveal = () => html.classList.remove("dms-auth-check");
  const timer = setTimeout(reveal, 5000);
  fetch("/rescue-net-frappe/api/method/rescue_net.api_auth.session_info", {
    credentials: "include", headers: { Accept: "application/json" }, cache: "no-store"
  }).then((r) => (r.ok ? r.json() : Promise.reject(new Error("HTTP " + r.status))))
    .then((p) => {
      const user = (p && p.message && p.message.user) || "Guest";
      if (user === "Guest") {
        const here = page + location.search + location.hash;
        location.replace(new URL("dms-login.html?next=" + encodeURIComponent(here), location.href).href);
        return;
      }
      clearTimeout(timer); reveal();
    })
    .catch(() => { clearTimeout(timer); reveal(); });
})();
