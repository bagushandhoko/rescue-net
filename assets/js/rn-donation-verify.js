/* Pengaturan Sistem RN > Verifikasi Pengelola Donasi (owner 2026-11-24). Super admin saja (server menolak lainnya). */
(function () {
  "use strict";
  var API = "rescue_net.api_donor_program.";
  var esc = function (t) { return String(t == null ? "" : t).replace(/[&<>"']/g, function (c) { return "&#" + c.charCodeAt(0) + ";"; }); };
  var box = function () { return document.getElementById("donVerifyList"); };

  function row(r) {
    var pay = [r.has_bank ? "rekening" : "", r.has_qris ? "QRIS" : ""].filter(Boolean).join(" + ") || "belum isi rekening/QRIS";
    var btn = r.verified ? '<span class="chip success">✔ terverifikasi</span>' :
      (r.action ? '<button type="button" class="btn primary mini" data-verify="' + esc(r.program) + '">' +
        (r.action.type === "vouch" ? "Jamin anggota pembuat" : "Verifikasi " + (r.action.kind === "posko" ? "posko" : "organisasi")) + "</button>" :
        '<span class="chip warning">periksa manual</span>');
    return '<div class="rn-donverify-row' + (r.verified ? " is-ok" : "") + '">' +
      '<div><b><a href="program-khusus.html?event=' + encodeURIComponent(r.disaster_event || "") + "&program=" + encodeURIComponent(r.program) + '" target="_blank" rel="noopener">' +
      esc(r.program_name) + "</a></b>" + (r.simulation ? ' <span class="chip neutral">simulasi</span>' : "") +
      "<small>" + esc(r.event_title || "-") + "</small>" +
      "<small>Pemrakarsa: " + esc(r.owner_title || "-") + " (" + esc(r.owner_type) + ", status: " + esc(r.owner_status || "-") + ")" +
      (r.creator ? " · dibuat oleh " + esc(r.creator) : "") + "</small>" +
      "<small>" + esc(pay) + (r.pending_donations ? " · " + r.pending_donations + " donasi menunggu konfirmasi" : "") + "</small>" +
      (r.reason ? '<small class="rn-donverify-reason">' + esc(r.reason) + "</small>" : "") +
      '</div><div class="rn-donverify-act">' + btn + '<span class="form-message" data-msg="' + esc(r.program) + '"></span></div></div>';
  }

  async function load() {
    var el = box(); if (!el || !window.RN_FRAPPE) return;
    el.innerHTML = '<p class="subtitle">Memuat…</p>';
    var all = document.getElementById("donVerifyAll"), sim = document.getElementById("donVerifySim");
    var d;
    try { d = await window.RN_FRAPPE.call(API + "initiator_queue", { include_verified: all && all.checked ? 1 : 0 }); }
    catch (e) { el.innerHTML = '<p class="subtitle">Gagal memuat: ' + esc(e && e.message || e) + "</p>"; return; }
    var rows = (d.rows || []).filter(function (r) { return !sim || sim.checked || !r.simulation; });
    el.innerHTML = '<p class="subtitle">' + rows.filter(function (r) { return !r.verified; }).length + " program menunggu verifikasi pemrakarsa.</p>" +
      (rows.length ? rows.map(row).join("") : '<p class="subtitle">Tidak ada program yang menunggu. 👍</p>');
    el.querySelectorAll("[data-verify]").forEach(function (b) {
      b.addEventListener("click", async function () {
        var prog = b.getAttribute("data-verify"), msg = el.querySelector('[data-msg="' + prog + '"]');
        if (!confirm("Verifikasi pemrakarsa program ini? Rekening/QRIS-nya akan tampil ke publik.")) return;
        b.disabled = true; msg.textContent = "Memproses…";
        try {
          var r = await window.RN_FRAPPE.call(API + "verify_initiator", { program: prog });
          msg.textContent = r.verified ? "✔ Terverifikasi — rekening/QRIS kini tampil ke publik." : "Belum terverifikasi, periksa manual.";
          setTimeout(load, 1200);
        } catch (e) { msg.textContent = "✗ " + (e && e.message || e); b.disabled = false; }
      });
    });
  }

  window.RNDonVerify = { load: load };
  document.addEventListener("change", function (e) {
    if (e.target && (e.target.id === "donVerifyAll" || e.target.id === "donVerifySim")) load();
  });
})();
