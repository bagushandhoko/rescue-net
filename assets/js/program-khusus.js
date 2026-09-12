/* ============================================================
 * New dashboard (matches "program khusus.png"): calls
 * rescue_net.api_donor_program.program_board / program_detail
 * (guest, event-wide). Legacy "Buat Program"/"Update Progress"
 * forms below (kept inside <details>) still call
 * api_donor_program.context/create_program/create_update.
 * ============================================================ */
(function () {
  "use strict";

  var BOARD_METHOD = "rescue_net.api_donor_program.program_board";
  var DETAIL_METHOD = "rescue_net.api_donor_program.program_detail";
  var BOARD_CACHE = null;
  var CURRENT_FILTER = "semua";
  var SELECTED = null;

  var $ = function (sel, root) { return (root || document).querySelector(sel); };
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function fmt(n) { return Number(n || 0).toLocaleString("id-ID"); }
  function rp(n) { return "Rp " + fmt(n); }
  function getEventId2() { return new URLSearchParams(window.location.search).get("event") || "event-sim-001"; }
  function shortDate(s) { return s ? String(s).slice(0, 10) : "-"; }

  var STATUS_LABEL = { planned: "Rencana", active: "Aktif", completed: "Selesai", cancelled: "Dibatalkan" };
  var STATUS_CHIP = { planned: "", active: "ok", completed: "", cancelled: "danger" };
  var PRIORITY_CRITICAL = { critical: 1, urgent: 1, high: 1, tinggi: 1, darurat: 1 };

  var DRILL_TITLES = {
    program_aktif: "Program Aktif", program_critical: "Program Critical",
    program_selesai: "Program Selesai", milestone_terlambat: "Milestone Terlambat",
    lokasi_belum_terlayani: "Lokasi Belum Terlayani", butuh_support: "Butuh Support",
  };

  function drillItemsHtml(items) {
    if (!items || !items.length) return '<p class="rn-muted">Tidak ada data untuk ditampilkan.</p>';
    return items.map(function (it) {
      return (
        '<a class="rn-ba-ditem" href="' + esc(it.href || "#") + '">' +
        "<span><b>" + esc(it.title) + "</b><small>" + esc(it.sub || "") + "</small></span>" +
        (it.href ? '<span class="rn-ba-ditem-go">→</span>' : "") + "</a>"
      );
    }).join("");
  }

  function openDrill(kind) {
    if (!BOARD_CACHE) return;
    $("#programDrillTitle").textContent = DRILL_TITLES[kind] || kind;
    var items = ((BOARD_CACHE.kpi_items || {})[kind + "_items"]) || [];
    $("#programDrillSub").textContent = items.length + " item";
    $("#programDrillBody").innerHTML = drillItemsHtml(items);
    $("#programDrill").hidden = false;
    document.body.style.overflow = "hidden";
  }
  function closeDrill() { $("#programDrill").hidden = true; document.body.style.overflow = ""; }

  function renderKpi(t) {
    $("#kpiAktif").textContent = fmt(t.program_aktif);
    $("#kpiCritical").textContent = fmt(t.program_critical);
    $("#kpiSelesai").textContent = fmt(t.program_selesai);
    $("#kpiTerlambat").textContent = fmt(t.milestone_terlambat);
    $("#kpiLokasi").textContent = fmt(t.lokasi_belum_terlayani);
    $("#kpiSupport").textContent = fmt(t.butuh_support);
  }

  function filteredPrograms() {
    var rows = (BOARD_CACHE && BOARD_CACHE.programs) || [];
    if (CURRENT_FILTER === "aktif") return rows.filter(function (p) { return p.status === "active"; });
    if (CURRENT_FILTER === "critical") return rows.filter(function (p) { return PRIORITY_CRITICAL[(p.priority || "").toLowerCase()] && p.status !== "completed"; });
    if (CURRENT_FILTER === "selesai") return rows.filter(function (p) { return p.status === "completed"; });
    return rows;
  }

  function renderList() {
    var rows = filteredPrograms();
    var el = $("#programList");
    if (!rows.length) {
      el.innerHTML = '<p class="rn-muted" style="padding:8px;">Tidak ada program pada filter ini.</p>';
      return;
    }
    el.innerHTML = rows.map(function (p) {
      var sel = SELECTED === p.name ? " is-selected" : "";
      return (
        '<button type="button" class="rn-pk-card' + sel + '" data-program="' + esc(p.name) + '">' +
        '<div class="rn-pk-card-head"><b>' + esc(p.program_name) + '</b>' +
          (p.is_own_hidden ? '<span class="chip danger" style="margin-right:4px">Belum Publik</span>' : "") +
          '<span class="chip ' + (STATUS_CHIP[p.status] || "") + '">' + (STATUS_LABEL[p.status] || p.status) + "</span></div>" +
        '<div class="rn-pk-card-meta">' +
          '<span class="chip ' + (p.program_kind === "project" ? "warning" : "neutral") + '" style="margin-right:6px">' +
          (p.program_kind === "project" ? "Project Base" : "Cash Base") + "</span>" +
          esc(p.category) + " · " + esc(p.location) + "</div>" +
        '<div class="rn-pk-bar"><div style="width:' + p.progress_percent + '%"></div></div>' +
        '<div class="rn-pk-bar-label"><span>' + p.progress_percent + "%</span></div></button>"
      );
    }).join("");

    el.querySelectorAll("[data-program]").forEach(function (btn) {
      btn.addEventListener("click", function () { selectProgram(btn.getAttribute("data-program")); });
    });
  }

  function setupFilterTabs() {
    $("#programTabs").querySelectorAll(".rn-tab").forEach(function (tab) {
      tab.addEventListener("click", function () {
        $("#programTabs").querySelectorAll(".rn-tab").forEach(function (t) { t.classList.remove("is-active"); });
        tab.classList.add("is-active");
        CURRENT_FILTER = tab.getAttribute("data-filter");
        renderList();
      });
    });
  }

  function setupDetailTabs() {
    $("#detailTabs").querySelectorAll(".rn-tab").forEach(function (tab) {
      tab.addEventListener("click", function () {
        $("#detailTabs").querySelectorAll(".rn-tab").forEach(function (t) { t.classList.remove("is-active"); });
        tab.classList.add("is-active");
        var name = tab.getAttribute("data-tab");
        ["ringkasan", "anggaran", "riwayat"].forEach(function (k) {
          $("#tab" + k.charAt(0).toUpperCase() + k.slice(1)).hidden = k !== name;
        });
      });
    });
  }

  function evidenceThumb(ev) {
    var url = ev.evidence_url || ev.file_url || "";
    return (
      '<a class="rn-bukti-thumb" href="' + esc(url) + '" target="_blank" rel="noopener">' +
      (url ? '<img src="' + esc(url) + '" alt="">' : "") + "</a>"
    );
  }

  var UPDATE_TYPE_LABEL = { progress: "Progress", spending: "Pengeluaran", handover: "Serah Terima", completion: "Selesai" };

  function renderUpdates(updates) {
    var el = $("#detailUpdates");
    if (!updates || !updates.length) {
      el.innerHTML = '<article class="event-card"><h4>Belum ada riwayat</h4><p>Belum ada update tercatat untuk program ini.</p></article>';
      return;
    }
    el.innerHTML = updates.map(function (u) {
      return (
        '<article class="event-card"><div class="event-main"><div>' +
        "<h4>" + esc(u.update_title) + "</h4><p>" + esc(u.update_notes || "") + "</p>" +
        '<p class="rn-muted">' + shortDate(u.observed_at) + " · " + fmt(u.progress_percent) + "% · " + rp(u.amount_spent) + "</p></div>" +
        '<div class="chips"><span class="chip">' + (UPDATE_TYPE_LABEL[u.update_type] || u.update_type) + "</span></div>" +
        "</div></article>"
      );
    }).join("");
  }

  function renderProject(project, eventId) {
    var wrap = $("#detailProject");
    if (!project) { wrap.hidden = true; return; }
    wrap.hidden = false;
    $("#projectScope").textContent = project.scope_description || "Belum ada uraian lingkup pekerjaan.";
    $("#projectRab").textContent = rp(project.rab_total);
    $("#projectStatus").textContent = project.status_label || project.status || "-";
    $("#projectPelaksana").textContent = project.pelaksana || "Belum ditetapkan";
    $("#projectRabDoc").textContent = project.rab_document_url ? "" : "Dokumen RAB belum diunggah.";
    $("#projectRabDoc").innerHTML = project.rab_document_url
      ? '<a href="' + esc(project.rab_document_url) + '" target="_blank" rel="noopener">Unduh dokumen RAB ↓</a>'
      : "Dokumen RAB belum diunggah.";
    $("#projectTenderLink").href = "pengadaan-tender.html?event=" + encodeURIComponent(eventId || "");
  }

  function renderNotPublicBanner(data) {
    var banner = $("#detailNotPublicBanner");
    var notPublic = data.can_manage && data.program.public_visibility !== "summary_public";
    banner.hidden = !notPublic;
    if (!notPublic) return;
    var btn = $("#recheckPublishBtn");
    var msg = $("#recheckPublishMsg");
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
    $("#detailEmpty").hidden = true;
    $("#detailBody").hidden = false;

    $("#detailName").textContent = p.program_name;
    $("#detailStatus").textContent = STATUS_LABEL[p.status] || p.status;
    $("#detailStatus").className = "chip " + (STATUS_CHIP[p.status] || "");
    $("#detailMeta").textContent = p.category + " · " + (p.target_location || p.location || "-") +
      (p.priority ? " · Prioritas " + p.priority : "");

    $("#detailProgressPct").textContent = p.progress_percent + "%";
    $("#detailProgressBar").style.width = p.progress_percent + "%";
    $("#detailTarget").textContent = fmt(p.target_amount) + " " + (p.target_unit || "");
    $("#detailCurrent").textContent = fmt(p.current_amount) + " " + (p.target_unit || "");

    $("#detailDescription").textContent = p.description || p.target_description || "Belum ada deskripsi program.";
    $("#detailOfficer").textContent = p.officer_in_charge_name || "-";
    $("#detailOfficerPhone").textContent = p.officer_in_charge_phone || "";
    $("#detailPeriod").textContent = (p.start_date ? shortDate(p.start_date) : "-") + " – " + (p.end_date ? shortDate(p.end_date) : "-");
    $("#detailBeneficiaries").textContent = p.target_beneficiaries || p.target_description || "-";

    $("#budgetTarget").textContent = rp(p.budget_target);
    $("#budgetReceived").textContent = rp(p.budget_received);
    $("#budgetSpent").textContent = rp(p.budget_spent);

    $("#detailEvidence").innerHTML = (data.bukti || []).length
      ? data.bukti.map(evidenceThumb).join("")
      : '<p class="rn-muted" style="grid-column:1/-1;">Belum ada evidence terhubung ke program ini.</p>';

    renderProject(data.project, getEventId2());
    renderUpdates(data.updates || []);
    renderNotPublicBanner(data);
    renderDonations(data.donations || {});
  }

  function renderDonations(d) {
    var wall = $("#donationWall");
    var pub = d.public || [];
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

    var pendingSection = $("#donationPendingSection");
    var pendingList = $("#donationPending");
    if (d.can_manage) {
      pendingSection.hidden = false;
      var pending = d.pending || [];
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

  function wireDonationActions() {
    var form = $("#donateForm");
    if (form && !form.dataset.wired) {
      form.dataset.wired = "1";
      form.addEventListener("submit", async function (e) {
        e.preventDefault();
        var msg = $("#donateMsg");
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
    }

    var pendingList = $("#donationPending");
    if (pendingList && !pendingList.dataset.wired) {
      pendingList.dataset.wired = "1";
      pendingList.addEventListener("click", async function (e) {
        var btn = e.target.closest("[data-donate-act]");
        if (!btn) return;
        var card = btn.closest("[data-donation]");
        var msg = card.querySelector("[data-donate-msg]");
        var act = btn.getAttribute("data-donate-act");
        var note = null;
        if (act === "reject") {
          note = window.prompt("Alasan menolak donasi ini (opsional):", "") || null;
        }
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

  async function selectProgram(name) {
    SELECTED = name;
    renderList();
    try {
      var data = await window.RN_FRAPPE.call(DETAIL_METHOD, { program: name });
      renderDetail(data);
    } catch (err) {
      console.error("[program detail]", err);
    }
  }

  async function loadBoard() {
    var data = await window.RN_FRAPPE.call(BOARD_METHOD, { disaster_event: getEventId2() });
    BOARD_CACHE = data;
    $("#programUpdated").textContent = "Program · Diperbarui " + String(data.generated_at || "").slice(11, 16);
    $("#programStatus").textContent = fmt((data.programs || []).length) + " program ditemukan.";

    renderKpi(data.totals || {});
    renderList();

    if (data.programs && data.programs.length && !SELECTED) {
      selectProgram(data.programs[0].name);
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    if (!window.RN_FRAPPE) return;
    document.querySelectorAll(".rn-pk-kpi .rn-kpi-btn").forEach(function (btn) {
      btn.addEventListener("click", function () { openDrill(btn.getAttribute("data-kpi")); });
    });
    document.querySelectorAll("#programDrill [data-close]").forEach(function (el) { el.addEventListener("click", closeDrill); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") closeDrill(); });
    setupFilterTabs();
    setupDetailTabs();
    wireDonationActions();
    loadBoard().catch(function (err) { console.error("[program board]", err); });
  });
})();

function getEventId() {
  return (
    new URLSearchParams(
      location.search
    ).get("event") ||
    "event-sim-001"
  );
}


function safe(v) {
  return (
    v === null ||
    v === undefined ||
    v === ""
  )
    ? "n/a"
    : v;
}


function rupiah(n) {
  return new Intl.NumberFormat(
    "id-ID"
  ).format(
    Number(n || 0)
  );
}


function setText(id, value) {
  const el =
    document.getElementById(id);

  if (el) {
    el.textContent = value;
  }
}


function programCard(p) {
  return `
    <article class="event-card">
      <div class="event-main">
        <div>
          <h4>${safe(p.program_name)}</h4>

          <p>
            Type: ${safe(p.program_type)}<br>
            Owner:
            ${safe(p.owner_type)} /
            ${safe(p.owner_id)}<br>
            Target:
            ${rupiah(p.target_amount)}
            ${safe(p.target_unit)}<br>
            Progress:
            ${safe(p.progress_percent)}%
          </p>
        </div>

        <div class="chips">
          <span class="chip warning">
            ${safe(p.program_status || p.status)}
          </span>
        </div>
      </div>
    </article>
  `;
}


async function loadPrograms() {
  const eventId =
    getEventId();

  const target =
    document.getElementById(
      "programListLegacy"
    );

  // api_donor_program.context is login-only (it carries create-form context).
  // The modern board (loadBoard → program_board, guest-allowed) is the real
  // list; this legacy <details> directory just degrades to a hint for guests.
  let ctx;
  try {
    ctx =
      await RN_FRAPPE.call(
        "rescue_net.api_donor_program.context",
        {
          disaster_event:
            eventId
        }
      );
  } catch (e) {
    if (target) {
      target.innerHTML = `
        <article class="event-card">
          <h4>Login untuk direktori lengkap</h4>
          <p>Daftar program di atas tetap tampil untuk umum.
             Masuk sebagai pengelola untuk direktori &amp; form program.</p>
        </article>`;
    }
    return;
  }

  const programs =
    ctx.programs || [];

  if (target) {
    target.innerHTML =
      programs.length
        ? programs
            .map(programCard)
            .join("")
        : `
          <article class="event-card">
            <h4>Belum ada program</h4>
            <p>
              Belum ada Donor Program pada event ini.
            </p>
          </article>
        `;
  }
}


function setupProgramForm() {
  const form =
    document.getElementById(
      "programForm"
    );

  if (!form) return;

  form.addEventListener(
    "submit",
    async e => {
      e.preventDefault();

      await RN_FRAPPE.call(
        "rescue_net.api_donor_program." +
        "create_program",
        {
          disaster_event:
            getEventId(),

          owner_type:
            form.owner_type?.value ||
            "organization",

          owner_id:
            form.owner_id.value.trim(),

          program_name:
            form.program_name.value.trim(),

          program_type:
            form.program_type.value.trim(),

          target_description:
            form.target_description.value
              .trim(),

          target_amount:
            Number(
              form.target_amount.value || 0
            ),

          target_unit:
            form.target_unit?.value ||
            "IDR",

          location:
            form.location?.value?.trim() ||
            null,

          notes:
            form.notes.value.trim()
        },
        {
          method: "POST"
        }
      );

      form.reset();

      await loadPrograms();
    }
  );
}


function setupUpdateForm() {
  const form =
    document.getElementById(
      "programUpdateForm"
    );

  if (!form) return;

  form.addEventListener(
    "submit",
    async e => {
      e.preventDefault();

      await RN_FRAPPE.call(
        "rescue_net.api_donor_program." +
        "create_update",
        {
          program:
            form.program_id.value.trim(),

          update_type:
            form.update_type.value.trim(),

          progress_percent:
            Number(
              form.progress_percent.value ||
              0
            ),

          amount_spent:
            Number(
              form.amount_spent.value ||
              0
            ),

          update_title:
            form.update_title.value
              .trim(),

          update_notes:
            form.update_notes.value
              .trim()
        },
        {
          method: "POST"
        }
      );

      form.reset();

      await loadPrograms();
    }
  );
}


document.addEventListener(
  "DOMContentLoaded",
  () => {
    if (!window.RN_FRAPPE) {
      return;
    }

    setupProgramForm();
    setupUpdateForm();

    const refresh =
      document.getElementById(
        "refreshPrograms"
      );

    if (refresh) {
      refresh.addEventListener(
        "click",
        () =>
          loadPrograms()
            .catch(err => console.error(err))
      );
    }

    loadPrograms()
      .catch(err => console.error(err));
  }
);
