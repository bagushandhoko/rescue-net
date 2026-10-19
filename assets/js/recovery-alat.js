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

  function toolCell(a) {
    if (!a || !a.obyek) return '<span class="rn-muted">belum ada obyek kerja</span>';
    var gap = Math.max(0, (a.diminta || 0) - (a.dikerahkan || 0));
    return fmt(a.dikerahkan) + " / " + fmt(a.diminta) + " dikerahkan" +
      '<span class="rn-ra-sub">' + fmt(a.obyek) + " obyek kerja" + (gap ? " · kurang " + fmt(gap) : "") + "</span>";
  }

  function usageCell(r) {
    if (!r.available_from && !r.available_until) return '<span class="rn-muted">belum diisi</span>';
    var from = r.available_from ? day(r.available_from) : "sekarang";
    var until = r.available_until ? day(r.available_until) : "tanpa batas";
    var days = "";
    if (r.available_until) {
      var a = r.available_from ? new Date(r.available_from) : new Date();
      var b = new Date(r.available_until);
      var n = Math.round((b - a) / 86400000) + 1;
      if (n > 0) days = '<span class="rn-ra-sub">± ' + fmt(n) + " hari</span>";
    }
    return esc(from) + " – " + esc(until) + days;
  }

  var SUPPORT_LABEL = { transport: "Transport", operator: "Operator", bbm: "BBM" };
  function supportCell(r) {
    var tags = (r.support || []).map(function (k) { return '<span class="chip warning">' + esc(SUPPORT_LABEL[k] || k) + "</span>"; });
    if (r.daily_cost) tags.push('<span class="chip">' + esc(rpShort(r.daily_cost)) + "/hari</span>");
    var html = tags.length ? '<div class="rn-ra-tags">' + tags.join("") + "</div>" : "";
    if (r.support_notes) html += '<span class="rn-ra-sub">' + esc(r.support_notes) + "</span>";
    return html || '<span class="rn-muted">belum diisi</span>';
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
        "<td>" + toolCell(p.alat) + "</td>" +
        "<td>" + esc(day(p.target_finish_date)) + "</td>" +
        "<td>" + (u ? esc(u.title) + '<span class="rn-ra-sub">' + esc(day(u.at)) + "</span>" : '<span class="rn-muted">belum ada</span>') + "</td>" +
        "</tr>";
    }).join("") : '<tr><td colspan="7">Belum ada rencana rekonstruksi untuk bencana ini. Tambahkan lewat tombol di bawah.</td></tr>';
    var obj = $("#objectRecoverySelect");
    if (obj) obj.innerHTML = '<option value="">— tidak terkait proyek —</option>' + PROJECTS.map(function (p) {
      return '<option value="' + esc(p.name) + '">' + esc(p.title) + "</option>";
    }).join("");
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
      ? '<tr><td colspan="8"><button type="button" class="btn ghost" id="raProvMore">Lihat semua ' + fmt(total) + " alat</button></td></tr>" : "";
    $("#raProvBody").innerHTML = (rows.length ? rows.map(function (r) {
      return "<tr>" +
        "<td><b>" + esc(r.resource_name) + '</b><span class="rn-ra-sub">' + esc(r.category || "") + "</span></td>" +
        '<td class="num">' + fmt(r.quantity || 1) + " " + esc(r.unit || "") + "</td>" +
        "<td>" + esc(r.provider || "-") + "</td>" +
        "<td>" + esc(r.location && r.location !== "-" ? r.location : "-") +
          (r.coverage ? '<span class="rn-ra-sub">layanan: ' + esc(r.coverage) + "</span>" : "") + "</td>" +
        "<td>" + usageCell(r) + "</td>" +
        "<td>" + supportCell(r) + "</td>" +
        "<td>" + esc(AVAIL[r.status] || r.status || "-") + "</td>" +
        '<td><button type="button" class="btn ghost mini" data-ra-edit="' + esc(r.code) + '">Ubah</button></td></tr>';
    }).join("") : '<tr><td colspan="8">' + (REGISTRY.length ? "Tidak ada yang cocok." : "Belum ada alat terdaftar untuk bencana ini.") + "</td></tr>") + more;
    var btn = $("#raProvMore");
    if (btn) btn.addEventListener("click", function () { SHOW_ALL = true; renderProviders(); });
    document.querySelectorAll("[data-ra-edit]").forEach(function (b) {
      b.addEventListener("click", function () { openEdit(b.getAttribute("data-ra-edit")); });
    });
  }

  async function openEdit(code) {
    var r = REGISTRY.filter(function (x) { return x.code === code; })[0];
    var f = $("#raEditForm");
    if (!r || !f) return;
    var s = await session();
    f.hidden = false;
    $("#raEditTitle").textContent = "Ubah masa pakai & dukungan — " + r.resource_name + " (" + (r.provider || "-") + ")";
    f.resource_profile.value = r.code;
    f.available_from.value = r.available_from || "";
    f.available_until.value = r.available_until || "";
    f.daily_operating_cost.value = r.daily_cost || "";
    f.support_notes.value = r.support_notes || "";
    f.support_transport.checked = (r.support || []).indexOf("transport") >= 0;
    f.support_operator.checked = (r.support || []).indexOf("operator") >= 0;
    f.support_fuel.checked = (r.support || []).indexOf("bbm") >= 0;
    $("#raEditMsg").innerHTML = (!s || s.user === "Guest")
      ? 'Perlu login sebagai pemilik/pengelola alat. <a href="auth.html?next=' + encodeURIComponent(location.pathname + location.search + "#penyedia") + '">Login</a>' : "";
    f.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  async function loadRecovery() {
    try {
      renderRecovery(await window.RN_FRAPPE.call("rescue_net.api_recovery.recovery_board", { disaster_event: eventId() }));
    } catch (err) {
      $("#raBody").innerHTML = '<tr><td colspan="7">Gagal memuat: ' + esc((err && err.message) || err) + "</td></tr>";
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
    var edit = $("#raEditForm");
    if (edit) {
      $("#raEditCancel").addEventListener("click", function () { edit.hidden = true; });
      edit.addEventListener("submit", async function (e) {
        e.preventDefault();
        var msg = $("#raEditMsg");
        msg.textContent = "Menyimpan…";
        try {
          await window.RN_FRAPPE.call("rescue_net.api_resource_tools.update_resource_profile", {
            resource_profile: edit.resource_profile.value,
            available_from: edit.available_from.value, available_until: edit.available_until.value,
            daily_operating_cost: edit.daily_operating_cost.value, support_notes: edit.support_notes.value,
            support_transport: edit.support_transport.checked ? 1 : 0,
            support_operator: edit.support_operator.checked ? 1 : 0,
            support_fuel: edit.support_fuel.checked ? 1 : 0
          }, { method: "POST" });
          msg.textContent = "Tersimpan. Memuat ulang…";
          location.reload();
        } catch (err) {
          var m = (err && err.message) || String(err);
          msg.textContent = "Gagal: " + m + (/akses|permission|login/i.test(m) ? " (hanya pemilik/pengelola alat ini)" : "");
        }
      });
    }
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
