
function rnCardSafe(title, body, chip = "") {
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

function rnMoney(n) {
  return new Intl.NumberFormat("id-ID", { maximumFractionDigits: 0 }).format(Number(n || 0));
}


let warScenario = localStorage.getItem("rn_war_scenario") || "optimal";
let latestScenarioPayload = null;
function getEventId() {
  const params = new URLSearchParams(window.location.search);
  return params.get("event") || params.get("id") || "event-sim-001";
}

function safe(v, fallback = "n/a") {
  return v === null || v === undefined || v === "" ? fallback : v;
}

function setText(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

function card(title, body, chip = "") {
  return `
    <article class="event-card">
      <div class="event-main">
        <div>
          <h4>${title}</h4>
          <p>${body}</p>
        </div>
        <div class="chips">
          ${chip ? `<span class="chip warning">${chip}</span>` : ""}
        </div>
      </div>
    </article>
  `;
}

// RN_CONTROL_CENTRE_FRAPPE_ROUTER_V1

const RN_FRAPPE_METHOD_BASE =
  location.origin + "/rescue-net-frappe/api/method";

async function frappeMethod(method, args = {}) {
  const url =
    RN_FRAPPE_METHOD_BASE + "/" + method;

  const params = new URLSearchParams();

  Object.entries(args).forEach(([key, value]) => {
    if (
      value !== undefined &&
      value !== null &&
      value !== ""
    ) {
      params.set(key, String(value));
    }
  });

  const target =
    params.toString()
      ? url + "?" + params.toString()
      : url;

  const response = await fetch(
    target,
    {
      method: "GET",
      credentials: "include",
      headers: {
        "Accept": "application/json"
      }
    }
  );

  const contentType =
    response.headers.get("content-type") || "";

  if (!response.ok) {
    const body = await response.text();

    throw new Error(
      "Frappe HTTP " +
      response.status +
      ": " +
      body.slice(0, 500)
    );
  }

  if (!contentType.includes("application/json")) {
    const body = await response.text();

    throw new Error(
      "Frappe returned non-JSON response: " +
      body.slice(0, 500)
    );
  }

  const payload = await response.json();

  if (
    payload &&
    Object.prototype.hasOwnProperty.call(
      payload,
      "message"
    )
  ) {
    return payload.message;
  }

  return payload;
}


async function api(path, options = {}) {
  /*
   * Compatibility router.
   *
   * war-room renderer masih menggunakan beberapa
   * legacy-style path. Semua read utama dialihkan
   * ke native Frappe methods.
   */

  let match;

  match = path.match(
    /^\/ai\/context\/(.+)$/
  );

  if (match) {
    return frappeMethod(
      "rescue_net.api_ai.context",
      {
        disaster_event_id:
          decodeURIComponent(match[1])
      }
    );
  }

  match = path.match(
    /^\/community-reports\?disaster_event_id=(.+)$/
  );

  if (match) {
    /*
     * Community reports untuk sementara diperoleh
     * dari sync pull Frappe supaya tidak menyentuh
     * FastAPI/PostgreSQL.
     */
    const pulled = await frappeMethod(
      "rescue_net.api_sync.pull",
      {
        disaster_event_id:
          decodeURIComponent(match[1])
      }
    );

    return (
      pulled.community_reports ||
      pulled.reports ||
      []
    );
  }

  match = path.match(
    /^\/resource-profiles\?disaster_event_id=(.+)$/
  );

  if (match) {
    const ctx = await frappeMethod(
      "rescue_net.api_ai.context",
      {
        disaster_event_id:
          decodeURIComponent(match[1])
      }
    );

    return ctx.resource_profiles || [];
  }

  match = path.match(
    /^\/recovery-projects\?disaster_event_id=(.+)$/
  );

  if (match) {
    const ctx = await frappeMethod(
      "rescue_net.api_ai.context",
      {
        disaster_event_id:
          decodeURIComponent(match[1])
      }
    );

    return ctx.recovery_projects || [];
  }

  match = path.match(
    /^\/recovery-project-updates\?disaster_event_id=(.+)$/
  );

  if (match) {
    const pulled = await frappeMethod(
      "rescue_net.api_sync.pull",
      {
        disaster_event_id:
          decodeURIComponent(match[1])
      }
    );

    return (
      pulled.recovery_project_updates ||
      []
    );
  }

  /*
   * Jangan fallback diam-diam ke legacy backend.
   * Kalau endpoint belum dipetakan, kita harus tahu.
   */
  throw new Error(
    "Control Centre endpoint belum dipetakan ke Frappe: " +
    path
  );
}

function renderAlerts(alerts) {
  const el = document.getElementById("alertsList");
  const top = (alerts || []).slice(0, 8);

  el.innerHTML = top.length ? top.map(a => card(
    `Alert • ${safe(a.type)}`,
    `${safe(a.message)}<br>Source: ${safe(a.source_id)}`,
    safe(a.severity)
  )).join("") : card("No critical alert", "Belum ada alert kritis dari modul operasional.", "ok");
}

function renderRecommendations(items) {
  const el = document.getElementById("recommendationsList");
  el.innerHTML = items && items.length ? items.slice(0, 8).map((r, i) => card(
    `Recommendation ${i + 1}`,
    r,
    "AI"
  )).join("") : card("No recommendation", "Belum ada rekomendasi otomatis.", "empty");
}

function renderStockWatch(ctx) {
  const el = document.getElementById("stockWatch");

  const needs = (ctx.logistic_needs || [])
    .filter(n => n.status === "open")
    .slice(0, 6)
    .map(n => card(
      `${safe(n.item_name)} masih ${safe(n.priority)}`,
      `Butuh ${safe(n.quantity_needed)} ${safe(n.unit)}, sebelum ${safe(n.needed_before)}.<br>Source: ${safe(n.id)}`,
      safe(n.priority)
    ));

  const stock = (ctx.stock_summary || [])
    .slice(0, 6)
    .map(s => card(
      `${safe(s.item_name)} • ${safe(s.posko_id)}`,
      `Saldo: ${safe(s.current_quantity)} ${safe(s.unit)}`,
      "stock"
    ));

  el.innerHTML = [...needs, ...stock].join("") || card("No stock data", "Belum ada data stok/kebutuhan.", "empty");
}

function formatQty(value) {
  const num = Number(value || 0);
  return Number.isInteger(num) ? String(num) : num.toFixed(2);
}

function renderCriticalNeedsTable(ctx) {
  const body = document.getElementById("criticalNeedsBody");
  if (!body) return;

  const stockByItem = {};
  (ctx.stock_summary || []).forEach(s => {
    const key = (s.item_name || "").toLowerCase();
    stockByItem[key] = (stockByItem[key] || 0) + Number(s.current_quantity || 0);
  });

  const priorityRank = { critical: 0, urgent: 1, high: 1, normal: 2, low: 3 };
  const needs = (ctx.logistic_needs || [])
    .filter(n => n.status === "open")
    .sort((a, b) => (priorityRank[a.priority] ?? 9) - (priorityRank[b.priority] ?? 9))
    .slice(0, 8);

  if (!needs.length) {
    body.innerHTML = `<tr><td colspan="4">Belum ada kebutuhan kritis terbuka.</td></tr>`;
    return;
  }

  body.innerHTML = needs.map(n => {
    const needed = Number(n.quantity_needed || 0);
    const key = (n.item_name || "").toLowerCase();
    const available = stockByItem[key] || 0;
    const gap = Math.max(needed - available, 0);
    const gapClass = gap > 0 ? "" : "ok";
    return `
      <tr>
        <td>${safe(n.item_name)}<br><small class="subtitle">${safe(n.priority)}</small></td>
        <td>${formatQty(needed)} ${safe(n.unit, "")}</td>
        <td>${formatQty(available)} ${safe(n.unit, "")}</td>
        <td class="gap-value ${gapClass}">${formatQty(gap)}</td>
      </tr>
    `;
  }).join("");
}

function renderNeedsByLocation(ctx) {
  const el = document.getElementById("needsByLocation");
  if (!el) return;

  const poskoById = {};
  (ctx.poskos || []).forEach(p => {
    const key = p.name || p.id;
    if (key) poskoById[key] = p;
  });

  const groups = {};
  (ctx.logistic_needs || [])
    .filter(n => n.status === "open")
    .forEach(n => {
      const posko = poskoById[n.node_id];
      const label = safe(posko && posko.location, "Lokasi belum terdata");
      groups[label] = (groups[label] || 0) + 1;
    });

  const rows = Object.entries(groups).sort((a, b) => b[1] - a[1]).slice(0, 8);

  el.innerHTML = rows.length
    ? rows.map(([loc, count]) => `<div><span>${loc}</span><b>${count} kebutuhan</b></div>`).join("")
    : `<div><span>Belum ada kebutuhan terbuka</span><b>-</b></div>`;
}

function renderDistributionStatus(ctx) {
  const body = document.getElementById("distributionStatusBody");
  if (!body) return;

  const statusLabel = {
    planned: "Planned",
    dispatched: "Dispatched",
    stock_transferred: "Dispatched",
    delivered: "Delivered",
    received_verified: "Confirmed",
    confirmed: "Confirmed"
  };

  const counts = {};
  (ctx.distribution_flows || []).forEach(f => {
    const key = statusLabel[f.status] || safe(f.status, "Unknown");
    counts[key] = (counts[key] || 0) + 1;
  });

  const order = ["Planned", "Dispatched", "Delivered", "Confirmed"];
  const rows = [
    ...order.filter(k => counts[k]).map(k => [k, counts[k]]),
    ...Object.entries(counts).filter(([k]) => !order.includes(k))
  ];

  body.innerHTML = rows.length
    ? rows.map(([status, count]) => `<tr><td>${status}</td><td>${count}</td></tr>`).join("")
    : `<tr><td colspan="2">Belum ada distribusi tercatat.</td></tr>`;
}

function scenarioLabel(scenario) {
  if (scenario === "minimum") return "Minimum";
  if (scenario === "maximum") return "Maximum";
  return "Optimal";
}

function renderScenarioButtons() {
  document.querySelectorAll("[data-war-scenario]").forEach(btn => {
    const active = btn.getAttribute("data-war-scenario") === warScenario;
    btn.classList.toggle("primary", active);
  });
}

function describeCorrectionTarget(row) {
  const trace = row.trace || {};
  const place = [trace.village, trace.district, trace.city, trace.province].filter(Boolean).join(", ") || trace.posko_name || "lokasi belum rinci";
  const warning = Number(row.duplicate_warning_count || 0) > 0 ? " | konflik/overlap" : "";
  const corrected = row.has_command_correction ? ` | koreksi ${formatQty(row.effective_quantity_final)}` : "";
  return `${safe(row.item_name)} ${formatQty(row.effective_quantity_final || row.quantity_final)} ${safe(row.quantity_unit, "")} | ${place}${warning}${corrected}`;
}

function populateCorrectionTargets(payload) {
  const select = document.getElementById("commandCorrectionTarget");
  if (!select) return;
  const rows = [...(payload?.detail_rows || [])].sort((a, b) => {
    const aw = Number(a.duplicate_warning_count || 0) + (a.has_command_correction ? 1 : 0);
    const bw = Number(b.duplicate_warning_count || 0) + (b.has_command_correction ? 1 : 0);
    return bw - aw;
  });
  select.innerHTML = rows.length ? rows.map(row => `
    <option value="${row.id}" data-current="${row.effective_quantity_final || row.quantity_final || 0}">
      ${describeCorrectionTarget(row)}
    </option>
  `).join("") : '<option value="">Belum ada consolidated detail</option>';
}

function renderCommandCorrectionTrace(payload) {
  const target = document.getElementById("commandCorrectionTrace");
  if (!target) return;
  const rows = (payload?.detail_rows || []).filter(row => row.has_command_correction);
  target.innerHTML = rows.length ? rows.slice(0, 8).map(row => {
    const correction = row.manual_correction || {};
    const delta = Number(row.manual_correction_delta || 0);
    const deltaText = `${delta >= 0 ? "+" : ""}${formatQty(delta)} ${safe(row.quantity_unit, "")}`;
    return card(
      `${safe(row.item_name)} | ${formatQty(row.effective_quantity_final)} ${safe(row.quantity_unit, "")}`,
      `Original: ${formatQty(row.original_quantity_final)} | Koreksi manual: ${deltaText}<br>` +
      `Alasan: ${safe(correction.correction_reason)}<br>${safe(correction.correction_note, "")}`,
      "manual correction"
    );
  }).join("") : card("Belum ada koreksi pusat", "Koreksi manual akan tampil di sini dan tetap terpisah dari raw data.", "empty");
}

async function renderWarScenarioRollup(eventId) {
  const listEl = document.getElementById("warScenarioRollup");
  const statusEl = document.getElementById("warScenarioStatus");
  if (!listEl) return;
  renderScenarioButtons();
  if (statusEl) statusEl.textContent = `Scenario: ${scenarioLabel(warScenario)}. Loading...`;
  try {
    const payload = await api(`/data-consolidation/national-rollup?disaster_event_id=${encodeURIComponent(eventId)}&scenario=${encodeURIComponent(warScenario)}`);
    latestScenarioPayload = payload;
    populateCorrectionTargets(payload);
    renderCommandCorrectionTrace(payload);
    const rows = payload.national_rollup || [];
    listEl.innerHTML = rows.length ? rows.slice(0, 8).map(row => {
      const warning = Number(row.duplicate_warning_count || 0) > 0;
      const chip = warning ? `${row.duplicate_warning_count} overlap` : row.view_mode;
      return card(
        `${safe(row.item_name)} | ${formatQty(row.baseline_quantity)} ${safe(row.quantity_unit, "")}`,
        `Range: ${formatQty(row.range_min)}-${formatQty(row.range_max)} ${safe(row.quantity_unit, "")}<br>` +
        `Detail: ${safe(row.detail_count)} | Sources: ${safe(row.source_count)}<br>` +
        `Koreksi manual: ${formatQty(row.manual_correction_abs_total)} ${safe(row.quantity_unit, "")} dari total | ${safe(row.corrected_detail_count, 0)} detail<br>` +
        `${safe(row.operator_note, "")}`,
        chip
      );
    }).join("") : card(
      "Belum ada rollup nasional",
      "Klik Rebuild Consolidated Needs di Data Konsolidasi agar skenario Control Centre punya basis data.",
      "empty"
    );
    if (statusEl) {
      const warningCount = rows.reduce((sum, row) => sum + Number(row.duplicate_warning_count || 0), 0);
      const correctionTotal = rows.reduce((sum, row) => sum + Number(row.manual_correction_abs_total || 0), 0);
      statusEl.textContent = `${scenarioLabel(warScenario)}: ${rows.length} item, ${warningCount} warning overlap, ${formatQty(correctionTotal)} koreksi manual.`;
    }
  } catch (err) {
    listEl.innerHTML = card("Scenario rollup belum siap", err.message, "pending");
    if (statusEl) statusEl.textContent = `Scenario: ${scenarioLabel(warScenario)} gagal dimuat.`;
  }
}

function setupCommandCorrectionForm() {
  const form = document.getElementById("commandCorrectionForm");
  if (!form) return;
  const select = document.getElementById("commandCorrectionTarget");
  const status = document.getElementById("commandCorrectionStatus");
  select?.addEventListener("change", () => {
    const selected = select.options[select.selectedIndex];
    const input = form.elements.corrected_quantity;
    if (input && selected?.dataset.current) input.value = selected.dataset.current;
  });
  document.getElementById("refreshCorrectionTargets")?.addEventListener("click", async () => {
    await renderWarScenarioRollup(getEventId());
  });
  form.addEventListener("submit", async e => {
    e.preventDefault();
    const targetId = form.elements.target_id.value;
    const correctedQuantity = Number(form.elements.corrected_quantity.value);
    if (!targetId || Number.isNaN(correctedQuantity)) {
      if (status) status.textContent = "Pilih data dan isi nilai koreksi dulu.";
      return;
    }
    if (status) status.textContent = "Menyimpan koreksi pusat...";
    await api("/command-corrections", {
      method: "POST",
      body: JSON.stringify({
        disaster_event_id: getEventId(),
        target_type: "consolidated_need",
        target_id: targetId,
        corrected_quantity: correctedQuantity,
        corrected_by: "command-center-web",
        correction_reason: form.elements.correction_reason.value,
        correction_note: form.elements.correction_note.value
      })
    });
    if (status) status.textContent = "Koreksi tersimpan. Rollup nasional diperbarui.";
    await renderWarScenarioRollup(getEventId());
  });
}


function renderModuleSummary(ctx) {
  const s = ctx.summary || {};
  const el = document.getElementById("moduleSummary");

  el.innerHTML = `
    <div><span>Organizations</span><b>${safe(s.organization_count)}</b></div>
    <div><span>Volunteers</span><b>${safe(s.volunteer_count)}</b></div>
    <div><span>Aid Offers</span><b>${safe(s.aid_offer_count)}</b></div>
    <div><span>Need Pickup</span><b>${safe(s.aid_need_pickup_count)}</b></div>
    <div><span>Distribution Flows</span><b>${safe(s.distribution_flow_count)}</b></div>
    <div><span>Resource Requests</span><b>${safe(s.resource_request_count)}</b></div>
    <div><span>Stock Movements</span><b>${safe(s.stock_movement_count)}</b></div>
    <div><span>Meal Productions</span><b>${safe(s.meal_production_count)}</b></div>
    <div><span>Medical Cases</span><b>${safe(s.medical_case_count)}</b></div>
    <div><span>Medical Supply Uses</span><b>${safe(s.medical_supply_use_count)}</b></div>
    <div><span>Shelter Occupancy</span><b>${safe(s.shelter_occupancy_count)}</b></div>
    <div><span>Shelter Needs</span><b>${safe(s.shelter_need_count)}</b></div>
    <div><span>Missing Reports</span><b>${safe(s.missing_person_count)}</b></div>
    <div><span>Found Reports</span><b>${safe(s.found_person_count)}</b></div>
    <div><span>Search Matches</span><b>${safe(s.search_found_match_count)}</b></div>
    <div><span>Reunited</span><b>${safe(s.reunited_count)}</b></div>
    <div><span>Special Programs</span><b>${safe(s.donor_program_count)}</b></div>
    <div><span>Program Updates</span><b>${safe(s.donor_program_update_count)}</b></div>
  `;
}

async function renderTrustedVerifierWarRoom(eventId) {
  const list = document.getElementById("warTrustedVerifierList");
  const summary = document.getElementById("warTrustedVerifierSummary");
  if (!list || !summary) return;
  try {
    const ctx = await api(`/verification-context/${encodeURIComponent(eventId)}`);
    const s = ctx.summary || {};
    summary.innerHTML = `
      <div><span>Pending requests</span><b>${safe(s.pending_verifier_request_count, 0)}</b></div>
      <div><span>Candidate verifiers</span><b>${safe(s.candidate_verifier_count, 0)}</b></div>
      <div><span>Active endorsements</span><b>${safe(s.active_endorsement_count, 0)}</b></div>
      <div><span>Revoked</span><b>${safe(s.revoked_endorsement_count, 0)}</b></div>
    `;
    const endorsements = (ctx.verification_endorsements || []).filter(x => x.status === "active");
    list.innerHTML = endorsements.length ? endorsements.slice(0, 6).map(e => card(
      `${safe(e.target_type)}: ${safe(e.target_id)}`,
      `Identitas/scope: ${safe(e.verification_scope)}<br>Diverifikasi oleh ${safe(e.verifier_display_name)} (${safe(e.verifier_role)})<br>Laporan dan kebutuhan tetap perlu verifikasi sendiri.`,
      `trust L${safe(e.verification_level)}`
    )).join("") : card("Belum ada endorsement aktif", "Request verifikator akan muncul setelah registrasi dan persetujuan.", "empty");
  } catch (err) {
    list.innerHTML = card("Trusted Verifier belum termuat", err.message, "pending");
  }
}

async function renderCommunityReports(eventId) {
  const listEl = document.getElementById("communityReportsList");
  const summaryEl = document.getElementById("communityReportSummary");
  if (!listEl || !summaryEl) return;

  try {
    const reports = await api(`/community-reports?disaster_event_id=${encodeURIComponent(eventId)}`);
    const submitted = reports.filter(r => ["submitted", "triage", "needs_verification"].includes(r.status)).length;
    const verified = reports.filter(r => r.status === "verified").length;
    const escalated = reports.filter(r => r.status === "escalated").length;

    summaryEl.innerHTML = `
      <div><span>Submitted</span><b>${submitted}</b></div>
      <div><span>Verified</span><b>${verified}</b></div>
      <div><span>Escalated</span><b>${escalated}</b></div>
      <div><span>Total</span><b>${reports.length}</b></div>
    `;

    listEl.innerHTML = reports.length ? reports.slice(0, 6).map(r => card(
      `${safe(r.title)} • ${safe(r.status)}`,
      `${safe(r.location_text)}<br>${safe(r.description)}<br>Trust: ${safe(r.trust_score)} • Type: ${safe(r.report_type)}`,
      safe(r.priority)
    )).join("") : card(
      "Belum ada laporan masyarakat",
      "Community reports akan muncul di sini setelah warga/relawan mengirim Lapor Kondisi.",
      "empty"
    );
  } catch (err) {
    listEl.innerHTML = card(
      "Community Reports menunggu rebuild API",
      "Endpoint /community-reports belum aktif di container live. Jalankan rebuild API setelah upload backend.",
      "pending"
    );
  }
}



function formatMoney(n) {
  return new Intl.NumberFormat("id-ID", { maximumFractionDigits: 0 }).format(Number(n || 0));
}

function renderSpecialPrograms(ctx) {
  const programsEl = document.getElementById("specialProgramsList");
  const updatesEl = document.getElementById("specialProgramUpdatesList");

  if (programsEl) {
    const programs = ctx.donor_programs || [];
    programsEl.innerHTML = programs.length ? programs.slice(0, 6).map(p => {
      const target = p.budget_target || p.target_amount || 0;
      const received = p.budget_received || p.current_amount || 0;
      const spent = p.budget_spent || 0;
      return card(
        safe(p.program_name),
        `${safe(p.program_type)} • ${safe(p.status)}<br>` +
        `Target: Rp ${formatMoney(target)} • Received/Current: Rp ${formatMoney(received)} • Spent: Rp ${formatMoney(spent)}<br>` +
        `Owner: ${safe(p.owner_id)} • ID: ${safe(p.name)}`,
        safe(p.priority || p.status)
      );
    }).join("") : card("Belum ada Program Khusus", "Belum ada program donor/proyek khusus untuk event ini.", "empty");
  }

  if (updatesEl) {
    const updates = ctx.donor_program_updates || [];
    updatesEl.innerHTML = updates.length ? updates.slice(0, 6).map(u => {
      return card(
        safe(u.update_title || u.update_type),
        `Program: ${safe(u.program)}<br>` +
        `Progress: ${safe(u.progress_percent)}% • Spent: Rp ${formatMoney(u.amount_spent)}<br>` +
        `${safe(u.update_notes)}`,
        safe(u.update_type)
      );
    }).join("") : card("Belum ada update", "Belum ada progress update program.", "empty");
  }
}


async function loadWarRoom() {
  setText("warRoomStatus", "Loading live AI context...");

  const eventId = getEventId();
  const ctx = await api(`/ai/context/${eventId}`);
  await attachResourceRecovery(ctx, eventId);
  const disaster = ctx.disaster || {};
  const s = ctx.summary || {};

  setText("disasterName", safe(disaster.name));
  setText("disasterMeta", `${safe(disaster.disaster_type)} • ${safe(disaster.location)} • severity ${safe(disaster.severity)} • status ${safe(disaster.status)}`);
  setText("eventIdChip", `Event: ${eventId}`);
  setText("severityChip", `Severity: ${safe(disaster.severity)}`);
  setText("statusChip", `Status: ${safe(disaster.status)}`);

  setText("kpiAlerts", (ctx.alerts || []).length);
  setText("kpiPosko", safe(s.posko_count));
  setText("kpiNeeds", Number(s.open_logistic_need_count || 0) + Number(s.shelter_need_count || 0));
  setText("kpiStock", safe(s.stock_item_count));
  setText("kpiMeals", safe(s.meal_production_count));
  setText("kpiMedical", safe(s.medical_case_count));
  setText("kpiShelter", safe(s.shelter_occupancy_count));
  setText("kpiMissing", safe(s.missing_person_count));

  setText("clockNow", new Date().toLocaleTimeString("id-ID", {hour: "2-digit", minute: "2-digit"}));
  setText("generatedAt", `Last data refresh: ${safe(ctx.generated_at)}`);
  setText("warRoomStatus", `Loaded: ${safe(ctx.generated_at)}`);

  renderAlerts(ctx.alerts || []);
  renderRecommendations(ctx.recommendations || []);
  renderStockWatch(ctx);
  renderCriticalNeedsTable(ctx);
  renderNeedsByLocation(ctx);
  renderDistributionStatus(ctx);
  try { await renderWarScenarioRollup(eventId); } catch (err) { console.error('render scenario rollup failed', err); }
  try { await renderTrustedVerifierWarRoom(eventId); } catch (err) { console.error('render trusted verifier failed', err); }
  renderModuleSummary(ctx);
  try { await renderCommunityReports(eventId); } catch (err) { console.error('render community reports failed', err); }
  try { renderSpecialPrograms(ctx); } catch (err) { console.error('render special programs failed', err); }
  try { renderResourceAndRecovery(ctx); } catch (err) { console.error('render resource/recovery failed', err); }
  try { renderSpecialProgramsSafe(ctx); } catch (err) { console.error('render special programs safe failed', err); }
}



function fixProgramLinks() {
  const eventId = getEventId();
  document.querySelectorAll('a[href^="program-khusus.html"]').forEach(a => {
    a.href = `program-khusus.html?event=${encodeURIComponent(eventId)}`;
  });
}


function setupQuickBookingForm() {
  const form = document.getElementById("quickBookingForm");
  if (!form) return;

  form.addEventListener("submit", async e => {
    e.preventDefault();

    if (!window.RNResourceBooking) {
      setText("warRoomStatus", "RNResourceBooking not loaded.");
      return;
    }

    const payload = {
      disaster_event_id: getEventId(),
      resource_id: form.resource_id.value.trim(),
      requested_by_type: form.requested_by_type.value.trim(),
      requested_by_id: form.requested_by_id.value.trim(),
      request_reason: form.request_reason.value.trim(),
      requested_quantity: Number(form.requested_quantity.value || 1),
      requested_time: form.requested_time.value.trim()
    };

    try {
      await window.RNResourceBooking.createResourceRequest(payload);

      if (window.RNSync) {
        await window.RNSync.triggerSync("booking-form");
      }

      await loadWarRoom();
    } catch (err) {
      setText("warRoomStatus", err.message);
    }
  });
}


document.addEventListener("DOMContentLoaded", () => {
  fixProgramLinks();
  setupQuickBookingForm();
  setupCommandCorrectionForm();
  document.querySelectorAll("[data-war-scenario]").forEach(btn => {
    btn.addEventListener("click", async () => {
      warScenario = btn.getAttribute("data-war-scenario") || "optimal";
      localStorage.setItem("rn_war_scenario", warScenario);
      renderScenarioButtons();
      await renderWarScenarioRollup(getEventId());
    });
  });
  const btn = document.getElementById("refreshWarRoom");
  if (btn) btn.addEventListener("click", () => loadWarRoom().catch(err => setText("warRoomStatus", err.message)));

  loadWarRoom().catch(err => setText("warRoomStatus", err.message));
});



async function attachResourceRecovery(ctx, eventId) {
  try {
    const [resources, projects, updates] = await Promise.all([
      api(`/resource-profiles?disaster_event_id=${encodeURIComponent(eventId)}`),
      api(`/recovery-projects?disaster_event_id=${encodeURIComponent(eventId)}`),
      api(`/recovery-project-updates?disaster_event_id=${encodeURIComponent(eventId)}`)
    ]);

    ctx.resource_profiles = Array.isArray(resources) ? resources : [];
    ctx.recovery_projects = Array.isArray(projects) ? projects : [];
    ctx.recovery_project_updates = Array.isArray(updates) ? updates : [];
    ctx.summary = ctx.summary || {};
    ctx.summary.resource_profile_count = ctx.resource_profiles.length;
    ctx.summary.recovery_project_count = ctx.recovery_projects.length;
    ctx.summary.recovery_project_update_count = ctx.recovery_project_updates.length;
  } catch (err) {
    console.error("attachResourceRecovery failed", err);
    ctx.resource_profiles = ctx.resource_profiles || [];
    ctx.recovery_projects = ctx.recovery_projects || [];
    ctx.recovery_project_updates = ctx.recovery_project_updates || [];
    ctx.summary = ctx.summary || {};
    ctx.summary.resource_profile_count = ctx.summary.resource_profile_count || 0;
    ctx.summary.recovery_project_count = ctx.summary.recovery_project_count || 0;
    ctx.summary.recovery_project_update_count = ctx.summary.recovery_project_update_count || 0;
  }

  return ctx;
}

function renderResourceAndRecovery(ctx) {
  const resourcesEl = document.getElementById("warRoomResourceProfiles");
  const recoveryEl = document.getElementById("warRoomRecoveryProjects");

  if (resourcesEl) {
    const resources = ctx.resource_profiles || [];
    resourcesEl.innerHTML = resources.length ? resources.slice(0, 6).map(r => card(
      safe(r.resource_name),
      `Type: ${safe(r.resource_type)} • ${safe(r.category)}<br>` +
      `Qty: ${safe(r.quantity)} ${safe(r.unit)} • Status: ${safe(r.availability_status)}<br>` +
      `Location: ${safe(r.current_location)}<br>` +
      `PIC: ${safe(r.pic_name)} / ${safe(r.pic_phone)}<br>` +
      `${safe(r.capacity_description)}`,
      safe(r.availability_status)
    )).join("") : card("Belum ada Profil Sumber Daya", "Belum ada aset/kapasitas operasional yang tercatat untuk event ini.", "empty");
  }

  if (recoveryEl) {
    const projects = ctx.recovery_projects || [];
    recoveryEl.innerHTML = projects.length ? projects.slice(0, 6).map(p => card(
      safe(p.project_name),
      `${safe(p.project_type)} • ${safe(p.status)} • ${safe(p.priority)}<br>` +
      `Progress: ${safe(p.progress_percent)}%<br>` +
      `Target: Rp ${formatMoney(p.target_amount)} • Current/Spent: Rp ${formatMoney(p.current_amount)}<br>` +
      `Location: ${safe(p.location)}<br>` +
      `PIC: ${safe(p.pic_name)} / ${safe(p.pic_phone)}`,
      safe(p.status)
    )).join("") : card("Belum ada Recovery Project", "Belum ada project pemulihan/rekonstruksi untuk event ini.", "empty");
  }
}
