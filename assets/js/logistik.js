let LOGISTICS_CACHE = null;

function safe(v) {
  return (
    v === null ||
    v === undefined ||
    v === ""
  ) ? "n/a" : v;
}

function rowId(row) {
  return (
    row?.name ||
    row?.id ||
    row?.legacy_id ||
    ""
  );
}

function priorityClass(priority) {
  if (priority === "critical") {
    return "danger";
  }

  if (
    priority === "urgent" ||
    priority === "high"
  ) {
    return "warning";
  }

  return "neutral";
}

function getLogisticsPosko() {
  const params =
    new URLSearchParams(
      location.search
    );

  return (
    params.get("id") ||
    params.get("posko") ||
    document.querySelector(
      "[data-rn-create-logistic-need] [name='node_id']"
    )?.value ||
    "posko-sim-logistik"
  );
}

async function dashboard() {
  return RN_FRAPPE.call(
    "rescue_net.api_logistics.dashboard",
    {
      posko:
        getLogisticsPosko()
    }
  );
}

async function loadLogisticNeeds() {
  const target =
    document.querySelector(
      "[data-rn-logistic-needs]"
    );

  if (!target) return;

  try {
    const ctx =
      await dashboard();

    LOGISTICS_CACHE = ctx;

    const needs =
      ctx.needs || [];

    target.innerHTML =
      needs.length
        ? needs.map(n => `
          <article class="event-card">
            <div class="event-main">
              <div>
                <h4>${safe(n.item_name)}</h4>
                <p>
                  Kebutuhan:
                  <b>${safe(n.quantity)} ${safe(n.unit)}</b>
                  · Status: ${safe(n.need_status)}
                </p>
              </div>
              <div class="chips">
                <span class="chip ${priorityClass(n.urgency)}">
                  ${safe(n.urgency)}
                </span>
                <span class="chip neutral">
                  ${safe(n.posko)}
                </span>
              </div>
            </div>
          </article>
        `).join("")
        : `
          <article class="event-card">
            <h4>Belum ada kebutuhan</h4>
            <p>Tidak ada kebutuhan aktif untuk Posko ini.</p>
          </article>
        `;

  } catch (err) {
    target.innerHTML =
      `<article class="event-card">` +
      `<h4>Gagal load kebutuhan</h4>` +
      `<p>${safe(err.message)}</p>` +
      `</article>`;
  }
}

async function loadAidOffers() {
  const target =
    document.querySelector(
      "[data-rn-aid-offers]"
    );

  if (!target) return;

  try {
    const ctx =
      LOGISTICS_CACHE ||
      await dashboard();

    LOGISTICS_CACHE = ctx;

    const offers =
      ctx.offers || [];

    target.innerHTML =
      offers.length
        ? offers.map(a => `
          <article class="event-card">
            <div class="event-main">
              <div>
                <h4>${safe(a.item_name)}</h4>
                <p>
                  Donatur: ${safe(a.donor_name)}
                  · Jumlah:
                  <b>${safe(a.quantity)} ${safe(a.unit)}</b>
                </p>
              </div>
              <div class="chips">
                <span class="chip neutral">
                  ${safe(a.offer_status)}
                </span>
              </div>
            </div>
          </article>
        `).join("")
        : `
          <article class="event-card">
            <h4>Belum ada bantuan</h4>
            <p>Tidak ada Aid Offer untuk Posko ini.</p>
          </article>
        `;

  } catch (err) {
    target.innerHTML =
      `<article class="event-card">` +
      `<h4>Gagal load bantuan</h4>` +
      `<p>${safe(err.message)}</p>` +
      `</article>`;
  }
}

function setupLogisticNeedForm() {
  const form =
    document.querySelector(
      "[data-rn-create-logistic-need]"
    );

  const msg =
    document.querySelector(
      "[data-rn-logistic-message]"
    );

  if (!form) return;

  form.addEventListener(
    "submit",
    async e => {
      e.preventDefault();

      try {
        if (msg) {
          msg.textContent =
            "Menyimpan kebutuhan logistik...";
        }

        await RN_FRAPPE.call(
          "rescue_net.api_logistics.create_need",
          {
            posko:
              form.node_id.value.trim() ||
              getLogisticsPosko(),

            item_text:
              form.item_name.value.trim(),

            quantity:
              Number(
                form.quantity_needed.value || 0
              ),

            unit:
              form.unit.value.trim(),

            quantity_mode:
              "known",

            urgency:
              form.priority.value,

            needed_before:
              form.needed_before.value.trim()
          },
          {
            method: "POST"
          }
        );

        LOGISTICS_CACHE = null;

        if (msg) {
          msg.textContent =
            "Kebutuhan logistik berhasil disimpan.";
        }

        await loadLogisticNeeds();

      } catch (err) {
        if (msg) {
          msg.textContent =
            err.message;
        }
      }
    }
  );
}

function setupAidOfferForm() {
  const form =
    document.querySelector(
      "[data-rn-create-aid-offer]"
    );

  const msg =
    document.querySelector(
      "[data-rn-aid-message]"
    );

  if (!form) return;

  form.addEventListener(
    "submit",
    async e => {
      e.preventDefault();

      try {
        if (msg) {
          msg.textContent =
            "Menyimpan bantuan tersedia...";
        }

        await RN_FRAPPE.call(
          "rescue_net.api_logistics.create_aid_offer",
          {
            target_posko:
              getLogisticsPosko(),

            donor_name:
              form.donor_name.value.trim(),

            item_text:
              form.item_name.value.trim(),

            quantity:
              Number(
                form.quantity.value || 0
              ),

            unit:
              form.unit.value.trim(),

            quantity_mode:
              "known",

            pickup_location:
              form.pickup_location.value.trim()
          },
          {
            method: "POST"
          }
        );

        LOGISTICS_CACHE = null;

        if (msg) {
          msg.textContent =
            "Bantuan berhasil disimpan.";
        }

        await loadAidOffers();

      } catch (err) {
        if (msg) {
          msg.textContent =
            err.message;
        }
      }
    }
  );
}

document.addEventListener(
  "DOMContentLoaded",
  () => {
    if (!window.RN_FRAPPE) {
      console.error(
        "RN_FRAPPE unavailable"
      );
      return;
    }

    setupLogisticNeedForm();
    setupAidOfferForm();

    loadLogisticNeeds();
    loadAidOffers();
  }
);
