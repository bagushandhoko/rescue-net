const EVENT_ID = new URLSearchParams(window.location.search).get("event") || "event-sim-001";


async function rnConsolFetch(path, options = {}) {
  const method =
    String(
      options.method || "GET"
    ).toUpperCase();

  const url =
    new URL(
      path,
      location.origin
    );

  const eventId =
    url.searchParams.get(
      "disaster_event_id"
    )
    || (
      typeof EVENT_ID !== "undefined"
        ? EVENT_ID
        : "event-sim-001"
    );

  if (
    url.pathname ===
      "/data-consolidation/edit-scope"
  ) {
    return await RN_FRAPPE.call(
      "rescue_net.api_frontend_bridge."
      + "consolidation_edit_scope",
      {
        disaster_event:
          eventId
      }
    );
  }

  if (
    url.pathname ===
      "/consolidation/override" && method === "POST"
  ) {
    const body = JSON.parse(options.body || "{}");
    return await RN_FRAPPE.call(
      "rescue_net.api_frontend_bridge."
      + "set_consolidation_override",
      {
        group_key: body.group_key,
        disaster_event: eventId,
        override_qty: body.override_qty,
        reason: body.reason
      },
      { method: "POST" }
    );
  }

  if (
    url.pathname ===
      "/consolidation/override/clear" && method === "POST"
  ) {
    const body = JSON.parse(options.body || "{}");
    return await RN_FRAPPE.call(
      "rescue_net.api_frontend_bridge."
      + "clear_consolidation_override",
      {
        group_key: body.group_key,
        disaster_event: eventId
      },
      { method: "POST" }
    );
  }

  if (
    url.pathname ===
      "/data-consolidation/summary"
  ) {
    return await RN_FRAPPE.call(
      "rescue_net.api_frontend_bridge."
      + "consolidation_summary",
      {
        disaster_event:
          eventId
      }
    );
  }

  if (
    url.pathname ===
      "/data-consolidation/raw-reports"
  ) {
    return await RN_FRAPPE.call(
      "rescue_net.api_frontend_bridge."
      + "consolidation_raw_reports",
      {
        disaster_event:
          eventId
      }
    );
  }

  if (
    url.pathname ===
      "/duplicates/candidates"
  ) {
    return await RN_FRAPPE.call(
      "rescue_net.api_frontend_bridge."
      + "duplicate_candidates",
      {
        disaster_event:
          eventId
      }
    );
  }

  if (
    url.pathname ===
      "/consolidated-needs"
  ) {
    return await RN_FRAPPE.call(
      "rescue_net.api_frontend_bridge."
      + "consolidated_needs",
      {
        disaster_event:
          eventId
      }
    );
  }

  if (
    url.pathname ===
      "/data-consolidation/national-rollup"
  ) {
    // Real consolidated rollup: canonical-group x base-unit with the
    // 3-bucket honest split (terukur / perkiraan / belum terukur).
    const ccs =
      await RN_FRAPPE.call(
        "rescue_net.api_intelligence.control_centre_summary",
        {}
      );
    return {
      disaster_event_id: eventId,
      groups: (ccs && ccs.groups) || [],
      raw_need_count: (ccs && ccs.raw_need_count) || 0,
      warning: ccs && ccs.warning
    };
  }

  if (
    url.pathname ===
      "/operational-areas"
  ) {
    const data =
      await RN_FRAPPE.call(
        "rescue_net.api_frontend_bridge."
        + "consolidation_auxiliary",
        {
          disaster_event:
            eventId
        }
      );

    return (
      data.operational_areas
      || []
    );
  }

  if (
    url.pathname ===
      "/beneficiary-groups"
  ) {
    const data =
      await RN_FRAPPE.call(
        "rescue_net.api_frontend_bridge."
        + "consolidation_auxiliary",
        {
          disaster_event:
            eventId
        }
      );

    return (
      data.beneficiary_groups
      || []
    );
  }

  if (
    url.pathname ===
      "/data-consolidation/evidence-requirements"
  ) {
    const data =
      await RN_FRAPPE.call(
        "rescue_net.api_frontend_bridge."
        + "consolidation_auxiliary",
        {
          disaster_event:
            eventId
        }
      );

    return (
      data.evidence_requirements
      || []
    );
  }

  if (url.pathname === "/duplicates/check" && method === "POST") {
    const body = JSON.parse(options.body || "{}");
    return await RN_FRAPPE.call(
      "rescue_net.api_frontend_bridge.duplicates_check",
      {
        disaster_event: body.disaster_event_id || eventId,
        object_type: body.object_type || "all"
      },
      { method: "POST" }
    );
  }

  if (/^\/duplicates\/.+\/resolve$/.test(url.pathname) && method === "POST") {
    const body = JSON.parse(options.body || "{}");
    const pairId = url.pathname.replace(/^\/duplicates\//, "").replace(/\/resolve$/, "");
    return await RN_FRAPPE.call(
      "rescue_net.api_frontend_bridge.resolve_duplicate_candidate",
      {
        pair_id: pairId,
        status: body.status,
        reviewed_by: body.reviewed_by,
        review_notes: body.review_notes
      },
      { method: "POST" }
    );
  }

  if (/^\/community-reports\/[^/]+\/consolidation$/.test(url.pathname) && method === "PATCH") {
    const body = JSON.parse(options.body || "{}");
    const report = url.pathname.split("/")[2];
    return await RN_FRAPPE.call(
      "rescue_net.api_frontend_bridge.community_report_set_consolidation",
      {
        report,
        consolidation_status: body.consolidation_status,
        location_status: body.location_status,
        is_aggregate: body.is_aggregate,
        reviewer_id: body.reviewer_id,
        notes: body.notes
      },
      { method: "POST" }
    );
  }

  if (url.pathname === "/consolidated-needs/rebuild" && method === "POST") {
    return await RN_FRAPPE.call(
      "rescue_net.api_intelligence.rebuild_consolidated_needs",
      { disaster_event: url.searchParams.get("disaster_event_id") || eventId },
      { method: "POST" }
    );
  }

  if (url.pathname === "/consolidated-needs/snapshots") {
    return await RN_FRAPPE.call(
      "rescue_net.api_intelligence.consolidated_need_snapshots",
      { disaster_event: eventId }
    );
  }

  if (url.pathname === "/consolidated-needs/snapshot-detail") {
    return await RN_FRAPPE.call(
      "rescue_net.api_intelligence.consolidated_need_snapshot_detail",
      { name: url.searchParams.get("name") }
    );
  }

  if (method !== "GET") {
    return await RN_FRAPPE.call(
      "rescue_net.api_frontend_bridge."
      + "unsupported_consolidation_operation",
      {
        operation:
          url.pathname
      },
      {
        method: "POST"
      }
    );
  }

  throw new Error(
    "Unsupported Consolidation route: "
    + url.pathname
  );
}


function setText(selector, value) {
  const el = document.querySelector(selector);
  if (el) el.textContent = value;
}

function safe(value, fallback = "n/a") {
  return value === null || value === undefined || value === "" ? fallback : value;
}

function card(title, body, chip = "") {
  return `
    <article class="event-card">
      <div class="event-main">
        <div>
          <h4>${title || "n/a"}</h4>
          <p>${body || ""}</p>
        </div>
        <div class="chips">${chip ? `<span class="chip warning">${chip}</span>` : ""}</div>
      </div>
    </article>
  `;
}

function statusChip(status) {
  const tone = ["verified_unique", "ready_for_review", "verified_location"].includes(status)
    ? "success"
    : ["not_ready_no_location", "not_ready_admin_only", "needs_location_review", "excluded_aggregate"].includes(status)
      ? "warning"
      : "neutral";
  return `<span class="chip ${tone}">${safe(status)}</span>`;
}

function renderRawReports(rows) {
  const target = document.querySelector("[data-raw-report-queue]");
  if (!target) return;
  target.innerHTML = rows.length ? rows.map(row => {
    const isAggregate = row.is_aggregate || ["province", "city", "district"].includes(row.area_level);
    const locationLine = [
      row.village_name,
      row.district_name,
      row.city_name,
      row.province_name
    ].filter(Boolean).join(", ") || row.location_text || "Belum ada lokasi rinci";
    // consolidation_raw_reports == api_frontend_bridge.community_reports:
    // rows are RN Community Report (report_type / affected_people_count /
    // consolidation_status / area_level), not the old flat "raw report" shape.
    const rid = row.id || row.name || row.legacy_id;
    const people = row.affected_people_count;
    return `
      <article class="event-card">
        <div class="event-main">
          <div>
            <h4>${safe(row.report_type, "laporan")}: ${safe(row.title)}</h4>
            <p>${locationLine}<br>${safe(row.description, "")}</p>
            <small>${safe(row.report_type, "-")}${people != null && people !== "" ? ` | ${people} jiwa terdampak` : ""}${row.trust_score != null ? ` | trust ${row.trust_score}` : ""}</small>
          </div>
          <div class="chips">
            ${statusChip(row.consolidation_status)}
            ${statusChip(row.verification_status)}
            ${isAggregate ? '<span class="chip warning">aggregate context</span>' : '<span class="chip success">detail candidate</span>'}
          </div>
        </div>
        <div class="community-report-actions">
          <button class="btn" type="button" data-community-consolidation="${rid}" data-status="needs_location_review">Review Lokasi</button>
          <button class="btn" type="button" data-community-consolidation="${rid}" data-status="excluded_aggregate">Tandai Agregat</button>
          <button class="btn primary" type="button" data-community-consolidation="${rid}" data-status="verified_unique">Verified Unique</button>
        </div>
      </article>
    `;
  }).join("") : card("Belum ada raw report", "Laporan mentah akan muncul di sini sebelum menjadi angka final.", "empty");
}

const DUPLICATE_STATUS_CHIP = {
  pending_review: "warning",
  needs_review: "warning",
  not_duplicate: "success",
  confirmed_duplicate: "neutral"
};

function renderDuplicates(rows) {
  const target = document.querySelector("[data-duplicate-candidates]");
  if (!target) return;
  target.innerHTML = rows.length ? rows.map(row => {
    return `
    <article class="event-card${row.status === "not_duplicate" ? " rn-dup-dismissed" : ""}">
      <div class="event-main">
        <div>
          <h4>${row.object_type}: ${row.object_id_a} vs ${row.object_id_b}</h4>
          <p>${row.match_reason || "candidate"} | score ${row.match_score} | status ${row.status}${row.reviewed_by ? ` · oleh ${row.reviewed_by}` : ""}</p>
          <p class="subtitle">${traceLinkHtml(row.posko_a, null, null, "Buka A →")} ${traceLinkHtml(row.posko_b, null, null, "Buka B →")}</p>
          <p class="subtitle" data-ai-dup-result="${row.id}">${row.ai_verdict ? `AI sebelumnya: ${row.ai_verdict === "duplicate" ? "DUPLIKAT" : row.ai_verdict === "different" ? "BEDA" : "tidak jelas"}` : ""}</p>
        </div>
        <div class="chips"><span class="chip ${DUPLICATE_STATUS_CHIP[row.status] || "warning"}">${row.status}</span></div>
      </div>
      <div class="community-report-actions">
        <button class="btn" type="button" data-analyze-duplicate="${row.id}" data-object-a="${row.object_id_a}" data-object-b="${row.object_id_b}">Analisa AI</button>
        <button class="btn" type="button" data-resolve-duplicate="${row.id}" data-status="needs_review">Needs Review</button>
        <button class="btn" type="button" data-resolve-duplicate="${row.id}" data-status="not_duplicate">Not Duplicate</button>
        <button class="btn primary" type="button" data-resolve-duplicate="${row.id}" data-status="confirmed_duplicate">Confirm Duplicate</button>
      </div>
    </article>
  `;
  }).join("") : card("Tidak ada kandidat duplikat", "Belum ada raw report yang terdeteksi berpotensi overlap.", "ok");
}

// Who may WRITE on this page for the current event — guest and any org
// that doesn't operate in this disaster event get can_edit_current:false;
// a System Manager gets it for every event. Fetched once on load (see
// loadEditScope()), applied by applyEditScope() (disables controls,
// never hides them — same rule as the rest of the app's posko pages).
let RN_EDIT_SCOPE = { logged_in: false, is_system_manager: false, editable_events: [], can_edit_current: false };

async function loadEditScope() {
  try {
    RN_EDIT_SCOPE = await rnConsolFetch(`/data-consolidation/edit-scope?disaster_event_id=${encodeURIComponent(EVENT_ID)}`);
  } catch (err) {
    RN_EDIT_SCOPE = { logged_in: false, is_system_manager: false, editable_events: [], can_edit_current: false };
  }
  applyEditScope();
}

function applyEditScope() {
  const canEdit = !!RN_EDIT_SCOPE.can_edit_current;

  document.querySelectorAll(
    "[data-check-duplicates], [data-check-community-duplicates], [data-rebuild-consolidated], " +
    "[data-resolve-duplicate], [data-community-consolidation], [data-consol-override-submit], [data-consol-override-clear]"
  ).forEach(el => { el.disabled = !canEdit; });

  const notice = document.querySelector("[data-consol-edit-notice]");
  if (notice) {
    notice.hidden = canEdit;
    notice.textContent = RN_EDIT_SCOPE.logged_in
      ? "Anda hanya bisa melihat bencana ini — edit hanya untuk organisasi yang menangani bencana ini, atau System Manager."
      : "Anda melihat sebagai tamu — login sebagai organisasi yang menangani bencana ini (atau System Manager) untuk bisa mengedit.";
  }
}

function renderConsolidated(rows) {
  const target = document.querySelector("[data-consolidated-needs]");
  if (!target) return;
  // consolidated_needs returns raw RN Community/Logistic Need rows
  // (quantity / unit / canonical_group), not a merged draft with
  // quantity_final / merge_method — fall back to the real fields.
  target.innerHTML = rows.length ? rows.map(row => {
    const qty = row.quantity_final != null ? row.quantity_final : row.quantity;
    const unit = row.quantity_unit || row.unit || "";
    const name = row.item_name || row.canonical_group || row.title || "Kebutuhan";
    const meta = [
      row.source_type ? `Sumber: ${row.source_type}` : null,
      row.canonical_group ? `Kelompok: ${row.canonical_group}` : null,
      row.merge_method ? `Metode: ${row.merge_method}` : null,
      row.source_count != null ? `Sumber: ${row.source_count}` : null,
    ].filter(Boolean).join(" | ");
    const link = traceLinkHtml(row.posko, row.source_report, row.disaster_event);
    return card(
      `${name} | ${formatQty(qty)} ${unit}`,
      `${meta}${meta ? "<br>" : ""}Status: ${safe(row.status, "-")}${link ? `<br>${link}` : ""}`,
      row.status
    );
  }).join("") : card("Belum ada consolidated needs", "Klik Rebuild untuk membuat draft kebutuhan terkonsolidasi dari raw logistic needs.", "empty");
}

function formatQty(value) {
  const num = Number(value || 0);
  return Number.isInteger(num) ? String(num) : num.toFixed(2);
}

// Real consolidated rollup from api_intelligence.control_centre_summary:
// one row per (canonical_group, base_unit) with the honest 3-bucket split.
// Kept here so a click can look a group back up without a second fetch.
let RN_ROLLUP_GROUPS = [];
let RN_ROLLUP_SELECTED = null;

function renderNationalRollup(payload) {
  const target = document.querySelector("[data-national-rollup]");
  if (!target) return;
  RN_ROLLUP_GROUPS = (payload?.groups || [])
    .slice()
    .sort((a, b) => (b.qty_total || 0) - (a.qty_total || 0));

  target.innerHTML = RN_ROLLUP_GROUPS.length ? RN_ROLLUP_GROUPS.map(g => {
    const unit = safe(g.base_unit, "");
    const est = Number(g.qty_estimated || 0) > 0;
    const um = Number(g.unmeasurable_count || 0) > 0;
    const active = g.group_key === RN_ROLLUP_SELECTED ? " selected" : "";
    return `
      <article class="event-card rn-rollup-card${active}" data-rollup-group="${g.group_key}" role="button" tabindex="0">
        <div class="event-main">
          <div>
            <h4>${safe(g.canonical_group || g.canonical_item)} | ${formatQty(g.qty_total)} ${unit}</h4>
            <p>
              Terukur: <b>${formatQty(g.qty_measurable)}</b> ${unit} ·
              Perkiraan AI: <b>${formatQty(g.qty_estimated)}</b> ${unit}<br>
              ${g.source_count != null ? `${g.source_count} laporan digabung` : ""}${g.organization_count > 1 ? ` · ${g.organization_count} organisasi` : ""}${um ? ` · ${g.unmeasurable_count} belum terukur` : ""}
              · <span class="rn-rollup-hint">klik untuk lihat sumber data asli →</span>
            </p>
          </div>
          <div class="chips">
            ${um ? `<span class="chip warning">${g.unmeasurable_count} belum terukur</span>`
                 : (est ? '<span class="chip neutral">ada perkiraan</span>'
                        : '<span class="chip success">terukur penuh</span>')}
          </div>
        </div>
      </article>
    `;
  }).join("") : card("Belum ada kebutuhan terkonsolidasi", "Belum ada kebutuhan logistik/komunitas aktif untuk dikonsolidasikan.", "empty");

  target.querySelectorAll("[data-rollup-group]").forEach(el => {
    function open() {
      renderRollupTrace(el.getAttribute("data-rollup-group"));
    }
    el.addEventListener("click", open);
    el.addEventListener("keydown", e => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(); }
    });
  });

  // Keep the previously-open trace in sync after a Rebuild/refresh.
  if (RN_ROLLUP_SELECTED) renderRollupTrace(RN_ROLLUP_SELECTED);
}

