const RN_API_BASE = window.RN_API_BASE || "http://192.168.100.32:8092";

function getEventId() {
  const params = new URLSearchParams(window.location.search);
  return params.get("event") || params.get("id") || "event-sim-001";
}

function safe(v) {
  return v === null || v === undefined || v === "" ? "n/a" : v;
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

function card(title, body, chip = "") {
  return `
    <article class="event-card">
      <div class="event-main">
        <div>
          <h4>${title}</h4>
          <p>${body}</p>
        </div>
        <div class="chips">${chip ? `<span class="chip warning">${chip}</span>` : ""}</div>
      </div>
    </article>
  `;
}

async function loadResourceProfile() {
  const eventId = getEventId();
  setText("resourceStatus", "Loading resource profiles...");

  const [ctx, resources] = await Promise.all([
    api(`/ai/context/${eventId}`),
    api(`/resource-profiles?disaster_event_id=${encodeURIComponent(eventId)}`)
  ]);

  const s = ctx.summary || {};
  const organizations = ctx.organizations || [];
  const poskos = ctx.poskos || [];
  const volunteers = ctx.volunteers || [];

  setText("kpiOrg", safe(s.organization_count || organizations.length));
  setText("kpiPosko", safe(s.posko_count || poskos.length));
  setText("kpiVolunteer", safe(s.volunteer_count || volunteers.length));
  setText("kpiResource", resources.length);

  document.getElementById("organizationList").innerHTML = organizations.length
    ? organizations.slice(0, 12).map(o => card(
        safe(o.name || o.organization_name),
        `Type: ${safe(o.organization_type)}<br>Status: ${safe(o.verification_status || o.status)}<br>ID: ${safe(o.id)}`,
        safe(o.status || "org")
      )).join("")
    : card("No organization data", "Belum ada data organisasi.", "empty");

  document.getElementById("poskoList").innerHTML = poskos.length
    ? poskos.slice(0, 12).map(p => card(
        safe(p.name),
        `Type: ${safe(p.node_type)}<br>Location: ${safe(p.location)}<br>Status: ${safe(p.operational_status || p.status)}<br>ID: ${safe(p.id)}`,
        safe(p.node_type)
      )).join("")
    : card("No posko data", "Belum ada data posko.", "empty");

  document.getElementById("volunteerList").innerHTML = volunteers.length
    ? volunteers.slice(0, 12).map(v => card(
        safe(v.name || v.full_name),
        `Skill: ${safe(v.skill || v.skills)}<br>Status: ${safe(v.status || v.availability_status)}<br>ID: ${safe(v.id)}`,
        "volunteer"
      )).join("")
    : card("No volunteer data", "Belum ada data relawan.", "empty");

  document.getElementById("resourceList").innerHTML = resources.length
    ? resources.slice(0, 20).map(r => card(
        safe(r.resource_name),
        `Type: ${safe(r.resource_type)} · ${safe(r.category)}<br>` +
        `Qty: ${safe(r.quantity)} ${safe(r.unit)}<br>` +
        `Status: ${safe(r.availability_status)}<br>` +
        `Location: ${safe(r.current_location)}<br>` +
        `PIC: ${safe(r.pic_name)} / ${safe(r.pic_phone)}<br>` +
        `${safe(r.capacity_description)}${evidenceLink("resource_profile", r.id)}`,
        safe(r.availability_status)
      )).join("")
    : card("No resource profile", "Belum ada profil sumber daya.", "empty");

  setText("resourceStatus", `Loaded ${resources.length} resource profile(s) for ${eventId}.`);
}

document.addEventListener("DOMContentLoaded", () => {
  const refresh = document.getElementById("refreshResource");
  if (refresh) refresh.addEventListener("click", () => loadResourceProfile().catch(err => setText("resourceStatus", err.message)));
  loadResourceProfile().catch(err => setText("resourceStatus", err.message));
});
