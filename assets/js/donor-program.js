const RN_API_BASE = "http://192.168.100.32:8092";
const DISASTER_ID = "event-aceh-2025";

let DONOR_CONTEXT = null;

function safe(v) {
  return v === null || v === undefined || v === "" ? "n/a" : v;
}

function money(v, unit = "IDR") {
  const n = Number(v || 0);
  if (unit === "IDR") return "Rp " + n.toLocaleString("id-ID");
  return n.toLocaleString("id-ID") + " " + unit;
}

function statusMsg(msg) {
  const el = document.getElementById("donorProgramStatus");
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

function renderSummary(summary) {
  const el = document.getElementById("donorProgramSummary");
  if (!el) return;

  el.innerHTML = `
    <div><span>Program</span><b>${summary.program_count || 0}</b></div>
    <div><span>Active</span><b>${summary.active_count || 0}</b></div>
    <div><span>Updates</span><b>${summary.update_count || 0}</b></div>
    <div><span>Target Total</span><b>${money(summary.target_total || 0)}</b></div>
    <div><span>Current Total</span><b>${money(summary.current_total || 0)}</b></div>
    <div><span>Spent/Reported</span><b>${money(summary.spent_total || 0)}</b></div>
  `;
}

function renderPrograms(programs) {
  const el = document.getElementById("donorProgramList");
  if (!el) return;

  el.innerHTML = programs.length ? programs.map(p => {
    const unit = p.target_unit || "IDR";
    const updates = (p.updates || []).slice(0, 5).map(u =>
      `<br>• ${safe(u.update_title)} — ${money(u.amount_used, u.amount_unit)} — ${safe(u.created_at)}`
    ).join("");

    return card(
      safe(p.program_name),
      `Type: ${safe(p.program_type)}<br>
       Owner: ${safe(p.owner_type)} · ${safe(p.owner_id)}<br>
       Target: ${money(p.target_amount, unit)}<br>
       Reported: ${money(p.current_amount, unit)}<br>
       Spent from updates: ${money(p.spent_amount, unit)}<br>
       Location: ${safe(p.location)}<br>
       PIC: ${safe(p.contact_person)} · HP: ${safe(p.contact_phone)}<br>
       Target Description: ${safe(p.target_description)}<br>
       Updates: ${p.update_count || 0}${updates}`,
      safe(p.status)
    );
  }).join("") : card("Belum ada donor program", "Buat program donasi/transparansi baru.", "empty");
}

function fillProgramSelect(programs) {
  const select = document.querySelector("[name='program_id']");
  if (!select) return;

  select.innerHTML = programs.map(p => `
    <option value="${p.id}">${safe(p.program_name)} · ${safe(p.status)}</option>
  `).join("");
}

async function loadDonorPrograms() {
  statusMsg("Loading donor program context...");
  const ctx = await api(`/donor-program-context/${DISASTER_ID}`);
  DONOR_CONTEXT = ctx;

  renderSummary(ctx.summary || {});
  renderPrograms(ctx.programs || []);
  fillProgramSelect(ctx.programs || []);

  statusMsg("Loaded: " + ctx.generated_at);
}

function setupProgramForm() {
  const form = document.getElementById("donorProgramForm");
  if (!form) return;

  form.addEventListener("submit", async e => {
    e.preventDefault();

    const payload = {
      disaster_event_id: DISASTER_ID,
      program_name: form.program_name.value.trim(),
      program_type: form.program_type.value.trim(),
      owner_type: form.owner_type.value,
      owner_id: form.owner_id.value.trim(),
      target_description: form.target_description.value.trim(),
      target_amount: Number(form.target_amount.value || 0),
      target_unit: form.target_unit.value.trim() || "IDR",
      location: form.location.value.trim(),
      contact_person: form.contact_person.value.trim(),
      contact_phone: form.contact_phone.value.trim(),
      notes: form.notes.value.trim(),
      created_by_user_id: "donor-program-operator"
    };

    statusMsg("Saving donor program...");
    await api("/donor-programs", {
      method: "POST",
      body: JSON.stringify(payload)
    });

    form.reset();
    statusMsg("Donor program saved.");
    await loadDonorPrograms();
  });
}

function setupUpdateForm() {
  const form = document.getElementById("donorProgramUpdateForm");
  if (!form) return;

  form.addEventListener("submit", async e => {
    e.preventDefault();

    const payload = {
      program_id: form.program_id.value,
      disaster_event_id: DISASTER_ID,
      update_title: form.update_title.value.trim(),
      update_type: form.update_type.value,
      amount_used: Number(form.amount_used.value || 0),
      amount_unit: form.amount_unit.value.trim() || "IDR",
      description: form.description.value.trim(),
      evidence_file_id: form.evidence_file_id.value.trim() || null,
      created_by_user_id: "donor-program-operator"
    };

    statusMsg("Saving donor program update...");
    await api("/donor-program-updates", {
      method: "POST",
      body: JSON.stringify(payload)
    });

    form.reset();
    statusMsg("Program update saved.");
    await loadDonorPrograms();
  });
}

document.addEventListener("DOMContentLoaded", () => {
  setupProgramForm();
  setupUpdateForm();

  const btn = document.getElementById("refreshDonorPrograms");
  if (btn) btn.addEventListener("click", () => loadDonorPrograms().catch(err => statusMsg(err.message)));

  loadDonorPrograms().catch(err => statusMsg(err.message));
});