function stripPrefix(value, prefix) {
  return String(value || "").startsWith(prefix) ? String(value).slice(prefix.length) : String(value || "");
}

// Shared "trace to source" link builder — same posko/laporan-masyarakat
// routing as sourceRowHtml() below, reused by renderConsolidated() and
// renderDuplicates() so every panel on this page can point back to where
// a number actually came from, not just the Rollup Nasional trace.
function traceLinkHtml(posko, sourceReport, eventId, label) {
  const ev = eventId || EVENT_ID;
  if (posko) {
    const href = `posko-logistik.html?id=${encodeURIComponent(stripPrefix(posko, "posko_nodes:"))}&event=${encodeURIComponent(ev)}`;
    return `<a href="${href}">${label || "Buka di Posko Logistik →"}</a>`;
  }
  if (sourceReport) {
    const href = `laporan-masyarakat.html?report=${encodeURIComponent(sourceReport)}&event=${encodeURIComponent(ev)}`;
    return `<a href="${href}">${label || "Buka laporan masyarakat →"}</a>`;
  }
  return "";
}

// One raw record behind a rollup number — linked back to where it actually
// lives so an operator can verify/correct it, not just trust the estimate.
function sourceRowHtml(s) {
  const qty = s.quantity_min != null && s.quantity_max != null && s.quantity_min !== s.quantity_max
    ? `${formatQty(s.quantity_min)}–${formatQty(s.quantity_max)}`
    : formatQty(s.quantity);
  const eventId = stripPrefix(s.disaster_event, "disaster_events:");
  let href = null;
  let linkLabel = null;
  if (s.posko) {
    href = `posko-logistik.html?id=${encodeURIComponent(stripPrefix(s.posko, "posko_nodes:"))}&event=${encodeURIComponent(eventId)}`;
    linkLabel = "Buka di Posko Logistik →";
  } else if (s.source_report) {
    href = `laporan-masyarakat.html?report=${encodeURIComponent(s.source_report)}&event=${encodeURIComponent(eventId)}`;
    linkLabel = "Buka laporan masyarakat →";
  }
  return `
    <tr>
      <td>${safe(s.item_text)}</td>
      <td>${qty} ${safe(s.unit, "")}</td>
      <td>${safe(s.area, "-")}</td>
      <td>${safe(s.verification_status, "-")}</td>
      <td>${safe((s.observed_at || "").toString().slice(0, 16), "-")}</td>
      <td>${href ? `<a href="${href}">${linkLabel}</a>` : safe(s.name)}</td>
    </tr>
  `;
}

