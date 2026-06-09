const RN_API_BASE = "http://192.168.100.32:8092";
let SHELTER_CONTEXT_CACHE = null;

function getShelterPoskoId() {
  const params = new URLSearchParams(window.location.search);
  return params.get("id") || "posko-shelter-melati";
}

function statusMsg(msg) {
  const el = document.getElementById("shelterStatus");
  if (el) el.textContent = msg;
}

async function api(path, options = {}) {
  const res = await fetch(RN_API_BASE + path, {
    headers: { "Content-Type": "application/json" },
    ...options
  });
  if (!res.ok) throw new Error(await res.text());
  return await res.json();
}

function safe(v) {
  return v === null || v === undefined || v === "" ? "n/a" : v;
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

function latestOccupancy(items) {
  return items && items.length ? items[0] : null;
}

function renderOccupancies(items) {
  const el = document.getElementById("shelterOccupancies");
  el.innerHTML = items.length ? items.map(o => card(
    o.shelter_name,
    `Occupancy: ${o.current_occupancy}/${o.capacity_total}<br>Families: ${safe(o.families_count)}<br>Children: ${safe(o.children_count)} · Elderly: ${safe(o.elderly_count)} · Disabled: ${safe(o.disabled_count)}<br>Water: ${safe(o.water_status)} · Sanitation: ${safe(o.sanitation_status)}<br>${safe(o.notes)}`,
    o.status
  )).join("") : card("Belum ada occupancy", "Catat data hunian shelter.", "empty");
}

function renderNeeds(items) {
  const el = document.getElementById("shelterNeeds");
  el.innerHTML = items.length ? items.map(n => card(
    n.item_name,
    `Need: ${n.quantity_needed} ${n.unit}<br>Priority: ${safe(n.priority)}<br>Before: ${safe(n.needed_before)}<br>${safe(n.notes)}`,
    n.status
  )).join("") : card("Belum ada kebutuhan shelter", "Tambahkan kebutuhan shelter.", "empty");
}

function renderStock(items) {
  const el = document.getElementById("shelterStock");
  el.innerHTML = items.length ? items.map(s => card(
    s.item_name,
    `Current stock: <b>${s.current_quantity}</b> ${s.unit}`,
    s.unit
  )).join("") : card("Belum ada stok shelter", "Belum ada distribusi barang ke shelter.", "empty");
}

function renderFlows(items) {
  const el = document.getElementById("shelterFlows");
  el.innerHTML = items.length ? items.map(f => card(
    f.id,
    `Aid: ${safe(f.aid_offer_id)}<br>Transport: ${safe(f.transport_space_id)}<br>ETA: ${safe(f.eta_final)}`,
    f.status
  )).join("") : card("Belum ada distribution flow", "Belum ada distribusi menuju shelter.", "empty");
}

async function loadShelter() {
  const poskoId = getShelterPoskoId();
  statusMsg("Loading shelter context...");

  const ctx = await api(`/shelter-context/${poskoId}`);
  SHELTER_CONTEXT_CACHE = ctx;

  const posko = ctx.posko || {};
  const occ = ctx.shelter_occupancies || [];
  const needs = ctx.shelter_needs || [];
  const stock = ctx.stock_summary || [];
  const flows = ctx.distribution_flows || [];
  const latest = latestOccupancy(occ);

  document.getElementById("shelterTitle").textContent = posko.name || poskoId;
  document.getElementById("shelterSubtitle").textContent = `${safe(posko.location)} · ${safe(posko.node_type)} · ${safe(posko.operational_status)}`;

  document.getElementById("kpiCapacity").textContent = latest ? latest.capacity_total : 0;
  document.getElementById("kpiOccupancy").textContent = latest ? latest.current_occupancy : 0;
  document.getElementById("kpiFamilies").textContent = latest ? latest.families_count : 0;
  document.getElementById("kpiNeeds").textContent = needs.length;

  renderOccupancies(occ);
  renderNeeds(needs);
  renderStock(stock);
  renderFlows(flows);

  const occForm = document.getElementById("occupancyForm");
  if (occForm && occForm.posko_id) occForm.posko_id.value = poskoId;

  statusMsg("Loaded: " + ctx.generated_at);
}

function setupOccupancyForm() {
  const form = document.getElementById("occupancyForm");
  if (!form) return;

  form.addEventListener("submit", async e => {
    e.preventDefault();

    if (!SHELTER_CONTEXT_CACHE) {
      await loadShelter();
    }

    const posko = SHELTER_CONTEXT_CACHE.posko;

    const payload = {
      disaster_event_id: posko.disaster_event_id,
      posko_id: form.posko_id.value.trim(),
      shelter_name: form.shelter_name.value.trim(),
      capacity_total: Number(form.capacity_total.value || 0),
      current_occupancy: Number(form.current_occupancy.value || 0),
      families_count: Number(form.families_count.value || 0),
      children_count: Number(form.children_count.value || 0),
      elderly_count: Number(form.elderly_count.value || 0),
      disabled_count: Number(form.disabled_count.value || 0),
      sanitation_status: form.sanitation_status.value.trim(),
      water_status: form.water_status.value.trim(),
      electricity_status: form.electricity_status.value.trim(),
      safety_status: form.safety_status.value.trim(),
      notes: form.notes.value.trim(),
      status: "active",
      created_by_user_id: "shelter-operator"
    };

    statusMsg("Saving shelter occupancy...");
    await api("/shelter-occupancy", {
      method: "POST",
      body: JSON.stringify(payload)
    });

    statusMsg("Shelter occupancy saved.");
    await loadShelter();
  });
}

function setupNeedForm() {
  const form = document.getElementById("needForm");
  if (!form) return;

  form.addEventListener("submit", async e => {
    e.preventDefault();

    if (!SHELTER_CONTEXT_CACHE) {
      await loadShelter();
    }

    const posko = SHELTER_CONTEXT_CACHE.posko;

    const payload = {
      disaster_event_id: posko.disaster_event_id,
      posko_id: getShelterPoskoId(),
      item_name: form.item_name.value.trim(),
      quantity_needed: Number(form.quantity_needed.value || 0),
      unit: form.unit.value.trim(),
      priority: form.priority.value,
      needed_before: form.needed_before.value.trim(),
      notes: form.notes.value.trim(),
      created_by_user_id: "shelter-operator"
    };

    statusMsg("Saving shelter need...");
    await api("/shelter-needs", {
      method: "POST",
      body: JSON.stringify(payload)
    });

    statusMsg("Shelter need saved.");
    await loadShelter();
  });
}

document.addEventListener("DOMContentLoaded", () => {
  setupOccupancyForm();
  setupNeedForm();

  const btn = document.getElementById("refreshShelter");
  if (btn) btn.addEventListener("click", () => loadShelter().catch(err => statusMsg(err.message)));

  loadShelter().catch(err => statusMsg(err.message));
});
