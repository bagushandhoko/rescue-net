const RN_API_BASE = "http://192.168.100.32:8092";
const DISASTER_ID = "event-aceh-2025";

let RELAWAN_CONTEXT = null;

function safe(v) {
  return v === null || v === undefined || v === "" ? "n/a" : v;
}

function statusMsg(msg) {
  const el = document.querySelector("[data-relawan-status]") || document.getElementById("relawanStatus");
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
  const target = document.querySelector("[data-relawan-summary]") || document.getElementById("relawanSummary");
  if (!target) return;

  target.innerHTML = `
    <div><span>Total Relawan</span><b>${summary.volunteer_count || 0}</b></div>
    <div><span>Available</span><b>${summary.available_count || 0}</b></div>
    <div><span>Assignments</span><b>${summary.assignment_count || 0}</b></div>
  `;
}

function renderVolunteers(items) {
  const target = document.querySelector("[data-relawan-list]") || document.getElementById("relawanList");
  if (!target) return;

  target.innerHTML = items.length ? items.map(v => card(
    `${safe(v.volunteer_name)}`,
    `Contact: ${safe(v.contact)}<br>Skills: ${safe(v.skill_tags)}<br>Location: ${safe(v.current_location)}<br>Assigned Posko: ${safe(v.assigned_posko_id)}<br>Notes: ${safe(v.notes)}`,
    v.availability_status
  )).join("") : card("Belum ada relawan", "Tambahkan relawan baru untuk bencana ini.", "empty");
}

function renderAssignments(items) {
  const target = document.querySelector("[data-relawan-assignments]") || document.getElementById("relawanAssignments");
  if (!target) return;

  target.innerHTML = items.length ? items.map(a => card(
    `${safe(a.task_name)}`,
    `Volunteer: ${safe(a.volunteer_name || a.volunteer_id)}<br>Assigned to: ${safe(a.assigned_to_type)} · ${safe(a.assigned_to_id)}<br>Description: ${safe(a.task_description)}`,
    a.status || a.priority
  )).join("") : card("Belum ada assignment", "Assign relawan ke posko atau tugas.", "empty");
}

function fillVolunteerSelect(items) {
  const select = document.querySelector("[name='volunteer_id']");
  if (!select) return;

  select.innerHTML = items.map(v => `
    <option value="${v.id}">${safe(v.volunteer_name)} · ${safe(v.availability_status)}</option>
  `).join("");
}

async function loadRelawan() {
  statusMsg("Loading relawan context...");
  const ctx = await api(`/volunteer-context/${DISASTER_ID}`);
  RELAWAN_CONTEXT = ctx;

  renderSummary(ctx.summary || {});
  renderVolunteers(ctx.volunteers || []);
  renderAssignments(ctx.assignments || []);
  fillVolunteerSelect(ctx.volunteers || []);

  statusMsg("Loaded: " + ctx.generated_at);
}

function setupVolunteerForm() {
  const form = document.querySelector("[data-create-relawan]") || document.getElementById("relawanForm");
  if (!form) return;

  form.addEventListener("submit", async e => {
    e.preventDefault();

    const payload = {
      disaster_event_id: DISASTER_ID,
      volunteer_name: form.volunteer_name.value.trim(),
      contact: form.contact.value.trim(),
      skill_tags: form.skill_tags.value.trim(),
      availability_status: form.availability_status.value || "available",
      current_location: form.current_location.value.trim(),
      assigned_posko_id: form.assigned_posko_id.value.trim() || null,
      notes: form.notes.value.trim()
    };

    statusMsg("Saving volunteer...");
    await api("/volunteers", {
      method: "POST",
      body: JSON.stringify(payload)
    });

    form.reset();
    statusMsg("Volunteer saved.");
    await loadRelawan();
  });
}

function setupAssignmentForm() {
  const form = document.querySelector("[data-create-relawan-assignment]") || document.getElementById("assignmentForm");
  if (!form) return;

  form.addEventListener("submit", async e => {
    e.preventDefault();

    const payload = {
      disaster_event_id: DISASTER_ID,
      volunteer_id: form.volunteer_id.value,
      assigned_to_type: form.assigned_to_type.value || "posko",
      assigned_to_id: form.assigned_to_id.value.trim(),
      task_name: form.task_name.value.trim(),
      task_description: form.task_description.value.trim(),
      priority: form.priority.value || "normal",
      created_by_user_id: "volunteer-operator"
    };

    statusMsg("Saving assignment...");
    await api("/volunteer-assignments", {
      method: "POST",
      body: JSON.stringify(payload)
    });

    form.reset();
    statusMsg("Assignment saved.");
    await loadRelawan();
  });
}

document.addEventListener("DOMContentLoaded", () => {
  setupVolunteerForm();
  setupAssignmentForm();

  const btn = document.querySelector("[data-refresh-relawan]") || document.getElementById("refreshRelawan");
  if (btn) btn.addEventListener("click", () => loadRelawan().catch(err => statusMsg(err.message)));

  loadRelawan().catch(err => statusMsg(err.message));
});