// "Trace": clicking a rollup card shows exactly which raw records (and
// where each one lives) were combined into that number, so an operator can
// judge whether MAX/the AI estimate is actually right instead of just
// trusting a black-box total.
function renderRollupTrace(groupKey) {
  const target = document.querySelector("[data-rollup-trace]");
  if (!target) return;

  RN_ROLLUP_SELECTED = groupKey || null;
  document.querySelectorAll("[data-rollup-group]").forEach(el => {
    el.classList.toggle("selected", el.getAttribute("data-rollup-group") === groupKey);
  });

  const g = RN_ROLLUP_GROUPS.find(row => row.group_key === groupKey);
  if (!g) {
    target.innerHTML = card(
      "Belum ada yang dipilih",
      "Klik salah satu baris di panel kiri (Rollup Nasional) untuk melihat daftar laporan mentah di baliknya.",
      ""
    );
    return;
  }

  target.innerHTML = groupDetailHtml(g, true);
  applyEditScope();
}

// Shared by the live rollup trace and the historical snapshot detail —
// same group shape (api_intelligence._group_rows output) either way.
// `live`: true only for the current Rollup Nasional trace (not the frozen
// historical snapshot replay) — that's the only context where "Override
// manual" / "Analisa AI" make sense, since they act on the LIVE group_key.
function groupDetailHtml(g, live) {
  const unit = safe(g.base_unit, "");
  const sources = g.sources || [];
  const hasOverride = g.override_reason != null || g.overridden_by;

  const overrideBlock = live ? `
    <article class="event-card">
      <div class="event-main">
        <div>
          <h4>Judgment manual</h4>
          <p>
            ${hasOverride
              ? `Override aktif: <b>${formatQty(g.qty_total)} ${unit}</b> (estimasi otomatis: ${formatQty(g.qty_total_computed)} ${unit})
                 oleh ${safe(g.overridden_by, "-")}${g.override_reason ? ` — ${g.override_reason}` : ""}`
              : "Belum ada override manual — angka di atas murni hasil MAX-rule."}
            ${g.ai_suggestion ? `<br>🤖 Saran AI: ${g.ai_suggestion}` : ""}
          </p>
        </div>
      </div>
      <div class="rn-form" style="margin-top:8px">
        <div class="form-grid">
          <label>Qty override
            <input type="number" step="any" data-consol-override-qty value="${hasOverride ? g.qty_total : ""}" placeholder="${formatQty(g.qty_total)}">
          </label>
          <label>Alasan
            <input type="text" data-consol-override-reason value="${safe(g.override_reason, "")}">
          </label>
        </div>
        <div class="form-actions">
          <button class="btn" type="button" data-analyze-rollup="${g.group_key}">Analisa AI</button>
          <button class="btn primary" type="button" data-consol-override-submit="${g.group_key}">Simpan Override</button>
          ${hasOverride ? `<button class="btn" type="button" data-consol-override-clear="${g.group_key}">Hapus Override</button>` : ""}
        </div>
      </div>
    </article>
  ` : "";

  return `
    <article class="event-card">
      <div class="event-main">
        <div>
          <h4>${safe(g.canonical_group || g.canonical_item)} — ${g.area || "Lintas wilayah"}</h4>
          <p>
            Total: <b>${formatQty(g.qty_total)} ${unit}</b> (MAX per overlap, bukan SUM)<br>
            Terukur: ${formatQty(g.qty_measurable)} ${unit} · Perkiraan AI: ${formatQty(g.qty_estimated)} ${unit}<br>
            Rentang mentah: ${g.estimate_min != null ? formatQty(g.estimate_min) : "-"}–${g.estimate_max != null ? formatQty(g.estimate_max) : "-"} ${unit} ·
            Confidence: ${g.confidence}% (${g.confidence_label})
          </p>
        </div>
      </div>
    </article>
    ${overrideBlock}
    <div class="rn-table-wrap">
      <table class="rn-table">
        <thead>
          <tr><th>Item (teks asli)</th><th>Qty</th><th>Area</th><th>Verifikasi</th><th>Diamati</th><th>Sumber</th></tr>
        </thead>
        <tbody>
          ${sources.length ? sources.map(sourceRowHtml).join("") : `<tr><td colspan="6">Tidak ada rincian sumber untuk kelompok ini.</td></tr>`}
        </tbody>
      </table>
    </div>
  `;
}

