let DISTRIBUTION_CACHE = null;

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

function getDistributionPosko() {
  const params =
    new URLSearchParams(
      location.search
    );

  return (
    params.get("id") ||
    params.get("posko") ||
    "posko-sim-logistik"
  );
}

function chipClass(status) {
  if (
    status === "in_transit" ||
    status === "assigned_pickup"
  ) {
    return "warning";
  }

  if (
    status === "arrived_at_posko"
  ) {
    return "danger";
  }

  return "neutral";
}

async function dashboard() {
  const ctx =
    await RN_FRAPPE.call(
      "rescue_net.api_logistics.dashboard",
      {
        posko:
          getDistributionPosko()
      }
    );

  DISTRIBUTION_CACHE = ctx;

  return ctx;
}

function renderOffer(a) {
  return `
    <article class="event-card">
      <div class="event-main">
        <div>
          <h4>
            ${safe(a.item_name)}
            · ${safe(a.quantity)}
            ${safe(a.unit)}
          </h4>
          <p>
            Donatur:
            ${safe(a.donor_name)}
          </p>
          <p>
            Tujuan:
            ${safe(a.target_posko)}
          </p>
        </div>
        <div class="chips">
          <span class="chip ${chipClass(a.offer_status)}">
            ${safe(a.offer_status)}
          </span>
        </div>
      </div>
    </article>
  `;
}

async function loadAidOffers() {
  const needPickup =
    document.querySelector(
      "[data-need-pickup]"
    );

  const selfDelivery =
    document.querySelector(
      "[data-self-delivery]"
    );

  if (
    !needPickup &&
    !selfDelivery
  ) {
    return;
  }

  try {
    const ctx =
      DISTRIBUTION_CACHE ||
      await dashboard();

    const offers =
      ctx.offers || [];

    const available =
      offers.filter(
        a =>
          [
            "available",
            "need_pickup"
          ].includes(
            a.offer_status
          )
      );

    if (needPickup) {
      needPickup.innerHTML =
        available.length
          ? available
              .map(renderOffer)
              .join("")
          : `
            <article class="event-card">
              <h4>Tidak ada bantuan perlu pickup</h4>
              <p>Tidak ada Aid Offer tersedia.</p>
            </article>
          `;
    }

    if (selfDelivery) {
      selfDelivery.innerHTML = `
        <article class="event-card">
          <h4>Frappe-native Aid Offer</h4>
          <p>
            Self-delivery legacy digantikan oleh lifecycle
            Aid Offer dan Distribution Flow.
          </p>
        </article>
      `;
    }

  } catch (err) {
    if (needPickup) {
      needPickup.innerHTML =
        `<article class="event-card">` +
        `<h4>Gagal load Aid Offer</h4>` +
        `<p>${safe(err.message)}</p>` +
        `</article>`;
    }
  }
}

async function loadTransportSpaces() {
  const target =
    document.querySelector(
      "[data-transport-spaces]"
    );

  if (!target) return;

  try {
    const ctx =
      DISTRIBUTION_CACHE ||
      await dashboard();

    const transports =
      ctx.transports || [];

    target.innerHTML =
      transports.length
        ? transports.map(t => `
          <article class="event-card">
            <div class="event-main">
              <div>
                <h4>${safe(t.provider_name)}</h4>
                <p>
                  ${safe(t.transport_type)}
                  · ${safe(t.route_origin)}
                  →
                  ${safe(t.route_destination)}
                </p>
                <p>
                  Kapasitas:
                  ${safe(t.capacity_weight_kg)} kg
                  · ${safe(t.capacity_volume_m3)} m³
                  · ETA: ${safe(t.eta)}
                </p>
              </div>
              <div class="chips">
                <span class="chip neutral">
                  ${safe(t.transport_status)}
                </span>
                <span class="chip neutral">
                  ${safe(rowId(t))}
                </span>
              </div>
            </div>
          </article>
        `).join("")
        : `
          <article class="event-card">
            <h4>Belum ada transport</h4>
          </article>
        `;

  } catch (err) {
    target.innerHTML =
      `<article class="event-card">` +
      `<h4>Gagal load transport</h4>` +
      `<p>${safe(err.message)}</p>` +
      `</article>`;
  }
}

