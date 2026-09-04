const EVENT_ID = new URLSearchParams(window.location.search).get("event") || "event-sim-001";


async function rnFetch(path, options = {}) {
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
    const summary =
      await RN_FRAPPE.call(
        "rescue_net.api_frontend_bridge."
        + "consolidation_summary",
        {
          disaster_event:
            eventId
        }
      );

    return {
      disaster_event_id:
        eventId,
      summary,
      national_rollup:
        summary
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

function renderDuplicates(rows) {
  const target = document.querySelector("[data-duplicate-candidates]");
  if (!target) return;
  target.innerHTML = rows.length ? rows.map(row => `
    <article class="event-card">
      <div class="event-main">
        <div>
          <h4>${row.object_type}: ${row.object_id_a} vs ${row.object_id_b}</h4>
          <p>${row.match_reason || "candidate"} | score ${row.match_score} | status ${row.status}</p>
        </div>
        <div class="chips"><span class="chip warning">${row.status}</span></div>
      </div>
      <div class="community-report-actions">
        <button class="btn" type="button" data-resolve-duplicate="${row.id}" data-status="needs_review">Needs Review</button>
        <button class="btn" type="button" data-resolve-duplicate="${row.id}" data-status="not_duplicate">Not Duplicate</button>
        <button class="btn primary" type="button" data-resolve-duplicate="${row.id}" data-status="confirmed_duplicate">Confirm Duplicate</button>
      </div>
    </article>
  `).join("") : card("Tidak ada kandidat duplikat", "Belum ada raw report yang terdeteksi berpotensi overlap.", "ok");
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
    return card(
      `${name} | ${formatQty(qty)} ${unit}`,
      `${meta}${meta ? "<br>" : ""}Status: ${safe(row.status, "-")}`,
      row.status
    );
  }).join("") : card("Belum ada consolidated needs", "Klik Rebuild untuk membuat draft kebutuhan terkonsolidasi dari raw logistic needs.", "empty");
}

function formatQty(value) {
  const num = Number(value || 0);
  return Number.isInteger(num) ? String(num) : num.toFixed(2);
}

function renderNationalRollup(payload) {
  const target = document.querySelector("[data-national-rollup]");
  if (!target) return;
  const rows = payload?.national_rollup || [];
  target.innerHTML = rows.length ? rows.map(row => {
    const warning = row.duplicate_warning_count > 0;
    const chip = warning ? `<span class="chip warning">${row.duplicate_warning_count} overlap</span>` : '<span class="chip success">baseline detail</span>';
    return `
      <article class="event-card">
        <div class="event-main">
          <div>
            <h4>${safe(row.item_name)} | ${formatQty(row.baseline_quantity)} ${safe(row.quantity_unit, "")}</h4>
            <p>
              Range: ${formatQty(row.range_min)}-${formatQty(row.range_max)} ${safe(row.quantity_unit, "")}<br>
              Detail: ${row.detail_count || 0} posko/area | Sources: ${row.source_count || 0}<br>
              ${row.operator_note || ""}
            </p>
          </div>
          <div class="chips">
            <span class="chip neutral">${safe(row.need_type)}</span>
            ${chip}
          </div>
        </div>
      </article>
    `;
  }).join("") : card("Belum ada rollup nasional", "Klik Rebuild Consolidated Needs lalu muat ulang data konsolidasi.", "empty");
}

