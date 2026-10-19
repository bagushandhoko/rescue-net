/* ============================================================
 * recovery-alat.js — "Recovery dan Alat Kerja" (owner 2026-10-19):
 * step 1 (Obyek Recovery & Rencana Rekonstruksi, from
 * api_recovery.recovery_board, guest-safe) and step 3 "Penyedia Alat"
 * (asset_registry of api_resource_tools.tools_board, handed over by
 * alat-kerja.js through the "rn:ak-board" event — no second fetch).
 * Writes (new plan / progress) use api_recovery.create_project /
 * create_update and need a logged-in organisation member.
 * ============================================================ */
(function () {
  "use strict";

  var $ = function (s) { return document.querySelector(s); };
  var esc = function (s) { return window.RNUI.esc(s); };
  var fmt = function (n) { return window.RNUI.fmt(n); };
  var STATUS = { planned: "Direncanakan", in_progress: "Berjalan", active: "Berjalan", on_hold: "Tertunda",
                 completed: "Selesai", selesai: "Selesai", cancelled: "Batal" };
  var AVAIL = { available: "Siap", ready: "Siap", assigned: "Sedang dipakai", in_use: "Sedang dipakai",
                maintenance: "Perawatan", unavailable: "Tidak tersedia", broken: "Rusak", limited: "Terbatas" };
  var SHOW_ALL = false;
  var PROJECTS = [];
  var REGISTRY = [];
  var SESSION = null;

  function eventId() { return window.RNUI.eventId(); }
  function day(s) { return s ? String(s).slice(0, 10).split("-").reverse().join("/") : "-"; }
  function rpShort(n) {
    n = Number(n || 0);
    if (n >= 1e9) return "Rp " + fmt(Math.round(n / 1e7) / 100) + " M";
    if (n >= 1e6) return "Rp " + fmt(Math.round(n / 1e4) / 100) + " jt";
    return "Rp " + fmt(Math.round(n));
  }
  function bar(p) {
    p = Math.max(0, Math.min(100, Number(p || 0)));
    var tone = p < 40 ? " low" : p < 80 ? " mid" : "";
    return '<div class="rn-ra-bar' + tone + '"><span style="width:' + p + '%"></span></div><span class="rn-ra-sub">' + fmt(p) + "%</span>";
  }

  function renderRecovery(data) {
    PROJECTS = data.projects || [];
    var t = data.totals || {};
    $("#raCount").textContent = fmt(t.projects) + " proyek";
    $("#raSum").innerHTML = PROJECTS.length ? [
      "Rata-rata progres " + fmt(t.rata_progress) + "%",
      fmt(t.selesai) + " selesai",
      "Anggaran " + rpShort(t.anggaran_target) + " · terkumpul " + rpShort(t.anggaran_terkumpul)
    ].map(function (x) { return '<span class="chip">' + esc(x) + "</span>"; }).join("") : "";
    $("#raBody").innerHTML = PROJECTS.length ? PROJECTS.map(function (p) {
      var u = p.last_update;
      return "<tr>" +
        "<td><b>" + esc(p.title) + "</b>" +
          '<span class="rn-ra-sub">' + esc([STATUS[p.status] || p.status, p.target].filter(Boolean).join(" · ")) + "</span></td>" +
        "<td>" + esc(p.location || "-") + "</td>" +
        "<td>" + esc(p.owner || "-") + "</td>" +
        "<td>" + bar(p.progress) + "</td>" +
        "<td>" + esc(day(p.target_finish_date)) + "</td>" +
        "<td>" + (u ? esc(u.title) + '<span class="rn-ra-sub">' + esc(day(u.at)) + "</span>" : '<span class="rn-muted">belum ada</span>') + "</td>" +
        "</tr>";
    }).join("") : '<tr><td colspan="6">Belum ada rencana rekonstruksi untuk bencana ini. Tambahkan lewat tombol di bawah.</td></tr>';
    var sel = $("#raUpdateProject");
    if (sel) sel.innerHTML = PROJECTS.map(function (p) {
      return '<option value="' + esc(p.name) + '">' + esc(p.title) + " (" + fmt(p.progress) + "%)</option>";
    }).join("");
  }

  function renderProviders() {
    var q = String(($("#raProvSearch") || {}).value || "").trim().toLowerCase();
    var rows = REGISTRY.filter(function (r) {
      return !q || [r.resource_name, r.category, r.provider, r.location, r.coverage].join(" ").toLowerCase().indexOf(q) >= 0;
    });
    var total = rows.length;
    if (!SHOW_ALL && !q) rows = rows.slice(0, 10);
    var more = total > rows.length
      ? '<tr><td colspan="6"><button type="button" class="btn ghost" id="raProvMore">Lihat semua ' + fmt(total) + " alat</button></td></tr>" : "";
    $("#raProvBody").innerHTML = (rows.length ? rows.map(function (r) {
      return "<tr>" +
        "<td><b>" + esc(r.resource_name) + '</b><span class="rn-ra-sub">' + esc(r.category || "") + "</span></td>" +
        '<td class="num">' + fmt(r.quantity || 1) + " " + esc(r.unit || "") + "</td>" +
        "<td>" + esc(r.provider || "-") + "</td>" +
        "<td>" + esc(r.location && r.location !== "-" ? r.location : "-") + "</td>" +
        "<td>" + esc(r.coverage || "-") + "</td>" +
        "<td>" + esc(AVAIL[r.status] || r.status || "-") + "</td></tr>";
    }).join("") : '<tr><td colspan="6">' + (REGISTRY.length ? "Tidak ada yang cocok." : "Belum ada alat terdaftar untuk bencana ini.") + "</td></tr>") + more;
    var btn = $("#raProvMore");
    if (btn) btn.addEventListener("click", function () { SHOW_ALL = true; renderProviders(); });
  }

  async function loadRecovery() {
    try {
      renderRecovery(await window.RN_FRAPPE.call("rescue_net.api_recovery.recovery_board", { disaster_event: eventId() }));
    } catch (err) {
      $("#raBody").innerHTML = '<tr><td colspan="6">Gagal memuat: ' + esc((err && err.message) || err) + "</td></tr>";
    }
  }

  async function session() {
    if (SESSION) return SESSION;
    try { SESSION = await window.RN_FRAPPE.call("rescue_net.api_auth.session_info"); } catch (e) { SESSION = { user: "Guest" }; }
    return SESSION;
  }

  function wireForms() {
    var create = $("#raCreateForm"), update = $("#raUpdateForm");
    if (create) create.addEventListener("submit", async function (e) {
      e.preventDefault();
      var msg = $("#raCreateMsg"), s = await session();
      if (!s || s.user === "Guest") { msg.innerHTML = 'Perlu login. <a href="auth.html?next=' + encodeURIComponent(location.pathname + location.search) + '">Login</a>'; return; }
      if (!s.organization_id) { msg.textContent = "Akun Anda belum tercatat sebagai anggota organisasi, jadi belum bisa membuat rencana."; return; }
      var f = new FormData(create);
      msg.textContent = "Menyimpan…";
      try {
        await window.RN_FRAPPE.call("rescue_net.api_recovery.create_project", {
          disaster_event_id: eventId(), project_name: f.get("project_name"), project_type: f.get("project_type"),
          owner_type: "organization", owner_id: s.organization_id, location: f.get("location"),
          target_description: f.get("target_description"), target_amount: f.get("target_amount") || 0,
          target_finish_date: f.get("target_finish_date") || null, status: "planned"
        }, { method: "POST" });
        msg.textContent = "Tersimpan.";
        create.reset();
        loadRecovery();
      } catch (err) { msg.textContent = "Gagal: " + ((err && err.message) || err); }
    });
    if (update) update.addEventListener("submit", async function (e) {
      e.preventDefault();
      var msg = $("#raUpdateMsg"), s = await session();
      if (!s || s.user === "Guest") { msg.innerHTML = 'Perlu login. <a href="auth.html?next=' + encodeURIComponent(location.pathname + location.search) + '">Login</a>'; return; }
      var f = new FormData(update);
      if (!f.get("project_id")) { msg.textContent = "Belum ada proyek untuk diperbarui."; return; }
      msg.textContent = "Menyimpan…";
      try {
        await window.RN_FRAPPE.call("rescue_net.api_recovery.create_update", {
          project_id: f.get("project_id"), disaster_event_id: eventId(), update_type: "progress",
          progress_percent: f.get("progress_percent"), update_title: f.get("update_title"),
          update_notes: f.get("update_notes") || null
        }, { method: "POST" });
        msg.textContent = "Progres tersimpan.";
        update.reset();
        loadRecovery();
      } catch (err) { msg.textContent = "Gagal: " + ((err && err.message) || err); }
    });
    var search = $("#raProvSearch");
    if (search) search.addEventListener("input", renderProviders);
  }

  document.addEventListener("rn:ak-board", function (e) {
    REGISTRY = (e.detail && e.detail.asset_registry) || [];
    renderProviders();
  });

  document.addEventListener("DOMContentLoaded", function () {
    if (!window.RN_FRAPPE) return;
    wireForms();
    loadRecovery();
  });
})();
