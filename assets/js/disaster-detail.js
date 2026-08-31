function getDisasterId() {
  const params = new URLSearchParams(window.location.search);
  return params.get("id") || "event-aceh-2025";
}


async function rnFetch(path, options = {}) {
  const method =
    String(
      options.method || "GET"
    ).toUpperCase();

  const url =
    new URL(
      path,
      location.origin
    );

  let body = {};

  if (options.body) {
    body =
      typeof options.body === "string"
        ? JSON.parse(options.body)
        : options.body;
  }

  if (
    url.pathname === "/disasters"
    && method === "GET"
  ) {
    return await RN_FRAPPE.call(
      "rescue_net.compat.api.disasters",
      {
        limit: 100
      }
    );
  }

  if (
    url.pathname.startsWith(
      "/ecosystem-members/"
    )
  ) {
    const eventId =
      decodeURIComponent(
        url.pathname.slice(
          "/ecosystem-members/".length
        )
      );

    return await RN_FRAPPE.call(
      "rescue_net.api_frontend_bridge."
      + "disaster_ecosystem_members",
      {
        disaster_event: eventId
      }
    );
  }

  if (
    url.pathname.startsWith(
      "/resources/"
    )
  ) {
    const eventId =
      decodeURIComponent(
        url.pathname.slice(
          "/resources/".length
        )
      );

    return await RN_FRAPPE.call(
      "rescue_net.api_frontend_bridge."
      + "disaster_resources",
      {
        disaster_event: eventId
      }
    );
  }

  if (
    url.pathname === "/resource-requests"
    && method === "GET"
  ) {
    return await RN_FRAPPE.call(
      "rescue_net.api_frontend_bridge."
      + "disaster_resource_requests",
      {
        disaster_event:
          getDisasterId()
      }
    );
  }

  if (
    url.pathname === "/resource-assignments"
  ) {
    return await RN_FRAPPE.call(
      "rescue_net.api_frontend_bridge."
      + "resource_assignments",
      {
        disaster_event:
          getDisasterId()
      }
    );
  }

  if (
    url.pathname.startsWith(
      "/ai/context/"
    )
  ) {
    const eventId =
      decodeURIComponent(
        url.pathname.slice(
          "/ai/context/".length
        )
      );

    return await RN_FRAPPE.call(
      "rescue_net.api_ai.context",
      {
        disaster_event_id:
          eventId
      }
    );
  }

  if (
    url.pathname === "/resource-requests"
    && method === "POST"
  ) {
    return await RN_FRAPPE.call(
      "rescue_net.api_frontend_bridge."
      + "create_resource_request",
      {
        ...body,
        disaster_event:
          getDisasterId()
      },
      {
        method: "POST"
      }
    );
  }

  const approveMatch =
    url.pathname.match(
      /^\/resource-requests\/([^/]+)\/approve$/
    );

  if (
    approveMatch
    && method === "POST"
  ) {
    return await RN_FRAPPE.call(
      "rescue_net.api_frontend_bridge."
      + "approve_resource_request",
      {
        resource_request:
          decodeURIComponent(
            approveMatch[1]
          ),
        assignment_notes:
          body.assignment_notes || null
      },
      {
        method: "POST"
      }
    );
  }

  throw new Error(
    "Unsupported Disaster Detail route: "
    + method
    + " "
    + url.pathname
  );
}


function safe(v) {
  return v === null || v === undefined || v === "" ? "n/a" : v;
}

function chipClass(value) {
  if (value === "official" || value === "official_verified" || value === "critical") return "danger";
  if (value === "trusted" || value === "local_trusted" || value === "urgent" || value === "requested") return "warning";
  return "neutral";
}

