const RN_API_BASE = "http://192.168.100.32:8092";
let MEDICAL_CONTEXT_CACHE = null;

function getMedicalPoskoId() {
  const params = new URLSearchParams(window.location.search);
  return params.get("id") || "posko-medis-aceh";
}

function statusMsg(msg) {
  const el = document.getElementById("medicalStatus");
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

function evidenceLink(objectType, objectId, label = "Add Evidence") {
  if (!objectId) return "";
  const eventId = MEDICAL_CONTEXT_CACHE?.posko?.disaster_event_id || "event-aceh-2025";
  return `<br><a href="evidence.html?event=${encodeURIComponent(eventId)}&object_type=${encodeURIComponent(objectType)}&object_id=${encodeURIComponent(objectId)}&node_id=${encodeURIComponent(getMedicalPoskoId())}">${label}</a>`;
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
  const el = document.getElementById("medicalStock");
  el.innerHTML = items.length ? items.map(s => card(
    s.item_name,
    `Current stock: <b>${s.current_quantity}</b> ${s.unit}`,
    s.unit
  )).join("") : card("Belum ada stok medis", "Tambahkan stok obat/alat medis dulu.", "empty");
}

function renderCases(items) {
  const el = document.getElementById("medicalCases");
  el.innerHTML = items.length ? items.map(c => card(
    c.patient_code,
    `Complaint: ${safe(c.complaint)}<br>Severity: ${safe(c.severity)} · Triage: ${safe(c.triage_status)}<br>Treatment: ${safe(c.treatment_notes)}<br>Case ID: ${c.id}${evidenceLink("medical_case", c.id)}`,
    c.status
  )).join("") : card("Belum ada kasus medis", "Catat kasus medis pertama.", "empty");
}

function renderUses(items) {
  const el = document.getElementById("medicalUses");
  el.innerHTML = items.length ? items.map(u => card(
    u.item_name,
    `${u.quantity} ${u.unit}<br>Case: ${safe(u.medical_case_id)}<br>${safe(u.notes)}${evidenceLink("medical_supply_use", u.id)}`,
    u.id
  )).join("") : card("Belum ada pemakaian medis", "Belum ada obat/alat dipakai.", "empty");
}

function renderMovements(items) {
  const el = document.getElementById("medicalMovements");
  el.innerHTML = items.length ? items.map(m => card(
    m.item_name,
    `${m.movement_type} · ${m.movement_direction}<br>${m.quantity} ${m.unit}<br>${safe(m.notes)}${evidenceLink("stock_movement", m.id)}`,
    m.created_at ? m.created_at.slice(0, 16).replace("T", " ") : m.id
  )).join("") : card("Belum ada movement", "Belum ada pergerakan stok medis.", "empty");
}

async function loadMedical() {
  const poskoId = getMedicalPoskoId();
  statusMsg("Loading medical context...");

  const ctx = await api(`/medical-context/${poskoId}`);
  MEDICAL_CONTEXT_CACHE = ctx;

  const posko = ctx.posko || {};
  const stock = ctx.stock_summary || [];
  const cases = ctx.medical_cases || [];
  const uses = ctx.medical_supply_uses || [];
  const movements = ctx.stock_movements || [];

  document.getElementById("medicalTitle").textContent = posko.name || poskoId;
  document.getElementById("medicalSubtitle").textContent = `${safe(posko.location)} · ${safe(posko.node_type)} · ${safe(posko.operational_status)}`;

  document.getElementById("kpiPosko").textContent = safe(posko.node_type);
  document.getElementById("kpiStock").textContent = stock.length;
  document.getElementById("kpiCases").textContent = cases.length;
  document.getElementById("kpiUses").textContent = uses.length;

  renderStock(stock);
  renderCases(cases);
  renderUses(uses);
  renderMovements(movements);

  const caseForm = document.getElementById("caseForm");
  const useForm = document.getElementById("supplyUseForm");
  if (caseForm && caseForm.posko_id) caseForm.posko_id.value = poskoId;

  if (useForm && uses.length === 0 && cases.length > 0) {
    useForm.medical_case_id.value = cases[0].id;
  }

  statusMsg("Loaded: " + ctx.generated_at);
}

function setupCaseForm() {
  const form = document.getElementById("caseForm");
  if (!form) return;

  form.addEventListener("submit", async e => {
    e.preventDefault();

    if (!MEDICAL_CONTEXT_CACHE) {
      await loadMedical();
    }

    const posko = MEDICAL_CONTEXT_CACHE.posko;

    const payload = {
      disaster_event_id: posko.disaster_event_id,
      posko_id: form.posko_id.value.trim(),
      patient_code: form.patient_code.value.trim(),
      age_group: form.age_group.value.trim(),
      gender: form.gender.value.trim(),
      complaint: form.complaint.value.trim(),
      severity: form.severity.value,
      triage_status: form.triage_status.value,
      treatment_notes: form.treatment_notes.value.trim(),
      referral_needed: false,
      status: "treated",
      created_by_user_id: "medical-operator"
    };

    statusMsg("Saving medical case...");
    const created = await api("/medical-cases", {
      method: "POST",
      body: JSON.stringify(payload)
    });

    const useForm = document.getElementById("supplyUseForm");
    if (useForm) useForm.medical_case_id.value = created.id;

    statusMsg("Medical case saved.");
    await loadMedical();
  });
}

function setupSupplyUseForm() {
  const form = document.getElementById("supplyUseForm");
  if (!form) return;

  form.addEventListener("submit", async e => {
    e.preventDefault();

    if (!MEDICAL_CONTEXT_CACHE) {
      await loadMedical();
    }

    const posko = MEDICAL_CONTEXT_CACHE.posko;

    const payload = {
      disaster_event_id: posko.disaster_event_id,
      posko_id: getMedicalPoskoId(),
      medical_case_id: form.medical_case_id.value.trim() || null,
      item_name: form.item_name.value.trim(),
      quantity: Number(form.quantity.value || 0),
      unit: form.unit.value.trim(),
      notes: form.notes.value.trim(),
      created_by_user_id: "medical-operator"
    };

    statusMsg("Saving medical supply use...");
    await api("/medical-supply-use", {
      method: "POST",
      body: JSON.stringify(payload)
    });

    statusMsg("Medical supply use saved.");
    await loadMedical();
  });
}

document.addEventListener("DOMContentLoaded", () => {
  setupCaseForm();
  setupSupplyUseForm();

  const btn = document.getElementById("refreshMedical");
  if (btn) btn.addEventListener("click", () => loadMedical().catch(err => statusMsg(err.message)));

  loadMedical().catch(err => statusMsg(err.message));
});
