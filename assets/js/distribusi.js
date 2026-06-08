const RN_API_BASE = "http://192.168.100.32:8092";

async function rnFetch(path, options = {}) {
  const res = await fetch(`${RN_API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {})
    },
    ...options
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }

  return await res.json();
}

function chipClass(status) {
  if (status === "need_pickup") return "warning";
  if (status === "self_delivery_planned") return "neutral";
  if (status === "planned") return "neutral";
  if (status === "in_transit") return "warning";
  if (status === "arrived_at_posko") return "danger";
  return "neutral";
}

function renderOffer(a) {
  return `
    <article class="event-card">
      <div class="event-main">
        <div>
          <h4>${a.item_name} · ${a.quantity} ${a.unit}</h4>
          <p>
            Donatur: ${a.donor_name}
            · Pickup: ${a.pickup_location}
            · Siap: ${a.ready_at || "n/a"}
          </p>
          <p>
            Tujuan: ${a.target_node_name || a.target_node_id || "belum dipilih"}
            · ETA: ${a.expected_arrival_at || "n/a"}
          </p>
        </div>
        <div class="chips">
          <span class="chip ${chipClass(a.status)}">${a.status}</span>
          <span class="chip neutral">${a.delivery_mode || "need_pickup"}</span>
        </div>
      </div>
    </article>
  `;
}

async function loadAidOffers() {
  const needPickup = document.querySelector("[data-need-pickup]");
  const selfDelivery = document.querySelector("[data-self-delivery]");
  if (!needPickup && !selfDelivery) return;

  try {
    const offers = await rnFetch("/aid-offers");

    const needPickupItems = offers.filter(a =>
      a.status === "need_pickup" || a.delivery_mode === "need_pickup"
    );

    const selfDeliveryItems = offers.filter(a =>
      a.status === "self_delivery_planned" || a.delivery_mode === "self_deliver_to_posko"
    );

    if (needPickup) {
      needPickup.innerHTML = needPickupItems.length
        ? needPickupItems.map(renderOffer).join("")
        : `<article class="event-card"><h4>Tidak ada bantuan perlu pickup</h4><p>Semua bantuan sudah punya alur.</p></article>`;
    }

    if (selfDelivery) {
      selfDelivery.innerHTML = selfDeliveryItems.length
        ? selfDeliveryItems.map(renderOffer).join("")
        : `<article class="event-card"><h4>Belum ada self delivery</h4><p>Belum ada donatur yang antar sendiri ke posko.</p></article>`;
    }

  } catch (err) {
    if (needPickup) needPickup.innerHTML = `<article class="event-card"><h4>Gagal load aid offers</h4><p>${err.message}</p></article>`;
  }
}

async function loadTransportSpaces() {
  const target = document.querySelector("[data-transport-spaces]");
  if (!target) return;

  try {
    const transports = await rnFetch("/transport-spaces");

    target.innerHTML = transports.map(t => `
      <article class="event-card">
        <div class="event-main">
          <div>
            <h4>${t.provider_name}</h4>
            <p>${t.transport_type} · ${t.route_origin} → ${t.route_destination}</p>
            <p>Kapasitas: ${t.capacity_weight_kg} kg · ${t.capacity_volume_m3} m³ · Berangkat: ${t.departure_time || "n/a"} · ETA: ${t.eta || "n/a"}</p>
          </div>
          <div class="chips">
            <span class="chip neutral">${t.status}</span>
            <span class="chip neutral">${t.id}</span>
          </div>
        </div>
      </article>
    `).join("");

  } catch (err) {
    target.innerHTML = `<article class="event-card"><h4>Gagal load transport</h4><p>${err.message}</p></article>`;
  }
}

async function loadDistributionFlows() {
  const target = document.querySelector("[data-distribution-flows]");
  if (!target) return;

  try {
    const flows = await rnFetch("/distribution-flows");

    target.innerHTML = flows.length ? flows.map(f => `
      <article class="event-card">
        <div class="event-main">
          <div>
            <h4>${f.id}</h4>
            <p>Aid: ${f.aid_offer_id || "n/a"} · Need: ${f.need_id || "n/a"}</p>
            <p>Transport: ${f.transport_space_id || "n/a"} · Destination: ${f.destination_node_id || "n/a"} · ETA final: ${f.eta_final || "n/a"}</p>
          </div>
          <div class="chips">
            <span class="chip ${chipClass(f.status)}">${f.status}</span>
          </div>
        </div>
      </article>
    `).join("") : `<article class="event-card"><h4>Belum ada flow</h4><p>Belum ada matching bantuan dengan transport.</p></article>`;

  } catch (err) {
    target.innerHTML = `<article class="event-card"><h4>Gagal load flow</h4><p>${err.message}</p></article>`;
  }
}

function setupTransportForm() {
  const form = document.querySelector("[data-create-transport]");
  const msg = document.querySelector("[data-transport-message]");
  if (!form) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const payload = {
      disaster_event_id: form.disaster_event_id.value.trim(),
      provider_name: form.provider_name.value.trim(),
      transport_type: form.transport_type.value.trim(),
      route_origin: form.route_origin.value.trim(),
      route_destination: form.route_destination.value.trim(),
      capacity_weight_kg: Number(form.capacity_weight_kg.value || 0),
      capacity_volume_m3: Number(form.capacity_volume_m3.value || 0),
      departure_time: form.departure_time.value.trim(),
      eta: form.eta.value.trim(),
      status: "available"
    };

    try {
      if (msg) msg.textContent = "Menyimpan transport...";
      await rnFetch("/transport-spaces", {
        method: "POST",
        body: JSON.stringify(payload)
      });
      form.reset();
      form.disaster_event_id.value = "event-aceh-2025";
      if (msg) msg.textContent = "Transport berhasil disimpan.";
      await loadTransportSpaces();
    } catch (err) {
      if (msg) msg.textContent = err.message;
    }
  });
}

function setupFlowForm() {
  const form = document.querySelector("[data-create-flow]");
  const msg = document.querySelector("[data-flow-message]");
  if (!form) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const payload = {
      disaster_event_id: form.disaster_event_id.value.trim(),
      need_id: form.need_id.value.trim() || null,
      aid_offer_id: form.aid_offer_id.value.trim() || null,
      transport_space_id: form.transport_space_id.value.trim() || null,
      destination_node_id: form.destination_node_id.value.trim() || null,
      eta_final: form.eta_final.value.trim(),
      status: form.status.value
    };

    try {
      if (msg) msg.textContent = "Menyimpan flow...";
      await rnFetch("/distribution-flows", {
        method: "POST",
        body: JSON.stringify(payload)
      });
      form.reset();
      form.disaster_event_id.value = "event-aceh-2025";
      if (msg) msg.textContent = "Distribution flow berhasil disimpan.";
      await loadDistributionFlows();
    } catch (err) {
      if (msg) msg.textContent = err.message;
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  loadAidOffers();
  loadTransportSpaces();
  loadDistributionFlows();
  setupTransportForm();
  setupFlowForm();
});
