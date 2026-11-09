/* rn-operational-mode.js — kartu "Mode Operasional Riil" di Setting (owner 2026-11-09).
 * "cukup menekan 1 tombol di pengaturan super admin, semua data simulasi tidak tampil di halaman Rescue-Net".
 * Hanya System Manager: server menolak (403) pengguna lain, kartu tetap tersembunyi. Data simulasi TIDAK dihapus;
 * tombol "Kembali ke Mode Simulasi" menampilkan semuanya lagi. Aturan penyaringan: services/drill.py. */
(function () {
  "use strict";
  var M = "rescue_net.api_operational_mode.";
  var CONFIRM = "AKTIFKAN";
  var loaded = false, pending = false;

  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return "&#" + c.charCodeAt(0) + ";"; }); }
  function $(id) { return document.getElementById(id); }
  function call(method, args, post) {
    return window.RN_FRAPPE.call(M + method, args || {}, post ? { method: "POST" } : {});
  }
  function msg(text, bad) {
    var el = $("opModeMsg");
    if (!el) return;
    el.textContent = text || "";
    el.style.color = bad ? "#b23b3b" : "";
  }

  function render(s) {
    var on = !!s.operational;
    var pill = $("opModePill");
    pill.textContent = on ? "AKTIF — data simulasi disembunyikan" : "MATI — data simulasi tampil (mode latihan)";
    pill.style.cssText = "display:inline-block;padding:4px 10px;border-radius:999px;font-weight:700;" +
      (on ? "background:#dcfce7;color:#166534;border:1px solid #86efac" : "background:#fff7e6;color:#7a4b00;border:1px solid #f59e0b");
    $("opModeWho").textContent = s.changed_at
      ? "Terakhir diubah oleh " + (s.changed_by || "-") + " pada " + s.changed_at
      : "Belum pernah diubah.";
    $("opModeCount").textContent = s.simulation_count + " bencana ditandai simulasi";
    var btn = $("opModeToggle");
    btn.textContent = on ? "Kembali ke Mode Simulasi (tampilkan data simulasi)" : "Aktifkan Mode Operasional Riil";
    btn.style.cssText = on ? "" : "background:#c23a3a;border-color:#c23a3a;color:#fff";
    btn.setAttribute("data-on", on ? "1" : "0");

    var rows = (s.events || []).map(function (e) {
      var src = e.source === "manual" ? "1" : e.source === "exclude" ? "0" : "auto";
      var autoLbl = "Otomatis (" + ((e.source === "auto" || e.source === "exclude") ? "terdeteksi simulasi" : "nyata") + ")";
      return "<tr>" +
        "<td>" + esc(e.title) + "<br><small class='rn-muted'>" + esc(e.id) + " · " + esc(e.status || "-") +
        " · " + e.posko_count + " posko" + (e.drill ? " · latihan (is_drill)" : "") + "</small></td>" +
        "<td><b style='color:" + (e.simulation ? "#b23b3b" : "#166534") + "'>" + (e.simulation ? "Simulasi" : "Nyata") + "</b></td>" +
        "<td><select data-ev='" + esc(e.name) + "' aria-label='Tandai " + esc(e.title) + "'>" +
        "<option value='auto'" + (src === "auto" ? " selected" : "") + ">" + esc(autoLbl) + "</option>" +
        "<option value='1'" + (src === "1" ? " selected" : "") + ">Simulasi (manual)</option>" +
        "<option value='0'" + (src === "0" ? " selected" : "") + ">Nyata (manual)</option>" +
        "</select></td></tr>";
    }).join("");
    $("opModeEvents").innerHTML = rows || "<tr><td colspan='3'>Belum ada bencana.</td></tr>";

    $("opModeLog").innerHTML = (s.log || []).map(function (l) {
      return "<li>" + esc(l.at) + " — <b>" + esc(l.by_name || l.by) + "</b>: " + esc(l.action) +
        (l.detail ? " (" + esc(l.detail) + ")" : "") + "</li>";
    }).join("") || "<li>Belum ada riwayat.</li>";
  }

  function toggle() {
    var on = $("opModeToggle").getAttribute("data-on") === "1";
    var p;
    if (!on) {
      var typed = window.prompt(
        "Aktifkan MODE OPERASIONAL RIIL?\n\n" +
        "Semua bencana simulasi beserta posko, armada, kiriman, bukti, program donasi, laporan, dan akun demo " +
        "di halaman login akan DISEMBUNYIKAN dari semua pengguna (super admin masih bisa membuka lewat tautan langsung).\n" +
        "Data TIDAK dihapus dan bisa ditampilkan lagi dengan tombol yang sama.\n\n" +
        "Ketik " + CONFIRM + " untuk melanjutkan:");
      if (typed == null) return;
      if (String(typed).trim().toUpperCase() !== CONFIRM) { msg("Dibatalkan: kata konfirmasi tidak cocok.", true); return; }
      p = call("set_operational_mode", { active: 1, confirm: CONFIRM }, true);
    } else {
      if (!window.confirm("Kembali ke mode simulasi?\n\nSemua data simulasi akan TAMPIL lagi di halaman publik.")) return;
      p = call("set_operational_mode", { active: 0 }, true);
    }
    msg("Menyimpan…");
    p.then(function (s) {
      try { sessionStorage.removeItem("rn_opmode"); } catch (e) { /* cache status di rn-public-header.js */ }
      render(s); msg(s.operational ? "✓ Mode Operasional Riil AKTIF." : "✓ Kembali ke mode simulasi."); })
      .catch(function (e) { msg("✗ " + (e && e.message || e), true); });
  }

  function mark(sel) {
    var ev = sel.getAttribute("data-ev");
    msg("Menyimpan tanda bencana…");
    call("set_event_simulation", { event: ev, simulation: sel.value }, true)
      .then(function (s) { render(s); msg("✓ Tanda bencana disimpan."); })
      .catch(function (e) { msg("✗ " + (e && e.message || e), true); });
  }

  function init() {
    var section = $("operationalModeSection");
    if (!section || loaded || pending || !window.RN_FRAPPE) return;
    pending = true;
    call("admin_status").then(function (s) {
      loaded = true;
      section.hidden = false;
      render(s);
      $("opModeToggle").addEventListener("click", toggle);
      $("opModeEvents").addEventListener("change", function (e) {
        if (e.target && e.target.matches("select[data-ev]")) mark(e.target);
      });
    }).catch(function () { section.hidden = true; /* bukan System Manager / belum login */ })
      .then(function () { pending = false; });
  }

  document.addEventListener("DOMContentLoaded", init);
  window.addEventListener("rn:frappe-session", init);
})();
