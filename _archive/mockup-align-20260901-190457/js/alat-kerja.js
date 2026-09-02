const DISASTER_ID =
  new URLSearchParams(
    location.search
  ).get("event") ||
  "event-sim-001";


function safe(v) {
  return (
    v === null ||
    v === undefined ||
    v === ""
  )
    ? "n/a"
    : v;
}


function statusMsg(msg) {
  const el =
    document.getElementById(
      "workToolStatus"
    );

  if (el) {
    el.textContent = msg;
  }
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


function renderSummary(ctx) {
  const el =
    document.getElementById(
      "workToolSummary"
    );

  if (!el) return;

  const requests =
    ctx.requests || [];

  const resources =
    ctx.resources || [];

  const deployments =
    ctx.deployments || [];

  el.innerHTML = `
    <div>
      <span>Requests</span>
      <b>${requests.length}</b>
    </div>

    <div>
      <span>Resources</span>
      <b>${resources.length}</b>
    </div>

    <div>
      <span>Deployments</span>
      <b>${deployments.length}</b>
    </div>
  `;
}


function renderRequests(items) {
  const el =
    document.getElementById(
      "workToolRequests"
    );

  if (!el) return;

  el.innerHTML =
    items.length
      ? items.map(r => card(
          r.tool_name,
          `${safe(r.quantity)} ${safe(r.unit)}<br>` +
          `Location: ${safe(r.location)}<br>` +
          `Needed for: ${safe(r.needed_for)}<br>` +
          `Requested by: ${safe(r.requested_by_type)} / ` +
          `${safe(r.requested_by_id)}`,
          r.request_status ||
          r.priority
        )).join("")
      : card(
          "Belum ada Work Tool Request",
          "Belum ada permintaan alat kerja.",
          "empty"
        );
}


async function loadWorkTools() {
  statusMsg(
    "Loading Resource Tools..."
  );

  const ctx =
    await RN_FRAPPE.call(
      "rescue_net.api_resource_tools.dashboard",
      {
        disaster_event:
          DISASTER_ID
      }
    );

  renderSummary(ctx);
  renderRequests(
    ctx.requests || []
  );

  statusMsg(
    "Loaded from Frappe"
  );
}


function setupForm() {
  const form =
    document.getElementById(
      "workToolForm"
    );

  if (!form) return;

  form.addEventListener(
    "submit",
    async e => {
      e.preventDefault();

      await RN_FRAPPE.call(
        "rescue_net.api_resource_tools." +
        "create_work_tool_request",
        {
          disaster_event:
            DISASTER_ID,

          requested_by_type:
            form.requested_by_type.value ||
            "posko",

          requested_by_id:
            form.requested_by_id.value
              .trim(),

          tool_name:
            form.tool_name.value.trim(),

          tool_type:
            form.tool_type.value.trim(),

          quantity:
            Number(
              form.quantity.value || 1
            ),

          unit:
            form.unit.value.trim() ||
            "unit",

          location:
            form.location.value.trim(),

          needed_for:
            form.needed_for.value.trim(),

          priority:
            form.priority.value ||
            "normal",

          required_operator_skill:
            form.required_operator_skill
              .value
              .trim(),

          notes:
            form.notes.value.trim()
        },
        {
          method: "POST"
        }
      );

      statusMsg(
        "Work Tool Request saved."
      );

      form.reset();

      await loadWorkTools();
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

    setupForm();

    const btn =
      document.getElementById(
        "refreshWorkTools"
      );

    if (btn) {
      btn.addEventListener(
        "click",
        () =>
          loadWorkTools().catch(
            err =>
              statusMsg(err.message)
          )
      );
    }

    loadWorkTools().catch(
      err =>
        statusMsg(err.message)
    );
  }
);
