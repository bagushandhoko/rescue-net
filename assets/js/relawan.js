/* ============================================================
 * New dashboard (matches manajemen relawan.png): calls
 * rescue_net.api_volunteer.volunteer_board (guest, event-wide).
 * The legacy per-posko panels below (Ringkasan/Daftar Relawan
 * mentah/Assignments, the 2 forms) keep calling
 * api_volunteer.dashboard / create_profile / create_assignment
 * unchanged.
 * ============================================================ */
(function () {
  "use strict";

  var BOARD_METHOD = "rescue_net.api_volunteer.volunteer_board";
  var BOARD_CACHE = null;

  var $ = function (sel, root) { return (root || document).querySelector(sel); };
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function fmt(n) { return Number(n || 0).toLocaleString("id-ID"); }
  function getEventId() { return new URLSearchParams(window.location.search).get("event") || "event-sim-001"; }

  function statusPillClass(status) {
    if (status === "unavailable" || status === "off_duty") return "";
    if (status === "assigned") return "warning";
    if (status === "available") return "ok";
    return "";
  }

  var DRILL_TITLES = {
    terdaftar: "Relawan Terdaftar", available: "Available Hari Ini",
    bertugas: "Sedang Bertugas", butuh: "Butuh Penugasan", fatigue: "Fatigue Risk",
  };
  var DRILL_FIELD = {
    terdaftar: "terdaftar_items", available: "available_items",
    bertugas: "bertugas_items", butuh: "butuh_items", fatigue: "fatigue_items",
  };

  function drillItemsHtml(items) {
    if (!items || !items.length) return '<p class="rn-muted">Tidak ada data untuk ditampilkan.</p>';
    return items.map(function (it) {
      var inner =
        "<span><b>" + esc(it.title) + "</b><small>" + esc(it.sub || "") + "</small></span>" +
        (it.href ? '<span class="rn-ba-ditem-go">→</span>' : "");
      return it.href
        ? '<a class="rn-ba-ditem" href="' + esc(it.href) + '">' + inner + "</a>"
        : '<div class="rn-ba-ditem" style="cursor:default">' + inner + "</div>";
    }).join("");
  }

  function openDrill(kind) {
    if (!BOARD_CACHE) return;
    var items = ((BOARD_CACHE.kpi_items || {})[DRILL_FIELD[kind]]) || [];
    $("#relawanDrillTitle").textContent = DRILL_TITLES[kind] || kind;
    $("#relawanDrillSub").textContent = items.length + " item";
    $("#relawanDrillBody").innerHTML = drillItemsHtml(items);
    $("#relawanDrill").hidden = false;
    document.body.style.overflow = "hidden";
  }
  function closeDrill() { $("#relawanDrill").hidden = true; document.body.style.overflow = ""; }

  function renderKpi(t) {
    $("#kpiTerdaftar").textContent = fmt(t.terdaftar);
    $("#kpiAvailable").textContent = fmt(t.available_hari_ini);
    $("#kpiBertugas").textContent = fmt(t.sedang_bertugas);
    $("#kpiButuh").textContent = fmt(t.butuh_penugasan);
    $("#kpiFatigue").textContent = fmt(t.fatigue_risk);
  }

  function renderDaftarRelawan(rows) {
    var body = $("#daftarRelawanBody");
    if (!rows.length) {
      body.innerHTML = '<tr><td colspan="6"><em class="rn-muted">Belum ada relawan tercatat untuk event ini.</em></td></tr>';
      $("#daftarRelawanShown").textContent = "0 relawan";
      return;
    }
    body.innerHTML = rows.map(function (r) {
      var skills = r.skills.map(function (s) { return '<span class="chip">' + esc(s) + "</span>"; }).join(" ");
      return (
        "<tr><td><b>" + esc(r.volunteer_name) + "</b></td><td>" + esc(r.organisasi) + "</td>" +
        "<td>" + skills + "</td><td>" + esc(r.lokasi) + "</td><td>" + esc(r.durasi) + "</td>" +
        '<td><span class="chip ' + statusPillClass(r.status) + '">' + esc(r.status) + "</span></td></tr>"
      );
    }).join("");
    $("#daftarRelawanShown").textContent = "Menampilkan " + rows.length + " dari " + rows.length + " relawan";
  }

  function setupSearch() {
    var input = $("#relawanSearch");
    if (!input) return;
    input.addEventListener("input", function () {
      var q = input.value.trim().toLowerCase();
      var rows = (BOARD_CACHE && BOARD_CACHE.daftar_relawan) || [];
      var filtered = !q ? rows : rows.filter(function (r) {
        return (r.volunteer_name + " " + r.organisasi + " " + r.skills.join(" ")).toLowerCase().indexOf(q) !== -1;
      });
      renderDaftarRelawan(filtered);
    });
  }

  function renderFilterKeterampilan(rows) {
    var el = $("#filterKeterampilan");
    if (!rows.length) { el.innerHTML = '<p class="rn-muted">Belum ada data skill.</p>'; return; }
    var max = Math.max.apply(null, rows.map(function (r) { return r.count; }));
    el.innerHTML = rows.map(function (r) {
      var pct = max ? Math.round((100 * r.count) / max) : 0;
      return (
        '<div class="rn-rw-skill-row"><div class="rn-rw-skill-head"><span>' + esc(r.label) + "</span><b>" + fmt(r.count) + "</b></div>" +
        '<div class="rn-rw-skill-bar"><i style="width:' + pct + '%"></i></div></div>'
      );
    }).join("");
  }

  function renderJenisRelawan(rows) {
    var el = $("#jenisRelawan");
    if (!rows.length) { el.innerHTML = '<p class="rn-muted">Belum ada data.</p>'; return; }
    el.innerHTML = rows.map(function (r) {
      return '<div class="rn-rw-jenis-tile"><b>' + fmt(r.count) + "</b><span>" + esc(r.label) + "</span></div>";
    }).join("");
  }

  function renderPapan(rows) {
    $("#papanCount").textContent = rows.length;
    var el = $("#papanPenugasan");
    if (!rows.length) {
      el.innerHTML = '<article class="event-card"><div class="event-main"><div><h4>Tidak ada tugas menunggu</h4><p>Semua assignment sudah diterima/berjalan.</p></div></div></article>';
      return;
    }
    el.innerHTML = rows.map(function (r) {
      var badge = r.priority === "critical" || r.priority === "urgent" ? "danger" : "";
      return (
        '<a class="event-card rn-sh-alert" href="' + esc(r.href) + '"><div class="event-main"><div><h4>' + esc(r.task_title) + "</h4>" +
        "<p>" + esc(r.posko) + " · menunggu konfirmasi: <b>" + esc(r.volunteer_name) + "</b></p></div>" +
        '<div class="chips"><span class="chip ' + badge + '">' + esc(r.priority) + "</span></div></div></a>"
      );
    }).join("");
  }

  async function loadBoard() {
    var data = await window.RN_FRAPPE.call(BOARD_METHOD, { disaster_event: getEventId() });
    BOARD_CACHE = data;
    $("#relawanUpdated").textContent = "Relawan · Diperbarui " + String(data.generated_at || "").slice(11, 16);
    renderKpi(data.totals || {});
    renderDaftarRelawan(data.daftar_relawan || []);
    renderFilterKeterampilan(data.filter_keterampilan || []);
    renderJenisRelawan(data.jenis_relawan || []);
    renderPapan(data.papan_penugasan || []);
  }

  document.addEventListener("DOMContentLoaded", function () {
    if (!window.RN_FRAPPE) return;
    document.querySelectorAll(".rn-rw-kpi .rn-kpi-btn").forEach(function (btn) {
      btn.addEventListener("click", function () { openDrill(btn.getAttribute("data-kpi")); });
    });
    document.querySelectorAll("#relawanDrill [data-close]").forEach(function (el) { el.addEventListener("click", closeDrill); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") closeDrill(); });
    setupSearch();
    loadBoard().catch(function (err) { console.error("[relawan board]", err); });
  });
})();

const RELAWAN_DEFAULT_POSKO =
  new URLSearchParams(
    location.search
  ).get("posko") ||
  "posko-sim-logistik";


function safe(v) {
  return (
    v === null ||
    v === undefined ||
    v === ""
  )
    ? "n/a"
    : v;
}


function statusMsg(msg) {
  const el =
    document.querySelector(
      "[data-relawan-status]"
    ) ||
    document.getElementById(
      "relawanStatus"
    );

  if (el) {
    el.textContent = msg;
  }
}


function card(
  title,
  body,
  chip = ""
) {
  return `
    <article class="event-card">
      <div class="event-main">
        <div>
          <h4>${safe(title)}</h4>
          <p>${body}</p>
        </div>

        <div class="chips">
          ${
            chip
              ? `<span class="chip warning">${safe(chip)}</span>`
              : ""
          }
        </div>
      </div>
    </article>
  `;
}


function renderSummary(ctx) {
  const target =
    document.querySelector(
      "[data-relawan-summary]"
    ) ||
    document.getElementById(
      "relawanSummary"
    );

  if (!target) return;

  const profiles =
    ctx.profiles || [];

  const assignments =
    ctx.assignments || [];

  const available =
    profiles.filter(
      x =>
        x.availability_status ===
        "available"
    ).length;

  target.innerHTML = `
    <div>
      <span>Volunteers</span>
      <b>${profiles.length}</b>
    </div>

    <div>
      <span>Available</span>
      <b>${available}</b>
    </div>

    <div>
      <span>Assignments</span>
      <b>${assignments.length}</b>
    </div>

    <div>
      <span>Mode</span>
      <b>${safe(ctx.mode)}</b>
    </div>
  `;
}


function renderVolunteers(items) {
  const target =
    document.querySelector(
      "[data-relawan-list]"
    ) ||
    document.getElementById(
      "relawanList"
    );

  if (!target) return;

  target.innerHTML =
    items.length
      ? items.map(v => card(
          v.volunteer_name,
          `Skill: ${safe(v.main_skill)}<br>` +
          `Tags: ${safe(v.skill_tags)}<br>` +
          `Location: ${safe(v.current_location)}<br>` +
          `Contact: ${safe(v.contact)}`,
          v.availability_status
        )).join("")
      : card(
          "Belum ada volunteer",
          "Belum ada RN Volunteer Profile.",
          "empty"
        );
}


function renderAssignments(items) {
  const target =
    document.querySelector(
      "[data-relawan-assignments]"
    ) ||
    document.getElementById(
      "relawanAssignments"
    );

  if (!target) return;

  target.innerHTML =
    items.length
      ? items.map(a => card(
          a.task_title,
          `Volunteer: ${safe(a.volunteer)}<br>` +
          `Posko: ${safe(a.posko)}<br>` +
          `Priority: ${safe(a.priority)}<br>` +
          `${safe(a.assignment_notes)}`,
          a.assignment_status
        )).join("")
      : card(
          "Belum ada assignment",
          "Belum ada RN Volunteer Assignment.",
          "empty"
        );
}


function fillVolunteerSelect(items) {
  const select =
    document.querySelector(
      "[name='volunteer_id']"
    );

  if (!select) return;

  select.innerHTML =
    `<option value="">Select volunteer</option>` +
    items.map(v => `
      <option value="${v.name}">
        ${safe(v.volunteer_name)}
      </option>
    `).join("");
}


async function loadRelawan() {
  statusMsg(
    "Loading volunteers from Frappe..."
  );

  const ctx =
    await RN_FRAPPE.call(
      "rescue_net.api_volunteer.dashboard",
      {
        posko:
          RELAWAN_DEFAULT_POSKO
      }
    );

  renderSummary(ctx);
  renderVolunteers(
    ctx.profiles || []
  );
  renderAssignments(
    ctx.assignments || []
  );
  fillVolunteerSelect(
    ctx.profiles || []
  );

  statusMsg(
    "Loaded from Frappe"
  );
}


function setupVolunteerForm() {
  const form =
    document.querySelector(
      "[data-create-relawan]"
    ) ||
    document.getElementById(
      "relawanForm"
    );

  if (!form) return;

  form.addEventListener(
    "submit",
    async e => {
      e.preventDefault();

      const tags =
        form.skill_tags.value
          .trim();

      const mainSkill =
        (
          tags.split(
            /[,;|]/
          )[0] ||
          "general"
        ).trim();

      await RN_FRAPPE.call(
        "rescue_net.api_volunteer.create_profile",
        {
          volunteer_name:
            form.volunteer_name.value
              .trim(),

          main_skill:
            mainSkill,

          contact:
            form.contact.value.trim(),

          skill_tags:
            tags,

          current_location:
            form.current_location.value
              .trim(),

          notes:
            form.notes.value.trim()
        },
        {
          method: "POST"
        }
      );

      statusMsg(
        "Volunteer profile saved."
      );

      form.reset();

      await loadRelawan();
    }
  );
}


function setupAssignmentForm() {
  const form =
    document.querySelector(
      "[data-create-relawan-assignment]"
    ) ||
    document.getElementById(
      "assignmentForm"
    );

  if (!form) return;

  form.addEventListener(
    "submit",
    async e => {
      e.preventDefault();

      await RN_FRAPPE.call(
        "rescue_net.api_volunteer.create_assignment",
        {
          volunteer:
            form.volunteer_id.value,

          posko:
            form.assigned_to_id.value
              .trim(),

          task_title:
            form.task_name.value
              .trim(),

          assignment_type:
            form.assigned_to_type.value ||
            "posko",

          priority:
            form.priority.value ||
            "normal",

          assignment_notes:
            form.task_description.value
              .trim()
        },
        {
          method: "POST"
        }
      );

      statusMsg(
        "Volunteer assignment saved."
      );

      form.reset();

      await loadRelawan();
    }
  );
}


document.addEventListener(
  "DOMContentLoaded",
  () => {
    if (!window.RN_FRAPPE) {
      statusMsg(
        "Frappe client tidak tersedia."
      );
      return;
    }

    setupVolunteerForm();
    setupAssignmentForm();

    const btn =
      document.querySelector(
        "[data-refresh-relawan]"
      ) ||
      document.getElementById(
        "refreshRelawan"
      );

    if (btn) {
      btn.addEventListener(
        "click",
        () =>
          loadRelawan()
            .catch(
              err =>
                statusMsg(err.message)
            )
      );
    }

    loadRelawan()
      .catch(
        err =>
          statusMsg(err.message)
      );
  }
);
