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
  result.innerHTML = `
    <div class="success-box">
      <h3>Bantuan berhasil dicatat</h3>

      <p>
        Bantuan sekarang terhubung dengan
        akun Rescue-Net yang sedang login.
      </p>

      <div class="code-grid">
        <div>
          <span>Aid Offer ID</span>
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

      <p class="subtitle">
        Edit berikutnya menggunakan session login,
        bukan kode edit legacy.
      </p>

      <a
        class="btn primary"
        href="edit-bantuan.html"
      >
        Edit Bantuan Saya
      </a>
    </div>
  `;
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

      const itemText =
        form.item_name.value.trim();

      const quantity =
        Number(
          form.quantity.value || 0
        );

      const unit =
        form.unit.value.trim();

      if (
        !donorName ||
        !donorContact ||
        !itemText ||
        !quantity ||
        !unit
      ) {
        result.innerHTML =
          `<div class="alert danger">` +
          `Lengkapi nama, HP, item, jumlah, ` +
          `dan satuan.` +
          `</div>`;

        return;
      }

      try {
        result.innerHTML =
          `<div class="alert neutral">` +
          `Menyimpan bantuan ke Frappe...` +
          `</div>`;

        const data =
          await RN_FRAPPE.call(
            "rescue_net.api_logistics." +
            "create_user_aid_offer",
            {
              disaster_event:
                form.disaster_event_id
                  .value
                  .trim(),

              donor_name:
                donorName,

              donor_contact:
                donorContact,

              item_text:
                itemText,

              quantity,

              unit,

              quantity_mode:
                "exact",

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
                form.ready_at
                  .value
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

        renderCreateSuccess(
          result,
          data
        );

        form.reset();

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
