let SHELTER_CONTEXT_CACHE = null;

function getShelterPoskoId() {
  const params =
    new URLSearchParams(
      window.location.search
    );

  return (
    params.get("id") ||
    "posko-sim-shelter"
  );
}

function statusMsg(msg) {
  const el =
    document.getElementById(
      "shelterStatus"
    );

  if (el) {
    el.textContent = msg;
  }
}

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

function latestOccupancy(items) {
  return (
    items &&
    items.length
  )
    ? items[0]
    : null;
}

function renderOccupancies(items) {
  const el =
    document.getElementById(
      "shelterOccupancies"
    );

  if (!el) return;

  el.innerHTML =
    items.length
      ? items.map(o => card(
          o.shelter_name,
          `Occupancy: ${safe(o.current_occupancy)}/` +
          `${safe(o.capacity_total)}<br>` +
          `Families: ${safe(o.families_count)}<br>` +
          `Children: ${safe(o.children_count)} · ` +
          `Elderly: ${safe(o.elderly_count)} · ` +
          `Disabled: ${safe(o.disability_count)}`,
          o.verification_status
        )).join("")
      : card(
          "Belum ada occupancy",
          "Catat data hunian shelter.",
          "empty"
        );
}

function renderNeeds(items) {
  const el =
    document.getElementById(
      "shelterNeeds"
    );

  if (!el) return;

  el.innerHTML =
    items.length
      ? items.map(n => card(
          n.item_name,
          `Need: ${safe(n.quantity_needed)} ${safe(n.unit)}<br>` +
          `Priority: ${safe(n.priority)}<br>` +
          `Before: ${safe(n.needed_before)}`,
          n.need_status
        )).join("")
      : card(
          "Belum ada kebutuhan shelter",
          "Tambahkan kebutuhan shelter.",
          "empty"
        );
}

function renderStock(items) {
  const el =
    document.getElementById(
      "shelterStock"
    );

  if (!el) return;

  el.innerHTML =
    items.length
      ? items.map(s => card(
          s.item_name,
          `Current stock: <b>${safe(s.quantity)}</b> ${safe(s.unit)}`,
          s.stock_state
        )).join("")
      : card(
          "Belum ada stok shelter",
          "Belum ada Stock Observation.",
          "empty"
        );
}

function renderFlows(items) {
  const el =
    document.getElementById(
      "shelterFlows"
    );

  if (!el) return;

  el.innerHTML =
    items.length
      ? items.map(f => card(
          rowId(f),
          `Item: ${safe(f.item_name)}<br>` +
          `Source: ${safe(f.source_posko)}<br>` +
          `ETA: ${safe(f.eta_final)}`,
          f.flow_status
        )).join("")
      : card(
          "Belum ada distribution flow",
          "Belum ada distribusi menuju shelter.",
          "empty"
        );
}

async function loadShelter() {
  const poskoId =
    getShelterPoskoId();

  statusMsg(
    "Loading shelter context..."
  );

  const [
    shelter,
    logistics
  ] = await Promise.all([
    RN_FRAPPE.call(
      "rescue_net.api_shelter.dashboard",
      {
        posko: poskoId
      }
    ),

    RN_FRAPPE.call(
      "rescue_net.api_logistics.dashboard",
      {
        posko: poskoId
      }
    )
  ]);

  const posko =
    shelter.poskos?.[0] ||
    logistics.poskos?.[0] ||
    {
      name: poskoId
    };

  const ctx = {
    posko,
    occupancies:
      shelter.occupancies || [],
    households:
      shelter.households || [],
    needs:
      shelter.needs || [],
    stocks:
      logistics.stocks || [],
    flows:
      logistics.flows || []
  };

  SHELTER_CONTEXT_CACHE = ctx;

  const latest =
    latestOccupancy(
      ctx.occupancies
    );

  const title =
    document.getElementById(
      "shelterTitle"
    );

  const subtitle =
    document.getElementById(
      "shelterSubtitle"
    );

  if (title) {
    title.textContent =
      posko.title ||
      posko.name ||
      poskoId;
  }

  if (subtitle) {
    subtitle.textContent =
      `${safe(posko.posko_type)} · ` +
      `${safe(posko.operational_status)} · ` +
      `${safe(posko.verification_status)}`;
  }

  const values = {
    kpiCapacity:
      latest?.capacity_total || 0,

    kpiOccupancy:
      latest?.current_occupancy || 0,

    kpiFamilies:
      latest?.families_count || 0,

    kpiNeeds:
      ctx.needs.length
  };

  Object.entries(values)
    .forEach(([id, value]) => {
      const el =
        document.getElementById(id);

      if (el) {
        el.textContent = value;
      }
    });

  renderOccupancies(
    ctx.occupancies
  );

  renderNeeds(
    ctx.needs
  );

  renderStock(
    ctx.stocks
  );

  renderFlows(
    ctx.flows
  );

  const form =
    document.getElementById(
      "occupancyForm"
    );

  if (
    form &&
    form.posko_id
  ) {
    form.posko_id.value =
      poskoId;
  }

  statusMsg(
    "Loaded from Frappe"
  );
}

function setupOccupancyForm() {
  const form =
    document.getElementById(
      "occupancyForm"
    );

  if (!form) return;

  form.addEventListener(
    "submit",
    async e => {
      e.preventDefault();

      await RN_FRAPPE.call(
        "rescue_net.api_shelter.create_occupancy",
        {
          posko:
            form.posko_id.value.trim(),

          shelter_name:
            form.shelter_name.value.trim(),

          capacity_total:
            Number(
              form.capacity_total.value || 0
            ),

          current_occupancy:
            Number(
              form.current_occupancy.value || 0
            ),

          families_count:
            Number(
              form.families_count.value || 0
            ),

          children_count:
            Number(
              form.children_count.value || 0
            ),

          elderly_count:
            Number(
              form.elderly_count.value || 0
            ),

          disability_count:
            Number(
              form.disabled_count.value || 0
            )
        },
        {
          method: "POST"
        }
      );

      statusMsg(
        "Shelter occupancy saved."
      );

      await loadShelter();
    }
  );
}

function setupNeedForm() {
  const form =
    document.getElementById(
      "needForm"
    );

  if (!form) return;

  form.addEventListener(
    "submit",
    async e => {
      e.preventDefault();

      await RN_FRAPPE.call(
        "rescue_net.api_shelter.create_need",
        {
          posko:
            getShelterPoskoId(),

          item_name:
            form.item_name.value.trim(),

          quantity_mode:
            "known",

          quantity_needed:
            Number(
              form.quantity_needed.value || 0
            ),

          unit:
            form.unit.value.trim(),

          priority:
            form.priority.value,

          needed_before:
            form.needed_before.value.trim(),

          notes:
            form.notes.value.trim()
        },
        {
          method: "POST"
        }
      );

      statusMsg(
        "Shelter need saved."
      );

      await loadShelter();
    }
  );
}

document.addEventListener(
  "DOMContentLoaded",
  () => {
    if (!window.RN_FRAPPE) {
      statusMsg(
        "Frappe client tidak tersedia."
      );
      return;
    }

    setupOccupancyForm();
    setupNeedForm();

    const btn =
      document.getElementById(
        "refreshShelter"
      );

    if (btn) {
      btn.addEventListener(
        "click",
        () =>
          loadShelter()
            .catch(
              err =>
                statusMsg(err.message)
            )
      );
    }

    loadShelter().catch(
      err =>
        statusMsg(err.message)
    );
  }
);