// ---- Riwayat Konsolidasi (RN Consolidated Need Snapshot) ----
// Metadata-only history: each snapshot stores which raw need IDs were
// included, not a copy of the computed numbers. Detail is recomputed live
// from those original records when opened.
let RN_SNAPSHOTS = [];
let RN_SNAPSHOT_SELECTED = null;
let RN_SNAPSHOT_GROUPS = [];
let RN_SNAPSHOT_GROUP_SELECTED = null;

function fmtSnapshotDate(value) {
  if (!value) return "-";
  return String(value).slice(0, 16).replace("T", " ");
}

function renderSnapshots() {
  const target = document.querySelector("[data-consolidation-snapshots]");
  if (!target) return;

  target.innerHTML = RN_SNAPSHOTS.length ? RN_SNAPSHOTS.map(s => {
    const active = s.name === RN_SNAPSHOT_SELECTED ? " selected" : "";
    return `
      <article class="event-card rn-rollup-card${active}" data-snapshot="${s.name}" role="button" tabindex="0">
        <div class="event-main">
          <div>
            <h4>${fmtSnapshotDate(s.creation)}</h4>
            <p>${s.raw_need_count} kebutuhan mentah → ${s.group_count} kelompok · rule ${safe(s.rule)} · oleh ${safe(s.triggered_by)}</p>
          </div>
        </div>
      </article>
    `;
  }).join("") : card("Belum ada snapshot", "Klik \"Rebuild Consolidated Needs\" untuk membuat snapshot pertama.", "empty");

  target.querySelectorAll("[data-snapshot]").forEach(el => {
    function open() { loadSnapshotDetail(el.getAttribute("data-snapshot")); }
    el.addEventListener("click", open);
    el.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(); } });
  });
}

