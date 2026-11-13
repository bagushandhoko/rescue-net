/* Backup & Pulihkan Data Organisasi (owner 2026-11-13) — bagian admin di Koordinasi Organisasi.
 * Backend: rescue_net.api_org_backup (hanya admin organisasi / super admin). */
(function () {
  "use strict";
  var A = "rescue_net.api_org_backup.";
  var $ = function (id) { return document.getElementById(id); };
  var esc = function (s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); };
  var call = function (m, a, post) { return window.RN_FRAPPE.call(A + m, a || {}, post ? { method: "POST" } : undefined); };
  var msg = function (t, bad) { var m = $("koBkMsg"); if (m) { m.innerHTML = t || ""; m.style.color = bad ? "#c0392b" : ""; } };
  var size = function (n) { n = Number(n || 0); return n > 1048576 ? (n / 1048576).toFixed(1) + " MB" : Math.max(1, Math.round(n / 1024)) + " KB"; };
  var errText = function (e) { return (e && (e.message || e.exc || e)) + ""; };
  function org() { return ($("koBkOrg") || {}).value; }

  async function load() {
    var o = org(); if (!o) return;
    $("koBkList").innerHTML = '<p class="rn-muted">Memuat…</p>';
    try {
      var r = await call("daftar_backup", { organization: o });
      $("koBkList").innerHTML = (r.backups || []).length ? r.backups.map(function (b) {
        var url = "/rescue-net-frappe/api/method/" + A + "unduh_backup?organization=" + encodeURIComponent(o) + "&file=" + encodeURIComponent(b.file);
        var auto = /sebelum-pulihkan/.test(b.file_name) ? ' <span class="chip neutral">otomatis sebelum pulihkan</span>' : "";
        return '<div class="rs-opt" style="display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap;padding:6px 0;border-bottom:1px solid rgba(104,64,45,.12)">' +
          "<div><b>" + esc(b.created) + "</b>" + auto + '<br><small class="rn-muted">' + size(b.size) + "</small></div>" +
          '<div><a class="btn mini" href="' + url + '">Unduh</a> <button type="button" class="btn ghost mini" data-restore="' + esc(b.file) + '" data-when="' + esc(b.created) + '">Pulihkan</button></div></div>';
      }).join("") : '<p class="rn-muted">Belum ada backup. Tekan "Buat backup sekarang".</p>';
      $("koBkLog").innerHTML = (r.log || []).map(function (l) { return "<li><small>" + esc(l.at) + "</small> — " + esc(l.text) + "</li>"; }).join("") || "<li class=\"rn-muted\">Belum ada riwayat.</li>";
    } catch (e) { $("koBkList").innerHTML = '<p class="rn-muted">' + esc(errText(e)) + "</p>"; }
  }

  async function restore(args, label) {
    var hapus = $("koBkHapus") && $("koBkHapus").checked;
    var warn = "Pulihkan data organisasi dari " + label + "?\n\n- Data yang rusak/terhapus dikembalikan ke isi saat backup.\n- " +
      (hapus ? "Data yang dibuat SETELAH backup akan DIHAPUS." : "Data yang dibuat setelah backup tetap ada.") +
      "\n- Sistem membuat backup keadaan sekarang dulu, jadi bisa dikembalikan.";
    if (!window.confirm(warn)) return;
    msg("Memulihkan… (bisa 1–2 menit)");
    try {
      args.organization = org(); args.hapus_baru = hapus ? 1 : 0;
      var r = await call("pulihkan_organisasi", args, true), h = r.hasil || {};
      msg("Selesai. Dipulihkan " + (h.dipulihkan || 0) + ", dibuat ulang " + (h.dibuat || 0) + ", tidak berubah " + (h.sama || 0) +
        (h.dihapus ? ", dihapus " + h.dihapus : "") + (h.dilewati ? ", dilewati (bukan milik organisasi ini) " + h.dilewati : "") +
        (h.gagal ? ', <b>gagal ' + h.gagal + "</b>" : "") + ". Backup sebelum pulihkan: " + esc(r.backup_sebelumnya) + ".", !!h.gagal);
      await load();
    } catch (e) { msg("Gagal: " + esc(errText(e)), true); }
  }

  function wire() {
    $("koBkOrg").addEventListener("change", load);
    $("koBkCreate").addEventListener("click", async function () {
      msg("Membuat backup…");
      try { var r = await call("backup_organisasi", { organization: org() }, true); msg("Backup dibuat: " + r.records + " catatan (" + size(r.size) + ")."); await load(); }
      catch (e) { msg("Gagal: " + esc(errText(e)), true); }
    });
    $("koBkList").addEventListener("click", function (e) {
      var b = e.target.closest("[data-restore]"); if (!b) return;
      restore({ file: b.dataset.restore }, "backup " + b.dataset.when);
    });
    $("koBkUpload").addEventListener("click", function () {
      var f = $("koBkFile").files[0];
      if (!f) { msg("Pilih berkas backup (.json.gz) dulu.", true); return; }
      if (f.size > 7 * 1024 * 1024) { msg("Berkas lebih dari 7 MB: pakai tombol Pulihkan pada daftar backup di server.", true); return; }
      var rd = new FileReader();
      rd.onload = function () { restore({ content_base64: String(rd.result) }, "berkas " + f.name); };
      rd.readAsDataURL(f);
    });
  }

  function init() {
    var sec = $("koBackupOrg"); if (!sec || !window.RN_FRAPPE) return;
    var tries = 0;
    var t = setInterval(function () {   // tunggu daftar organisasi admin diisi koordinasi-organisasi.js
      var src = $("koAiKeyOrg"); tries++;
      if (src && src.options.length) {
        clearInterval(t);
        $("koBkOrg").innerHTML = src.innerHTML;
        sec.hidden = false; wire(); load();
      } else if (tries > 60) clearInterval(t);
    }, 500);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
