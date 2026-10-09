/* kebutuhan-publik.js — donor-facing needs board (Fase 10f).
 * Guest endpoint rescue_net.api_public_needs.board. */
(function () {
  "use strict";
  function $(s) { return document.querySelector(s); }
  function esc(s) { return window.RNUI.esc(s); }

  function ago(v) {
    var d = new Date(String(v).replace(" ", "T"));
    if (isNaN(d.getTime())) return "";
    var h = Math.max(0, Math.round((Date.now() - d.getTime()) / 3600000));
    return h < 1 ? "diperbarui baru saja" : h < 48 ? "diperbarui " + h + " jam lalu" : "diperbarui " + Math.round(h / 24) + " hari lalu";
  }
  function qty(n) { return Number(n).toLocaleString("id-ID", { maximumFractionDigits: 1 }); }

  function li(r, enough) {
    return '<li class="kp-item"><div><b>' + esc(r.item) + "</b>" +
      (r.critical && !enough ? '<span class="kp-pill">KRITIS</span>' : "") +
      '<div class="kp-muted">' + esc(r.posko_title) + (r.region ? " · " + esc(r.region) : "") +
      " · " + esc(ago(r.updated_at)) + "</div></div>" +
      (enough
        ? '<span class="kp-muted"><span class="kp-x">✕</span>jangan kirim</span>'
        : '<span class="kp-qty">kurang ' + esc(qty(r.gap)) + " " + esc(r.unit || "") + "</span>" +
          '<a class="kp-btn" href="' + esc(r.href) + '">Kirim ke posko ini</a>') +
      "</li>";
  }

  async function load() {
    var args = {};
    if ($("#kpEvent").value) args.event = $("#kpEvent").value;
    if ($("#kpRegion").value.trim()) args.wilayah = $("#kpRegion").value.trim();
    try {
      var b = await window.RN_FRAPPE.call("rescue_net.api_public_needs.board", args);
      $("#kpMeta").textContent = b.poskos + " posko publik" + (b.needs.length ? "" : " — belum ada kekurangan tercatat.");
      $("#kpNeeds").innerHTML = b.needs.map(function (r) { return li(r, false); }).join("");
      $("#kpEnough").innerHTML = b.enough.map(function (r) { return li(r, true); }).join("");
    } catch (e) {
      $("#kpMeta").textContent = "Gagal memuat data kebutuhan.";
    }
  }

  document.addEventListener("DOMContentLoaded", async function () {
    var q = new URLSearchParams(location.search);
    try {
      var rows = await window.RN_FRAPPE.call("rescue_net.api_ai.public_active_disasters", {});
      (rows || []).forEach(function (d) {
        var id = d.id || d.legacy_id || d.name;
        $("#kpEvent").insertAdjacentHTML("beforeend", '<option value="' + esc(id) + '">' + esc(d.title || id) + "</option>");
      });
    } catch (e) { /* board still works without the picker */ }
    if (q.get("event")) $("#kpEvent").value = q.get("event");
    $("#kpEvent").addEventListener("change", load);
    var t; $("#kpRegion").addEventListener("input", function () { clearTimeout(t); t = setTimeout(load, 350); });
    load();
  });
})();
