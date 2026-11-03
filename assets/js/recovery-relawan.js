/* recovery-relawan.js — Kebutuhan Relawan Recovery (owner 2026-11-03: "untuk recovery ini juga selain alat
   juga kebutuhan relawan"). api_recovery_support.volunteer_needs (guest) + signup (login) + project-owner
   management (create need, list signups with contact, confirm / reject, close). */
(function () {
  "use strict";
  var A = "rescue_net.api_recovery_support.";
  var $ = function (s, r) { return (r || document).querySelector(s); };
  function esc(s) { return window.RNUI.esc(s); }
  function fmt(n) { return window.RNUI.fmt(n); }
  function eventId() { return window.RNUI.eventId(); }
  function day(s) { return s ? String(s).slice(0, 10).split("-").reverse().join("/") : ""; }
  function errMsg(e) { return (e && e.message) || String(e); }
  function call(m, args, post) { return window.RN_FRAPPE.call(A + m, args || {}, post ? { method: "POST" } : undefined); }
  var STATUS = { open: ["Butuh relawan", "warning"], filled: ["Terpenuhi", "success"], closed: ["Ditutup", "neutral"] };
  var SIGN = { requested: "Menunggu", confirmed: "Diterima", rejected: "Ditolak", cancelled: "Dibatalkan" };
  var DATA = null;

  function loginLink() {
    return '<a href="auth.html?next=' + encodeURIComponent(location.pathname + location.search + "#relawan-recovery") + '">Login</a>';
  }

  function card(n) {
    var st = STATUS[n.need_status] || [n.need_status, "neutral"];
    var when = [day(n.date_from), day(n.date_to)].filter(Boolean).join(" – ");
    var rows = [
      ["Proyek", n.project_title + (n.project_owner ? " · " + n.project_owner : "")],
      ["Lokasi", n.location], ["Waktu", when], ["Tugas", n.task_description],
      ["Syarat", n.requirements], ["Disediakan", n.provisions],
    ].filter(function (r) { return r[1]; });
    var mine = n.my_signup;
    var act = "";
    if (mine) {
      act += '<span class="chip success">Anda terdaftar · ' + esc(SIGN[mine.status] || mine.status) + "</span>" +
        ' <button type="button" class="btn ghost mini" data-rv-cancel="' + esc(mine.signup) + '">Batalkan</button>';
    } else if (n.need_status === "open") {
      act += '<button type="button" class="btn primary mini" data-rv-join="' + esc(n.name) + '">Daftar jadi relawan</button>';
    }
    if (n.can_manage) {
      act += ' <button type="button" class="btn ghost mini" data-rv-list="' + esc(n.name) + '">Pendaftar (' + fmt(n.requested + n.confirmed) + ")</button>" +
        (n.need_status !== "closed"
          ? ' <button type="button" class="btn ghost mini" data-rv-close="' + esc(n.name) + '">Tutup</button>'
          : ' <button type="button" class="btn ghost mini" data-rv-open="' + esc(n.name) + '">Buka lagi</button>');
    }
    return '<article class="rn-rv-card" data-need="' + esc(n.name) + '">' +
      '<span class="chip ' + st[1] + '">' + esc(st[0]) + "</span> " +
      '<span class="chip">' + fmt(n.confirmed) + " / " + fmt(n.people_needed) + " orang diterima</span>" +
      (n.requested ? ' <span class="chip neutral">' + fmt(n.requested) + " menunggu</span>" : "") +
      "<h4>" + esc(n.role_needed) + " — " + fmt(n.people_needed) + " orang</h4>" +
      '<div class="rn-rv-meta">' + rows.map(function (r) { return "<span><b>" + esc(r[0]) + ":</b> " + esc(r[1]) + "</span>"; }).join("") + "</div>" +
      '<div class="rn-rv-actions">' + act + '<span class="rn-muted" data-rv-msg></span></div>' +
      '<div data-rv-box></div></article>';
  }

  async function load() {
    try { DATA = await call("volunteer_needs", { disaster_event: eventId() }); }
    catch (e) { $("#rvList").innerHTML = '<p class="rn-muted">Gagal memuat: ' + esc(errMsg(e)) + "</p>"; return; }
    var t = DATA.totals || {};
    $("#rvCount").textContent = fmt(t.open) + " terbuka · " + fmt(t.confirmed) + "/" + fmt(t.people_needed) + " orang";
    var needs = DATA.needs || [];
    $("#rvList").innerHTML = needs.length ? needs.map(card).join("")
      : '<p class="rn-muted">Belum ada kebutuhan relawan untuk proyek recovery bencana ini.</p>';
    var drawer = $("#rvDrawer"), sel = $("#rvProject");
    var projects = DATA.managed_projects || [];
    if (drawer) drawer.hidden = !projects.length;
    if (sel) sel.innerHTML = projects.map(function (p) { return '<option value="' + esc(p.name) + '">' + esc(p.title) + "</option>"; }).join("");
  }

  function joinForm(box, need) {
    if (!DATA.logged_in) { box.innerHTML = "Perlu login untuk mendaftar. " + loginLink(); return; }
    box.innerHTML = '<div class="rn-form rn-rv-box" style="display:grid;gap:6px;max-width:460px">' +
      '<input data-f="phone" placeholder="HP / WhatsApp (kosong = nomor di akun)">' +
      '<input data-f="skill" placeholder="Keahlian / pengalaman">' +
      '<div style="display:flex;gap:6px;flex-wrap:wrap"><label>Bisa mulai <input data-f="date_from" type="date"></label>' +
      '<label>Sampai <input data-f="date_to" type="date"></label></div>' +
      '<textarea data-f="note" rows="2" placeholder="Catatan (opsional)"></textarea>' +
      '<div><button type="button" class="btn primary mini" data-rv-send>Kirim pendaftaran</button> <span class="rn-muted" data-rv-smsg></span></div></div>';
    box.querySelector("[data-rv-send]").addEventListener("click", async function () {
      var g = function (k) { return box.querySelector('[data-f="' + k + '"]').value.trim(); };
      var m = box.querySelector("[data-rv-smsg]");
      m.textContent = "Mengirim…";
      try {
        await call("signup_volunteer_need", { need: need, phone: g("phone"), skill: g("skill"), note: g("note"),
          date_from: g("date_from"), date_to: g("date_to") }, true);
        await load();
      } catch (e) { m.textContent = "Gagal: " + errMsg(e); }
    });
  }

  async function signupList(box, need) {
    box.innerHTML = '<div class="rn-rv-box">memuat…</div>';
    var d;
    try { d = await call("need_signups", { need: need }); }
    catch (e) { box.innerHTML = '<div class="rn-rv-box">Gagal: ' + esc(errMsg(e)) + "</div>"; return; }
    var rows = d.signups || [];
    box.innerHTML = '<div class="rn-rv-box">' + (rows.length ? rows.map(function (s) {
      var when = [day(s.date_from), day(s.date_to)].filter(Boolean).join(" – ");
      return '<div class="rn-rv-sign"><b>' + esc(s.volunteer_name || "-") + "</b>" +
        (s.skill ? '<span class="rn-muted">' + esc(s.skill) + "</span>" : "") +
        (when ? '<span class="rn-muted">' + esc(when) + "</span>" : "") +
        (s.phone ? (s.whatsapp_url ? '<a href="' + esc(s.whatsapp_url) + '" target="_blank" rel="noopener">WA ' + esc(s.phone) + "</a>" : esc(s.phone)) : "") +
        '<span class="chip ' + (s.status === "confirmed" ? "success" : "neutral") + '">' + esc(SIGN[s.status] || s.status) + "</span>" +
        (s.status === "requested" ? '<button type="button" class="btn primary mini" data-dec="confirmed" data-s="' + esc(s.name) + '">Terima</button>' : "") +
        (s.status === "requested" || s.status === "confirmed" ? '<button type="button" class="btn ghost mini" data-dec="rejected" data-s="' + esc(s.name) + '">Tolak</button>' : "") +
        (s.note ? '<span class="rn-muted" style="flex-basis:100%">' + esc(s.note) + "</span>" : "") + "</div>";
    }).join("") : '<span class="rn-muted">Belum ada pendaftar.</span>') + "</div>";
    box.querySelectorAll("[data-dec]").forEach(function (b) {
      b.addEventListener("click", async function () {
        try {
          await call("decide_signup", { signup: b.getAttribute("data-s"), status: b.getAttribute("data-dec") }, true);
          await load();
          var card = document.querySelector('#rvList [data-need="' + need + '"]');
          if (card) signupList(card.querySelector("[data-rv-box]"), need);
        } catch (e) { window.alert("Gagal: " + errMsg(e)); }
      });
    });
  }

  function wire() {
    $("#rvList").addEventListener("click", async function (e) {
      var b = e.target.closest("button");
      if (!b) return;
      var card = b.closest("[data-need]");
      var box = card.querySelector("[data-rv-box]");
      var msg = card.querySelector("[data-rv-msg]");
      try {
        if (b.dataset.rvJoin) joinForm(box, b.dataset.rvJoin);
        else if (b.dataset.rvList) signupList(box, b.dataset.rvList);
        else if (b.dataset.rvCancel) {
          if (window.confirm && !window.confirm("Batalkan pendaftaran Anda?")) return;
          await call("cancel_my_signup", { signup: b.dataset.rvCancel }, true); await load();
        } else if (b.dataset.rvClose) {
          await call("update_volunteer_need", { need: b.dataset.rvClose, need_status: "closed" }, true); await load();
        } else if (b.dataset.rvOpen) {
          await call("update_volunteer_need", { need: b.dataset.rvOpen, need_status: "open" }, true); await load();
        }
      } catch (err) { msg.textContent = " Gagal: " + errMsg(err); }
    });
    var f = $("#rvForm");
    if (f) f.addEventListener("submit", async function (e) {
      e.preventDefault();
      var m = $("#rvMsg"), fd = new FormData(f), args = {};
      fd.forEach(function (v, k) { args[k] = String(v).trim(); });
      m.textContent = "Menyimpan…";
      try { await call("create_volunteer_need", args, true); m.textContent = "Tersimpan."; f.reset(); await load(); }
      catch (err) { m.textContent = "Gagal: " + errMsg(err); }
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    if (!window.RN_FRAPPE || !$("#rvList")) return;
    wire();
    load();
  });
})();
