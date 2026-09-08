/* ============================================================
 * Koordinasi Internal Organisasi — the org-member workspace.
 * Board: rescue_net.api_control_centre.my_org_coordination
 *
 * A logged-in org member sees his OWN posko (editable) plus his
 * organisation's other poskos and open external poskos (read-only).
 * The full cross-org picture stays on the Control Centre page.
 * ============================================================ */
(function () {
  "use strict";

  var BOARD = "rescue_net.api_control_centre.my_org_coordination";

  var $ = function (s, r) { return (r || document).querySelector(s); };
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  var qs = new URLSearchParams(location.search);
  function getEvent() { return qs.get("event") || "event-sim-001"; }

  var TYPE_LABEL = {
    logistics: "Logistik", collection_hub: "Gudang Pengumpul", transport: "Transport / Distribusi",
    medical: "Medis", shelter: "Shelter", kitchen: "Dapur Umum",
    field_assessment: "Assessment Lapangan", posko_operator: "Operator Posko", org_admin: "Admin Organisasi"
  };
  function typeLabel(t) { return TYPE_LABEL[String(t || "").toLowerCase()] || (t || "Posko"); }

  function statusChip(s) {
    var l = String(s || "").toLowerCase();
    var cls = "neutral", label = s || "normal";
    if (l === "critical") { cls = "danger"; label = "Kritis"; }
    else if (l === "urgent") { cls = "warning"; label = "Mendesak"; }
    else if (l === "active" || l === "normal") { cls = "success"; label = l === "active" ? "Aktif" : "Normal"; }
    return '<span class="chip ' + cls + '">' + esc(label) + "</span>";
  }

  function shareTag(mode) {
    return mode === "full"
      ? '<span class="ko-tag full">Detail terbuka</span>'
      : '<span class="ko-tag summary">Ringkasan</span>';
  }

  function card(c, opts) {
    opts = opts || {};
    var mine = !!opts.mine;
    var actions = [];
    if (c.can_edit) {
      actions.push('<a class="btn primary mini" href="' + esc(c.operate_href) + '">Kelola Posko</a>');
    }
    actions.push('<a class="btn ghost mini" href="' + esc(c.detail_href) + '">Lihat detail</a>');

    return (
      '<article class="ko-posko-card' + (mine ? " is-mine" : "") + '">' +
      '<div class="rn-row">' +
        (c.can_edit ? '<span class="ko-tag edit">Bisa dikelola</span>' : '<span class="ko-tag view">Hanya-lihat</span>') +
        shareTag(c.share_mode) +
      "</div>" +
      "<h4>" + esc(c.title) + "</h4>" +
      '<div class="ko-posko-meta">' + esc(typeLabel(c.posko_type)) + " · " + esc(c.city_name || "-") + "</div>" +
      '<div class="rn-row">' + statusChip(c.operational_status) +
        (window.RNVerifBadge ? window.RNVerifBadge.html(c.verification_status, c.trusted_verifier_count) : "") + "</div>" +
      '<div class="ko-card-actions">' + actions.join("") + "</div>" +
      "</article>"
    );
  }

  function setBrand(brand) {
    if (!brand) return;
    var shell = $("#koShell");
    if (shell && brand.accent) shell.style.setProperty("--ko-accent", brand.accent);
    var initial = $("#koInitial");
    if (initial) {
      if (brand.logo) {
        initial.innerHTML = '<img src="' + esc(brand.logo) + '" alt="" '
          + 'style="width:100%;height:100%;object-fit:cover;border-radius:inherit">';
        initial.style.background = "transparent";
        initial.hidden = false;
      } else if (brand.initial) {
        initial.textContent = brand.initial;
        initial.hidden = false;
      }
    }
    if (brand.title) {
      $("#koTitleText").textContent = brand.title;
      document.title = "Rescue-Net | Koordinasi " + brand.title;
    }
  }

  function showNotice(title, text, loginHref, ccHref) {
    $("#koNoticeTitle").textContent = title;
    $("#koNoticeText").textContent = text;
    if (loginHref) $("#koLoginBtn").href = loginHref;
    $("#koLoginBtn").hidden = !loginHref;
    if (ccHref) { $("#koNoticeCc").href = ccHref; $("#koFootCc").href = ccHref; }
    $("#koNoticeWrap").hidden = false;
  }

  function render(d) {
    var ev = getEvent();
    var ccHref = d.control_centre_href || ("war-room.html?event=" + ev);
    $("#koCcLink").href = ccHref;
    $("#koNoticeCc").href = ccHref;
    $("#koFootCc").href = ccHref;

    if (!d.logged_in) {
      $("#koStatus").textContent = "Belum masuk.";
      showNotice(
        "Masuk sebagai anggota organisasi",
        "Halaman ini untuk anggota organisasi yang terdaftar (mis. Komunitas Landrover). "
        + "Masuk dulu, atau lihat gambaran publik lintas organisasi di Control Centre.",
        d.login_href || window.RN_FRAPPE.loginUrl(), ccHref
      );
      return;
    }
    if (!d.is_org_member) {
      $("#koStatus").textContent = "Akun Anda belum terhubung ke organisasi.";
      showNotice(
        "Akun belum terhubung ke organisasi",
        "Akun Anda aktif tapi belum menjadi anggota organisasi mana pun, jadi tidak ada posko organisasi untuk dikoordinasikan. "
        + "Hubungi koordinator organisasi Anda, atau lihat Control Centre.",
        null, ccHref
      );
      return;
    }

    setBrand(d.brand);
    var t = d.totals || {};
    var roleTxt = d.actor && d.actor.role ? d.actor.role.replace(/_/g, " ") : "anggota";
    $("#koStatus").textContent =
      "Masuk sebagai " + roleTxt + " · " + (t.org_posko_count || 0) + " posko organisasi · "
      + (t.editable_count || 0) + " bisa Anda kelola · " + (t.open_external_count || 0) + " posko organisasi lain terbuka.";
    $("#koUpdated").textContent = (d.brand && d.brand.title ? d.brand.title : "Organisasi") + " · Koordinasi Internal";

    // Posko Saya
    var myWrap = $("#koMyPosko");
    if (d.my_posko) {
      myWrap.innerHTML = '<div class="ko-card-grid">' + card(d.my_posko, { mine: true }) + "</div>";
    } else if ((t.editable_count || 0) > 0) {
      myWrap.innerHTML =
        '<p class="ko-empty">Anda koordinator organisasi — tidak memegang satu posko tertentu, '
        + "tapi bisa mengelola semua posko organisasi di bawah ini.</p>";
    } else {
      myWrap.innerHTML =
        '<p class="ko-empty">Anda tidak memegang posko tertentu (mis. koordinator organisasi). '
        + "Semua posko di bawah ini hanya-lihat; kelola lewat operator posko masing-masing.</p>";
    }
    $("#koMyPoskoSection").hidden = false;

    // Posko Organisasi
    var org = d.my_org_poskos || [];
    $("#koOrgSectionTitle").textContent = "Posko " + (d.brand && d.brand.title ? d.brand.title : "Organisasi");
    $("#koOrgCount").textContent = org.length + " posko";
    $("#koOrgPoskos").innerHTML = org.length
      ? org.map(function (c) { return card(c); }).join("")
      : '<p class="ko-empty">Tidak ada posko lain di organisasi Anda untuk bencana ini.</p>';
    $("#koOrgSection").hidden = false;

    // Posko organisasi lain (terbuka)
    var ext = d.open_external_poskos || [];
    $("#koExtCount").textContent = ext.length + " posko";
    $("#koExtPoskos").innerHTML = ext.length
      ? ext.map(function (c) { return card(c); }).join("")
      : '<p class="ko-empty">Belum ada posko organisasi lain yang membuka detail koordinasi untuk bencana ini. '
        + "Sisanya bisa dilihat sebagai ringkasan di Control Centre.</p>";
    $("#koExtSection").hidden = false;

    $("#koFootNote").hidden = false;
  }

  function fmtDate(s) {
    if (!s) return "-";
    return String(s).slice(0, 16).replace("T", " ");
  }

  async function loadMembers() {
    var sec = $("#koMemberSection"), admin = $("#koMemberAdmin"), self = $("#koMemberSelf");
    var mine = { memberships: [] };
    try { mine = await window.RN_FRAPPE.call("rescue_net.api_community_cluster.my_memberships"); } catch (e) {}
    var adminData = { is_org_admin: false, memberships: [] };
    try { adminData = await window.RN_FRAPPE.call("rescue_net.api_community_cluster.org_membership_admin"); } catch (e) {}

    // ---- self: the caller's own membership status ----
    var ms = (mine && mine.memberships) || [];
    if (ms.length) {
      self.innerHTML = '<p class="rn-muted" style="margin:4px 0 8px">Keanggotaan Anda:</p>' +
        ms.map(function (m) {
          var badge = m.status === "approved"
            ? '<span class="ko-tag full">Anggota' + (m.member_verified ? " · terverifikasi pusat" : "") + "</span>"
            : '<span class="ko-tag summary">' + esc(m.status) + "</span>";
          return '<div class="rn-row" style="padding:4px 0">' + badge +
            " <b>" + esc(m.organization_title) + "</b> <span class=\"rn-muted\">(" + esc(m.membership_role) + ")</span></div>";
        }).join("");
    } else {
      self.innerHTML = '<p class="ko-empty">Anda belum tergabung sebagai anggota organisasi mana pun. ' +
        'Ajukan lewat halaman <a href="organisasi-posko.html">Organisasi &amp; Posko</a>.</p>';
    }

    // ---- admin: pending requests + roster for orgs the caller owns ----
    if (adminData && adminData.is_org_admin) {
      admin.hidden = false;
      var all = adminData.memberships || [];
      var pending = all.filter(function (m) { return m.status === "pending"; });
      var roster = all.filter(function (m) { return m.status === "approved"; });
      $("#koMemberCount").textContent = pending.length + " menunggu · " + roster.length + " anggota";

      $("#koMemberPending").innerHTML = pending.length ? pending.map(function (m) {
        return '<article class="ko-posko-card" data-mid="' + esc(m.name) + '">' +
          "<h4>" + esc(m.user_name) + "</h4>" +
          '<div class="ko-posko-meta">' + esc(m.user_email || m.user_phone || "-") +
          " · minta " + fmtDate(m.requested_at) + " · " + esc(m.organization_title) + "</div>" +
          '<label class="rn-row" style="font-size:12px"><input type="checkbox" class="koVerifyChk"> Identitas terverifikasi pusat</label>' +
          '<div class="ko-card-actions">' +
          '<button type="button" class="btn primary mini" data-act="approve">Setujui</button>' +
          '<button type="button" class="btn ghost mini" data-act="reject">Tolak</button>' +
          '<span class="rn-muted koMsg"></span></div></article>';
      }).join("") : '<p class="ko-empty">Tidak ada permohonan menunggu.</p>';

      $("#koMemberRoster").innerHTML = roster.length ? '<div class="ko-card-grid">' + roster.map(function (m) {
        var vtag = m.member_verified
          ? '<span class="ko-tag full">Terverifikasi pusat</span>'
          : '<span class="ko-tag view">Belum diverifikasi</span>';
        return '<article class="ko-posko-card" data-mid="' + esc(m.name) + '">' +
          '<div class="rn-row">' + vtag + (m.membership_role === "owner" ? '<span class="ko-tag edit">Owner</span>' : "") + "</div>" +
          "<h4>" + esc(m.user_name) + "</h4>" +
          '<div class="ko-posko-meta">' + esc(m.user_email || m.user_phone || "-") + " · " + esc(m.organization_title) + "</div>" +
          (m.membership_role === "owner" ? "" :
            '<div class="ko-card-actions">' +
            '<button type="button" class="btn ghost mini" data-act="toggle-verify">' +
            (m.member_verified ? "Cabut verifikasi" : "Verifikasi identitas") + "</button>" +
            '<button type="button" class="btn ghost mini" data-act="revoke">Keluarkan</button>' +
            '<span class="rn-muted koMsg"></span></div>') +
          "</article>";
      }).join("") + "</div>" : '<p class="ko-empty">Belum ada anggota disetujui.</p>';

      wireMemberActions();
    } else {
      admin.hidden = true;
      $("#koMemberCount").textContent = ms.length + " keanggotaan";
    }
    sec.hidden = false;
  }

  function wireMemberActions() {
    document.querySelectorAll("#koMemberAdmin [data-act]").forEach(function (btn) {
      btn.addEventListener("click", async function () {
        var card = btn.closest("[data-mid]");
        var mid = card.getAttribute("data-mid");
        var act = btn.getAttribute("data-act");
        var msg = card.querySelector(".koMsg");
        var chk = card.querySelector(".koVerifyChk");
        if (msg) msg.textContent = " memproses…";
        try {
          if (act === "toggle-verify") {
            var on = /Verifikasi identitas/.test(btn.textContent);
            await window.RN_FRAPPE.call("rescue_net.api_community_cluster.set_member_verified",
              { membership: mid, verified: on ? 1 : 0 }, { method: "POST" });
          } else {
            await window.RN_FRAPPE.call("rescue_net.api_community_cluster.decide_membership",
              { membership: mid, action: act, member_verified: (chk && chk.checked) ? 1 : 0 },
              { method: "POST" });
          }
          await loadMembers();
        } catch (err) {
          var m = (err && err.message) || String(err);
          if (msg) msg.textContent = " gagal: " + m;
        }
      });
    });
  }

  /* ---------- Organisasi Saya: hierarki + merger + kunci AI ---------- */
  var ORG_ADMIN = null;

  function mergeReqCard(r, kind) {
    var acts = "";
    if (r.status === "pending" && kind === "incoming") {
      acts =
        '<button type="button" class="btn primary mini" data-merge-act="approve" data-merge-id="' + esc(r.name) + '">Setujui (jadikan anak)</button>' +
        '<button type="button" class="btn ghost mini" data-merge-act="reject" data-merge-id="' + esc(r.name) + '">Tolak</button>';
    } else if (r.status === "pending" && kind === "outgoing") {
      acts = '<button type="button" class="btn ghost mini" data-merge-act="withdraw" data-merge-id="' + esc(r.name) + '">Tarik</button>';
    }
    var line = kind === "incoming"
      ? esc(r.requester_title) + " → minta jadi anak dari <b>" + esc(r.target_title) + "</b>"
      : "<b>" + esc(r.requester_title) + "</b> → minta jadi anak dari " + esc(r.target_title);
    return '<article class="ko-posko-card">' +
      '<div class="ko-posko-meta">' + line + "</div>" +
      '<div class="ko-posko-meta">status: ' + esc(r.status) +
        (r.note ? " · catatan: " + esc(r.note) : "") +
        (r.decision_note ? " · keputusan: " + esc(r.decision_note) : "") + "</div>" +
      (acts ? '<div style="margin-top:6px;display:flex;gap:6px;flex-wrap:wrap;align-items:center">' + acts + '<span class="koMergeMsg rn-muted"></span></div>' : "") +
      "</article>";
  }

  function renderOrgAdmin(d) {
    ORG_ADMIN = d;
    var sec = $("#koOrgAdminSection");
    if (!sec) return;
    if (!d || !d.is_org_admin || !(d.organizations || []).length) { sec.hidden = true; return; }
    sec.hidden = false;

    $("#koOrgAdminCount").textContent = d.organizations.length + " organisasi";

    $("#koOrgHierarchy").innerHTML = d.organizations.map(function (o) {
      var kids = (o.children || []).length
        ? "<ul>" + o.children.map(function (c) { return "<li>" + esc(c.title) + ' <span class="rn-muted">(' + esc(c.status) + ")</span></li>"; }).join("") + "</ul>"
        : '<div class="rn-muted">Belum ada sub-organisasi.</div>';
      return '<article class="ko-posko-card">' +
        "<h4>" + esc(o.title) + "</h4>" +
        '<div class="ko-posko-meta">' + esc(o.organization_type || "-") + " · " + esc(o.status || "-") +
          (o.parent_title ? " · induk: <b>" + esc(o.parent_title) + "</b>" : " · tidak punya induk") + "</div>" +
        '<div class="ko-posko-meta">Sub-organisasi:</div>' + kids +
        "</article>";
    }).join("");

    var reqOpts = d.organizations.map(function (o) {
      return '<option value="' + esc(o.name) + '">' + esc(o.title) + "</option>";
    }).join("");
    $("#koMergeRequester").innerHTML = reqOpts;
    $("#koAiKeyOrg").innerHTML = reqOpts;

    fillMergeTargets();

    $("#koMergeIncoming").innerHTML = (d.incoming_requests || []).length
      ? d.incoming_requests.map(function (r) { return mergeReqCard(r, "incoming"); }).join("")
      : '<div class="rn-muted">Tidak ada permintaan masuk.</div>';
    $("#koMergeOutgoing").innerHTML = (d.outgoing_requests || []).length
      ? d.outgoing_requests.map(function (r) { return mergeReqCard(r, "outgoing"); }).join("")
      : '<div class="rn-muted">Belum ada permintaan dikirim.</div>';

    wireOrgAdminActions();
    refreshAiKeyStatus();
  }

  async function fillMergeTargets() {
    var sel = $("#koMergeTarget");
    if (!sel || !ORG_ADMIN) return;
    var mine = {};
    (ORG_ADMIN.organizations || []).forEach(function (o) { mine[o.name] = 1; });
    var all = [];
    try { all = await window.RN_FRAPPE.call("rescue_net.api_community_cluster.list_organizations"); } catch (e) {}
    var opts = ['<option value="">— pilih —</option>'];
    (all || []).forEach(function (o) {
      if (mine[o.name]) return;
      opts.push('<option value="' + esc(o.name) + '">' + esc(o.title || o.name) + "</option>");
    });
    sel.innerHTML = opts.join("");
  }

  async function refreshAiKeyStatus() {
    var orgEl = $("#koAiKeyOrg"), provEl = $("#koAiKeyProvider"), el = $("#koAiKeyStatus");
    if (!orgEl || !el) return;
    var org = orgEl.value, provider = (provEl && provEl.value) || "openai";
    if (!org) { el.textContent = "—"; return; }
    el.textContent = "memeriksa…";
    try {
      var r = await window.RN_FRAPPE.call("rescue_net.api_ai.get_org_key_status",
        { organization_id: org, provider: provider });
      el.textContent = r && r.key_exists
        ? "Kunci aktif: " + (r.masked_key || "****") +
          (r.setting && r.setting.api_key_label ? " (" + r.setting.api_key_label + ")" : "")
        : "Belum ada kunci untuk provider ini.";
    } catch (err) {
      el.textContent = "status tidak tersedia: " + ((err && err.message) || err);
    }
  }

  function wireOrgAdminActions() {
    document.querySelectorAll("#koOrgAdminSection [data-merge-act]").forEach(function (btn) {
      btn.addEventListener("click", async function () {
        var id = btn.getAttribute("data-merge-id");
        var act = btn.getAttribute("data-merge-act");
        var msg = btn.parentElement.querySelector(".koMergeMsg");
        if (msg) msg.textContent = " memproses…";
        try {
          await window.RN_FRAPPE.call("rescue_net.api_community_cluster.decide_org_merge",
            { merge_request: id, action: act }, { method: "POST" });
          await loadOrgAdmin();
        } catch (err) {
          if (msg) msg.textContent = " gagal: " + ((err && err.message) || err);
        }
      });
    });
  }

  async function loadOrgAdmin() {
    var d = null;
    try { d = await window.RN_FRAPPE.call("rescue_net.api_community_cluster.org_coordination"); } catch (e) {}
    renderOrgAdmin(d || {});
  }

  var _orgAdminFormsWired = false;
  function initOrgAdminForms() {
    if (_orgAdminFormsWired) return;
    _orgAdminFormsWired = true;

    var mf = $("#koMergeForm");
    if (mf) mf.addEventListener("submit", async function (e) {
      e.preventDefault();
      var msg = $("#koMergeMsg");
      var target = $("#koMergeTarget").value;
      if (!target) { msg.textContent = "Pilih organisasi tujuan."; return; }
      msg.textContent = "mengirim…";
      try {
        await window.RN_FRAPPE.call("rescue_net.api_community_cluster.request_org_merge", {
          requester_organization: $("#koMergeRequester").value,
          target_organization: target,
          note: (mf.note.value || "").trim() || null,
        }, { method: "POST" });
        msg.textContent = "Terkirim — menunggu keputusan organisasi tujuan.";
        mf.note.value = "";
        await loadOrgAdmin();
      } catch (err) { msg.textContent = "Gagal: " + ((err && err.message) || err); }
    });

    var kf = $("#koAiKeyForm");
    if (kf) kf.addEventListener("submit", async function (e) {
      e.preventDefault();
      var msg = $("#koAiKeyMsg");
      var key = (kf.api_key.value || "").trim();
      if (key.length < 20) { msg.textContent = "Kunci terlalu pendek."; return; }
      msg.textContent = "menyimpan…";
      try {
        await window.RN_FRAPPE.call("rescue_net.api_ai.save_org_key", {
          organization_id: $("#koAiKeyOrg").value,
          api_key: key,
          provider: $("#koAiKeyProvider").value || "openai",
          api_key_label: (kf.api_key_label.value || "").trim() || null,
        }, { method: "POST" });
        msg.textContent = "Tersimpan (terenkripsi di server).";
        kf.api_key.value = "";
        refreshAiKeyStatus();
      } catch (err) { msg.textContent = "Gagal: " + ((err && err.message) || err); }
    });

    var del = $("#koAiKeyDelete");
    if (del) del.addEventListener("click", async function () {
      var msg = $("#koAiKeyMsg");
      if (!window.confirm("Hapus kunci AI untuk organisasi + provider ini?")) return;
      msg.textContent = "menghapus…";
      try {
        await window.RN_FRAPPE.call("rescue_net.api_ai.delete_org_key", {
          organization_id: $("#koAiKeyOrg").value,
          provider: $("#koAiKeyProvider").value || "openai",
        }, { method: "POST" });
        msg.textContent = "Terhapus.";
        refreshAiKeyStatus();
      } catch (err) { msg.textContent = "Gagal: " + ((err && err.message) || err); }
    });

    ["#koAiKeyOrg", "#koAiKeyProvider"].forEach(function (s) {
      var el = $(s);
      if (el) el.addEventListener("change", refreshAiKeyStatus);
    });
  }

  async function load() {
    try {
      var d = await window.RN_FRAPPE.call(BOARD, { disaster_event: getEvent() });
      render(d || {});
      if (d && d.logged_in) {
        loadMembers();
        initOrgAdminForms();
        loadOrgAdmin();
      }
    } catch (err) {
      console.error("[koordinasi organisasi]", err);
      $("#koStatus").textContent = "Gagal memuat data koordinasi organisasi.";
      showNotice(
        "Gagal memuat",
        "Tidak bisa memuat data koordinasi organisasi saat ini. Coba muat ulang, atau buka Control Centre.",
        null, "war-room.html?event=" + getEvent()
      );
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", load);
  } else {
    load();
  }
})();
