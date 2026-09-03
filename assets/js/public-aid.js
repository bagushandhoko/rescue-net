function safe(v) {
  return (
    v === null ||
    v === undefined ||
    v === ""
  )
    ? "n/a"
    : v;
}


function mapDeliveryMode(value) {
  if (
    value === "self_deliver_to_posko"
  ) {
    return "active_booking";
  }

  return "need_pickup";
}


function setupDeliveryModeToggle(form) {
  if (!form) return;

  const deliveryMode =
    form.querySelector(
      '[name="delivery_mode"]'
    );

  const selfDeliverBox =
    document.querySelector(
      "[data-self-deliver-fields]"
    );

  function update() {
    if (
      !selfDeliverBox ||
      !deliveryMode
    ) {
      return;
    }

    selfDeliverBox.style.display =
      deliveryMode.value ===
      "self_deliver_to_posko"
        ? "grid"
        : "none";
  }

  if (deliveryMode) {
    deliveryMode.addEventListener(
      "change",
      update
    );

    update();
  }
}


function renderCreateSuccess(
  result,
  data
) {
  const offers = data.aid_offers || (data.aid_offer ? [{ aid_offer: data.aid_offer, offer_status: data.offer_status }] : []);
  const rows = offers.map(o => `
        <div>
          <span>${safe(o.item || "Aid Offer")}${o.quantity ? " — " + safe(o.quantity) + " " + safe(o.unit || "") : ""}${o.ready_at ? " · siap: " + safe(o.ready_at) : ""}</span>
          <strong>${safe(o.aid_offer)} · ${safe(o.offer_status)}</strong>
        </div>`).join("");
  result.innerHTML = `
    <div class="success-box">
      <h3>Bantuan berhasil dicatat${offers.length > 1 ? " (" + offers.length + " item)" : ""}</h3>

      <p>Tiap item menjadi satu Aid Offer yang bisa dipantau di Manajemen Distribusi &amp; Posko Logistik.</p>

      <div class="code-grid">
        ${rows}
        <div>
          <span>Handling</span>
          <strong>${safe(data.handling_mode)}</strong>
        </div>
        <div>
          <span>Target Posko</span>
          <strong>${safe(data.target_posko)}</strong>
        </div>
      </div>

      <p class="subtitle">Simpan Aid Offer ID di atas untuk mengedit lewat "Edit Bantuan Saya".</p>

      <a class="btn primary" href="edit-bantuan.html">Edit Bantuan Saya</a>
    </div>
  `;
}


/* ---------- repeatable item rows ---------- */
function initAidItems(form) {
  const wrap = form.querySelector("[data-aid-items]");
  if (!wrap) return;
  const rowsEl = wrap.querySelector("[data-aid-rows]");
  const tpl = wrap.querySelector("[data-aid-row-tpl]");

  function addRow(preset) {
    const node = tpl.content.firstElementChild.cloneNode(true);
    if (preset) {
      ["item_name", "quantity", "unit", "ready_at"].forEach(k => {
        const i = node.querySelector('[data-f="' + k + '"]');
        if (i && preset[k] != null) i.value = preset[k];
      });
    }
    node.querySelector("[data-del-item]").addEventListener("click", () => {
      if (rowsEl.querySelectorAll(".rn-aid-row").length > 1) node.remove();
      else clearRow(node);
      syncDelState();
    });
    rowsEl.appendChild(node);
    syncDelState();
    return node;
  }
  function clearRow(node) {
    node.querySelectorAll("input").forEach(i => { i.value = ""; });
  }
  function syncDelState() {
    const only = rowsEl.querySelectorAll(".rn-aid-row").length <= 1;
    rowsEl.querySelectorAll("[data-del-item]").forEach(b => { b.disabled = only; });
  }

  wrap.querySelector("[data-add-item]").addEventListener("click", () => addRow());
  if (!rowsEl.querySelector(".rn-aid-row")) addRow();

  form.__collectAidItems = function () {
    const out = [];
    rowsEl.querySelectorAll(".rn-aid-row").forEach(r => {
      const g = k => (r.querySelector('[data-f="' + k + '"]').value || "").trim();
      const item = g("item_name");
      if (!item) return;
      out.push({
        item_text: item,
        quantity: g("quantity") ? Number(g("quantity")) : null,
        unit: g("unit") || null,
        ready_at: g("ready_at") || null,
      });
    });
    return out;
  };
  form.__resetAidItems = function () {
    rowsEl.innerHTML = "";
    addRow();
  };
}