async function loadSnapshots() {
  RN_SNAPSHOTS = await rnConsolFetch("/consolidated-needs/snapshots");
  renderSnapshots();
}

async function loadSnapshotDetail(name) {
  RN_SNAPSHOT_SELECTED = name;
  RN_SNAPSHOT_GROUP_SELECTED = null;
  renderSnapshots();

  const hint = document.querySelector("[data-snapshot-detail-hint]");
  const target = document.querySelector("[data-snapshot-detail]");
  if (hint) hint.textContent = "Memuat…";

  try {
    const detail = await rnConsolFetch(`/consolidated-needs/snapshot-detail?name=${encodeURIComponent(name)}`);
    RN_SNAPSHOT_GROUPS = detail.groups || [];

    if (hint) {
      hint.textContent = `${fmtSnapshotDate(detail.created)} · ${detail.raw_need_count_now} kebutuhan (saat ini)` +
        (detail.missing_since_snapshot ? `, ${detail.missing_since_snapshot} sudah dihapus/berubah sejak snapshot` : "") +
        " — klik kelompok untuk rincian sumber.";
    }

    if (target) {
      target.innerHTML = RN_SNAPSHOT_GROUPS.length ? RN_SNAPSHOT_GROUPS.map(g => `
        <article class="event-card rn-rollup-card" data-snapshot-group="${g.group_key}" role="button" tabindex="0">
          <div class="event-main">
            <div>
              <h4>${safe(g.canonical_group || g.canonical_item)} | ${formatQty(g.qty_total)} ${safe(g.base_unit, "")}</h4>
              <p>${g.area || "Lintas wilayah"} · <span class="rn-rollup-hint">klik untuk rincian →</span></p>
            </div>
          </div>
        </article>
      `).join("") : card("Tidak ada kelompok", "Semua record di snapshot ini sudah dihapus/berubah.", "empty");

      target.querySelectorAll("[data-snapshot-group]").forEach(el => {
        el.addEventListener("click", () => {
          const g = RN_SNAPSHOT_GROUPS.find(row => row.group_key === el.getAttribute("data-snapshot-group"));
          if (g) target.insertAdjacentHTML("beforeend", groupDetailHtml(g));
        });
      });
    }
  } catch (err) {
    if (hint) hint.textContent = "✗ " + err.message;
  }
}