function renderOverview(disaster) {
  const target = document.querySelector("[data-disaster-overview]");
  if (!target) return;

  target.innerHTML = `
    <div><span>ID</span><b>${safe(disaster.id)}</b></div>
    <div><span>Name</span><b>${safe(disaster.name)}</b></div>
    <div><span>Type</span><b>${safe(disaster.disaster_type)}</b></div>
    <div><span>Location</span><b>${safe(disaster.location)}</b></div>
    <div><span>Status</span><b>${safe(disaster.status)}</b></div>
    <div><span>Severity</span><b>${safe(disaster.severity)}</b></div>
  `;
}

function renderMembers(items) {
  const target = document.querySelector("[data-eco-members]");
  if (!target) return;

  target.innerHTML = items.length ? items.map(m => `
    <article class="event-card">
      <div class="event-main">
        <div>
          <h4>${m.member_id}</h4>
          <p>${m.member_type} · role: ${m.role_in_disaster}</p>
          <p>verification: ${m.verification_status}</p>
        </div>
        <div class="chips">
          <span class="chip ${chipClass(m.trust_level)}">${m.trust_level}</span>
          <span class="chip neutral">${m.status}</span>
        </div>
      </div>
    </article>
  `).join("") : `<article class="event-card"><h4>Belum ada ecosystem member</h4></article>`;
}

function renderResources(items) {
  const target = document.querySelector("[data-eco-resources]");
  if (!target) return;

  target.innerHTML = items.length ? items.map(r => `
    <article class="event-card">
      <div class="event-main">
        <div>
          <h4>${r.name}</h4>
          <p>${r.resource_type} · owner: ${r.owner_type}/${r.owner_id}</p>
          <p>${r.description || ""}</p>
          <p>location: ${safe(r.location)}</p>
        </div>
        <div class="chips">
          <span class="chip ${chipClass(r.trust_level)}">${r.trust_level}</span>
          <span class="chip neutral">${r.visibility_scope}</span>
          <span class="chip warning">${r.access_policy}</span>
        </div>
      </div>
    </article>
  `).join("") : `<article class="event-card"><h4>Belum ada shared resource</h4></article>`;
}

function renderRequests(items) {
  const target = document.querySelector("[data-eco-requests]");
  if (!target) return;

  target.innerHTML = items.length ? items.map(r => `
    <article class="event-card">
      <div class="event-main">
        <div>
          <h4>${r.resource_name || r.resource_id}</h4>
          <p>requested by: ${r.requested_by_type}/${r.requested_by_id}</p>
          <p>${r.request_reason || ""}</p>
          <p>time: ${safe(r.requested_time)} · approved_by: ${safe(r.approved_by)}</p>
        </div>
        <div class="chips">
          <span class="chip ${chipClass(r.status)}">${r.status}</span>
          <span class="chip neutral">${r.id}</span>
          ${r.status === "requested" ? `<button class="btn primary" type="button" onclick="approveResourceRequest('${r.id}')">Approve</button>` : ""}
        </div>
      </div>
    </article>
  `).join("") : `<article class="event-card"><h4>Belum ada resource request</h4></article>`;
}

function renderAISummary(summary) {
  const target = document.querySelector("[data-ai-summary]");
  if (!target) return;

  target.innerHTML = `
    <div><span>Critical Needs</span><b>${summary.critical_needs ?? 0}</b></div>
    <div><span>Aid Offers</span><b>${summary.total_aid_offers ?? 0}</b></div>
    <div><span>Need Pickup</span><b>${summary.aid_need_pickup ?? 0}</b></div>
    <div><span>Transport Spaces</span><b>${summary.available_transport_spaces ?? 0}</b></div>
    <div><span>Distribution Flows</span><b>${summary.distribution_flows ?? 0}</b></div>
    <div><span>Ecosystem Members</span><b>${summary.ecosystem_members ?? 0}</b></div>
    <div><span>Shared Resources</span><b>${summary.shared_resources ?? 0}</b></div>
    <div><span>Resource Requests</span><b>${summary.resource_requests ?? 0}</b></div>
  `;
}

