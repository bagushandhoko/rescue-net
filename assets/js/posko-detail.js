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


const METHOD_LABEL_VF = {
  site_visit: "kunjungan langsung",
  network_vouch: "rekomendasi jaringan",
  document_review: "telaah dokumen",
};

async function renderVerifPanel(poskoName) {
  const el = document.getElementById("poskoVerifPanel");
  if (!el || !poskoName) return;
  let d;
  try {
    d = await RN_FRAPPE.call(
      "rescue_net.api_verifier.posko_verification_public",
      { posko: poskoName }
    );
  } catch (e) { el.hidden = true; return; }
  if (!d || !d.found) { el.hidden = true; return; }

  const badge = window.RNVerifBadge
    ? window.RNVerifBadge.html(d.verification_status, d.trusted_verifier_count)
    : safe(d.verification_status);
  const ends = d.endorsements || [];
  const list = ends.length
    ? ends.map(e => `
        <div class="rn-vf-end">
          <b>${safe(e.verifier)}</b> <span class="rn-muted">(${safe(e.role)})</span>
          — ${safe(METHOD_LABEL_VF[e.method] || e.method)}
          ${e.vouched_via ? `· via ${safe(e.vouched_via)}` : ""}
          ${e.verified_at ? `· ${String(e.verified_at).slice(0, 10)}` : ""}
          ${e.statement ? `<div class="rn-muted">"${safe(e.statement)}"</div>` : ""}
        </div>`).join("")
    : `<p class="rn-muted">Belum ada endorsement verifikator.
       <a href="verifikator.html">Minta verifikasi ke verifikator wilayah →</a></p>`;

  el.innerHTML = `
    <div class="panel-header">
      <div><h3>Kredibilitas &amp; Verifikasi</h3>
      <p>Endorsement dari jaringan verifikator wilayah (lurah / polsek / tokoh publik).</p></div>
      ${badge}
    </div>
    <div class="rn-vf-ends">${list}</div>`;
  el.hidden = false;
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
    const vb = window.RNVerifBadge
      ? window.RNVerifBadge.html(posko.verification_status, posko.trusted_verifier_count)
      : safe(posko.verification_status);
    subtitle.innerHTML =
      `${safe(posko.posko_type)} · ` +
      `${safe(posko.operational_status)} &nbsp; ${vb}`;
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
        <span>Level Verifikasi</span>
        <b>${window.RNVerifBadge ? window.RNVerifBadge.html(posko.verification_status, posko.trusted_verifier_count) : safe(posko.verification_status)}</b>
      </div>
    `;
  }

  renderVerifPanel(posko.name);

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


function currentEventParam() {
  const p = new URLSearchParams(location.search);
  return p.get("event") || p.get("disaster_event_id") || "";
}


function renderShareBanner(res) {
  const el = document.getElementById("poskoShareBanner");
  if (!el) return;

  const orgTitle =
    (res.organization && res.organization.title) || "organisasi ini";

  if (res.detail_allowed) {
    el.className = "rn-share-banner is-full";
    el.innerHTML =
      `<b>Detail penuh</b> — ${safe(orgTitle)} membuka koordinasi penuh ` +
      `untuk Control Centre.`;
  } else {
    el.className = "rn-share-banner is-summary";
    el.innerHTML =
      `<b>Ringkasan saja</b> — ${safe(orgTitle)} menutup koordinasi detail. ` +
      `Yang tampil hanya angka gabungan. Login sebagai anggota/operator ` +
      `${safe(orgTitle)} untuk melihat detail per-record.`;
  }

  el.hidden = false;
}


function renderSummaryRollup(summary) {
  const panel = document.getElementById("poskoSummaryPanel");
  const el = document.getElementById("poskoSummaryRollup");
  if (!el || !panel) return;

  const s = summary || {};

  const rows = [
    ["Kebutuhan terbuka", s.open_need_count],
    ["Kebutuhan kritis", s.critical_need_count],
    [
      "Realisasi kebutuhan",
      `${Number(s.need_realization_percent || 0).toFixed(0)}% ` +
      `(${safe(s.need_realized_total)} / ${safe(s.need_required_total)})`
    ],
    ["Item stok", s.stock_item_count],
    ["Distribusi masuk", s.incoming_flow_count],
    ["Distribusi keluar", s.outgoing_flow_count],
    ["Tawaran bantuan", s.aid_offer_count],
    ["Kasus medis", s.medical_case_count],
    ["Penugasan relawan", s.volunteer_assignment_count],
    ["Okupansi shelter", s.shelter_occupancy_count]
  ];

  el.innerHTML = rows
    .map(
      ([label, value]) => `
        <div>
          <span>${label}</span>
          <b>${safe(value)}</b>
        </div>
      `
    )
    .join("");

  panel.hidden = false;
}


async function loadPosko() {
  setStatus(
    "Loading Frappe Posko context..."
  );

  const res =
    await RN_FRAPPE.call(
      "rescue_net.api_control_centre.posko_detail",
      {
        posko: getPoskoId(),
        disaster_event: currentEventParam()
      }
    );

  renderShareBanner(res);
  renderSummaryRollup(res.summary);

  // Summary-only viewers cannot record/transfer for this posko.
  const canEdit = !!res.detail_allowed;
  document
    .querySelectorAll(".create-panel")
    .forEach(el => { el.hidden = !canEdit; });
  const stockPanel =
    document.getElementById("stockForm") &&
    document.getElementById("stockForm").closest(".panel");
  if (stockPanel) stockPanel.hidden = !canEdit;

  const manageLink = document.getElementById("logistikManageLink");
  if (manageLink) {
    manageLink.hidden = !canEdit;
    const a = document.getElementById("logistikManageLinkHref");
    if (a) {
      a.href = `posko-logistik.html?id=${encodeURIComponent(getPoskoId())}&event=${encodeURIComponent(currentEventParam())}`;
    }
  }

  try {
    const logBoard = await RN_FRAPPE.call(
      "rescue_net.api_control_centre.logistik_board",
      { posko: getPoskoId(), disaster_event: currentEventParam() }
    );
    if (window.RNLogistikInfo) {
      RNLogistikInfo.renderKpi(logBoard);
      RNLogistikInfo.renderUrgentNeeds(logBoard);
      RNLogistikInfo.renderPublicShipmentsInfo(logBoard);
      RNLogistikInfo.renderMovements(logBoard);
      RNLogistikInfo.wireMovementsTabs(() => logBoard);
    }
  } catch (e) {
    // Kondisi Logistik is supplementary info — a failure here shouldn't
    // block the rest of Posko Detail from rendering.
  }

  const d = res.detail || {};

  const ctx = {
    posko: {
      name: res.posko && res.posko.name || getPoskoId(),
      title: res.posko && res.posko.title,
      posko_type: res.posko && res.posko.posko_type,
      organization:
        (res.organization && res.organization.title) ||
        (res.organization && res.organization.id) ||
        "-",
      operational_status: res.posko && res.posko.operational_status,
      verification_status: res.posko && res.posko.verification_status
    },

    needs: (d.needs || []).map(n => ({
      item_name: n.item_name,
      quantity: n.quantity_required,
      unit: n.unit,
      urgency: n.priority,
      need_status: n.status
    })),

    stocks: d.stocks || [],

    offers: (d.aid_offers || []).map(a => ({
      item_name: a.item_name,
      quantity: a.quantity,
      unit: a.unit,
      offer_status: a.offer_status || a.status,
      donor_name:
        (res.organization && res.organization.title) || ""
    })),

    flows: [
      ...(d.incoming_flows || []).map(f => ({
        ...f,
        destination_posko: res.posko && res.posko.title
      })),
      ...(d.outgoing_flows || []).map(f => ({
        ...f,
        source_posko: res.posko && res.posko.title
      }))
    ]
  };

  POSKO_CONTEXT_CACHE = ctx;

  renderOverview(ctx);
  renderStockSummary(ctx.stocks);
  renderStockObservations(ctx.stocks);
  renderNeeds(ctx.needs);
  renderIncomingAid(ctx.offers);
  renderFlows(ctx.flows);

  setStatus(
    res.detail_allowed
      ? "Loaded from Frappe - detail penuh"
      : "Loaded from Frappe - ringkasan (koordinasi organisasi tertutup)"
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