function setupPublicAidForm() {
  const form =
    document.querySelector(
      "[data-public-aid-form]"
    );

  const result =
    document.querySelector(
      "[data-public-aid-result]"
    );

  if (!form) return;

  setupDeliveryModeToggle(form);
  initAidItems(form);

  form.addEventListener(
    "submit",
    async e => {
      e.preventDefault();

      if (!window.RN_FRAPPE) {
        result.innerHTML =
          `<div class="alert danger">` +
          `Frappe client tidak tersedia.` +
          `</div>`;

        return;
      }

      const deliveryMode =
        form.delivery_mode.value;

      const handlingMode =
        mapDeliveryMode(
          deliveryMode
        );

      const targetPosko =
        deliveryMode ===
        "self_deliver_to_posko"
          ? (
              form.target_node_id.value
                .trim() ||
              null
            )
          : null;

      const donorName =
        form.donor_name.value.trim();

      const donorContact =
        form.donor_contact.value.trim();

      const items = form.__collectAidItems
        ? form.__collectAidItems()
        : [];

      if (!donorName || !donorContact || !items.length) {
        result.innerHTML =
          `<div class="alert danger">` +
          `Lengkapi nama, HP, dan minimal satu item barang.` +
          `</div>`;
        return;
      }

      const incomplete = items.find(it => !it.quantity || !it.unit);
      if (incomplete) {
        result.innerHTML =
          `<div class="alert danger">` +
          `Lengkapi jumlah &amp; satuan untuk "${safe(incomplete.item_text)}".` +
          `</div>`;
        return;
      }

      try {
        result.innerHTML =
          `<div class="alert neutral">` +
          `Menyimpan ${items.length} item bantuan ke Frappe...` +
          `</div>`;

        const data =
          await RN_FRAPPE.call(
            "rescue_net.api_logistics." +
            "create_user_aid_offer_multi",
            {
              disaster_event:
                form.disaster_event_id.value.trim(),

              donor_name: donorName,
              donor_contact: donorContact,

              items_json: JSON.stringify(items),

              handling_mode: handlingMode,
              target_posko: targetPosko,

              pickup_location:
                form.pickup_location.value.trim() || null,

              ready_at:
                form.ready_at.value.trim() || null,

              expected_arrival_at:
                (form.expected_arrival_at &&
                  form.expected_arrival_at.value.trim()) || null,

              notes:
                form.notes.value.trim() || null
            },
            {
              method: "POST"
            }
          );

        renderCreateSuccess(
          result,
          data
        );

        form.reset();
        if (form.__resetAidItems) form.__resetAidItems();

        if (
          form.disaster_event_id
        ) {
          form.disaster_event_id.value =
            "event-sim-001";
        }

        if (
          form.delivery_mode
        ) {
          form.delivery_mode.value =
            "need_pickup";
        }

        setupDeliveryModeToggle(
          form
        );

      } catch (err) {
        result.innerHTML =
          `<div class="alert danger">` +
          `${safe(err.message)}` +
          `</div>`;
      }
    }
  );
}


function setupEditAidForm() {
  const form =
    document.querySelector(
      "[data-edit-aid-form]"
    );

  const result =
    document.querySelector(
      "[data-edit-aid-result]"
    );

  if (!form) return;

  setupDeliveryModeToggle(form);

  form.addEventListener(
    "submit",
    async e => {
      e.preventDefault();

      if (!window.RN_FRAPPE) {
        result.innerHTML =
          `<div class="alert danger">` +
          `Frappe client tidak tersedia.` +
          `</div>`;

        return;
      }

      const aidId =
        form.aid_offer_id.value
          .trim();

      if (!aidId) {
        result.innerHTML =
          `<div class="alert danger">` +
          `Aid Offer ID wajib diisi.` +
          `</div>`;

        return;
      }

      const deliveryMode =
        form.delivery_mode.value;

      const handlingMode =
        mapDeliveryMode(
          deliveryMode
        );

      const targetPosko =
        deliveryMode ===
        "self_deliver_to_posko"
          ? (
              form.target_node_id.value
                .trim() ||
              null
            )
          : null;

      try {
        result.innerHTML =
          `<div class="alert neutral">` +
          `Mengupdate bantuan...` +
          `</div>`;

        const data =
          await RN_FRAPPE.call(
            "rescue_net.api_logistics." +
            "update_user_aid_offer",
            {
              aid_offer:
                aidId,

              item_text:
                form.item_name.value
                  .trim() ||
                null,

              quantity:
                form.quantity.value
                  ? Number(
                      form.quantity.value
                    )
                  : null,

              unit:
                form.unit.value
                  .trim() ||
                null,

              handling_mode:
                handlingMode,

              target_posko:
                targetPosko,

              pickup_location:
                form.pickup_location
                  .value
                  .trim() ||
                null,

              ready_at:
                form.ready_at.value
                  .trim() ||
                null,

              notes:
                form.notes.value
                  .trim() ||
                null
            },
            {
              method: "POST"
            }
          );

        result.innerHTML = `
          <div class="success-box">
            <h3>Bantuan berhasil diupdate</h3>

            <div class="code-grid">
              <div>
                <span>Aid Offer</span>
                <strong>${safe(data.aid_offer)}</strong>
              </div>

              <div>
                <span>Status</span>
                <strong>${safe(data.offer_status)}</strong>
              </div>

              <div>
                <span>Handling</span>
                <strong>${safe(data.handling_mode)}</strong>
              </div>

              <div>
                <span>Target Posko</span>
                <strong>${safe(data.target_posko)}</strong>
              </div>
            </div>
          </div>
        `;

      } catch (err) {
        result.innerHTML =
          `<div class="alert danger">` +
          `${safe(err.message)}` +
          `</div>`;
      }
    }
  );
}


document.addEventListener(
  "DOMContentLoaded",
  () => {
    setupPublicAidForm();
    setupEditAidForm();
  }
);
