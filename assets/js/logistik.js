const RN_API_BASE = (location.protocol === "https:" ? location.origin + "/rescue-net-api" : "http://192.168.100.32:8092");

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

function priorityClass(priority) {
  if (priority === "critical") return "danger";
  if (priority === "urgent") return "warning";
  return "neutral";
}

function evidenceLink(objectType, objectId, eventId = "event-aceh-2025", label = "Add Evidence") {
  if (!objectId) return "";
  return `<br><a href="evidence.html?event=${encodeURIComponent(eventId)}&object_type=${encodeURIComponent(objectType)}&object_id=${encodeURIComponent(objectId)}">${label}</a>`;
}

async function loadLogisticNeeds() {
  const target = document.querySelector("[data-rn-logistic-needs]");
  if (!target) return;

  try {
    const needs = await rnFetch("/logistic-needs");

    target.innerHTML = needs.map(n => `
      <article class="event-card">
        <div class="event-main">
          <div>
            <h4>${n.item_name}</h4>
            <p>
              Kebutuhan: <b>${n.quantity_needed} ${n.unit}</b>
              · Harus tiba: ${n.needed_before || "belum ditentukan"}
              · Status: ${n.status}${evidenceLink("logistic_need", n.id, n.disaster_event_id)}
            </p>
          </div>
          <div class="chips">
            <span class="chip ${priorityClass(n.priority)}">${n.priority}</span>
            <span class="chip neutral">${n.node_id || "no node"}</span>
          </div>
        </div>
      </article>
    `).join("");

  } catch (err) {
    target.innerHTML = `<article class="event-card"><h4>Gagal load kebutuhan</h4><p>${err.message}</p></article>`;
  }
}

async function loadAidOffers() {
  const target = document.querySelector("[data-rn-aid-offers]");
  if (!target) return;

  try {
    const offers = await rnFetch("/aid-offers");

    target.innerHTML = offers.map(a => `
      <article class="event-card">
        <div class="event-main">
          <div>
            <h4>${a.item_name}</h4>
            <p>
              Donatur: ${a.donor_name}
              · Jumlah: <b>${a.quantity} ${a.unit}</b>
              · Pickup: ${a.pickup_location}${evidenceLink("aid_offer", a.id, a.disaster_event_id)}
            </p>
          </div>
          <div class="chips">
            <span class="chip neutral">${a.status}</span>
            <span class="chip neutral">${a.ready_at || "ready time n/a"}</span>
          </div>
        </div>
      </article>
    `).join("");

  } catch (err) {
    target.innerHTML = `<article class="event-card"><h4>Gagal load bantuan</h4><p>${err.message}</p></article>`;
  }
}

function setupLogisticNeedForm() {
  const form = document.querySelector("[data-rn-create-logistic-need]");
  const msg = document.querySelector("[data-rn-logistic-message]");
  if (!form) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const payload = {
      disaster_event_id: form.disaster_event_id.value.trim(),
      node_id: form.node_id.value.trim() || null,
      item_name: form.item_name.value.trim(),
      quantity_needed: Number(form.quantity_needed.value),
      unit: form.unit.value.trim(),
      priority: form.priority.value,
      needed_before: form.needed_before.value.trim(),
      status: "open"
    };

    if (!payload.item_name || !payload.quantity_needed || !payload.unit) {
      if (msg) msg.textContent = "Lengkapi item, jumlah, dan satuan.";
      return;
    }

    try {
      if (msg) msg.textContent = "Menyimpan kebutuhan logistik...";
      await rnFetch("/logistic-needs", {
        method: "POST",
        body: JSON.stringify(payload)
      });

      form.reset();
      form.disaster_event_id.value = "event-aceh-2025";
      form.node_id.value = "posko-logistik-aceh";
      if (msg) msg.textContent = "Kebutuhan logistik berhasil disimpan.";
      await loadLogisticNeeds();

    } catch (err) {
      if (msg) msg.textContent = err.message;
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  loadLogisticNeeds();
  loadAidOffers();
  setupLogisticNeedForm();
});

function setupAidOfferForm() {
  const form = document.querySelector("[data-rn-create-aid-offer]");
  const msg = document.querySelector("[data-rn-aid-message]");
  if (!form) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const payload = {
      disaster_event_id: form.disaster_event_id.value.trim(),
      donor_name: form.donor_name.value.trim(),
      item_name: form.item_name.value.trim(),
      quantity: Number(form.quantity.value),
      unit: form.unit.value.trim(),
      pickup_location: form.pickup_location.value.trim(),
      ready_at: form.ready_at.value.trim(),
      status: form.status.value
    };

    if (!payload.donor_name || !payload.item_name || !payload.quantity || !payload.unit || !payload.pickup_location) {
      if (msg) msg.textContent = "Lengkapi donor, item, jumlah, satuan, dan lokasi pickup.";
      return;
    }

    try {
      if (msg) msg.textContent = "Menyimpan bantuan tersedia...";
      await rnFetch("/aid-offers", {
        method: "POST",
        body: JSON.stringify(payload)
      });

      form.reset();
      form.disaster_event_id.value = "event-aceh-2025";
      if (msg) msg.textContent = "Bantuan berhasil disimpan.";
      await loadAidOffers();

    } catch (err) {
      if (msg) msg.textContent = err.message;
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  setupAidOfferForm();
});
