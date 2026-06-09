const RN_API_BASE = "http://192.168.100.32:8092";
const DISASTER_ID = "event-aceh-2025";

let VERIFY_CONTEXT = null;

function safe(v) {
  return v === null || v === undefined || v === "" ? "n/a" : v;
}

function statusMsg(msg) {
  const el = document.getElementById("verificationStatus");
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

function card(title, body, chip = "", actions = "") {
  return `
    <article class="event-card">
      <div class="event-main">
        <div>
          <h4>${title}</h4>
          <p>${body}</p>
        </div>
        <div class="chips">
          ${chip ? `<span class="chip warning">${chip}</span>` : ""}
          ${actions}
        </div>
      </div>
    </article>
  `;
}

function verifyButton(objectType, objectId, status = "verified", trust = "trusted") {
  return `<button class="btn primary" type="button" onclick="verifyObject('${objectType}', '${objectId}', '${status}', '${trust}')">Verify</button>`;
}

function renderSummary(summary) {
  const el = document.getElementById("verificationSummary");
  if (!el) return;

  el.innerHTML = `
    <div><span>Organizations</span><b>${summary.organization_count || 0}</b></div>
    <div><span>Poskos</span><b>${summary.posko_count || 0}</b></div>
    <div><span>Volunteers</span><b>${summary.volunteer_count || 0}</b></div>
    <div><span>Aid Offers</span><b>${summary.aid_offer_count || 0}</b></div>
    <div><span>Work Tools</span><b>${summary.work_tool_request_count || 0}</b></div>
    <div><span>Actions</span><b>${summary.verification_action_count || 0}</b></div>
  `;
}

function renderList(id, items, objectType, titleField, bodyFn, statusFn) {
  const el = document.getElementById(id);
  if (!el) return;

  el.innerHTML = items.length ? items.map(x => {
    const status = statusFn(x);
    const action = verifyButton(objectType, x.id, objectType === "posko" ? "official_verified" : "verified", "trusted");
    return card(safe(x[titleField] || x.name || x.id), bodyFn(x), status, action);
  }).join("") : card("Tidak ada data", "Belum ada item untuk diverifikasi.", "empty");
}

function renderActions(items) {
  const el = document.getElementById("verificationActions");
  if (!el) return;

  el.innerHTML = items.length ? items.map(a => card(
    `${safe(a.object_type)} · ${safe(a.object_id)}`,
    `Action: ${safe(a.action_type)}<br>Status: ${safe(a.verification_status)}<br>Trust: ${safe(a.trust_level)}<br>Reviewer: ${safe(a.reviewed_by)}<br>Notes: ${safe(a.review_notes)}`,
    a.verification_status
  )).join("") : card("Belum ada verification action", "Aksi verifikasi akan tampil di sini.", "empty");
}

async function loadVerification() {
  statusMsg("Loading verification context...");
  const ctx = await api(`/verification-context/${DISASTER_ID}`);
  VERIFY_CONTEXT = ctx;

  renderSummary(ctx.summary || {});

  renderList(
    "verifyOrganizations",
    ctx.organizations || [],
    "organization",
    "name",
    x => `Type: ${safe(x.organization_type)}<br>Status: ${safe(x.status)}<br>Trust: ${safe(x.trust_level)}`,
    x => safe(x.status || x.trust_level)
  );

  renderList(
    "verifyPoskos",
    ctx.poskos || [],
    "posko",
    "name",
    x => `Type: ${safe(x.node_type)}<br>Location: ${safe(x.location)}<br>Status: ${safe(x.verification_status)} · ${safe(x.operational_status)}`,
    x => safe(x.verification_status)
  );

  renderList(
    "verifyVolunteers",
    ctx.volunteers || [],
    "volunteer",
    "volunteer_name",
    x => `Contact: ${safe(x.contact)}<br>Skills: ${safe(x.skill_tags)}<br>Status: ${safe(x.verification_status || x.availability_status)}`,
    x => safe(x.verification_status || x.availability_status)
  );

  renderList(
    "verifyAidOffers",
    ctx.aid_offers || [],
    "aid_offer",
    "item_name",
    x => `Donor: ${safe(x.donor_name)} · ${safe(x.donor_contact)}<br>Qty: ${safe(x.quantity)} ${safe(x.unit)}<br>Status: ${safe(x.status)}`,
    x => safe(x.status)
  );

  renderList(
    "verifyWorkTools",
    ctx.work_tool_requests || [],
    "work_tool_request",
    "tool_name",
    x => `Location: ${safe(x.location)}<br>Needed for: ${safe(x.needed_for)}<br>Priority: ${safe(x.priority)}<br>Status: ${safe(x.status)}`,
    x => safe(x.status)
  );

  renderActions(ctx.verification_actions || []);

  statusMsg("Loaded: " + ctx.generated_at);
}

async function verifyObject(objectType, objectId, verificationStatus, trustLevel) {
  const notes = prompt("Review notes", `Verified ${objectType} ${objectId}`) || "";

  statusMsg("Saving verification action...");
  await api("/verification-actions", {
    method: "POST",
    body: JSON.stringify({
      disaster_event_id: DISASTER_ID,
      object_type: objectType,
      object_id: objectId,
      action_type: "verify",
      verification_status: verificationStatus,
      trust_level: trustLevel,
      reviewed_by: "command-center-demo",
      reviewer_role: "command_center",
      review_notes: notes
    })
  });

  statusMsg("Verification saved.");
  await loadVerification();
}

document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("refreshVerification");
  if (btn) btn.addEventListener("click", () => loadVerification().catch(err => statusMsg(err.message)));

  loadVerification().catch(err => statusMsg(err.message));
});
