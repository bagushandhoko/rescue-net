let POSKO_CONTEXT_CACHE = null;


function getPoskoId() {
  const params =
    new URLSearchParams(
      window.location.search
    );

  return (
    params.get("id") ||
    "posko-sim-logistik"
  );
}


function safe(v) {
  return (
    v === null ||
    v === undefined ||
    v === ""
  )
    ? "n/a"
    : v;
}


function rowId(row) {
  return (
    row?.name ||
    row?.id ||
    row?.legacy_id ||
    ""
  );
}


function setStatus(msg) {
  const el =
    document.getElementById(
      "poskoStatus"
    );

  if (el) {
    el.textContent = msg;
  }
}


function card(
  title,
  body,
  chip = ""
) {
  return `
    <article class="event-card">
      <div class="event-main">
        <div>
          <h4>${safe(title)}</h4>
          <p>${body}</p>
        </div>

        <div class="chips">
          ${
            chip
              ? `<span class="chip warning">${safe(chip)}</span>`
              : ""
          }
        </div>
      </div>
    </article>
  `;
}


function renderOverview(ctx) {
  const posko =
    ctx.posko || {};

  const title =
    document.getElementById(
      "poskoTitle"
    );

  const subtitle =
    document.getElementById(
      "poskoSubtitle"
    );

  if (title) {
    title.textContent =
      posko.title ||
      posko.name ||
      getPoskoId();
  }

  if (subtitle) {
    subtitle.textContent =
      `${safe(posko.posko_type)} · ` +
      `${safe(posko.operational_status)} · ` +
      `${safe(posko.verification_status)}`;
  }

  const overview =
    document.getElementById(
      "poskoOverview"
    );

  if (overview) {
    overview.innerHTML = `
      <div>
        <span>Posko</span>
        <b>${safe(posko.title)}</b>
      </div>

      <div>
        <span>Canonical ID</span>
        <b>${safe(posko.name)}</b>
      </div>

      <div>
        <span>Type</span>
        <b>${safe(posko.posko_type)}</b>
      </div>

      <div>
        <span>Organization</span>
        <b>${safe(posko.organization)}</b>
      </div>

      <div>
        <span>Status</span>
        <b>${safe(posko.operational_status)}</b>
      </div>

      <div>
        <span>Verification</span>
        <b>${safe(posko.verification_status)}</b>
      </div>
    `;
  }

  const values = {
    kpiRole:
      posko.posko_type || "-",

    kpiNeeds:
      (ctx.needs || []).length,

    kpiStock:
      (ctx.stocks || []).length,

    kpiFlows:
      (ctx.flows || []).length
  };

  Object.entries(values)
    .forEach(
      ([id, value]) => {
        const el =
          document.getElementById(id);

        if (el) {
          el.textContent = value;
        }
      }
    );
}


function renderStockSummary(items) {
  const el =
    document.getElementById(
      "stockSummary"
    );

  if (!el) {
    return;
  }

  el.innerHTML =
    items.length
      ? items.map(s => card(
          s.item_name,
          `Quantity: <b>${safe(s.quantity)}</b> ` +
          `${safe(s.unit)}<br>` +
          `Mode: ${safe(s.quantity_mode)}<br>` +
          `Observed: ${safe(s.observed_at)}`,
          s.stock_state
        )).join("")
      : card(
          "Belum ada stock observation",
          "Belum ada snapshot stok.",
          "empty"
        );
}


function renderStockObservations(items) {
  const el =
    document.getElementById(
      "stockMovements"
    );

  if (!el) {
    return;
  }

  el.innerHTML =
    items.length
      ? items.map(s => card(
          s.item_name,
          `${safe(s.quantity)} ${safe(s.unit)}<br>` +
          `${safe(s.notes)}<br>` +
          `Observed: ${safe(s.observed_at)}`,
          s.quantity_mode
        )).join("")
      : card(
          "Belum ada observation",
          "Belum ada riwayat snapshot stok.",
          "empty"
        );
}


function renderNeeds(items) {
  const el =
    document.getElementById(
      "logisticNeeds"
    );

  if (!el) {
    return;
  }

  el.innerHTML =
    items.length
      ? items.map(n => card(
          n.item_name,
          `Need: ${safe(n.quantity)} ${safe(n.unit)}<br>` +
          `Urgency: ${safe(n.urgency)}<br>` +
          `Status: ${safe(n.need_status)}`,
          n.need_status
        )).join("")
      : card(
          "Belum ada kebutuhan",
          "Tidak ada kebutuhan aktif.",
          "empty"
        );
}


function renderIncomingAid(items) {
  const el =
    document.getElementById(
      "incomingAid"
    );

  if (!el) {
    return;
  }

  el.innerHTML =
    items.length
      ? items.map(a => card(
          a.item_name,
          `${safe(a.quantity)} ${safe(a.unit)}<br>` +
          `Donor: ${safe(a.donor_name)}<br>` +
          `Status: ${safe(a.offer_status)}`,
          a.offer_status
        )).join("")
      : card(
          "Belum ada incoming aid",
          "Belum ada Aid Offer menuju Posko ini.",
          "empty"
        );
}


function canReceiveFlow(flow) {
  return [
    "arrived_at_posko",
    "partially_received"
  ].includes(
    String(
      flow.flow_status || ""
    )
  );
}


