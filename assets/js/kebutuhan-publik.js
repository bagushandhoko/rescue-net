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
      var notes = b.notes || [];
      $("#kpNotesCard").hidden = !notes.length;
      $("#kpNotes").innerHTML = notes.map(function (n) {
        return '<li class="kp-item"><div><b>' + esc(n.posko_title) + "</b>" +
          '<div class="kp-muted">' + (n.region ? esc(n.region) + " · " : "") + esc(ago(n.updated_at)) + "</div>" +
          (n.not_needed ? '<div><span class="kp-x">✕</span>Tidak dibutuhkan: ' + esc(n.not_needed) + "</div>" : "") +
          (n.not_accepted_packaging ? '<div><span class="kp-x">✕</span>Kemasan tidak diterima: ' + esc(n.not_accepted_packaging) + "</div>" : "") +
          "</div></li>";
      }).join("");
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
    initEditor();
  });

  var mine = [];
  function fillEditor() {
    var m = mine.filter(function (x) { return x.posko === $("#kpEdPosko").value; })[0] || {};
    $("#kpEdNot").value = m.not_needed || "";
    $("#kpEdPack").value = m.not_accepted_packaging || "";
  }
  async function initEditor() {
    try {
      mine = await window.RN_FRAPPE.call("rescue_net.api_public_needs.my_editable_poskos", {});
    } catch (e) { return; /* tamu / bukan pengelola: editor tidak tampil */ }
    if (!mine || !mine.length) return;
    $("#kpEdPosko").innerHTML = mine.map(function (x) {
      return '<option value="' + esc(x.posko) + '">' + esc(x.title) + (x.public ? "" : " (tidak publik)") + "</option>";
    }).join("");
    $("#kpEditor").hidden = false;
    fillEditor();
    $("#kpEdPosko").addEventListener("change", fillEditor);
    $("#kpEdSave").addEventListener("click", async function () {
      $("#kpEdMsg").textContent = "Menyimpan…";
      try {
        var r = await window.RN_FRAPPE.call("rescue_net.api_public_needs.set_public_notes", {
          posko: $("#kpEdPosko").value, not_needed: $("#kpEdNot").value, not_accepted_packaging: $("#kpEdPack").value
        });
        mine.forEach(function (x) { if (x.posko === r.posko) { x.not_needed = r.not_needed; x.not_accepted_packaging = r.not_accepted_packaging; } });
        $("#kpEdMsg").textContent = r.public ? "Tersimpan dan tampil publik." : "Tersimpan (posko tidak publik, belum tampil).";
        load();
      } catch (e) { $("#kpEdMsg").textContent = (e && e.message) || "Gagal menyimpan."; }
    });
  }
})();