function renderRollupTrace(payload) {
  const target = document.querySelector("[data-rollup-trace]");
  if (!target) return;
  const details = payload?.detail_rows || [];
  const aggregate = payload?.aggregate_context || [];
  const rows = details.slice(0, 12).map(row => {
    const trace = row.trace || {};
    const place = [trace.village, trace.district, trace.city, trace.province].filter(Boolean).join(", ") || trace.area_level || "lokasi belum rinci";
    const warning = row.duplicate_warning_count > 0;
    return `
      <article class="event-card">
        <div class="event-main">
          <div>
            <h4>${safe(row.item_name)} | ${formatQty(row.quantity_final)} ${safe(row.quantity_unit, "")}</h4>
            <p>${place}<br>${safe(trace.posko_name)} | ${safe(trace.posko_id, "area report")}</p>
            <small>Sources: ${(trace.source_ids || []).join(", ") || "n/a"}</small>
          </div>
          <div class="chips">
            <span class="chip ${warning ? "warning" : "success"}">${warning ? "ada overlap" : "detail"}</span>
            <span class="chip neutral">${safe(trace.area_level)}</span>
          </div>
        </div>
      </article>
    `;
  });
  const aggregateRows = aggregate.slice(0, 6).map(row => {
    const trace = row.trace || {};
    const place = [trace.district, trace.city, trace.province].filter(Boolean).join(", ") || trace.area_level || "area agregat";
    return card(
      `${safe(row.item_name)} | konteks agregat`,
      `${place}<br>${row.sop_note || "Jangan masuk angka final sebelum dipecah ke posko/desa."}`,
      "aggregate context"
    );
  });
  target.innerHTML = rows.concat(aggregateRows).join("") || card("Belum ada trace", "Trace akan muncul setelah consolidated needs tersedia.", "empty");
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
      rnFetch(`/data-consolidation/summary?disaster_event_id=${encodeURIComponent(EVENT_ID)}`),
      rnFetch(`/data-consolidation/raw-reports?disaster_event_id=${encodeURIComponent(EVENT_ID)}`),
      rnFetch(`/duplicates/candidates?disaster_event_id=${encodeURIComponent(EVENT_ID)}`),
      rnFetch(`/consolidated-needs?disaster_event_id=${encodeURIComponent(EVENT_ID)}`),
      rnFetch(`/data-consolidation/national-rollup?disaster_event_id=${encodeURIComponent(EVENT_ID)}`),
      rnFetch(`/operational-areas?disaster_event_id=${encodeURIComponent(EVENT_ID)}`),
      rnFetch(`/beneficiary-groups?disaster_event_id=${encodeURIComponent(EVENT_ID)}`),
      rnFetch("/data-consolidation/evidence-requirements")
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
    renderRollupTrace(nationalRollup);
    renderAreas(areas);
    renderBeneficiaryGroups(groups);
    renderEvidenceRequirements(evidenceRules);
    setText("[data-consolidation-status]", "Loaded");
  } catch (err) {
    setText("[data-consolidation-status]", `${err.message}. Jika endpoint 404, jalankan rebuild API.`);
  }
}

function setupActions() {
  document.querySelector("[data-check-duplicates]")?.addEventListener("click", async () => {
    setText("[data-consolidation-status]", "Checking duplicate candidates...");
    await rnFetch("/duplicates/check", {
      method: "POST",
      body: JSON.stringify({ disaster_event_id: EVENT_ID, object_type: "all" })
    });
    await loadDataConsolidation();
  });

  document.querySelector("[data-check-community-duplicates]")?.addEventListener("click", async () => {
    setText("[data-consolidation-status]", "Checking community report overlap...");
    await rnFetch("/duplicates/check", {
      method: "POST",
      body: JSON.stringify({ disaster_event_id: EVENT_ID, object_type: "community_report" })
    });
    await loadDataConsolidation();
  });

  document.querySelector("[data-rebuild-consolidated]")?.addEventListener("click", async () => {
    setText("[data-consolidation-status]", "Rebuilding consolidated needs...");
    await rnFetch(`/consolidated-needs/rebuild?disaster_event_id=${encodeURIComponent(EVENT_ID)}`, {
      method: "POST"
    });
    await loadDataConsolidation();
  });

  document.addEventListener("click", async (event) => {
    const btn = event.target.closest("[data-resolve-duplicate]");
    if (!btn) return;
    await rnFetch(`/duplicates/${btn.getAttribute("data-resolve-duplicate")}/resolve`, {
      method: "POST",
      body: JSON.stringify({
        status: btn.getAttribute("data-status"),
        reviewed_by: "operator-web",
        review_notes: "Updated from Data Konsolidasi UI"
      })
    });
    await loadDataConsolidation();
  });

  document.addEventListener("click", async (event) => {
    const btn = event.target.closest("[data-community-consolidation]");
    if (!btn) return;
    const status = btn.getAttribute("data-status");
    await rnFetch(`/community-reports/${btn.getAttribute("data-community-consolidation")}/consolidation`, {
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
  });
}

document.addEventListener("DOMContentLoaded", () => {
  setupActions();
  loadDataConsolidation();
});
