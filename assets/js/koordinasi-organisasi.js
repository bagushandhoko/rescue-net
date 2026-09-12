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
          '<div class="ko-posko-meta">Kontak: ' + esc(m.user_email || "-") + (m.user_phone ? " · " + esc(m.user_phone) : "") +
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
        var reason = null;
        if (act === "reject" || act === "revoke") {
          reason = window.prompt(act === "reject" ? "Alasan menolak permohonan ini:" : "Alasan mengeluarkan anggota ini:", "");
          if (reason === null) return; // cancelled
          if (!reason.trim()) { if (msg) msg.textContent = " alasan wajib diisi"; return; }
        }
        if (msg) msg.textContent = " memproses…";
        try {
          if (act === "toggle-verify") {
            var on = /Verifikasi identitas/.test(btn.textContent);
            await window.RN_FRAPPE.call("rescue_net.api_community_cluster.set_member_verified",
              { membership: mid, verified: on ? 1 : 0 }, { method: "POST" });
          } else {
            await window.RN_FRAPPE.call("rescue_net.api_community_cluster.decide_membership",
              { membership: mid, action: act, member_verified: (chk && chk.checked) ? 1 : 0, note: reason },
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

  /* ---------- Organisasi Saya: hierarki "satu komando" + kunci AI ---------- */
  var ORG_ADMIN = null;

  function fmtDateTime(s) {
    if (!s) return "";
    var d = new Date(String(s).replace(" ", "T"));
    return isNaN(d.getTime()) ? String(s) : d.toLocaleString("id-ID",
      { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
  }

  function orgHierCard(o, ownedSet) {
    var kids = (o.children || []).length
      ? "<ul>" + o.children.map(function (c) { return "<li>" + esc(c.title) + "</li>"; }).join("") + "</ul>"
      : '<div class="rn-muted">Belum ada sub-organisasi.</div>';

    // "pindah induk" select — every org except this one and its descendants;
    // server rejects cycles anyway, this just trims the obvious ones.
    var opts = ['<option value="">— tidak punya induk (berdiri sendiri) —</option>'];
    (ORG_ADMIN.all_orgs || []).forEach(function (a) {
      if (a.name === o.name) return;
      var sel = a.name === o.parent_organization ? " selected" : "";
      opts.push('<option value="' + esc(a.name) + '"' + sel + ">" + esc(a.title) + "</option>");
    });

    return '<article class="ko-posko-card" data-org="' + esc(o.name) + '">' +
      "<h4>" + esc(o.title) + "</h4>" +
      '<div class="ko-posko-meta">' +
        (o.parent_title ? "induk: <b>" + esc(o.parent_title) + "</b>" : "tidak punya induk (berdiri sendiri)") +
      "</div>" +
      '<div class="ko-posko-meta" style="margin-top:6px">Sub-organisasi:</div>' + kids +
      '<div style="margin-top:8px;display:flex;gap:6px;flex-wrap:wrap;align-items:center">' +
        '<label class="rn-muted" style="font-size:12px">Ubah induk: ' +
          '<select class="koSetParent">' + opts.join("") + "</select></label>" +
        '<button type="button" class="btn ghost mini koApplyParent">Ajukan</button>' +
        (o.parent_organization
          ? '<button type="button" class="btn ghost mini koDetach">Ajukan lepas (berdiri sendiri)</button>'
          : "") +
        '<span class="koOrgMsg rn-muted" style="font-size:12px"></span>' +
      "</div>" +
      "</article>";
  }

  function contactLine(label, contact) {
    if (!contact) return "";
    var bits = [];
    if (contact.contact_person) bits.push(contact.contact_person);
    if (contact.contact_summary) bits.push(contact.contact_summary);
    return '<div class="ko-posko-meta">' + esc(label) + ": " + (bits.length ? esc(bits.join(" · ")) : "belum diisi") + "</div>";
  }

  function pendingCard(r, ownedSet) {
    var verb = r.action === "attach" ? "minta jadi anak dari" : "minta lepas dari";
    var reqBy = r.requested_by_contact
      ? esc(r.requested_by_contact.username || r.requested_by) + (r.requested_by_contact.email ? " (" + esc(r.requested_by_contact.email) + (r.requested_by_contact.phone ? ", " + esc(r.requested_by_contact.phone) : "") + ")" : "")
      : esc(r.requested_by || "-");
    return '<article class="ko-posko-card" data-req="' + esc(r.name) + '" data-decidable="' + (r.can_decide ? "1" : "0") + '">' +
      '<div class="rn-row">' + (r.can_decide ? '<span class="ko-tag edit">Perlu keputusan Anda</span>' : '<span class="ko-tag view">Menunggu pihak lain</span>') + "</div>" +
      "<h4>" + esc(r.child_title) + " " + verb + " " + esc(r.parent_title) + "</h4>" +
      '<div class="ko-posko-meta">Diajukan oleh ' + reqBy + " · " + esc(fmtDateTime(r.requested_at)) + "</div>" +
      (r.note ? '<div class="ko-posko-meta">Catatan: ' + esc(r.note) + "</div>" : "") +
      contactLine("Kontak " + r.parent_title, r.parent_contact) +
      contactLine("Kontak " + r.child_title, r.child_contact) +
      '<div class="ko-card-actions">' +
      (r.can_decide
        ? '<button type="button" class="btn primary mini" data-act="approve">Setujui</button>' +
          '<button type="button" class="btn ghost mini" data-act="reject">Tolak</button>'
        : "") +
      (r.can_withdraw ? '<button type="button" class="btn ghost mini" data-act="withdraw">Batalkan</button>' : "") +
      '<span class="rn-muted koReqMsg"></span></div></article>';
  }

  function renderPendingRequests(list) {
    var wrap = $("#koPendingRequests");
    if (!wrap) return;
    wrap.innerHTML = (list && list.length)
      ? list.map(pendingCard).join("")
      : '<p class="ko-empty">Tidak ada permintaan hierarki yang menunggu.</p>';
    wrap.querySelectorAll("[data-req] [data-act]").forEach(function (btn) {
      btn.addEventListener("click", async function () {
        var card = btn.closest("[data-req]");
        var reqName = card.getAttribute("data-req");
        var act = btn.getAttribute("data-act");
        var msg = card.querySelector(".koReqMsg");
        var note = null;
        if (act === "reject") {
          note = window.prompt("Alasan menolak permintaan ini (wajib):", "");
          if (note === null) return;
          if (!note.trim()) { msg.textContent = " alasan wajib diisi"; return; }
        } else if (act === "withdraw") {
          if (!window.confirm("Batalkan permintaan ini?")) return;
        }
        msg.textContent = " memproses…";
        try {
          await window.RN_FRAPPE.call("rescue_net.api_community_cluster.decide_org_link",
            { request: reqName, action: act, note: note }, { method: "POST" });
          await loadOrgAdmin();
        } catch (err) {
          msg.textContent = " gagal: " + ((err && err.message) || err);
        }
      });
    });
  }

  function hierLogRow(r) {
    var verb = r.action === "attached"
      ? "→ dijadikan anak dari"
      : "dilepas dari";
    return '<div class="ko-posko-meta">' +
      esc(fmtDateTime(r.at)) + " — <b>" + esc(r.child_title) + "</b> " + verb +
      " <b>" + esc(r.parent_title) + "</b>" +
      (r.note ? ' <span class="rn-muted">· ' + esc(r.note) + "</span>" : "") +
      "</div>";
  }

  function renderOrgAdmin(d) {
    ORG_ADMIN = d;
    var sec = $("#koOrgAdminSection");
    if (!sec) return;
    if (!d || !d.is_org_admin || !(d.organizations || []).length) { sec.hidden = true; return; }
    sec.hidden = false;

    var ownedSet = {};
    (d.owned || []).forEach(function (n) { ownedSet[n] = 1; });

    $("#koOrgAdminCount").textContent = d.organizations.length + " organisasi";

    $("#koOrgHierarchy").innerHTML =
      d.organizations.map(function (o) { return orgHierCard(o, ownedSet); }).join("");

    var myOpts = d.organizations.map(function (o) {
      return '<option value="' + esc(o.name) + '">' + esc(o.title) + "</option>";
    }).join("");
    $("#koAttachParent").innerHTML = myOpts;
    $("#koAiKeyOrg").innerHTML = myOpts;

    // child picker: every org that is not one of mine
    var childOpts = ['<option value="">— pilih —</option>'];
    (d.all_orgs || []).forEach(function (a) {
      if (ownedSet[a.name]) return;
      childOpts.push('<option value="' + esc(a.name) + '">' + esc(a.title) +
        (a.parent_organization ? " (kini anak dari lain)" : "") + "</option>");
    });
    $("#koAttachChild").innerHTML = childOpts.join("");

    $("#koHierLog").innerHTML = (d.hierarchy_log || []).length
      ? d.hierarchy_log.map(hierLogRow).join("")
      : '<div class="rn-muted">Belum ada perubahan hierarki.</div>';

    renderPendingRequests(d.pending_requests || []);
    wireOrgAdminActions();
    refreshAiKeyStatus();
  }

  async function setParent(organization, parent, note, msgEl) {
    if (msgEl) msgEl.textContent = " memproses…";
    try {
      var r = await window.RN_FRAPPE.call("rescue_net.api_community_cluster.set_org_parent",
        { organization: organization, parent_organization: parent || "", note: note || null },
        { method: "POST" });
      if (msgEl) msgEl.textContent = r && r.pending ? " diajukan — menunggu persetujuan pihak lain." : " berhasil.";
      await loadOrgAdmin();
    } catch (err) {
      if (msgEl) msgEl.textContent = " gagal: " + ((err && err.message) || err);
    }
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
    document.querySelectorAll("#koOrgHierarchy [data-org]").forEach(function (cardEl) {
      var org = cardEl.getAttribute("data-org");
      var msg = cardEl.querySelector(".koOrgMsg");
      var apply = cardEl.querySelector(".koApplyParent");
      var detach = cardEl.querySelector(".koDetach");
      if (apply) apply.addEventListener("click", function () {
        setParent(org, cardEl.querySelector(".koSetParent").value, null, msg);
      });
      if (detach) detach.addEventListener("click", function () {
        if (window.confirm("Lepaskan organisasi ini dari induknya?")) setParent(org, "", null, msg);
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

    var af = $("#koAttachForm");
    if (af) af.addEventListener("submit", async function (e) {
      e.preventDefault();
      var msg = $("#koAttachMsg");
      var child = $("#koAttachChild").value;
      var parent = $("#koAttachParent").value;
      if (!child) { msg.textContent = "Pilih organisasi yang ditarik."; return; }
      if (!parent) { msg.textContent = "Pilih induk."; return; }
      msg.textContent = "memproses…";
      try {
        var r = await window.RN_FRAPPE.call("rescue_net.api_community_cluster.set_org_parent", {
          organization: child,
          parent_organization: parent,
          note: (af.note.value || "").trim() || null,
        }, { method: "POST" });
        msg.textContent = r && r.pending
          ? "Diajukan — menunggu persetujuan pengelola organisasi tujuan."
          : "Berhasil — sekarang jadi anak.";
        af.note.value = "";
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
