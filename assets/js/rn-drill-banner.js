/* rn-drill-banner.js — banner merah "MODE LATIHAN" (Fase 10g).
 * Hanya jalan bila URL membawa ?event= / ?disaster_event= / ?disaster_event_id= dan pengguna login;
 * tamu tidak bisa membuka event latihan sama sekali (server menolak), jadi tidak ada panggilan tamu. */
(function () {
  "use strict";
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return "&#" + c.charCodeAt(0) + ";"; }); }
  document.addEventListener("DOMContentLoaded", function () {
    if (!window.RN_FRAPPE) return;
    var q = new URLSearchParams(location.search);
    var ev = q.get("event") || q.get("disaster_event") || q.get("disaster_event_id");
    if (!ev) return;
    window.RN_FRAPPE.call("rescue_net.api_events.drill_status", { event: ev }).then(function (r) {
      if (!r || !r.is_drill) return;
      var el = document.createElement("div");
      el.id = "rnDrillBanner";
      el.setAttribute("role", "alert");
      el.style.cssText = "position:sticky;top:0;z-index:9999;padding:8px 14px;background:#b91c1c;color:#fff;font:700 13px/1.3 system-ui,sans-serif;text-align:center;letter-spacing:.04em";
      el.textContent = "MODE LATIHAN — " + (r.label || "Latihan") + ". Data ini simulasi; tidak masuk angka nyata dan notifikasi hanya simulasi.";
      document.body.insertBefore(el, document.body.firstChild);
    }).catch(function () { /* banner opsional */ });
  });
})();
