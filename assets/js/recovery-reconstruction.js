const RN_API_BASE = window.RN_API_BASE || "http://192.168.100.32:8092";

function getEventId() {
  const params = new URLSearchParams(window.location.search);
  return params.get("event") || params.get("id") || "event-sim-001";
}

function safe(v) {
  return v === null || v === undefined || v === "" ? "n/a" : v;
}

function money(n) {
  return new Intl.NumberFormat("id-ID", { maximumFractionDigits: 0 }).format(Number(n || 0));
}

function setText(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

async function api(path, options = {}) {
  const res = await fetch(RN_API_BASE + path, {
    headers: { "Content-Type": "application/json" },
    ...options
  });
  if (!res.ok) throw new Error(await res.text());
  return await res.json();
}

function card(p) {
  return `
    <article class="event-card">
      <div class="event-main">
        <div>
          <h4>${safe(p.program_name)}</h4>
          <p>
            ${safe(p.program_type)} · ${safe(p.status)}<br>
            Target: Rp ${money(p.target_amount || p.budget_target)} · Current: Rp ${money(p.current_amount || p.budget_received)}<br>
            ${safe(p.target_description || p.description || p.notes)}<br>
            ID: ${safe(p.id)}
          </p>
        </div>
        <div class="chips"><span class="chip warning">${safe(p.status)}</span></div>
      </div>
    </article>
  `;
}

async function loadRecovery() {
  const eventId = getEventId();
  setText("recoveryStatus", "Loading recovery projects...");

  const programs = await api(`/donor-programs?disaster_event_id=${encodeURIComponent(eventId)}`);
  const recovery = programs.filter(p => {
    const t = String(p.program_type || "").toLowerCase();
    const n = String(p.program_name || "").toLowerCase();
    return t.includes("recovery") || t.includes("reconstruction") || n.includes("jembatan") || n.includes("pemulihan") || n.includes("recovery");
  });

  const totalTarget = recovery.reduce((s, p) => s + Number(p.target_amount || p.budget_target || 0), 0);
  const totalCurrent = recovery.reduce((s, p) => s + Number(p.current_amount || p.budget_received || 0), 0);

  setText("kpiProjects", recovery.length);
  setText("kpiTarget", money(totalTarget));
  setText("kpiCurrent", money(totalCurrent));
  setText("kpiUpdates", "-");

  document.getElementById("recoveryList").innerHTML = recovery.length
    ? recovery.map(card).join("")
    : `<article class="event-card"><h4>Belum ada recovery project</h4><p>Buat project recovery pertama untuk event ini.</p></article>`;

  setText("recoveryStatus", `Loaded ${recovery.length} recovery project(s).`);
}

function setupForm() {
  const form = document.getElementById("recoveryForm");
  if (!form) return;

  form.addEventListener("submit", async e => {
    e.preventDefault();

    const payload = {
      disaster_event_id: getEventId(),
      owner_type: "organization",
      owner_id: "org-sim-bpbd",
      program_name: form.program_name.value.trim(),
      program_type: "recovery_reconstruction",
      target_description: form.target_description.value.trim(),
      target_amount: Number(form.target_amount.value || 0),
      target_unit: "IDR",
      current_amount: 0,
      status: "active",
      notes: form.notes.value.trim(),
      created_by_user_id: "recovery-operator"
    };

    try {
      setText("recoveryStatus", "Saving recovery project...");
      await api("/donor-programs", {
        method: "POST",
        body: JSON.stringify(payload)
      });
      await loadRecovery();
    } catch (err) {
      setText("recoveryStatus", err.message);
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  setupForm();
  const refresh = document.getElementById("refreshRecovery");
  if (refresh) refresh.addEventListener("click", () => loadRecovery().catch(err => setText("recoveryStatus", err.message)));
  loadRecovery().catch(err => setText("recoveryStatus", err.message));
});
