/* rn-early-warning.js — BMKG earthquake + weather-warning banner (Fase 10a; cuaca 23 Nov 2026).
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

  function until(v) {
    var d = new Date(String(v).replace(" ", "T") + "Z");
    return isNaN(d) ? "" : d.toLocaleString("id-ID", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
  }

  function render(b) {
    var host = document.querySelector("main") || document.body;
    var old = document.getElementById("rnEwBanner");
    // audit SOP 12 Nov (S9) + perbandingan layout: dulu 4-5 baris gempa nasional memenuhi layar pertama HP dan terkesan
    // terkait bencana yang dibuka. Kini satu baris ringkas yang bisa dibuka, dengan label cakupan nasional.
    // owner 2026-11-23: "batasi tampilan, cukup read more" — banner selalu tertutup (1 baris); bila dibuka maks 3 baris
    // per kelompok, sisanya lewat "Lihat semua". Status buka/tutup dipertahankan saat banner dimuat ulang tiap 5 menit.
    var wasOpen = !!(old && old.querySelector("details[open]"));
    var showAll = !!(old && old.getAttribute("data-all") === "1");
    var warn = b.warnings || [], last = b.latest || [], wx = b.weather || [];
    var alert = warn.length > 0;
    var MAX = 3;
    function limited(list, fn) {
      return list.map(function (x, i) {
        return '<div class="rn-ew-item"' + (i >= MAX ? ' data-more="1"' + (showAll ? "" : " hidden") : "") + ">" + fn(x) + "</div>";
      }).join("");
    }
    var rows = limited(alert ? warn : last, function (w) {
      return (alert ? "<b>⚠ " + esc(w.title) + "</b>" : esc(w.title)) + " · kedalaman " + esc(w.depth_km) +
        " km · " + esc(ago(w.issued_at)) + (w.potential ? " · " + esc(w.potential) : "");
    });
    var wxRows = wx.length ? '<div class="rn-ew-item" style="margin-top:6px"><b>⛈ Peringatan dini cuaca BMKG</b> (berlaku sekarang)</div>' +
      limited(wx, function (w) { return esc(w.title) + (w.expires_at ? " · sampai " + esc(until(w.expires_at)) : ""); }) : "";
    var hidden = Math.max(0, (alert ? warn : last).length - MAX) + Math.max(0, wx.length - MAX);
    var more = hidden ? '<button type="button" class="rn-ew-more" style="margin-top:4px;padding:2px 10px;border-radius:8px;border:1px solid rgba(104,64,45,.3);' +
      'background:#fff;color:#5b3a26;font:inherit;font-size:12px;cursor:pointer">' + (showAll ? "Tampilkan lebih sedikit ▴" : "Lihat semua (" + hidden + " lagi) ▾") + "</button>" : "";
    var head = alert
      ? "⚠ <b>Peringatan gempa BMKG</b>: " + esc(warn[0].title) + (warn.length > 1 ? " (+" + (warn.length - 1) + ")" : "")
      : "<b>Gempa terkini BMKG</b>" + (last.length ? " · " + last.length + " gempa · terbaru " + esc(ago(last[0].issued_at)) : " · tidak ada gempa 48 jam terakhir");
    if (wx.length) head += ' · <span style="color:#8a4b00">⛈ ' + wx.length + " peringatan cuaca</span>";
    head += ' <span style="color:#7c6458;font-size:12px">(seluruh Indonesia · klik untuk rincian)</span>';
    var html = "<details" + (wasOpen ? " open" : "") + '><summary style="cursor:pointer">' + head + "</summary>" +
      rows + wxRows + more + (b.weather_ok === false ? '<div class="rn-ew-item rn-ew-warn">Data cuaca BMKG tidak terjangkau saat ini.</div>' : "") + (b.source_ok === false ? '<div class="rn-ew-item rn-ew-warn">Data BMKG tidak terjangkau saat ini; daftar mungkin tertinggal.</div>' : "") +
      '<div style="color:#7c6458;font-size:12px;margin-top:4px">' + esc(b.attribution) + "</div></details>";
    var el = document.createElement("div");
    el.id = "rnEwBanner";
    el.setAttribute("role", "status");
    el.style.cssText = "margin:0 0 12px;padding:8px 12px;border-radius:12px;font-size:13px;line-height:1.5;" +
      (alert ? "border:1px solid #c0392b;background:rgba(192,57,43,.08)" : "border:1px solid rgba(104,64,45,.18);background:rgba(104,64,45,.04)");
    el.innerHTML = html;
    if (showAll) el.setAttribute("data-all", "1");
    var mb = el.querySelector(".rn-ew-more");
    if (mb) mb.addEventListener("click", function () {
      var all = el.getAttribute("data-all") !== "1";
      el.setAttribute("data-all", all ? "1" : "0");
      el.querySelectorAll("[data-more]").forEach(function (r) { r.hidden = !all; });
      mb.textContent = all ? "Tampilkan lebih sedikit ▴" : "Lihat semua (" + hidden + " lagi) ▾";
    });
    if (old && old.parentNode) old.parentNode.replaceChild(el, old); else host.insertBefore(el, host.firstChild);
  }

  function load() {
    if (!window.RN_FRAPPE) return;
    window.RN_FRAPPE.call("rescue_net.api_early_warning.banner", {}).then(render).catch(function () { /* banner is optional */ });
  }

  document.addEventListener("DOMContentLoaded", function () { load(); setInterval(load, 300000); });
})();