function renderAreas(rows) {
  const target = document.querySelector("[data-operational-areas]");
  if (!target) return;
  // consolidation_auxiliary.operational_areas: distinct posko place tuples
  // { province_name, city_name, district_name, village_name, area_level }.
  target.innerHTML = rows.length ? rows.map(row => {
    const place = [row.village_name, row.district_name, row.city_name, row.province_name]
      .filter(Boolean).join(", ") || "Lokasi belum rinci";
    return card(
      place,
      `Level area: ${safe(row.area_level, "-")}`,
      row.area_level
    );
  }).join("") : card("Belum ada operational area", "Tambahkan area kerja agar organisasi provinsi tidak dianggap mewakili semua desa.", "empty");
}

function renderBeneficiaryGroups(rows) {
  const target = document.querySelector("[data-beneficiary-groups]");
  if (!target) return;
  target.innerHTML = rows.length ? rows.map(row => card(
    row.group_name,
    `${row.group_type} | ${row.estimated_people_count || 0} orang | ${row.household_count || 0} KK<br>${row.description || ""}`,
    row.verified_status
  )).join("") : card("Belum ada beneficiary group", "Kelompok penerima membantu mencegah kebutuhan untuk orang yang sama dijumlahkan dua kali.", "empty");
}

function renderEvidenceRequirements(payload) {
  const target = document.querySelector("[data-evidence-requirements]");
  if (!target) return;
  const official = payload.official_area_reference;
  const intro = official ? `
    <article class="event-card">
      <div class="event-main">
        <div>
          <h4>${official.label}</h4>
          <p><a href="${official.url}" target="_blank" rel="noopener">${official.url}</a><br>${official.notes}</p>
        </div>
        <div class="chips"><span class="chip neutral">${official.usage}</span></div>
      </div>
    </article>
  ` : "";
  const rules = payload.rules || [];
  target.innerHTML = intro + (rules.length ? rules.map(rule => card(
    rule.data_type,
    `Camera: ${rule.camera_required}<br>Status butuh bukti: ${(rule.evidence_required_for_status || []).join(", ")}<br>Bukti diterima: ${(rule.accepted_evidence || []).join(", ")}<br>${rule.notes || ""}`,
    rule.camera_required
  )).join("") : card("Belum ada aturan evidence", "Endpoint evidence requirements belum mengirim aturan.", "empty"));
}

