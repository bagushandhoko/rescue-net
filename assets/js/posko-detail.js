const RN_API_BASE = "http://192.168.100.32:8092";
let POSKO_CONTEXT_CACHE = null;

function getPoskoId() {
  const params = new URLSearchParams(window.location.search);
  return params.get("id") || "posko-logistik-aceh";
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

function setStatus(msg) {
  const el = document.getElementById("poskoStatus");
  if (el) el.textContent = msg;
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

function renderOverview(ctx) {
  const p = ctx.posko || {};
  const org = ctx.organization || {};
  const disaster = ctx.disaster || {};

  document.getElementById("poskoTitle").textContent = p.name || p.id || "Posko";
  document.getElementById("poskoSubtitle").textContent = `${safe(p.location)} · ${safe(p.node_type)} · ${safe(p.operational_status)}`;

  document.getElementById("kpiRole").textContent = safe(p.node_type);
  document.getElementById("kpiNeeds").textContent = (ctx.logistic_needs || []).length;
  document.getElementById("kpiStock").textContent = (ctx.stock_summary || []).length;
  document.getElementById("kpiFlows").textContent = (ctx.distribution_flows || []).length;

  document.getElementById("poskoOverview").innerHTML = `
    <div><span>Posko ID</span><b>${safe(p.id)}</b></div>
    <div><span>Name</span><b>${safe(p.name)}</b></div>
    <div><span>Type</span><b>${safe(p.node_type)}</b></div>
    <div><span>Location</span><b>${safe(p.location)}</b></div>
    <div><span>Organization</span><b>${safe(org.name || p.organization_id)}</b></div>
    <div><span>Disaster</span><b>${safe(disaster.name || p.disaster_event_id)}</b></div>
    <div><span>Verification</span><b>${safe(p.verification_status)}</b></div>
    <div><span>Sync</span><b>${safe(p.sync_status)}</b></div>
  `;
}

function renderStockSummary(items) {
  const el = document.getElementById("stockSummary");
  el.innerHTML = items.length ? items.map(s => card(
    s.item_name,
    `Current stock: <b>${s.current_quantity}</b> ${s.unit}`,
    s.unit
  )).join("") : card("Belum ada stock summary", "Tambahkan stock movement dulu.", "empty");
}

function renderStockMovements(items) {
  const el = document.getElementById("stockMovements");
  el.innerHTML = items.length ? items.map(m => card(
    m.item_name,
    `${m.movement_type} · ${m.movement_direction}<br>${m.quantity} ${m.unit}<br>${safe(m.notes)}`,
    m.created_at ? m.created_at.slice(0, 16).replace("T", " ") : m.id
  )).join("") : card("Belum ada stock movement", "Belum ada barang masuk/keluar.", "empty");
}

function renderNeeds(items) {
  const el = document.getElementById("logisticNeeds");
  el.innerHTML = items.length ? items.map(n => card(
    n.item_name,
    `Need: ${safe(n.quantity_needed)} ${safe(n.unit)}<br>Priority: ${safe(n.priority)}<br>Before: ${safe(n.needed_before)}`,
    n.status
  )).join("") : card("Belum ada kebutuhan", "Tidak ada kebutuhan aktif.", "empty");
}


function renderIncomingAid(items) {
  const el = document.getElementById("incomingAid");

  el.innerHTML = items.length ? items.map(a => {
    const isReceived = a.status === "received_verified";
    return `
      <article class="event-card">
        <div class="event-main">
          <div>
            <h4>${a.item_name}</h4>
            <p>${safe(a.quantity)} ${safe(a.unit)}<br>Donor: ${safe(a.donor_name)}<br>Status: ${safe(a.status)}</p>
          </div>
          <div class="chips">
            <span class="chip warning">${a.delivery_mode || a.status}</span>
            ${isReceived ? `<span class="chip neutral">verified</span>` : `<button class="btn primary" type="button" onclick="verifyAidReceived('${a.id}')">Verify Received</button>`}
          </div>
        </div>
      </article>
    `;
  }).join("") : card("Belum ada incoming aid", "Belum ada bantuan menuju posko ini.", "empty");
}

async function verifyAidReceived(aidOfferId) {
  if (!POSKO_CONTEXT_CACHE) {
    await loadPosko();
  }

  const ctx = POSKO_CONTEXT_CACHE;
  const aid = (ctx.incoming_aid || []).find(x => x.id === aidOfferId);

  if (!aid) {
    setStatus("Aid offer not found in current context.");
    return;
  }

  const flow = (ctx.distribution_flows || []).find(f => f.aid_offer_id === aidOfferId);

  const qty = Number(prompt(`Jumlah diterima untuk ${aid.item_name} (${aid.unit})`, aid.quantity || 1));
  if (!qty || qty <= 0) {
    setStatus("Verify cancelled: invalid quantity.");
    return;
  }

  const payload = {
    posko_id: getPoskoId(),
    disaster_event_id: ctx.posko.disaster_event_id,
    aid_offer_id: aid.id,
    item_name: aid.item_name,
    quantity_received: qty,
    unit: aid.unit,
    received_by: "operator-posko",
    notes: "Diverifikasi diterima melalui Posko Detail.",
    distribution_flow_id: flow ? flow.id : null
  };

  setStatus("Verifying received aid...");
  await api("/posko/verify-aid-received", {
    method: "POST",
    body: JSON.stringify(payload)
  });

  setStatus("Aid verified and stock updated.");
  await loadPosko();
}

function renderFlows(items) {
  const el = document.getElementById("distributionFlows");
  el.innerHTML = items.length ? items.map(f => card(
    f.id,
    `Aid: ${safe(f.aid_offer_id)}<br>Transport: ${safe(f.transport_space_id)}<br>ETA: ${safe(f.eta_final)}`,
    f.status
  )).join("") : card("Belum ada distribution flow", "Belum ada distribusi menuju posko ini.", "empty");
}

async function loadPosko() {
  const poskoId = getPoskoId();
  setStatus("Loading posko context...");

  const ctx = await api(`/posko-context/${poskoId}`);
  POSKO_CONTEXT_CACHE = ctx;

  renderOverview(ctx);
  renderStockSummary(ctx.stock_summary || []);
  renderStockMovements(ctx.stock_movements || []);
  renderNeeds(ctx.logistic_needs || []);
  renderIncomingAid(ctx.incoming_aid || []);
  renderFlows(ctx.distribution_flows || []);

  setStatus("Loaded: " + ctx.generated_at);
}

function setupStockForm() {
  const form = document.getElementById("stockForm");
  if (!form) return;

  form.addEventListener("submit", async e => {
    e.preventDefault();

    const ctx = await api(`/posko-context/${getPoskoId()}`);
    const disasterId = ctx.posko.disaster_event_id;

    const payload = {
      disaster_event_id: disasterId,
      posko_id: getPoskoId(),
      item_name: form.item_name.value.trim(),
      quantity: Number(form.quantity.value || 0),
      unit: form.unit.value.trim(),
      movement_type: form.movement_type.value,
      movement_direction: form.movement_direction.value,
      notes: form.notes.value.trim()
    };

    setStatus("Saving stock movement...");
    await api("/stock-movements", {
      method: "POST",
      body: JSON.stringify(payload)
    });

    setStatus("Stock movement saved.");
    await loadPosko();
  });
}

document.addEventListener("DOMContentLoaded", () => {
  setupStockForm();
  loadPosko().catch(err => setStatus(err.message));
});
