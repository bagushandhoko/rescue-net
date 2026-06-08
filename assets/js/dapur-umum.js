const RN_API_BASE = "http://192.168.100.32:8092";
let KITCHEN_CONTEXT_CACHE = null;

function getKitchenPoskoId() {
  const params = new URLSearchParams(window.location.search);
  return params.get("id") || "posko-dapur-melati";
}

function statusMsg(msg) {
  const el = document.getElementById("kitchenStatus");
  if (el) el.textContent = msg;
}

async function api(path, options = {}) {
  const res = await fetch(RN_API_BASE + path, {
    headers: { "Content-Type": "application/json" },
    ...options
  });
  if (!res.ok) throw new Error(await res.text());
  return await res.json();
}

function safe(v) {
  return v === null || v === undefined || v === "" ? "n/a" : v;
}

function card(title, body, chip = "") {
  return `
    <article class="event-card">
      <div class="event-main">
        <div>
          <h4>${title}</h4>
          <p>${body}</p>
        </div>
        <div class="chips">
          ${chip ? `<span class="chip warning">${chip}</span>` : ""}
        </div>
      </div>
    </article>
  `;
}

function renderStock(items) {
  const el = document.getElementById("kitchenStock");
  el.innerHTML = items.length ? items.map(s => card(
    s.item_name,
    `Current stock: <b>${s.current_quantity}</b> ${s.unit}`,
    s.unit
  )).join("") : card("Belum ada stok", "Transfer bahan dari Posko Logistik dulu.", "empty");
}

function renderMeals(items) {
  const el = document.getElementById("mealProductions");
  el.innerHTML = items.length ? items.map(m => card(
    m.meal_name,
    `Portions: ${safe(m.portions)}<br>Target: ${safe(m.target_distribution_location)}<br>Time: ${safe(m.production_time)}<br>${safe(m.notes)}`,
    m.status
  )).join("") : card("Belum ada produksi makanan", "Catat produksi makanan pertama.", "empty");
}

function renderMovements(items) {
  const el = document.getElementById("kitchenMovements");
  el.innerHTML = items.length ? items.map(m => card(
    m.item_name,
    `${m.movement_type} · ${m.movement_direction}<br>${m.quantity} ${m.unit}<br>${safe(m.notes)}`,
    m.created_at ? m.created_at.slice(0, 16).replace("T", " ") : m.id
  )).join("") : card("Belum ada movement", "Belum ada pergerakan stok dapur.", "empty");
}

async function loadKitchen() {
  const poskoId = getKitchenPoskoId();
  statusMsg("Loading kitchen context...");

  const ctx = await api(`/kitchen-context/${poskoId}`);
  KITCHEN_CONTEXT_CACHE = ctx;

  const posko = ctx.posko_context?.posko || {};
  const stock = ctx.posko_context?.stock_summary || [];
  const movements = ctx.posko_context?.stock_movements || [];
  const meals = ctx.meal_productions || [];

  document.getElementById("kitchenTitle").textContent = posko.name || poskoId;
  document.getElementById("kitchenSubtitle").textContent = `${safe(posko.location)} · ${safe(posko.node_type)} · ${safe(posko.operational_status)}`;

  document.getElementById("kpiPosko").textContent = safe(posko.node_type);
  document.getElementById("kpiStock").textContent = stock.length;
  document.getElementById("kpiMeals").textContent = meals.length;
  document.getElementById("kpiUpdate").textContent = ctx.generated_at ? ctx.generated_at.slice(11, 16) : "-";

  renderStock(stock);
  renderMeals(meals);
  renderMovements(movements);

  const form = document.getElementById("mealForm");
  if (form && form.posko_id) form.posko_id.value = poskoId;

  statusMsg("Loaded: " + ctx.generated_at);
}

function setupMealForm() {
  const form = document.getElementById("mealForm");
  if (!form) return;

  form.addEventListener("submit", async e => {
    e.preventDefault();

    if (!KITCHEN_CONTEXT_CACHE) {
      await loadKitchen();
    }

    const posko = KITCHEN_CONTEXT_CACHE.posko_context.posko;

    const payload = {
      disaster_event_id: posko.disaster_event_id,
      posko_id: form.posko_id.value.trim(),
      meal_name: form.meal_name.value.trim(),
      portions: Number(form.portions.value || 0),
      production_time: form.production_time.value.trim(),
      target_distribution_location: form.target_distribution_location.value.trim(),
      ingredients: [
        {
          item_name: form.ingredient_item_name.value.trim(),
          quantity: Number(form.ingredient_quantity.value || 0),
          unit: form.ingredient_unit.value.trim()
        }
      ],
      notes: form.notes.value.trim(),
      created_by_user_id: "kitchen-operator"
    };

    statusMsg("Saving meal production...");
    await api("/kitchen-meal-production", {
      method: "POST",
      body: JSON.stringify(payload)
    });

    statusMsg("Meal production saved.");
    await loadKitchen();
  });
}

document.addEventListener("DOMContentLoaded", () => {
  setupMealForm();

  const btn = document.getElementById("refreshKitchen");
  if (btn) btn.addEventListener("click", () => loadKitchen().catch(err => statusMsg(err.message)));

  loadKitchen().catch(err => statusMsg(err.message));
});