async function loadDisasterDetail() {
  const disasterId = getDisasterId();
  const status = document.querySelector("[data-detail-status]");

  try {
    if (status) status.textContent = "Loading disaster ecosystem...";

    const [disasters, members, resources, requests, assignments, aiContext] = await Promise.all([
      rnFetch("/disasters"),
      rnFetch(`/ecosystem-members/${disasterId}`),
      rnFetch(`/resources/${disasterId}`),
      rnFetch("/resource-requests"),
      rnFetch("/resource-assignments"),
      rnFetch(`/ai/context/${disasterId}`)
    ]);

    const disaster = disasters.find(d => d.id === disasterId) || aiContext.disaster || { id: disasterId };

    document.querySelector("[data-disaster-title]").textContent = disaster.name || disasterId;
    document.querySelector("[data-disaster-subtitle]").textContent =
      `${safe(disaster.location)} · ${safe(disaster.disaster_type)} · ${safe(disaster.status)}`;

    const severity = document.querySelector("[data-kpi-severity]");
    const membersKpi = document.querySelector("[data-kpi-members]");
    const resourcesKpi = document.querySelector("[data-kpi-resources]");
    const requestsKpi = document.querySelector("[data-kpi-requests]");

    if (severity) severity.textContent = safe(disaster.severity);
    if (membersKpi) membersKpi.textContent = members.length;
    if (resourcesKpi) resourcesKpi.textContent = resources.length;
    if (requestsKpi) requestsKpi.textContent = requests.length;

    renderOverview(disaster);
    renderMembers(members);
    renderResources(resources);
    renderRequests(requests);
    renderAssignments(assignments);
    renderAISummary(aiContext.summary || {});

    if (status) status.textContent = `Loaded ecosystem for ${disasterId}.`;

  } catch (err) {
    if (status) status.textContent = err.message;
  }
}


function renderAssignments(items) {
  const target = document.querySelector("[data-eco-assignments]");
  if (!target) return;

  target.innerHTML = items.length ? items.map(a => `
    <article class="event-card">
      <div class="event-main">
        <div>
          <h4>${a.resource_name || a.resource_id}</h4>
          <p>assigned to: ${a.assigned_to_type}/${a.assigned_to_id}</p>
          <p>assigned by: ${safe(a.assigned_by)} · quantity: ${safe(a.assigned_quantity)}</p>
          <p>${a.assignment_notes || ""}</p>
        </div>
        <div class="chips">
          <span class="chip warning">${a.status}</span>
          <span class="chip neutral">${a.id}</span>
        </div>
      </div>
    </article>
  `).join("") : `<article class="event-card"><h4>Belum ada resource assignment</h4></article>`;
}

async function approveResourceRequest(requestId) {
  const ok = confirm(`Approve resource request ${requestId}?`);
  if (!ok) return;

  await rnFetch(`/resource-requests/${requestId}/approve`, {
    method: "POST",
    body: JSON.stringify({
      approved_by: "command-center",
      assignment_notes: "Disetujui melalui Disaster Detail dashboard.",
      assigned_quantity: 1
    })
  });

  await loadDisasterDetail();
}

function setupRequestForm() {
  const form = document.querySelector("[data-resource-request-form]");
  const msg = document.querySelector("[data-resource-request-message]");
  if (!form) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const payload = {
      resource_id: form.resource_id.value.trim(),
      requested_by_type: form.requested_by_type.value.trim(),
      requested_by_id: form.requested_by_id.value.trim(),
      request_reason: form.request_reason.value.trim(),
      requested_quantity: Number(form.requested_quantity.value || 1),
      requested_time: form.requested_time.value.trim()
    };

    try {
      if (msg) msg.textContent = "Mengirim request...";
      await rnFetch("/resource-requests", {
        method: "POST",
        body: JSON.stringify(payload)
      });
      if (msg) msg.textContent = "Resource request berhasil dibuat.";
      await loadDisasterDetail();
    } catch (err) {
      if (msg) msg.textContent = err.message;
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  loadDisasterDetail();
  setupRequestForm();
});
