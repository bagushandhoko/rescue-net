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

function setupDeliveryModeToggle(form) {
  if (!form) return;

  const deliveryMode = form.querySelector('[name="delivery_mode"]');
  const selfDeliverBox = document.querySelector("[data-self-deliver-fields]");

  function update() {
    if (!selfDeliverBox || !deliveryMode) return;
    selfDeliverBox.style.display = deliveryMode.value === "self_deliver_to_posko" ? "grid" : "none";
  }

  if (deliveryMode) {
    deliveryMode.addEventListener("change", update);
    update();
  }
}

function setupPublicAidForm() {
  const form = document.querySelector("[data-public-aid-form]");
  const result = document.querySelector("[data-public-aid-result]");
  if (!form) return;

  setupDeliveryModeToggle(form);

  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const payload = {
      disaster_event_id: form.disaster_event_id.value.trim(),
      donor_name: form.donor_name.value.trim(),
      donor_contact: form.donor_contact.value.trim(),
      item_name: form.item_name.value.trim(),
      quantity: Number(form.quantity.value),
      unit: form.unit.value.trim(),
      pickup_location: form.pickup_location.value.trim(),
      ready_at: form.ready_at.value.trim(),
      delivery_mode: form.delivery_mode.value,
      target_node_id: form.target_node_id.value.trim() || null,
      target_node_name: form.target_node_name.value.trim() || null,
      expected_arrival_at: form.expected_arrival_at.value.trim() || null,
      notes: form.notes.value.trim() || null
    };

    if (!payload.donor_name || !payload.donor_contact || !payload.item_name || !payload.quantity || !payload.unit) {
      result.innerHTML = `<div class="alert danger">Lengkapi nama, HP, item, jumlah, dan satuan.</div>`;
      return;
    }

    try {
      result.innerHTML = `<div class="alert neutral">Menyimpan bantuan...</div>`;

      const data = await rnFetch("/public/aid-offers", {
        method: "POST",
        body: JSON.stringify(payload)
      });

      result.innerHTML = `
        <div class="success-box">
          <h3>Bantuan berhasil dicatat</h3>
          <p>Simpan kode ini. Kode diperlukan jika ingin mengubah data bantuan.</p>

          <div class="code-grid">
            <div>
              <span>Kode Bantuan / Aid ID</span>
              <strong>${data.id}</strong>
            </div>
            <div>
              <span>Kode Edit</span>
              <strong>${data.edit_code}</strong>
            </div>
            <div>
              <span>Status</span>
              <strong>${data.status}</strong>
            </div>
            <div>
              <span>Mode</span>
              <strong>${data.delivery_mode}</strong>
            </div>
          </div>

          <p class="subtitle">Silakan screenshot halaman ini.</p>
          <a class="btn primary" href="edit-bantuan.html">Edit Bantuan Saya</a>
        </div>
      `;

      form.reset();
      form.disaster_event_id.value = "event-aceh-2025";
      form.delivery_mode.value = "need_pickup";
      setupDeliveryModeToggle(form);

    } catch (err) {
      result.innerHTML = `<div class="alert danger">${err.message}</div>`;
    }
  });
}

function setupEditAidForm() {
  const form = document.querySelector("[data-edit-aid-form]");
  const result = document.querySelector("[data-edit-aid-result]");
  if (!form) return;

  setupDeliveryModeToggle(form);

  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const aidId = form.aid_offer_id.value.trim();

    const payload = {
      donor_contact: form.donor_contact.value.trim(),
      edit_code: form.edit_code.value.trim(),
      item_name: form.item_name.value.trim() || null,
      quantity: form.quantity.value ? Number(form.quantity.value) : null,
      unit: form.unit.value.trim() || null,
      pickup_location: form.pickup_location.value.trim() || null,
      ready_at: form.ready_at.value.trim() || null,
      delivery_mode: form.delivery_mode.value,
      target_node_id: form.target_node_id.value.trim() || null,
      target_node_name: form.target_node_name.value.trim() || null,
      expected_arrival_at: form.expected_arrival_at.value.trim() || null,
      notes: form.notes.value.trim() || null
    };

    if (!aidId || !payload.donor_contact || !payload.edit_code) {
      result.innerHTML = `<div class="alert danger">Isi Aid ID, nomor HP, dan kode edit.</div>`;
      return;
    }

    try {
      result.innerHTML = `<div class="alert neutral">Mengupdate bantuan...</div>`;

      const data = await rnFetch(`/public/aid-offers/${aidId}`, {
        method: "PUT",
        body: JSON.stringify(payload)
      });

      result.innerHTML = `
        <div class="success-box">
          <h3>Bantuan berhasil diupdate</h3>
          <div class="code-grid">
            <div><span>Aid ID</span><strong>${data.id}</strong></div>
            <div><span>Status</span><strong>${data.status}</strong></div>
            <div><span>Mode</span><strong>${data.delivery_mode}</strong></div>
            <div><span>Edit Count</span><strong>${data.edit_count}</strong></div>
          </div>
        </div>
      `;

    } catch (err) {
      result.innerHTML = `<div class="alert danger">${err.message}</div>`;
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  setupPublicAidForm();
  setupEditAidForm();
});
