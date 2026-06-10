const RN_API_BASE = "http://192.168.100.32:8092";
const EVENT_ID = "event-aceh-2025";

function safe(v) {
  return v === null || v === undefined || v === "" ? "n/a" : v;
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

async function api(path) {
  const res = await fetch(RN_API_BASE + path);
  if (!res.ok) throw new Error(await res.text());
  return await res.json();
}

function renderAlerts(alerts) {
  const el = document.getElementById("alertsList");
  const top = (alerts || []).slice(0, 8);

  el.innerHTML = top.length ? top.map(a => card(
    `Alert · ${safe(a.type)}`,
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
      `${safe(s.item_name)} · ${safe(s.posko_id)}`,
      `Saldo: ${safe(s.current_quantity)} ${safe(s.unit)}`,
      "stock"
    ));

  el.innerHTML = [...needs, ...stock].join("") || card("No stock data", "Belum ada data stok/kebutuhan.", "empty");
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
        `${safe(p.program_type)} · ${safe(p.status)}<br>` +
        `Target: Rp ${formatMoney(target)} · Received/Current: Rp ${formatMoney(received)} · Spent: Rp ${formatMoney(spent)}<br>` +
        `Owner: ${safe(p.owner_id)} · ID: ${safe(p.id)}`,
        safe(p.priority || p.status)
      );
    }).join("") : card("Belum ada Program Khusus", "Belum ada program donor/proyek khusus untuk event ini.", "empty");
  }

  if (updatesEl) {
    const updates = ctx.donor_program_updates || [];
    updatesEl.innerHTML = updates.length ? updates.slice(0, 6).map(u => {
      return card(
        safe(u.update_title || u.update_type),
        `Program: ${safe(u.program_id)}<br>` +
        `Progress: ${safe(u.progress_percent)}% · Spent: Rp ${formatMoney(u.amount_spent)}<br>` +
        `${safe(u.update_notes)}`,
        safe(u.update_type)
      );
    }).join("") : card("Belum ada update", "Belum ada progress update program.", "empty");
  }
}


async function loadWarRoom() {
  setText("warRoomStatus", "Loading live AI context...");

  const ctx = await api(`/ai/context/${EVENT_ID}`);
  const disaster = ctx.disaster || {};
  const s = ctx.summary || {};

  setText("disasterName", safe(disaster.name));
  setText("disasterMeta", `${safe(disaster.disaster_type)} · ${safe(disaster.location)} · severity ${safe(disaster.severity)} · status ${safe(disaster.status)}`);
  setText("eventIdChip", `Event: ${EVENT_ID}`);
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
  renderModuleSummary(ctx);
  renderSpecialPrograms(ctx);
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
  const btn = document.getElementById("refreshWarRoom");
  if (btn) btn.addEventListener("click", () => loadWarRoom().catch(err => setText("warRoomStatus", err.message)));

  loadWarRoom().catch(err => setText("warRoomStatus", err.message));
});
