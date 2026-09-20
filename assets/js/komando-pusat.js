/* Komando Pusat — halaman pengelola pusat (skema koordinasi terpusat).
 *
 * Backend: rescue_net.api_command.*  (command_overview, create_command_account,
 * decide_command_request, set_command_account_active, reset_command_account_password,
 * my_command_requests). Aturan ada di server; halaman ini hanya menampilkan dan memanggil.
 */
(function () {
  "use strict";

  var API = "rescue_net.api_command.";
  var $ = function (id) { return document.getElementById(id); };
  var esc = function (v) {
    return String(v == null ? "" : v).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  };
  var state = { data: null, center: null, query: "" };

  var ACTION_LABEL = {
    create_posko: "Tambah posko", update_posko: "Ubah posko",
    set_posko_functions: "Ubah fungsi posko", create_account: "Tambah akun"
  };
  var ROLE_LABEL = {
    posko_operator: "Operator posko", medical_operator: "Operator medis",
    shelter_operator: "Operator shelter", community_coordinator: "Koordinator organisasi"
  };
  var STATUS_TAG = {
    pending: ["wait", "Menunggu"], applied: ["ok", "Diterapkan"], rejected: ["bad", "Ditolak"],
    failed: ["bad", "Gagal diterapkan"], withdrawn: ["", "Ditarik"], approved: ["ok", "Disetujui"]
  };

  function call(method, args, write) {
    return window.RN_FRAPPE.call(API + method, args || {}, write ? { method: "POST" } : {});
  }
  function errText(e) { return (e && e.message) || String(e || "Terjadi kesalahan"); }
  function fmtDt(v) { return v ? String(v).slice(0, 16).replace("T", " ") : "-"; }
  function tag(kind, text) { return '<span class="kp-tag ' + kind + '">' + esc(text) + "</span>"; }
  function setMsg(el, text, bad) { el.textContent = text || ""; el.style.color = bad ? "var(--red, #c0392b)" : ""; }

  // ---------- muat ----------

  async function load(center) {
    $("kpStatus").textContent = "Memuat…";
    try {
      var data = await call("command_overview", center ? { organization: center } : {});
      state.data = data; state.center = data.center.organization;
      showCenter();
    } catch (e) {
      await showNotice(e);
    }
  }

  async function showNotice(e) {
    $("kpCenterView").hidden = true;
    $("kpNotice").hidden = false;
    var msg = errText(e), loggedOut = /login|belum masuk|diperlukan|tidak ditemukan/i.test(msg);
    $("kpLoginBtn").hidden = !loggedOut;
    $("kpNoticeTitle").textContent = loggedOut ? "Masuk sebagai pengelola pusat" : "Anda bukan pengelola pusat komando";
    $("kpNoticeText").textContent = loggedOut
      ? "Halaman ini untuk pengelola organisasi berskema komando terpusat. Silakan masuk."
      : "Halaman ini untuk pemilik organisasi berskema komando terpusat. Skema dipilih sekali saat organisasi pusat didaftarkan. Jika organisasi Anda berada di bawah komando pusat, perubahan Anda diajukan ke pusat dan statusnya tampil di bawah.";
    $("kpStatus").textContent = loggedOut ? "Belum masuk" : "Akses pusat komando diperlukan";
    $("kpBadge").textContent = "Bukan pusat";
    if (!loggedOut) {
      try {
        var mine = await call("my_command_requests");
        renderMine((mine && mine.requests) || []);
      } catch (_) { /* tampilan tamu */ }
    }
  }

  function renderMine(rows) {
    $("kpMineWrap").hidden = !rows.length;
    $("kpMineTable").innerHTML = "<thead><tr><th>Diajukan</th><th>Ke pusat</th><th>Permintaan</th><th>Status</th><th>Catatan pusat</th></tr></thead><tbody>" +
      rows.map(function (r) {
        var st = STATUS_TAG[r.status] || ["", r.status];
        return "<tr><td>" + esc(fmtDt(r.requested_at)) + "</td><td>" + esc(r.command_title) + "</td><td>" + esc(ACTION_LABEL[r.action] || r.action) +
          "<small>" + esc(r.summary) + "</small></td><td>" + tag(st[0], st[1]) + "</td><td>" + esc(r.decision_note || "-") + "</td></tr>";
      }).join("") + "</tbody>";
  }

  // ---------- tampilan pusat ----------

  function showCenter() {
    var d = state.data;
    $("kpNotice").hidden = true;
    $("kpCenterView").hidden = false;
    $("kpTitle").textContent = "Komando Pusat — " + d.center.title;
    $("kpBadge").textContent = d.pending_count ? d.pending_count + " menunggu persetujuan" : "Tidak ada antrean";
    $("kpStatus").textContent = d.organizations.length + " organisasi · " + d.poskos.length + " posko · " + d.accounts.length + " akun";

    $("kpCenterPickWrap").hidden = d.centers.length < 2;
    $("kpCenterPick").innerHTML = d.centers.map(function (c) {
      return '<option value="' + esc(c.organization) + '"' + (c.organization === state.center ? " selected" : "") + ">" + esc(c.title) + "</option>";
    }).join("");

    renderKpis(); renderPending(); renderAccountForm(); renderOrgs(); renderAccounts(); renderHistory();
  }

  function renderKpis() {
    var d = state.data;
    var active = d.accounts.filter(function (a) { return a.status === "active"; }).length;
    var kp = [
      ["Organisasi", d.organizations.length, ""], ["Posko", d.poskos.length, ""],
      ["Akun aktif", active, ""], ["Menunggu persetujuan", d.pending_count, d.pending_count ? "warn" : ""]
    ];
    $("kpKpis").innerHTML = kp.map(function (k) {
      return '<div class="kp-kpi ' + k[2] + '"><b>' + esc(k[1]) + "</b><span>" + esc(k[0]) + "</span></div>";
    }).join("");
  }

  function renderNotifyInfo() {
    var rec = state.data.notify_recipients || [];
    var withPhone = rec.filter(function (r) { return r.has_phone; }), without = rec.filter(function (r) { return !r.has_phone; });
    $("kpNotifyInfo").textContent = "Permintaan baru dikabarkan lewat WhatsApp ke: " +
      (withPhone.length ? withPhone.map(function (r) { return r.name + (r.role === "deputy" ? " (wakil)" : ""); }).join(", ") : "belum ada penerima (isi nomor HP akun pengelola)") +
      (without.length ? ". Tanpa nomor HP: " + without.map(function (r) { return r.name; }).join(", ") + "." : ".");
  }

  function renderPending() {
    renderNotifyInfo();
    var rows = state.data.requests.filter(function (r) { return r.status === "pending"; });
    $("kpPending").innerHTML = rows.length ? rows.map(function (r) {
      return '<div class="kp-req" data-req="' + esc(r.name) + '">' +
        "<div><h4>" + esc(ACTION_LABEL[r.action] || r.action) + " — " + esc(r.organization_title) + "</h4>" +
        '<div class="kp-req-meta">' + esc(r.summary) + "</div>" +
        '<div class="kp-req-meta">Diajukan oleh ' + esc(r.requested_by_name || "-") + " · " + esc(fmtDt(r.requested_at)) + "</div></div>" +
        '<div class="kp-req-actions"><input type="text" maxlength="500" placeholder="Catatan (wajib jika menolak)" aria-label="Catatan keputusan">' +
        '<button type="button" class="btn primary mini" data-decide="approve">Setujui &amp; terapkan</button>' +
        '<button type="button" class="btn ghost mini" data-decide="reject">Tolak</button></div></div>';
    }).join("") : '<p class="kp-empty">Tidak ada permintaan yang menunggu.</p>';
  }

  function renderAccountForm() {
    var d = state.data;
    $("kpAccOrg").innerHTML = d.organizations.map(function (o) {
      return '<option value="' + esc(o.name) + '">' + esc(o.title) + (o.is_center ? " (pusat)" : "") + "</option>";
    }).join("");
    $("kpAccRole").innerHTML = d.account_roles.map(function (r) {
      return '<option value="' + esc(r) + '">' + esc(ROLE_LABEL[r] || r) + "</option>";
    }).join("");
    syncPoskoOptions();
  }

  function syncPoskoOptions() {
    var org = $("kpAccOrg").value;
    var poskos = state.data.poskos.filter(function (p) { return p.organization === org; });
    $("kpAccPosko").innerHTML = '<option value="">- Tanpa posko (koordinator) -</option>' + poskos.map(function (p) {
      return '<option value="' + esc(p.name) + '">' + esc(p.title || p.name) + "</option>";
    }).join("");
  }

  function renderOrgs() {
    var d = state.data;
    $("kpOrgTable").innerHTML = "<thead><tr><th>Organisasi</th><th>Skema</th><th>Posko</th><th>Akun</th></tr></thead><tbody>" +
      d.organizations.map(function (o) {
        var mine = d.poskos.filter(function (p) { return p.organization === o.name; });
        return "<tr><td><b>" + esc(o.title) + "</b>" + (o.is_center ? " " + tag("ok", "pusat") : "") +
          (o.parent_organization ? "<small>di bawah " + esc((d.organizations.find(function (x) { return x.name === o.parent_organization; }) || {}).title || o.parent_organization) + "</small>" : "") +
          "</td><td>" + esc(o.coordination_scheme === "terpusat" ? "Komando terpusat" : "Mandiri") + "</td><td>" +
          (mine.length ? mine.map(function (p) { return esc(p.title || p.name) + " <small>" + esc(p.posko_type || "") + " · " + esc(p.operational_status || "-") + "</small>"; }).join("") : '<span class="kp-empty">-</span>') +
          "</td><td>" + esc(o.account_count) + "</td></tr>";
      }).join("") + "</tbody>";
  }

  function renderAccounts() {
    var q = state.query;
    var rows = state.data.accounts.filter(function (a) {
      return !q || (a.name + " " + a.email + " " + (a.posko_title || "") + " " + a.organization_title).toLowerCase().indexOf(q) !== -1;
    });
    $("kpAccTable").innerHTML = "<thead><tr><th>Akun</th><th>Peran</th><th>Organisasi / Posko</th><th>Status</th><th>Aksi</th></tr></thead><tbody>" +
      (rows.length ? rows.map(function (a) {
        var owner = a.membership_role === "owner", deputy = a.membership_role === "deputy";
        var viewerOwner = !!state.data.viewer_is_owner;
        var on = a.status === "active";
        var roleLabel = owner ? "Pemilik (super admin)" : deputy ? "Wakil pusat" : (ROLE_LABEL[a.role] || a.role || "-");
        // owner accounts are never managed here; a deputy account only by the owner
        var canManage = !owner && (!deputy || viewerOwner);
        var canAppoint = viewerOwner && !owner && a.organization === state.center;
        return "<tr><td><b>" + esc(a.name) + "</b><small>" + esc(a.email) + "</small></td><td>" + esc(roleLabel) +
          "</td><td>" + esc(a.organization_title) + "<small>" + esc(a.posko_title || "-") + "</small></td><td>" + tag(on ? "ok" : "bad", on ? "Aktif" : a.status) + "</td><td>" +
          (!canManage && !canAppoint ? '<span class="kp-empty">-</span>' :
            '<div class="kp-btn-row" data-acc="' + esc(a.user_account) + '">' +
            (canManage ? (on ? '<button type="button" class="btn ghost mini" data-accact="suspend">Nonaktifkan</button>' : '<button type="button" class="btn ghost mini" data-accact="activate">Aktifkan</button>') +
              '<button type="button" class="btn ghost mini" data-accact="reset">Reset password</button>' : "") +
            (canAppoint ? (deputy ? '<button type="button" class="btn ghost mini" data-accact="deputy-off">Cabut wakil</button>' : '<button type="button" class="btn ghost mini" data-accact="deputy-on">Jadikan wakil pusat</button>') : "") +
            "</div>") + "</td></tr>";
      }).join("") : '<tr><td colspan="5" class="kp-empty">Belum ada akun.</td></tr>') + "</tbody>";
  }

  function renderHistory() {
    var rows = state.data.requests.filter(function (r) { return r.status !== "pending"; });
    $("kpHistTable").innerHTML = "<thead><tr><th>Diputuskan</th><th>Organisasi</th><th>Permintaan</th><th>Status</th><th>Catatan</th></tr></thead><tbody>" +
      (rows.length ? rows.map(function (r) {
        var st = STATUS_TAG[r.status] || ["", r.status];
        return "<tr><td>" + esc(fmtDt(r.decided_at || r.requested_at)) + "</td><td>" + esc(r.organization_title) + "</td><td>" + esc(ACTION_LABEL[r.action] || r.action) +
          "<small>" + esc(r.summary) + "</small></td><td>" + tag(st[0], st[1]) + "</td><td>" + esc(r.decision_note || r.apply_result || "-") + "</td></tr>";
      }).join("") : '<tr><td colspan="5" class="kp-empty">Belum ada riwayat.</td></tr>') + "</tbody>";
  }

  // ---------- aksi ----------

  function showSecret(email, pw) {
    $("kpSecretEmail").textContent = email;
    $("kpSecretPw").textContent = pw;
    $("kpSecretCopy").textContent = "Salin";
    $("kpSecret").hidden = false;
  }

  async function onDecide(btn) {
    var box = btn.closest("[data-req]");
    var decision = btn.getAttribute("data-decide");
    var note = box.querySelector("input").value.trim();
    if (decision === "reject" && !note) { box.querySelector("input").focus(); box.querySelector("input").placeholder = "Alasan penolakan wajib diisi"; return; }
    if (decision === "approve" && !window.confirm("Setujui dan terapkan perubahan ini sekarang?")) return;
    btn.disabled = true;
    try {
      var res = await call("decide_command_request", { request: box.getAttribute("data-req"), decision: decision, note: note }, true);
      if (res.temporary_password) showSecret(res.email, res.temporary_password);
      $("kpStatus").textContent = res.status === "failed" ? "Gagal diterapkan: " + (res.apply_result || "") : "Keputusan tersimpan (" + res.status + ")";
      await load(state.center);
      if (res.status === "failed") $("kpStatus").textContent = "Gagal diterapkan: " + (res.apply_result || "");
    } catch (e) { $("kpStatus").textContent = errText(e); btn.disabled = false; }
  }

  async function onAccountAction(btn) {
    var user = btn.closest("[data-acc]").getAttribute("data-acc");
    var act = btn.getAttribute("data-accact");
    btn.disabled = true;
    try {
      if (act === "suspend") {
        var why = window.prompt("Alasan menonaktifkan akun ini (wajib):");
        if (!why || !why.trim()) { btn.disabled = false; return; }
        await call("set_command_account_active", { user_account: user, active: 0, note: why.trim() }, true);
      } else if (act === "activate") {
        await call("set_command_account_active", { user_account: user, active: 1 }, true);
      } else if (act === "deputy-on" || act === "deputy-off") {
        var deputyOn = act === "deputy-on";
        if (!window.confirm(deputyOn ? "Jadikan akun ini wakil pusat? Ia dapat memutuskan permintaan, membuat akun, dan mengelola seluruh organisasi/posko di bawah komando (kecuali mengangkat wakil)." : "Cabut peran wakil pusat dari akun ini?")) { btn.disabled = false; return; }
        await call("set_command_deputy", { organization: state.center, user_account: user, active: deputyOn ? 1 : 0 }, true);
      } else if (act === "reset") {
        if (!window.confirm("Reset password akun ini? Semua sesi loginnya akan keluar.")) { btn.disabled = false; return; }
        var res = await call("reset_command_account_password", { user_account: user }, true);
        var acc = state.data.accounts.find(function (a) { return a.user_account === user; });
        showSecret(acc ? acc.email : user, res.temporary_password);
      }
      await load(state.center);
    } catch (e) { $("kpStatus").textContent = errText(e); btn.disabled = false; }
  }

  async function onCreateAccount(e) {
    e.preventDefault();
    var f = e.target, msg = $("kpAccMsg"), btn = f.querySelector("button[type=submit]");
    if (f.elements.password.value !== f.elements.password2.value) { setMsg(msg, "Konfirmasi password tidak sama.", true); return; }
    if (f.elements.role.value !== "community_coordinator" && !f.elements.posko.value) { setMsg(msg, "Pilih posko untuk akun operator.", true); return; }
    btn.disabled = true; setMsg(msg, "Membuat akun…");
    try {
      var res = await call("create_command_account", {
        organization: f.elements.organization.value, posko: f.elements.posko.value || "", role: f.elements.role.value,
        full_name: f.elements.full_name.value.trim(), email: f.elements.email.value.trim(), phone: f.elements.phone.value.trim(),
        password: f.elements.password.value
      }, true);
      setMsg(msg, "Akun " + res.email + " dibuat.");
      if (res.temporary_password) showSecret(res.email, res.temporary_password);
      f.reset(); syncPoskoOptions();
      await load(state.center);
    } catch (err) { setMsg(msg, errText(err), true); }
    btn.disabled = false;
  }

  // ---------- pasang ----------

  document.addEventListener("DOMContentLoaded", function () {
    if (!window.RN_FRAPPE) { $("kpStatus").textContent = "Frappe client tidak tersedia."; return; }
    $("kpCenterPick").addEventListener("change", function (e) { load(e.target.value); });
    $("kpAccOrg").addEventListener("change", syncPoskoOptions);
    $("kpAccountForm").addEventListener("submit", onCreateAccount);
    $("kpAccSearch").addEventListener("input", function (e) { state.query = e.target.value.trim().toLowerCase(); if (state.data) renderAccounts(); });
    $("kpSecretClose").addEventListener("click", function () { $("kpSecret").hidden = true; $("kpSecretPw").textContent = ""; });
    $("kpSecretCopy").addEventListener("click", async function () {
      try { await navigator.clipboard.writeText($("kpSecretPw").textContent); $("kpSecretCopy").textContent = "Tersalin"; } catch (_) { /* teks sudah bisa disalin manual */ }
    });
    $("kpPending").addEventListener("click", function (e) { var b = e.target.closest("[data-decide]"); if (b) onDecide(b); });
    $("kpAccTable").addEventListener("click", function (e) { var b = e.target.closest("[data-accact]"); if (b) onAccountAction(b); });
    load();
  });
})();
