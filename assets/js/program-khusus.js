const RN_API_BASE = window.RN_API_BASE || "http://192.168.100.32:8092";

function getEventId() {
  const params = new URLSearchParams(window.location.search);
  return params.get("event") || params.get("id") || "event-sim-001";
}

function safe(v) {
  return v === null || v === undefined || v === "" ? "n/a" : v;
}

function rupiah(n) {
  return new Intl.NumberFormat("id-ID", { maximumFractionDigits: 0 }).format(Number(n || 0));
}

function setText(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

function evidenceLink(objectType, objectId, label = "Add Evidence") {
  if (!objectId || objectId === "n/a") return "";
  const eventId = encodeURIComponent(getEventId());
  return `<br><a href="evidence.html?event=${eventId}&object_type=${encodeURIComponent(objectType)}&object_id=${encodeURIComponent(objectId)}">${label}</a>`;
}

async function api(path, options = {}) {
  const res = await fetch(RN_API_BASE + path, {
    headers: { "Content-Type": "application/json" },
    ...options
  });
  if (!res.ok) throw new Error(await res.text());
  return await res.json();
}

function programCard(p) {
  const target = p.target_amount || p.budget_target || 0;
  const current = p.current_amount || p.budget_received || 0;

  return `
    <article class="event-card">
      <div class="event-main">
        <div>
          <h4>${safe(p.program_name)}</h4>
          <p>
            ${safe(p.program_type)} · ${safe(p.status)}<br>
            Target: Rp ${rupiah(target)} · Current: Rp ${rupiah(current)}<br>
            Owner: ${safe(p.owner_id)}<br>
            ID: ${safe(p.id)}${evidenceLink("donor_program", p.id)}
          </p>
        </div>
        <div class="chips">
          <span class="chip warning">${safe(p.status)}</span>
        </div>
      </div>
    </article>
  `;
}

async function loadPrograms() {
  const eventId = getEventId();
  setText("programStatus", "Loading programs...");

  const programs = await api(`/donor-programs?disaster_event_id=${encodeURIComponent(eventId)}`);

  const target = document.getElementById("programList");
  target.innerHTML = programs.length
    ? programs.map(programCard).join("")
    : `<article class="event-card"><h4>Belum ada program</h4><p>Buat program khusus pertama untuk bencana ini.</p></article>`;

  const totalTarget = programs.reduce((s, p) => s + Number(p.target_amount || p.budget_target || 0), 0);
  const totalCurrent = programs.reduce((s, p) => s + Number(p.current_amount || p.budget_received || 0), 0);

  setText("kpiPrograms", programs.length);
  setText("kpiBudgetTarget", rupiah(totalTarget));
  setText("kpiBudgetReceived", rupiah(totalCurrent));
  setText("programStatus", `Loaded ${programs.length} program(s).`);
}

function setupProgramForm() {
  const form = document.getElementById("programForm");
  if (!form) return;

  form.addEventListener("submit", async e => {
    e.preventDefault();

    const payload = {
      disaster_event_id: getEventId(),
      owner_type: "organization",
      owner_id: form.owner_id.value.trim(),
      program_name: form.program_name.value.trim(),
      program_type: form.program_type.value.trim(),
      target_description: form.target_description.value.trim(),
      target_amount: Number(form.target_amount.value || 0),
      target_unit: "IDR",
      current_amount: 0,
      status: "active",
      notes: form.notes.value.trim(),
      created_by_user_id: "program-operator"
    };

    try {
      setText("programStatus", "Saving program...");
      await api("/donor-programs", {
        method: "POST",
        body: JSON.stringify(payload)
      });
      await loadPrograms();
    } catch (err) {
      setText("programStatus", err.message);
    }
  });
}

function setupUpdateForm() {
  const form = document.getElementById("programUpdateForm");
  if (!form) return;

  form.addEventListener("submit", async e => {
    e.preventDefault();

    const payload = {
      program_id: form.program_id.value.trim(),
      disaster_event_id: getEventId(),
      update_type: form.update_type.value.trim(),
      progress_percent: Number(form.progress_percent.value || 0),
      amount_spent: Number(form.amount_spent.value || 0),
      update_title: form.update_title.value.trim(),
      update_notes: form.update_notes.value.trim()
    };

    try {
      setText("programStatus", "Saving program update...");
      await api("/donor-program-updates", {
        method: "POST",
        body: JSON.stringify(payload)
      });
      await loadPrograms();
    } catch (err) {
      setText("programStatus", err.message);
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  setupProgramForm();
  setupUpdateForm();

  const refresh = document.getElementById("refreshPrograms");
  if (refresh) refresh.addEventListener("click", () => loadPrograms().catch(err => setText("programStatus", err.message)));

  loadPrograms().catch(err => setText("programStatus", err.message));
});
