let KITCHEN_CONTEXT_CACHE = null;

function getKitchenPoskoId() {
  const params =
    new URLSearchParams(
      window.location.search
    );

  let value =
    params.get("id") ||
    "posko_nodes:posko-sim-dapur";

  value = String(value).trim();

  /*
   * Compatibility bridge:
   * legacy Posko IDs from old frontend navigation
   * are normalized to canonical Frappe RN Posko names.
   */
  if (
    value &&
    !value.includes(":") &&
    value.startsWith("posko-")
  ) {
    value =
      "posko_nodes:" +
      value;
  }

  return value;
}

function statusMsg(msg) {
  const el =
    document.getElementById(
      "kitchenStatus"
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
  )
    ? "n/a"
    : v;
}

function rowId(row) {
  if (!row) {
    return "";
  }

  return (
    row.name ||
    row.id ||
    row.legacy_id ||
    ""
  );
}

function evidenceLink(
  objectType,
  objectId,
  label = "Add Evidence"
) {
  if (!objectId) {
    return "";
  }

  const ctx =
    KITCHEN_CONTEXT_CACHE || {};

  const posko =
    ctx.posko ||
    ctx.posko_context?.posko ||
    {};

  const eventId =
    posko.disaster_event ||
    posko.disaster_event_id ||
    "event-sim-001";

  return (
    `<br><a href="evidence.html?event=${
      encodeURIComponent(eventId)
    }` +
    `&object_type=${
      encodeURIComponent(objectType)
    }` +
    `&object_id=${
      encodeURIComponent(objectId)
    }` +
    `&node_id=${
      encodeURIComponent(
        getKitchenPoskoId()
      )
    }">${label}</a>`
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
          <h4>${title}</h4>
          <p>${body}</p>
        </div>

        <div class="chips">
          ${
            chip
              ? `<span class="chip warning">${chip}</span>`
              : ""
          }
        </div>
      </div>
    </article>
  `;
}

function renderStock(items) {
  const el =
    document.getElementById(
      "kitchenStock"
    );

  if (!el) {
    return;
  }

  el.innerHTML =
    items.length
      ? items.map(s => {
          const qty =
            s.current_quantity ??
            s.quantity ??
            s.effective_quantity ??
            0;

          return card(
            safe(s.item_name),
            `Current stock: <b>${safe(qty)}</b> ${safe(s.unit)}`,
            safe(s.unit)
          );
        }).join("")
      : card(
          "Belum ada stok",
          "Transfer bahan dari Posko Logistik dulu.",
          "empty"
        );
}

function renderMeals(items) {
  const el =
    document.getElementById(
      "mealProductions"
    );

  if (!el) {
    return;
  }

  el.innerHTML =
    items.length
      ? items.map(m => {
          const id = rowId(m);

          return card(
            safe(m.meal_name),
            `Portions: ${safe(m.portions)}<br>` +
            `Target: ${safe(m.target_distribution_location)}<br>` +
            `Time: ${safe(m.production_time)}<br>` +
            `${safe(m.notes)}` +
            evidenceLink(
              "meal_production",
              id
            ),
            safe(
              m.status ||
              m.production_status
            )
          );
        }).join("")
      : card(
          "Belum ada produksi makanan",
          "Catat produksi makanan pertama.",
          "empty"
        );
}

function renderMovements(items) {
  const el =
    document.getElementById(
      "kitchenMovements"
    );

  if (!el) {
    return;
  }

  el.innerHTML =
    items.length
      ? items.map(m => {
          const id = rowId(m);

          const created =
            m.created_at ||
            m.creation ||
            m.observed_at ||
            "";

          return card(
            safe(m.item_name),
            `${safe(m.movement_type)} · ` +
            `${safe(m.movement_direction)}<br>` +
            `${safe(m.quantity)} ${safe(m.unit)}<br>` +
            `${safe(m.notes)}` +
            evidenceLink(
              "stock_movement",
              id
            ),
            created
              ? String(created)
                  .slice(0, 16)
                  .replace("T", " ")
              : safe(id)
          );
        }).join("")
      : card(
          "Belum ada movement",
          "Belum ada pergerakan stok dapur.",
          "empty"
        );
}

function normalizeKitchenContext(
  raw,
  poskoId
) {
  const ctx = raw || {};

  const posko =
    ctx.posko ||
    ctx.posko_context?.posko ||
    {
      name: poskoId
    };

  const stock =
    ctx.stock_summary ||
    ctx.stock ||
    ctx.posko_context?.stock_summary ||
    [];

  const movements =
    ctx.ingredient_usages ||
    ctx.stock_movements ||
    ctx.movements ||
    ctx.posko_context?.stock_movements ||
    [];

  const meals =
    ctx.productions ||
    ctx.meal_productions ||
    ctx.kitchen_meal_productions ||
    [];

  return {
    ...ctx,
    posko,
    stock_summary: stock,
    stock_movements: movements,
    meal_productions: meals
  };
}

async function loadKitchen() {
  const poskoId =
    getKitchenPoskoId();

  statusMsg(
    "Loading kitchen context..."
  );

  const raw =
    await window.RN_FRAPPE.call(
      "rescue_net.api_kitchen.dashboard",
      {
        posko: poskoId
      }
    );

  const ctx =
    normalizeKitchenContext(
      raw,
      poskoId
    );

  KITCHEN_CONTEXT_CACHE =
    ctx;

  const posko =
    ctx.posko || {};

  const stock =
    ctx.stock_summary || [];

  const movements =
    ctx.stock_movements || [];

  const meals =
    ctx.meal_productions || [];

  const title =
    document.getElementById(
      "kitchenTitle"
    );

  const subtitle =
    document.getElementById(
      "kitchenSubtitle"
    );

  if (title) {
    title.textContent =
      posko.posko_name ||
      posko.title ||
      posko.name ||
      poskoId;
  }

  if (subtitle) {
    subtitle.textContent =
      `${safe(posko.location)} · ` +
      `${safe(
        posko.node_type ||
        posko.posko_type
      )} · ` +
      `${safe(
        posko.operational_status
      )}`;
  }

  const kpiPosko =
    document.getElementById(
      "kpiPosko"
    );

  const kpiStock =
    document.getElementById(
      "kpiStock"
    );

  const kpiMeals =
    document.getElementById(
      "kpiMeals"
    );

  const kpiUpdate =
    document.getElementById(
      "kpiUpdate"
    );

  if (kpiPosko) {
    kpiPosko.textContent =
      safe(
        posko.node_type ||
        posko.posko_type
      );
  }

  if (kpiStock) {
    kpiStock.textContent =
      stock.length;
  }

  if (kpiMeals) {
    kpiMeals.textContent =
      meals.length;
  }

  if (kpiUpdate) {
    const generated =
      ctx.generated_at ||
      "";

    kpiUpdate.textContent =
      generated
        ? String(generated)
            .slice(11, 16)
        : "-";
  }

  renderStock(stock);
  renderMeals(meals);
  renderMovements(movements);

  const form =
    document.getElementById(
      "mealForm"
    );

  if (
    form &&
    form.posko_id
  ) {
    form.posko_id.value =
      poskoId;
  }

  statusMsg(
    "Loaded: " +
    safe(ctx.generated_at)
  );
}

function setupMealForm() {
  const form =
    document.getElementById(
      "mealForm"
    );

  if (!form) {
    return;
  }

  form.addEventListener(
    "submit",
    async e => {
      e.preventDefault();

      if (
        !KITCHEN_CONTEXT_CACHE
      ) {
        await loadKitchen();
      }

      const posko =
        KITCHEN_CONTEXT_CACHE
          ?.posko ||
        {};

      const eventId =
        posko.disaster_event ||
        posko.disaster_event_id ||
        null;

      const ingredients = [
        {
          item_name:
            form
              .ingredient_item_name
              .value
              .trim(),

          quantity:
            Number(
              form
                .ingredient_quantity
                .value || 0
            ),

          unit:
            form
              .ingredient_unit
              .value
              .trim()
        }
      ];

      const payload = {
        posko:
          form
            .posko_id
            .value
            .trim(),

        meal_name:
          form
            .meal_name
            .value
            .trim(),

        portions:
          Number(
            form.portions.value || 0
          ),

        ingredients,

        disaster_event:
          eventId,

        production_time:
          form
            .production_time
            .value
            .trim(),

        target_distribution_location:
          form
            .target_distribution_location
            .value
            .trim(),

        notes:
          form
            .notes
            .value
            .trim()
      };

      statusMsg(
        "Saving meal production..."
      );

      await window.RN_FRAPPE.call(
        "rescue_net.api_kitchen." +
        "create_production",
        payload,
        {
          method: "POST"
        }
      );

      statusMsg(
        "Meal production saved."
      );

      form.reset();

      await loadKitchen();
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

    setupMealForm();

    const btn =
      document.getElementById(
        "refreshKitchen"
      );

    if (btn) {
      btn.addEventListener(
        "click",
        () => {
          loadKitchen().catch(
            err =>
              statusMsg(
                err.message
              )
          );
        }
      );
    }

    loadKitchen().catch(
      err =>
        statusMsg(
          err.message
        )
    );
  }
);
