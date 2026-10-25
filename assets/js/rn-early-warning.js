/* rn-early-warning.js — BMKG earthquake banner (Fase 10a).
 * Guest endpoint rescue_net.api_early_warning.banner. Informational only:
 * "belum diverifikasi"; activating an event stays a manual step. */
(function () {
  "use strict";
  function esc(s) { return window.RNUI ? window.RNUI.esc(s) : String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return "&#" + c.charCodeAt(0) + ";"; }); }

  function ago(v) {
    var d = new Date(String(v).replace(" ", "T") + "Z");
    var m = Math.max(0, Math.round((Date.now() - d.getTime()) / 60000));
    return isNaN(m) ? "" : m < 60 ? m + " mnt lalu" : Math.round(m / 60) + " jam lalu";
  }

  function render(b) {
    var host = document.querySelector("main") || document.body;
    var old = document.getElementById("rnEwBanner");
    if (old) old.remove();
    var html = "";
    (b.warnings || []).forEach(function (w) {
      html += '<div class="rn-ew-item"><b>⚠ ' + esc(w.title) + "</b> · kedalaman " + esc(w.depth_km) + " km · " + esc(ago(w.issued_at)) +
        (w.potential ? " · " + esc(w.potential) : "") + "</div>";
    });
    var alert = !!html;
    // no big quake: a quiet strip with the latest BMKG quakes (any magnitude)
    if (!alert) {
      var last = b.latest || [];
      html = '<div class="rn-ew-item"><b>Gempa terkini BMKG</b>' + (last.length ? "" : " · tidak ada gempa tercatat 48 jam terakhir") + "</div>";
      last.forEach(function (w) {
        html += '<div class="rn-ew-item">' + esc(w.title) + " · kedalaman " + esc(w.depth_km) + " km · " + esc(ago(w.issued_at)) + "</div>";
      });
    }
    if (b.source_ok === false) html += '<div class="rn-ew-item rn-ew-warn">Data BMKG tidak terjangkau saat ini; peringatan di bawah mungkin tertinggal.</div>';
    var el = document.createElement("div");
    el.id = "rnEwBanner";
    el.setAttribute("role", "status");
    el.style.cssText = "margin:0 0 12px;padding:10px 14px;border-radius:12px;font-size:13px;line-height:1.5;" +
      (alert ? "border:1px solid #c0392b;background:rgba(192,57,43,.08)" : "border:1px solid rgba(104,64,45,.18);background:rgba(104,64,45,.04)");
    el.innerHTML = html + '<div style="color:#7c6458;font-size:11px;margin-top:4px">' + esc(b.attribution) + "</div>";
    host.insertBefore(el, host.firstChild);
  }

  function load() {
    if (!window.RN_FRAPPE) return;
    window.RN_FRAPPE.call("rescue_net.api_early_warning.banner", {}).then(render).catch(function () { /* banner is optional */ });
  }

  document.addEventListener("DOMContentLoaded", function () { load(); setInterval(load, 300000); });
})();