function renderFlows(items) {
  const el =
    document.getElementById(
      "distributionFlows"
    );

  if (!el) {
    return;
  }

  el.innerHTML =
    items.length
      ? items.map(f => {
          const id =
            rowId(f);

          const button =
            canReceiveFlow(f)
              ? `
                <button
                  class="btn primary"
                  type="button"
                  onclick="receiveFlow('${id}')"
                >
                  Verify Received
                </button>
              `
              : "";

          return `
            <article class="event-card">
              <div class="event-main">
                <div>
                  <h4>${safe(f.item_name)}</h4>

                  <p>
                    Flow: ${safe(id)}<br>
                    Source: ${safe(f.source_posko)}<br>
                    Destination: ${safe(f.destination_posko)}<br>
                    Quantity:
                    ${safe(f.quantity)}
                    ${safe(f.unit)}<br>
                    ETA: ${safe(f.eta_final)}
                  </p>
                </div>

                <div class="chips">
                  <span class="chip warning">
                    ${safe(f.flow_status)}
                  </span>

                  ${button}
                </div>
              </div>
            </article>
          `;
        }).join("")
      : card(
          "Belum ada distribution flow",
          "Belum ada distribusi menuju Posko ini.",
          "empty"
        );
}


async function loadPosko() {
  setStatus(
    "Loading Frappe Posko context..."
  );

  const result =
    await RN_FRAPPE.call(
      "rescue_net.api_logistics.dashboard",
      {
        posko:
          getPoskoId()
      }
    );

  const ctx = {
    posko:
      result.poskos?.[0] ||
      {
        name:
          getPoskoId()
      },

    needs:
      result.needs || [],

    stocks:
      result.stocks || [],

    offers:
      result.offers || [],

    transports:
      result.transports || [],

    flows:
      result.flows || []
  };

  POSKO_CONTEXT_CACHE =
    ctx;

  renderOverview(ctx);
  renderStockSummary(
    ctx.stocks
  );
  renderStockObservations(
    ctx.stocks
  );
  renderNeeds(
    ctx.needs
  );
  renderIncomingAid(
    ctx.offers
  );
  renderFlows(
    ctx.flows
  );

  setStatus(
    "Loaded from Frappe"
  );
}


async function receiveFlow(flowId) {
  if (!POSKO_CONTEXT_CACHE) {
    await loadPosko();
  }

  const flow =
    (
      POSKO_CONTEXT_CACHE.flows ||
      []
    ).find(
      item =>
        rowId(item) === flowId
    );

  if (!flow) {
    setStatus(
      "Distribution Flow tidak ditemukan."
    );

    return;
  }

  const quantity =
    Number(
      prompt(
        `Jumlah diterima untuk ${safe(flow.item_name)} ` +
        `(${safe(flow.unit)})`,
        flow.quantity || 1
      )
    );

  if (
    !quantity ||
    quantity <= 0
  ) {
    setStatus(
      "Verify receipt dibatalkan."
    );

    return;
  }

  setStatus(
    "Verifying received flow..."
  );

  const result =
    await RN_FRAPPE.call(
      "rescue_net.api_logistics." +
      "receive_flow_and_update_stock",
      {
        flow:
          flowId,

        received_quantity:
          quantity,

        received_unit:
          flow.unit || null,

        receipt_note:
          "Diverifikasi melalui Posko Detail."
      },
      {
        method: "POST"
      }
    );

  setStatus(
    `Receipt verified. Current stock: ` +
    `${safe(result.current_quantity)} ` +
    `${safe(result.unit)}`
  );

  await loadPosko();
}


function setupStockForm() {
  const form =
    document.getElementById(
      "stockForm"
    );

  if (!form) {
    return;
  }

  form.addEventListener(
    "submit",
    async event => {
      event.preventDefault();

      const quantity =
        Number(
          form.quantity.value || 0
        );

      if (quantity < 0) {
        setStatus(
          "Quantity tidak boleh negatif."
        );

        return;
      }

      setStatus(
        "Saving stock observation..."
      );

      await RN_FRAPPE.call(
        "rescue_net.api_logistics." +
        "create_stock_observation",
        {
          posko:
            getPoskoId(),

          item_text:
            form.item_name
              .value
              .trim(),

          quantity,

          unit:
            form.unit
              .value
              .trim(),

          quantity_mode:
            "exact",

          stock_state:
            "available",

          notes:
            form.notes
              .value
              .trim()
        },
        {
          method: "POST"
        }
      );

      setStatus(
        "Stock observation saved."
      );

      await loadPosko();
    }
  );
}


function setupTransferForm() {
  const form =
    document.getElementById(
      "transferForm"
    );

  if (!form) {
    return;
  }

  form.addEventListener(
    "submit",
    async event => {
      event.preventDefault();

      const quantity =
        Number(
          form.quantity.value || 0
        );

      if (
        !quantity ||
        quantity <= 0
      ) {
        setStatus(
          "Quantity transfer harus lebih dari 0."
        );

        return;
      }

      setStatus(
        "Creating Distribution Flow..."
      );

      const result =
        await RN_FRAPPE.call(
          "rescue_net.api_logistics." +
          "create_flow",
          {
            source_posko:
              getPoskoId(),

            destination_posko:
              form.destination_posko_id
                .value
                .trim(),

            item_text:
              form.item_name
                .value
                .trim(),

            quantity,

            unit:
              form.unit
                .value
                .trim(),

            quantity_mode:
              "exact"
          },
          {
            method: "POST"
          }
        );

      setStatus(
        "Distribution Flow created: " +
        safe(
          result.flow ||
          result.name
        )
      );

      await loadPosko();
    }
  );
}


document.addEventListener(
  "DOMContentLoaded",
  () => {
    if (!window.RN_FRAPPE) {
      setStatus(
        "Frappe client tidak tersedia."
      );

      return;
    }

    setupStockForm();
    setupTransferForm();

    loadPosko()
      .catch(
        err =>
          setStatus(
            err.message
          )
      );
  }
);


window.receiveFlow =
  receiveFlow;
