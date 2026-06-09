const RN_API_BASE = "http://192.168.100.32:8092";
const DISASTER_ID = "event-aceh-2025";

function safe(v) {
  return v === null || v === undefined || v === "" ? "n/a" : v;
}

function statusMsg(msg) {
  const el = document.getElementById("warRoomStatus");
  if (el) el.textContent = msg;
}

async function api(path) {
  const res = await fetch(RN_API_BASE + path, {
    headers: { "Content-Type": "application/json" }
  });
  if (!res.ok) throw new Error(await res.text());
  return await res.json();
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

function renderSummary(ai, verification, volunteers, worktools) {
  const el = document.getElementById("warRoomSummary");
  if (!el) return;

  const s = ai.summary || {};
  const vs = verification.summary || {};
  const vols = volunteers.summary || {};
  const ws = worktools.summary || {};

  el.innerHTML = `
    <div><span>Posko</span><b>${s.posko_count || 0}</b></div>
    <div><span>Open Logistic Needs</span><b>${s.open_logistic_need_count || 0}</b></div>
    <div><span>Stock Items</span><b>${s.stock_item_count || 0}</b></div>
    <div><span>Medical Cases</span><b>${s.medical_case_count || 0}</b></div>
    <div><span>Shelter Needs</span><b>${s.shelter_need_count || 0}</b></div>
    <div><span>Missing Open</span><b>${s.missing_person_count || 0}</b></div>
    <div><span>Verification Actions</span><b>${vs.verification_action_count || 0}</b></div>
    <div><span>Relawan Available</span><b>${vols.available_count || 0}</b></div>
    <div><span>Work Tool Open</span><b>${ws.open_count || 0}</b></div>
  `;
}

function renderAlerts(items) {
  const el = document.getElementById("warRoomAlerts");
  if (!el) return;

  el.innerHTML = items && items.length ? items.map(a => card(
    safe(a.type),
    `${safe(a.message)}<br>Source: ${safe(a.source_id)}`,
    safe(a.severity)
  )).join("") : card("Tidak ada alert besar", "Belum ada alert urgent dari AI Context.", "ok");
}

function renderRecommendations(items) {
  const el = document.getElementById("warRoomRecommendations");
  if (!el) return;

  el.innerHTML = items && items.length ? items.map((r, i) => card(
    `Recommendation ${i + 1}`,
    safe(r),
    "AI"
  )).join("") : card("Belum ada rekomendasi", "AI Context belum memberi rekomendasi khusus.", "empty");
}

function renderCriticalNeeds(items) {
  const el = document.getElementById("warRoomNeeds");
  if (!el) return;

  const critical = (items || []).filter(x =>
    x.priority === "critical" || x.priority === "urgent" || x.status === "open"
  ).slice(0, 12);

  el.innerHTML = critical.length ? critical.map(n => card(
    `${safe(n.item_name)} · ${safe(n.quantity_needed)} ${safe(n.unit)}`,
    `Node: ${safe(n.node_id)}<br>Needed before: ${safe(n.needed_before)}<br>Status: ${safe(n.status)}`,
    safe(n.priority)
  )).join("") : card("Tidak ada kebutuhan kritis", "Tidak ada open urgent/critical logistic needs.", "ok");
}

function renderMedical(items) {
  const el = document.getElementById("warRoomMedical");
  if (!el) return;

  const high = (items || []).filter(x =>
    x.severity === "critical" || x.severity === "severe" || x.triage_status === "red"
  ).slice(0, 10);

  el.innerHTML = high.length ? high.map(m => card(
    `${safe(m.patient_code)} · ${safe(m.complaint)}`,
    `Posko: ${safe(m.posko_id)}<br>Triage: ${safe(m.triage_status)}<br>Severity: ${safe(m.severity)}<br>Status: ${safe(m.status)}`,
    safe(m.triage_status || m.severity)
  )).join("") : card("Tidak ada medical red case", "Tidak ada kasus medis critical/severe/red.", "ok");
}

function renderShelter(ai) {
  const el = document.getElementById("warRoomShelter");
  if (!el) return;

  const needs = ai.shelter_needs || [];
  const occs = ai.shelter_occupancies || [];

  const rows = [];

  for (const o of occs.slice(0, 8)) {
    rows.push(card(
      safe(o.shelter_name || o.posko_id),
      `Occupancy: ${safe(o.current_occupancy)} / ${safe(o.capacity_total)}<br>Sanitation: ${safe(o.sanitation_status)}<br>Water: ${safe(o.water_status)}`,
      "occupancy"
    ));
  }

  for (const n of needs.slice(0, 8)) {
    rows.push(card(
      `${safe(n.item_name)} · ${safe(n.quantity_needed)} ${safe(n.unit)}`,
      `Posko: ${safe(n.posko_id)}<br>Needed before: ${safe(n.needed_before)}<br>Notes: ${safe(n.notes)}`,
      safe(n.priority)
    ));
  }

  el.innerHTML = rows.length ? rows.join("") : card("Shelter aman", "Belum ada shelter occupancy/need penting.", "ok");
}

function renderSearchFound(ai) {
  const el = document.getElementById("warRoomSearchFound");
  if (!el) return;

  const missing = ai.missing_person_reports || [];
  const found = ai.found_person_reports || [];
  const matches = ai.search_found_matches || [];

  const rows = [
    card("Missing Reports", `${missing.length} laporan orang hilang`, "missing"),
    card("Found Reports", `${found.length} laporan ditemukan`, "found"),
    card("Matches", `${matches.length} kandidat/match`, "match")
  ];

  el.innerHTML = rows.join("");
}

function renderVerification(v) {
  const el = document.getElementById("warRoomVerification");
  if (!el) return;

  const s = v.summary || {};
  el.innerHTML = `
    ${card("Pending Organization", `${s.pending_organization_count || 0} perlu review`, "verification")}
    ${card("Pending Posko", `${s.pending_posko_count || 0} perlu review`, "verification")}
    ${card("Pending Volunteer", `${s.pending_volunteer_count || 0} perlu review`, "verification")}
    ${card("Pending Aid Offer", `${s.pending_aid_offer_count || 0} perlu review`, "verification")}
    ${card("Pending Work Tool", `${s.pending_work_tool_count || 0} perlu review`, "verification")}
  `;
}

function renderWorkTools(ctx) {
  const el = document.getElementById("warRoomWorkTools");
  if (!el) return;

  const items = (ctx.work_tool_requests || []).filter(x =>
    x.priority === "urgent" || x.priority === "critical" || x.status === "requested"
  ).slice(0, 10);

  el.innerHTML = items.length ? items.map(t => card(
    `${safe(t.tool_name)} · ${safe(t.quantity)} ${safe(t.unit)}`,
    `Location: ${safe(t.location)}<br>Needed for: ${safe(t.needed_for)}<br>Skill: ${safe(t.required_operator_skill)}`,
    `${safe(t.priority)} · ${safe(t.status)}`
  )).join("") : card("Tidak ada request alat urgent", "Belum ada kebutuhan alat kerja terbuka.", "ok");
}

function renderVolunteers(ctx) {
  const el = document.getElementById("warRoomVolunteers");
  if (!el) return;

  const items = ctx.volunteers || [];
  el.innerHTML = items.length ? items.slice(0, 10).map(v => card(
    safe(v.volunteer_name),
    `Contact: ${safe(v.contact)}<br>Skills: ${safe(v.skill_tags)}<br>Location: ${safe(v.current_location)}<br>Assigned: ${safe(v.assigned_posko_id)}`,
    safe(v.availability_status)
  )).join("") : card("Belum ada relawan", "Belum ada relawan tercatat.", "empty");
}

async function loadWarRoom() {
  statusMsg("Loading command center data...");

  const [ai, verification, volunteers, worktools] = await Promise.all([
    api(`/ai/context/${DISASTER_ID}`),
    api(`/verification-context/${DISASTER_ID}`),
    api(`/volunteer-context/${DISASTER_ID}`),
    api(`/work-tools-context/${DISASTER_ID}`)
  ]);

  renderSummary(ai, verification, volunteers, worktools);
  renderAlerts(ai.alerts || []);
  renderRecommendations(ai.recommendations || []);
  renderCriticalNeeds(ai.logistic_needs || []);
  renderMedical(ai.medical_cases || []);
  renderShelter(ai);
  renderSearchFound(ai);
  renderVerification(verification);
  renderWorkTools(worktools);
  renderVolunteers(volunteers);

  statusMsg(`Loaded: ${new Date().toISOString()}`);
}

document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("refreshWarRoom");
  if (btn) btn.addEventListener("click", () => loadWarRoom().catch(err => statusMsg(err.message)));

  loadWarRoom().catch(err => statusMsg(err.message));
});
