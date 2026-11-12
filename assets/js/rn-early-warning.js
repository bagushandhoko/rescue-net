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
    // audit SOP 12 Nov (S9) + perbandingan layout: dulu 4-5 baris gempa nasional memenuhi layar pertama HP dan terkesan
    // terkait bencana yang dibuka. Kini satu baris ringkas yang bisa dibuka, dengan label cakupan nasional.
    var warn = b.warnings || [], last = b.latest || [];
    var alert = warn.length > 0;
    var rows = (alert ? warn : last).map(function (w) {
      return '<div class="rn-ew-item">' + (alert ? "<b>⚠ " + esc(w.title) + "</b>" : esc(w.title)) + " · kedalaman " + esc(w.depth_km) +
        " km · " + esc(ago(w.issued_at)) + (w.potential ? " · " + esc(w.potential) : "") + "</div>";
    }).join("");
    var first = (alert ? warn : last)[0];
    var head = alert
      ? "⚠ <b>Peringatan gempa BMKG</b> (seluruh Indonesia): " + esc(first.title) + (warn.length > 1 ? " (+" + (warn.length - 1) + " lainnya)" : "")
      : "<b>Gempa terkini BMKG</b> (seluruh Indonesia, belum tentu terkait bencana ini)" +
        (last.length ? " · " + last.length + " gempa · terbaru " + esc(ago(last[0].issued_at)) : " · tidak ada gempa tercatat 48 jam terakhir");
    var html = "<details" + (alert && window.innerWidth > 900 ? " open" : "") + '><summary style="cursor:pointer">' + head + "</summary>" +
      rows + (b.source_ok === false ? '<div class="rn-ew-item rn-ew-warn">Data BMKG tidak terjangkau saat ini; daftar mungkin tertinggal.</div>' : "") +
      '<div style="color:#7c6458;font-size:12px;margin-top:4px">' + esc(b.attribution) + "</div></details>";
    var el = document.createElement("div");
    el.id = "rnEwBanner";
    el.setAttribute("role", "status");
    el.style.cssText = "margin:0 0 12px;padding:8px 12px;border-radius:12px;font-size:13px;line-height:1.5;" +
      (alert ? "border:1px solid #c0392b;background:rgba(192,57,43,.08)" : "border:1px solid rgba(104,64,45,.18);background:rgba(104,64,45,.04)");
    el.innerHTML = html;
    host.insertBefore(el, host.firstChild);
  }

  function load() {
    if (!window.RN_FRAPPE) return;
    window.RN_FRAPPE.call("rescue_net.api_early_warning.banner", {}).then(render).catch(function () { /* banner is optional */ });
  }

  document.addEventListener("DOMContentLoaded", function () { load(); setInterval(load, 300000); });
})();
