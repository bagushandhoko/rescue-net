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

async function api(path) {
  const res = await fetch(RN_API_BASE + path);
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
  setText("resourceStatus", "Loading resource profile...");

  const ctx = await api(`/ai/context/${eventId}`);
  const s = ctx.summary || {};

  const organizations = ctx.organizations || [];
  const poskos = ctx.poskos || [];
  const volunteers = ctx.volunteers || [];
  const resources = ctx.resources || ctx.shared_resources || [];

  setText("kpiOrg", safe(s.organization_count || organizations.length));
  setText("kpiPosko", safe(s.posko_count || poskos.length));
  setText("kpiVolunteer", safe(s.volunteer_count || volunteers.length));
  setText("kpiResource", safe(s.shared_resource_count || s.resource_count || resources.length));

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
    ? resources.slice(0, 12).map(r => card(
        safe(r.resource_name || r.name || r.title),
        `Type: ${safe(r.resource_type || r.type)}<br>Status: ${safe(r.status)}<br>Owner: ${safe(r.owner_id || r.organization_id)}<br>ID: ${safe(r.id)}`,
        safe(r.status || "resource")
      )).join("")
    : card("No resource data", "Belum ada data resource/alat bersama.", "empty");

  setText("resourceStatus", `Loaded resource profile for ${eventId}.`);
}

document.addEventListener("DOMContentLoaded", () => {
  const refresh = document.getElementById("refreshResource");
  if (refresh) refresh.addEventListener("click", () => loadResourceProfile().catch(err => setText("resourceStatus", err.message)));
  loadResourceProfile().catch(err => setText("resourceStatus", err.message));
});