async function loadDataConsolidation() {
  try {
    const [summary, rawReports, duplicates, consolidated, nationalRollup, areas, groups, evidenceRules] = await Promise.all([
      rnConsolFetch(`/data-consolidation/summary?disaster_event_id=${encodeURIComponent(EVENT_ID)}`),
      rnConsolFetch(`/data-consolidation/raw-reports?disaster_event_id=${encodeURIComponent(EVENT_ID)}`),
      rnConsolFetch(`/duplicates/candidates?disaster_event_id=${encodeURIComponent(EVENT_ID)}`),
      rnConsolFetch(`/consolidated-needs?disaster_event_id=${encodeURIComponent(EVENT_ID)}`),
      rnConsolFetch(`/data-consolidation/national-rollup?disaster_event_id=${encodeURIComponent(EVENT_ID)}`),
      rnConsolFetch(`/operational-areas?disaster_event_id=${encodeURIComponent(EVENT_ID)}`),
      rnConsolFetch(`/beneficiary-groups?disaster_event_id=${encodeURIComponent(EVENT_ID)}`),
      rnConsolFetch("/data-consolidation/evidence-requirements"),
      loadEditScope()
    ]);

    // consolidation_summary only returns *_count totals; derive the tiles the
    // page actually shows from the lists we just fetched.
    const rawList = rawReports || [];
    const AGG_LEVELS = ["province", "city", "district"];
    const reviewCount = rawList.filter(r =>
      ["needs_location_review", "not_ready_no_location", "not_ready_admin_only"].includes(r.consolidation_status)
    ).length;
    const aggCount = rawList.filter(r =>
      r.is_aggregate || r.consolidation_status === "excluded_aggregate" || AGG_LEVELS.includes(r.area_level)
    ).length;
    setText("[data-raw-reports]", rawList.length);
    setText("[data-consolidated-count]", (consolidated || []).length);
    setText("[data-duplicate-count]", (duplicates || []).length);
    setText("[data-location-review-count]", reviewCount);
    setText("[data-aggregate-count]", aggCount);

    renderRawReports(rawReports);
    renderDuplicates(duplicates);
    renderConsolidated(consolidated);
    renderNationalRollup(nationalRollup);
    if (!RN_ROLLUP_SELECTED) renderRollupTrace(null);
    renderAreas(areas);
    renderBeneficiaryGroups(groups);
    renderEvidenceRequirements(evidenceRules);
    applyEditScope();
    setText("[data-consolidation-status]", "Loaded");
  } catch (err) {
    setText("[data-consolidation-status]", `${err.message}. Jika endpoint 404, jalankan rebuild API.`);
  }

  try {
    await loadSnapshots();
  } catch (err) {
    setText("[data-snapshot-detail-hint]", "✗ " + err.message);
  }
}

