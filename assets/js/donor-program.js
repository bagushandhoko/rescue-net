/* ============================================================
 * Donor Program — the main donation landing page.
 * Owner ask: one list of every donation program (cash-base AND
 * project-base — RAB/design/pelaksana already modeled by Pengadaan &
 * Tender), click a card for detail (project detail if project-base),
 * click further for the donor list + amounts.
 * Calls rescue_net.api_donor_program.program_board / program_detail /
 * create_cash_donation / decide_cash_donation / recheck_and_publish /
 * create_special_program (guest reads, login writes) — same guest-safe
 * backend program-khusus.html already uses.
 * ============================================================ */
(function () {
  "use strict";

  var BOARD_METHOD = "rescue_net.api_donor_program.program_board";
  var DETAIL_METHOD = "rescue_net.api_donor_program.program_detail";
  var BOARD_CACHE = null;
  var SELECTED = null;

  var $ = function (sel, root) { return (root || document).querySelector(sel); };
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function fmt(n) { return Number(n || 0).toLocaleString("id-ID"); }
  function rp(n) { return "Rp " + fmt(n); }
  function getEventId() { return new URLSearchParams(window.location.search).get("event") || "event-sim-001"; }
  function shortDate(s) { return s ? String(s).slice(0, 10) : "-"; }

  var STATUS_LABEL = { planned: "Rencana", active: "Aktif", completed: "Selesai", cancelled: "Dibatalkan" };
  var STATUS_CHIP = { planned: "", active: "ok", completed: "", cancelled: "danger" };

  function programCard(p) {
    var sel = SELECTED === p.name ? " is-selected" : "";
    return (
      '<button type="button" class="rn-pk-card' + sel + '" data-program="' + esc(p.name) + '">' +
      '<div class="rn-pk-card-head"><b>' + esc(p.program_name) + '</b>' +
        (p.is_own_hidden ? '<span class="chip danger" style="margin-right:4px">Belum Publik</span>' : "") +
        '<span class="chip ' + (STATUS_CHIP[p.status] || "") + '">' + (STATUS_LABEL[p.status] || p.status) + "</span></div>" +
      '<div class="rn-pk-card-meta">' + esc(p.category) + " · " + esc(p.location) + "</div>" +
      '<div class="rn-pk-bar"><div style="width:' + p.progress_percent + '%"></div></div>' +
      '<div class="rn-pk-bar-label"><span>' + p.progress_percent + "%</span></div></button>"
    );
  }

  // Grouped by Cash Base / Project Base (a program funding a real
  // Pengadaan & Tender tender) — easier to scan than one flat mixed list
  // once there are several of each kind.
  function renderList() {
    var rows = (BOARD_CACHE && BOARD_CACHE.programs) || [];
    var el = $("#donorList");
    if (!rows.length) {
      el.innerHTML = '<p class="rn-muted" style="padding:8px;">Belum ada program donasi untuk bencana ini.</p>';
      return;
    }
    var cash = rows.filter(function (p) { return p.program_kind !== "project"; });
    var project = rows.filter(function (p) { return p.program_kind === "project"; });

    var html = "";
    if (cash.length) {
      html += '<div class="rn-pk-group-head"><span class="chip neutral">Cash Base</span><span class="rn-muted">' + cash.length + " program</span></div>";
      html += cash.map(programCard).join("");
    }
    if (project.length) {
      html += '<div class="rn-pk-group-head"><span class="chip warning">Project Base</span><span class="rn-muted">' + project.length + " program</span></div>";
      html += project.map(programCard).join("");
    }
    el.innerHTML = html;

    el.querySelectorAll("[data-program]").forEach(function (btn) {
      btn.addEventListener("click", function () { selectProgram(btn.getAttribute("data-program")); });
    });
  }

  function renderProject(project) {
    var wrap = $("#ddProject");
    if (!project) { wrap.hidden = true; return; }
    wrap.hidden = false;
    var designWrap = $("#ddProjectDesignWrap");
    if (project.design_image_url) {
      $("#ddProjectDesignImg").src = project.design_image_url;
      designWrap.hidden = false;
    } else {
      designWrap.hidden = true;
    }
    $("#ddProjectScope").textContent = project.scope_description || "Belum ada uraian lingkup pekerjaan.";
    $("#ddProjectRab").textContent = rp(project.rab_total);
    $("#ddProjectStatus").textContent = project.status_label || project.status || "-";
    $("#ddProjectPelaksana").textContent = project.pelaksana || "Belum ditetapkan";
    $("#ddProjectRabDoc").innerHTML = project.rab_document_url
      ? '<a href="' + esc(project.rab_document_url) + '" target="_blank" rel="noopener">Unduh dokumen RAB ↓</a>'
      : "Dokumen RAB belum diunggah.";
    $("#ddProjectTenderLink").href = "pengadaan-tender.html?event=" + encodeURIComponent(getEventId());
  }

  function renderDonations(d) {
    var wall = $("#ddDonationWall");
    var pub = (d && d.public) || [];
    wall.innerHTML = pub.length
      ? pub.map(function (r) {
          return '<article class="event-card"><div class="event-main"><div>' +
            "<h4>" + esc(r.donor_name) + "</h4>" +
            (r.message ? "<p>" + esc(r.message) + "</p>" : "") +
            '<p class="rn-muted">' + shortDate(r.confirmed_at) + "</p></div>" +
            '<div class="chips"><span class="chip ok">' + rp(r.amount) + "</span></div>" +
            "</div></article>";
        }).join("")
      : '<p class="rn-muted">Belum ada donasi terkonfirmasi untuk program ini.</p>';

    var pendingSection = $("#ddPendingSection");
    var pendingList = $("#ddPending");
    var pending = (d && d.pending) || [];
    if (d && d.can_manage) {
      pendingSection.hidden = false;
      pendingList.innerHTML = pending.length
        ? pending.map(function (r) {
            return '<article class="event-card" data-donation="' + esc(r.name) + '"><div class="event-main"><div>' +
              "<h4>" + esc(r.donor_name) + (r.is_anonymous ? " (ingin anonim di publik)" : "") + "</h4>" +
              '<p class="rn-muted">Kontak: ' + esc(r.donor_contact || "-") + " · " + shortDate(r.creation) + "</p>" +
              (r.message ? "<p>" + esc(r.message) + "</p>" : "") +
              "</div><div class=\"chips\"><span class=\"chip\">" + rp(r.amount) + "</span></div></div>" +
              '<div class="form-actions">' +
              '<button type="button" class="btn primary" data-donate-act="confirm">Konfirmasi Diterima</button>' +
              '<button type="button" class="btn" data-donate-act="reject">Tolak</button>' +
              '<span class="form-message" data-donate-msg></span></div></article>';
          }).join("")
        : '<p class="rn-muted">Tidak ada donasi menunggu konfirmasi.</p>';
    } else {
      pendingSection.hidden = true;
      pendingList.innerHTML = "";
    }
  }

  function renderNotPublicBanner(data) {
    var banner = $("#ddNotPublicBanner");
    var notPublic = data.can_manage && data.program.public_visibility !== "summary_public";
    banner.hidden = !notPublic;
    if (!notPublic) return;
    var btn = $("#ddRecheckBtn");
    var msg = $("#ddRecheckMsg");
    msg.textContent = data.owner_verified === false ? " (belum terverifikasi)" : "";
    if (!btn.dataset.wired) {
      btn.dataset.wired = "1";
      btn.addEventListener("click", async function () {
        msg.textContent = " memproses…";
        try {
          var r = await window.RN_FRAPPE.call("rescue_net.api_donor_program.recheck_and_publish",
            { donor_program: SELECTED }, { method: "POST" });
          msg.textContent = " berhasil dipublikasikan" +
            (r.tenders_opened && r.tenders_opened.length ? " (tender ikut dibuka)" : "") + ".";
          await selectProgram(SELECTED);
          await loadBoard();
        } catch (err) {
          msg.textContent = " gagal: " + ((err && err.message) || err);
        }
      });
    }
  }

  function renderDetail(data) {
    var p = data.program;
    $("#donorDetailEmpty").hidden = true;
    $("#donorDetailBody").hidden = false;

    $("#ddName").textContent = p.program_name;
    $("#ddStatus").textContent = STATUS_LABEL[p.status] || p.status;
    $("#ddStatus").className = "chip " + (STATUS_CHIP[p.status] || "");
    $("#ddMeta").textContent = (p.program_kind === "project" ? "Project Base" : "Cash Base") + " · " + esc(p.category || "-");

    $("#ddProgressPct").textContent = p.progress_percent + "%";
    $("#ddProgressBar").style.width = p.progress_percent + "%";
    $("#ddTarget").textContent = fmt(p.target_amount) + " " + (p.target_unit || "");
    $("#ddCurrent").textContent = fmt(p.current_amount) + " " + (p.target_unit || "");

    $("#ddDescription").textContent = p.description || p.target_description || "Belum ada deskripsi program.";
    $("#ddOfficer").textContent = p.officer_in_charge_name || "-";
    $("#ddOfficerPhone").textContent = p.officer_in_charge_phone || "";
    $("#ddLocation").textContent = p.target_location || p.location || "-";
    $("#ddBeneficiaries").textContent = p.target_beneficiaries || p.target_description || "-";

    $("#ddBudgetTarget").textContent = rp(p.budget_target);
    $("#ddBudgetReceived").textContent = rp(p.budget_received);
    $("#ddBudgetSpent").textContent = rp(p.budget_spent);

    renderProject(data.project);
    renderDonations(data.donations || {});
    renderNotPublicBanner(data);
  }

  async function selectProgram(name) {
    SELECTED = name;
    renderList();
    try {
      var data = await window.RN_FRAPPE.call(DETAIL_METHOD, { program: name });
      renderDetail(data);
    } catch (err) {
      $("#donorStatus").textContent = "Gagal memuat detail: " + ((err && err.message) || err);
    }
  }

  async function loadBoard() {
    var data = await window.RN_FRAPPE.call(BOARD_METHOD, { disaster_event: getEventId() });
    BOARD_CACHE = data;
    $("#donorUpdated").textContent = "Donor Program · Diperbarui " + String(data.generated_at || "").slice(11, 16);
    $("#donorStatus").textContent = fmt((data.programs || []).length) + " program ditemukan.";
    renderList();
  }

  function wireDonateForm() {
    var form = $("#ddDonateForm");
    if (!form || form.dataset.wired) return;
    form.dataset.wired = "1";
    form.addEventListener("submit", async function (e) {
      e.preventDefault();
      var msg = $("#ddDonateMsg");
      if (!SELECTED) { msg.textContent = "Pilih program dulu."; return; }
      var amount = Number(form.amount.value || 0);
      if (!(amount > 0)) { msg.textContent = "Nominal tidak valid."; return; }
      msg.textContent = "Mengirim…";
      try {
        await window.RN_FRAPPE.call("rescue_net.api_donor_program.create_cash_donation", {
          donor_program: SELECTED,
          amount: amount,
          is_anonymous: form.is_anonymous.checked ? 1 : 0,
          message: (form.message.value || "").trim() || null,
        }, { method: "POST" });
        msg.textContent = "Terkirim — menunggu konfirmasi lembaga penerima.";
        form.reset();
        await selectProgram(SELECTED);
      } catch (err) {
        msg.textContent = "Gagal: " + ((err && err.message) || err) +
          (/login|permission|akses|diperlukan/i.test(String(err && err.message)) ? " (perlu login sebagai donatur)" : "");
      }
    });

    var pendingList = $("#ddPending");
    if (pendingList && !pendingList.dataset.wired) {
      pendingList.dataset.wired = "1";
      pendingList.addEventListener("click", async function (e) {
        var btn = e.target.closest("[data-donate-act]");
        if (!btn) return;
        var card = btn.closest("[data-donation]");
        var msg = card.querySelector("[data-donate-msg]");
        var act = btn.getAttribute("data-donate-act");
        var note = act === "reject" ? (window.prompt("Alasan menolak donasi ini (opsional):", "") || null) : null;
        msg.textContent = " memproses…";
        try {
          await window.RN_FRAPPE.call("rescue_net.api_donor_program.decide_cash_donation", {
            donation: card.getAttribute("data-donation"), action: act, note: note,
          }, { method: "POST" });
          await selectProgram(SELECTED);
        } catch (err) {
          msg.textContent = " gagal: " + ((err && err.message) || err);
        }
      });
    }
  }

  function wireCreateForm() {
    var form = $("#donorCreateForm");
    if (!form) return;
    form.addEventListener("submit", async function (e) {
      e.preventDefault();
      var msg = $("#donorCreateMsg");
      msg.textContent = "Menyimpan…";
      try {
        var res = await window.RN_FRAPPE.call("rescue_net.api_donor_program.create_special_program", {
          disaster_event: getEventId(),
          program_name: (form.program_name.value || "").trim(),
          program_type: (form.program_type.value || "").trim() || "general_relief",
          owner_type: form.owner_type.value,
          owner_id: (form.owner_id.value || "").trim() || null,
          target_description: (form.target_description.value || "").trim() || null,
          budget_target: Number(form.budget_target.value || 0),
          location: (form.location.value || "").trim() || null,
        }, { method: "POST" });
        msg.textContent = "Program tersimpan: " + res.program +
          (res.status === "planned" ? "" : "") + ".";
        form.reset();
        await loadBoard();
      } catch (err) {
        msg.textContent = "Gagal: " + ((err && err.message) || err) +
          (/login|permission|akses|diperlukan/i.test(String(err && err.message)) ? " (perlu login)" : "");
      }
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    if (!window.RN_FRAPPE) return;
    wireDonateForm();
    wireCreateForm();
    loadBoard().catch(function (err) {
      console.error("[donor program]", err);
      $("#donorStatus").textContent = "Gagal memuat daftar program.";
    });
  });
})();
