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

function evidenceLink(objectType, objectId, label = "Add Evidence") {
  if (!objectId || objectId === "n/a") return "";
  const eventId = encodeURIComponent(getEventId());
  return `<br><a href="evidence.html?event=${eventId}&object_type=${encodeURIComponent(objectType)}&object_id=${encodeURIComponent(objectId)}">${label}</a>`;
}

async function api(path, options = {}) {
  const method =
    String(
      options.method || "GET"
    ).toUpperCase();

  let body = {};

  if (options.body) {
    body =
      typeof options.body === "string"
        ? JSON.parse(options.body)
        : options.body;
  }

  const url =
    new URL(
      path,
      location.origin
    );

  if (
    url.pathname ===
      "/recovery-projects" &&
    method === "GET"
  ) {
    const disasterEventId =
      url.searchParams.get(
        "disaster_event_id"
      );

    const status =
      url.searchParams.get(
        "status"
      );

    return await RN_FRAPPE.call(
      "rescue_net.api_recovery.list_projects",
      {
        disaster_event_id:
          disasterEventId || null,

        status:
          status || null
      }
    );
  }

  if (
    url.pathname ===
      "/recovery-projects" &&
    method === "POST"
  ) {
    return await RN_FRAPPE.call(
      "rescue_net.api_recovery.create_project",
      {
        disaster_event_id:
          body.disaster_event_id,

        project_name:
          body.project_name,

        project_type:
          body.project_type || null,

        owner_type:
          body.owner_type || null,

        owner_id:
          body.owner_id || null,

        target_description:
          body.target_description || null,

        location:
          body.location || null,

        priority:
          body.priority || null,

        target_amount:
          Number(
            body.target_amount || 0
          ),

        current_amount:
          Number(
            body.current_amount || 0
          ),

        progress_percent:
          Number(
            body.progress_percent || 0
          ),

        status:
          body.status || null,

        start_date:
          body.start_date || null,

        target_finish_date:
          body.target_finish_date || null,

        pic_name:
          body.pic_name || null,

        pic_phone:
          body.pic_phone || null,

        notes:
          body.notes || null
      },
      {
        method: "POST"
      }
    );
  }

  throw new Error(
    "Unsupported Recovery route after "
    + "Frappe cutover: "
    + method
    + " "
    + url.pathname
  );
}


function card(p) {
  return `
    <article class="event-card">
      <div class="event-main">
        <div>
          <h4>${safe(p.project_name)}</h4>
          <p>
            ${safe(p.project_type)} · ${safe(p.status)} · ${safe(p.priority)}<br>
            Progress: ${safe(p.progress_percent)}%<br>
            Target: Rp ${money(p.target_amount)} · Current/Spent: Rp ${money(p.current_amount)}<br>
            Location: ${safe(p.location)}<br>
            PIC: ${safe(p.pic_name)} / ${safe(p.pic_phone)}<br>
            ${safe(p.target_description || p.notes)}<br>
            ID: ${safe(p.id)}${evidenceLink("recovery_project", p.id)}
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

  const projects = await api(`/recovery-projects?disaster_event_id=${encodeURIComponent(eventId)}`);

  const totalTarget = projects.reduce((s, p) => s + Number(p.target_amount || 0), 0);
  const totalCurrent = projects.reduce((s, p) => s + Number(p.current_amount || 0), 0);

  setText("kpiProjects", projects.length);
  setText("kpiTarget", money(totalTarget));
  setText("kpiCurrent", money(totalCurrent));
  setText("kpiUpdates", "-");

  document.getElementById("recoveryList").innerHTML = projects.length
    ? projects.map(card).join("")
    : `<article class="event-card"><h4>Belum ada recovery project</h4><p>Buat project recovery pertama untuk event ini.</p></article>`;

  setText("recoveryStatus", `Loaded ${projects.length} recovery project(s).`);
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
      project_name: form.program_name.value.trim(),
      project_type: "recovery_reconstruction",
      target_description: form.target_description.value.trim(),
      target_amount: Number(form.target_amount.value || 0),
      current_amount: 0,
      progress_percent: 0,
      status: "planned",
      priority: "urgent",
      notes: form.notes.value.trim(),
      created_by_user_id: "recovery-operator"
    };

    try {
      setText("recoveryStatus", "Saving recovery project...");
      await api("/recovery-projects", {
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
