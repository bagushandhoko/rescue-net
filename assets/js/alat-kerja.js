const RN_API_BASE = "http://192.168.100.32:8092";
const DISASTER_ID = "event-aceh-2025";

function safe(v) {
  return v === null || v === undefined || v === "" ? "n/a" : v;
}

function statusMsg(msg) {
  const el = document.getElementById("workToolStatus");
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
  const el = document.getElementById("workToolSummary");
  if (!el) return;

  el.innerHTML = `
    <div><span>Total Request</span><b>${summary.request_count || 0}</b></div>
    <div><span>Open</span><b>${summary.open_count || 0}</b></div>
    <div><span>Urgent/Critical</span><b>${summary.urgent_count || 0}</b></div>
  `;
}

function renderRequests(items) {
  const el = document.getElementById("workToolRequests");
  if (!el) return;

  el.innerHTML = items.length ? items.map(r => card(
    `${safe(r.tool_name)} · ${safe(r.quantity)} ${safe(r.unit)}`,
    `Type: ${safe(r.tool_type)}<br>
     Location: ${safe(r.location)}<br>
     Needed for: ${safe(r.needed_for)}<br>
     Required operator skill: ${safe(r.required_operator_skill)}<br>
     Requested by: ${safe(r.requested_by_type)} · ${safe(r.requested_by_id)}<br>
     Notes: ${safe(r.notes)}`,
    `${safe(r.priority)} · ${safe(r.status)}`
  )).join("") : card("Belum ada request alat kerja", "Tambahkan kebutuhan alat kerja/heavy equipment.", "empty");
}

async function loadWorkTools() {
  statusMsg("Loading Alat Kerja context...");
  const ctx = await api(`/work-tools-context/${DISASTER_ID}`);

  renderSummary(ctx.summary || {});
  renderRequests(ctx.work_tool_requests || []);

  statusMsg("Loaded: " + ctx.generated_at);
}

function setupForm() {
  const form = document.getElementById("workToolForm");
  if (!form) return;

  form.addEventListener("submit", async e => {
    e.preventDefault();

    const payload = {
      disaster_event_id: DISASTER_ID,
      requested_by_type: form.requested_by_type.value || "posko",
      requested_by_id: form.requested_by_id.value.trim(),
      tool_name: form.tool_name.value.trim(),
      tool_type: form.tool_type.value.trim(),
      quantity: Number(form.quantity.value || 1),
      unit: form.unit.value.trim() || "unit",
      location: form.location.value.trim(),
      needed_for: form.needed_for.value.trim(),
      priority: form.priority.value || "normal",
      required_operator_skill: form.required_operator_skill.value.trim(),
      notes: form.notes.value.trim(),
      created_by_user_id: "worktool-operator"
    };

    statusMsg("Saving work tool request...");
    await api("/work-tool-requests", {
      method: "POST",
      body: JSON.stringify(payload)
    });

    form.reset();
    statusMsg("Work tool request saved.");
    await loadWorkTools();
  });
}

document.addEventListener("DOMContentLoaded", () => {
  setupForm();

  const btn = document.getElementById("refreshWorkTools");
  if (btn) btn.addEventListener("click", () => loadWorkTools().catch(err => statusMsg(err.message)));

  loadWorkTools().catch(err => statusMsg(err.message));
});