function setupActions() {
  document.querySelector("[data-check-duplicates]")?.addEventListener("click", async () => {
    setText("[data-consolidation-status]", "Checking duplicate candidates...");
    try {
      const r = await rnConsolFetch("/duplicates/check", {
        method: "POST",
        body: JSON.stringify({ disaster_event_id: EVENT_ID, object_type: "all" })
      });
      await loadDataConsolidation();
      setText("[data-consolidation-status]", `${(r && r.candidate_count) || 0} kandidat duplikat ditemukan.`);
    } catch (err) {
      setText("[data-consolidation-status]", err.message);
    }
  });

  document.querySelector("[data-check-community-duplicates]")?.addEventListener("click", async () => {
    setText("[data-consolidation-status]", "Checking community report overlap...");
    try {
      await rnConsolFetch("/duplicates/check", {
        method: "POST",
        body: JSON.stringify({ disaster_event_id: EVENT_ID, object_type: "community_report" })
      });
      await loadDataConsolidation();
    } catch (err) {
      setText("[data-consolidation-status]", err.message);
    }
  });

  // Creates an RN Consolidated Need Snapshot — metadata + the raw need IDs
  // included right now, not a copy of the computed numbers (see Riwayat
  // Konsolidasi panel). Recomputed live from those original records when
  // a past snapshot is opened, so nothing drifts out of sync with source.
  document.querySelector("[data-rebuild-consolidated]")?.addEventListener("click", async () => {
    setText("[data-consolidation-status]", "Rebuilding consolidated needs...");
    try {
      const r = await rnConsolFetch(`/consolidated-needs/rebuild?disaster_event_id=${encodeURIComponent(EVENT_ID)}`, {
        method: "POST"
      });
      await loadDataConsolidation();
      setText("[data-consolidation-status]", `Snapshot dibuat: ${r.raw_need_count} kebutuhan → ${r.group_count} kelompok.`);
    } catch (err) {
      setText("[data-consolidation-status]", err.message);
    }
  });

  // Manual, on-demand AI judgment per candidate pair (real paid API call
  // against the operator's own BYOK key — deliberately not automatic).
  document.addEventListener("click", async (event) => {
    const btn = event.target.closest("[data-analyze-duplicate]");
    if (!btn) return;
    const pairId = btn.getAttribute("data-analyze-duplicate");
    const out = document.querySelector(`[data-ai-dup-result="${pairId}"]`);
    const originalLabel = btn.textContent;
    btn.disabled = true;
    btn.textContent = "Menganalisa…";
    if (out) out.textContent = "";
    try {
      const session = await RN_FRAPPE.session();
      if (!session || !session.user) throw new Error("Perlu login untuk fitur ini.");
      const r = await RN_FRAPPE.call(
        "rescue_net.api_ai.analyze_duplicate_candidate",
        {
          user_id: session.user,
          object_id_a: btn.getAttribute("data-object-a"),
          object_id_b: btn.getAttribute("data-object-b")
        },
        { method: "POST" }
      );
      if (out) {
        const label = r.verdict === "duplicate" ? "🔴 AI: kemungkinan DUPLIKAT"
          : r.verdict === "different" ? "🟢 AI: kemungkinan BEDA"
          : "⚪ AI: tidak jelas";
        out.textContent = `${label} — ${r.answer || ""}`;
      }
    } catch (err) {
      if (out) out.textContent = "✗ " + err.message;
    } finally {
      btn.disabled = false;
      btn.textContent = originalLabel;
    }
  });

  document.addEventListener("click", async (event) => {
    const btn = event.target.closest("[data-resolve-duplicate]");
    if (!btn) return;
    // Persists to RN Duplicate Candidate Resolution (upserted by pair_id),
    // overlaid back onto duplicate_candidates() on the next load.
    try {
      await rnConsolFetch(`/duplicates/${btn.getAttribute("data-resolve-duplicate")}/resolve`, {
        method: "POST",
        body: JSON.stringify({
          status: btn.getAttribute("data-status"),
          reviewed_by: "operator-web",
          review_notes: "Updated from Data Konsolidasi UI"
        })
      });
      await loadDataConsolidation();
      setText("[data-consolidation-status]", "Status kandidat duplikat disimpan.");
    } catch (err) {
      setText("[data-consolidation-status]", err.message);
    }
  });

  document.addEventListener("click", async (event) => {
    const btn = event.target.closest("[data-community-consolidation]");
    if (!btn) return;
    const status = btn.getAttribute("data-status");
    try {
      await rnConsolFetch(`/community-reports/${btn.getAttribute("data-community-consolidation")}/consolidation`, {
        method: "PATCH",
        body: JSON.stringify({
          consolidation_status: status,
          location_status: status === "verified_unique" ? "verified_location" : undefined,
          is_aggregate: status === "excluded_aggregate" ? true : undefined,
          reviewer_id: "operator-web",
          notes: "Updated from Data Konsolidasi UI"
        })
      });
      await loadDataConsolidation();
    } catch (err) {
      setText("[data-consolidation-status]", err.message);
    }
  });

  // Manual, on-demand AI judgment for one Rollup Nasional group —
  // advisory only, mirrors the duplicate-candidate "Analisa AI" pattern.
  document.addEventListener("click", async (event) => {
    const btn = event.target.closest("[data-analyze-rollup]");
    if (!btn) return;
    const groupKey = btn.getAttribute("data-analyze-rollup");
    const originalLabel = btn.textContent;
    btn.disabled = true;
    btn.textContent = "Menganalisa…";
    try {
      const session = await RN_FRAPPE.session();
      if (!session || !session.user) throw new Error("Perlu login untuk fitur ini.");
      await RN_FRAPPE.call(
        "rescue_net.api_ai.analyze_rollup_group",
        { user_id: session.user, disaster_event: EVENT_ID, group_key: groupKey },
        { method: "POST" }
      );
      renderRollupTrace(RN_ROLLUP_SELECTED);
      setText("[data-consolidation-status]", "Analisa AI selesai.");
    } catch (err) {
      setText("[data-consolidation-status]", err.message);
    } finally {
      btn.disabled = false;
      btn.textContent = originalLabel;
    }
  });

  // Operator's manual judgment on a rollup group's total — persists to
  // RN Consolidation Group Override, overlaid back onto the live rollup.
  document.addEventListener("click", async (event) => {
    const btn = event.target.closest("[data-consol-override-submit]");
    if (!btn) return;
    const groupKey = btn.getAttribute("data-consol-override-submit");
    const form = btn.closest(".rn-form");
    const qty = form?.querySelector("[data-consol-override-qty]")?.value;
    const reason = form?.querySelector("[data-consol-override-reason]")?.value;
    if (qty === "" || qty == null) {
      setText("[data-consolidation-status]", "Isi qty override dulu.");
      return;
    }
    try {
      await rnConsolFetch("/consolidation/override", {
        method: "POST",
        body: JSON.stringify({ group_key: groupKey, override_qty: qty, reason })
      });
      await loadDataConsolidation();
      setText("[data-consolidation-status]", "Override manual disimpan.");
    } catch (err) {
      setText("[data-consolidation-status]", err.message);
    }
  });

  document.addEventListener("click", async (event) => {
    const btn = event.target.closest("[data-consol-override-clear]");
    if (!btn) return;
    const groupKey = btn.getAttribute("data-consol-override-clear");
    try {
      await rnConsolFetch("/consolidation/override/clear", {
        method: "POST",
        body: JSON.stringify({ group_key: groupKey })
      });
      await loadDataConsolidation();
      setText("[data-consolidation-status]", "Override manual dihapus.");
    } catch (err) {
      setText("[data-consolidation-status]", err.message);
    }
  });

  // KPI cards -> jump to + briefly highlight the panel with that detail.
  document.querySelectorAll("[data-kpi-target]").forEach(btn => {
    btn.addEventListener("click", () => {
      const target = document.getElementById(btn.getAttribute("data-kpi-target"));
      if (!target) return;
      target.scrollIntoView({ behavior: "smooth", block: "start" });
      target.classList.add("rn-kpi-jump-highlight");
      setTimeout(() => target.classList.remove("rn-kpi-jump-highlight"), 1600);
    });
  });
}

document.addEventListener("DOMContentLoaded", () => {
  setupActions();
  loadDataConsolidation();
});