async function loadDistributionFlows() {
  const target =
    document.querySelector(
      "[data-distribution-flows]"
    );

  if (!target) return;

  try {
    const ctx =
      DISTRIBUTION_CACHE ||
      await dashboard();

    const flows =
      ctx.flows || [];

    target.innerHTML =
      flows.length
        ? flows.map(f => `
          <article class="event-card">
            <div class="event-main">
              <div>
                <h4>${safe(rowId(f))}</h4>
                <p>
                  Item: ${safe(f.item_name)}
                  · Quantity:
                  ${safe(f.quantity)}
                  ${safe(f.unit)}
                </p>
                <p>
                  Source:
                  ${safe(f.source_posko)}
                  · Destination:
                  ${safe(f.destination_posko)}
                  · ETA:
                  ${safe(f.eta_final)}
                </p>
              </div>
              <div class="chips">
                <span class="chip ${chipClass(f.flow_status)}">
                  ${safe(f.flow_status)}
                </span>
              </div>
            </div>
          </article>
        `).join("")
        : `
          <article class="event-card">
            <h4>Belum ada flow</h4>
            <p>
              Belum ada Distribution Flow.
            </p>
          </article>
        `;

  } catch (err) {
    target.innerHTML =
      `<article class="event-card">` +
      `<h4>Gagal load flow</h4>` +
      `<p>${safe(err.message)}</p>` +
      `</article>`;
  }
}

function setupTransportForm() {
  const form =
    document.querySelector(
      "[data-create-transport]"
    );

  const msg =
    document.querySelector(
      "[data-transport-message]"
    );

  if (!form) return;

  form.addEventListener(
    "submit",
    async e => {
      e.preventDefault();

      try {
        if (msg) {
          msg.textContent =
            "Menyimpan transport...";
        }

        await RN_FRAPPE.call(
          "rescue_net.api_logistics.create_transport_space",
          {
            coordination_posko:
              getDistributionPosko(),

            provider_name:
              form.provider_name.value.trim(),

            transport_type:
              form.transport_type.value.trim(),

            route_origin:
              form.route_origin.value.trim(),

            route_destination:
              form.route_destination.value.trim(),

            capacity_weight_kg:
              Number(
                form.capacity_weight_kg.value || 0
              ),

            capacity_volume_m3:
              Number(
                form.capacity_volume_m3.value || 0
              ),

            departure_time:
              form.departure_time.value.trim(),

            eta:
              form.eta.value.trim()
          },
          {
            method: "POST"
          }
        );

        DISTRIBUTION_CACHE = null;

        if (msg) {
          msg.textContent =
            "Transport berhasil disimpan.";
        }

        await loadTransportSpaces();

      } catch (err) {
        if (msg) {
          msg.textContent =
            err.message;
        }
      }
    }
  );
}

function findReference(
  list,
  id
) {
  return (
    list || []
  ).find(
    row =>
      rowId(row) === id ||
      row.legacy_id === id
  );
}

function setupFlowForm() {
  const form =
    document.querySelector(
      "[data-create-flow]"
    );

  const msg =
    document.querySelector(
      "[data-flow-message]"
    );

  if (!form) return;

  form.addEventListener(
    "submit",
    async e => {
      e.preventDefault();

      try {
        const ctx =
          DISTRIBUTION_CACHE ||
          await dashboard();

        const needId =
          form.need_id.value.trim();

        const aidId =
          form.aid_offer_id.value.trim();

        const transportId =
          form.transport_space_id.value.trim();

        const need =
          findReference(
            ctx.needs,
            needId
          );

        const aid =
          findReference(
            ctx.offers,
            aidId
          );

        const selected =
          need ||
          aid ||
          {};

        const destination =
          form.destination_node_id
            .value
            .trim() ||
          selected.posko ||
          selected.target_posko ||
          getDistributionPosko();

        const item =
          selected.item_name ||
          "Distribution";

        if (msg) {
          msg.textContent =
            "Menyimpan flow...";
        }

        await RN_FRAPPE.call(
          "rescue_net.api_logistics.create_flow",
          {
            destination_posko:
              destination,

            item_text:
              item,

            quantity:
              selected.quantity || null,

            unit:
              selected.unit || null,

            quantity_mode:
              selected.quantity_mode ||
              "unknown",

            logistic_need:
              needId || null,

            aid_offer:
              aidId || null,

            transport_space:
              transportId || null,

            eta_final:
              form.eta_final.value.trim()
          },
          {
            method: "POST"
          }
        );

        DISTRIBUTION_CACHE = null;

        if (msg) {
          msg.textContent =
            "Distribution Flow berhasil disimpan.";
        }

        await loadDistributionFlows();

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

    setupTransportForm();
    setupFlowForm();

    dashboard()
      .then(() =>
        Promise.all([
          loadAidOffers(),
          loadTransportSpaces(),
          loadDistributionFlows()
        ])
      )
      .catch(console.error);
  }
);
