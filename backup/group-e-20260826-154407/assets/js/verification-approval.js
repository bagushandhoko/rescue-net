const RN_API_BASE = (location.protocol === "https:" ? location.origin + "/rescue-net-api" : "http://192.168.100.32:8092");
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
  return `<button class="btn primary" data-requires-role-action="verify" type="button" onclick="verifyObject('${objectType}', '${objectId}', '${status}', '${trust}')">Verify</button>`;
}

function evidenceButton(objectType, objectId) {
  if (!objectId) return "";
  return `<a class="btn" href="evidence.html?event=${encodeURIComponent(DISASTER_ID)}&object_type=${encodeURIComponent(objectType)}&object_id=${encodeURIComponent(objectId)}">Evidence</a>`;
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
    <div><span>Verifier Requests</span><b>${summary.pending_verifier_request_count || 0}</b></div>
    <div><span>Active Endorsements</span><b>${summary.active_endorsement_count || 0}</b></div>
    <div><span>Candidate Verifiers</span><b>${summary.candidate_verifier_count || 0}</b></div>
  `;
}

function renderList(id, items, objectType, titleField, bodyFn, statusFn) {
  const el = document.getElementById(id);
  if (!el) return;

  el.innerHTML = items.length ? items.map(x => {
    const status = statusFn(x);
    const action = verifyButton(objectType, x.id, objectType === "posko" ? "official_verified" : "verified", "trusted") + evidenceButton(objectType, x.id);
    return card(safe(x[titleField] || x.name || x.id), bodyFn(x), status, action);
  }).join("") : card("Tidak ada data", "Belum ada item untuk diverifikasi.", "empty");
}

function renderActions(items) {
  const el = document.getElementById("verificationActions");
  if (!el) return;

  el.innerHTML = items.length ? items.map(a => card(
    `${safe(a.object_type)} ? ${safe(a.object_id)}`,
    `Action: ${safe(a.action_type)}<br>Status: ${safe(a.verification_status)}<br>Trust: ${safe(a.trust_level)}<br>Reviewer: ${safe(a.reviewed_by)}<br>Notes: ${safe(a.review_notes)}`,
    a.verification_status
  )).join("") : card("Belum ada verification action", "Aksi verifikasi akan tampil di sini.", "empty");
}

function renderTrustedVerifier(ctx) {
  const requestsEl = document.getElementById("trustedVerifierRequests");
  const endorsementsEl = document.getElementById("trustedEndorsements");
  const registryEl = document.getElementById("trustedVerifierRegistry");
  const revokedEl = document.getElementById("revokedVerifications");
  const requests = ctx.verification_requests || [];
  const endorsements = ctx.verification_endorsements || [];
  const registry = ctx.verifier_profiles || [];

  requestsEl.innerHTML = requests.length ? requests.map(r => card(
    `${safe(r.target_type)}: ${safe(r.target_id)}`,
    `Scope: ${safe(r.verification_scope)}<br>Verifier: ${safe(r.requested_verifier_name || r.requested_verifier_id)}<br>Hubungan: ${safe(r.relationship_description)}<br>Expires: ${safe(r.expires_at)}`,
    r.status
  )).join("") : card("Tidak ada request", "Permintaan verifikasi baru akan tampil di sini.", "empty");

  endorsementsEl.innerHTML = endorsements.filter(x => x.status === "active").length
    ? endorsements.filter(x => x.status === "active").map(e => card(
      `${safe(e.target_type)}: ${safe(e.target_id)}`,
      `Identitas/scope: ${safe(e.verification_scope)}<br>Diverifikasi oleh: ${safe(e.verifier_display_name)}<br>Peran: ${safe(e.verifier_role)}<br>${safe(e.statement, "")}`,
      `level ${safe(e.verification_level)}`,
      `<button class="btn" type="button" data-revoke-endorsement="${e.id}">Revoke</button>`
    )).join("")
    : card("Belum ada endorsement aktif", "Persetujuan Trusted Verifier akan tampil di sini.", "empty");

  registryEl.innerHTML = registry.length ? registry.map(v => {
    const actions = v.verifier_status === "candidate_verifier"
      ? `<button class="btn primary" type="button" data-approve-verifier="${v.id}" data-verifier-type="${v.verifier_type}">Approve</button>`
      : "";
    return card(
      safe(v.display_name),
      `${safe(v.position_title || v.public_role_description)}<br>Type: ${safe(v.verifier_type)} | Trust: ${safe(v.trust_level)}<br>Scope: ${safe(JSON.stringify(v.allowed_verification_scope_json))}`,
      v.verifier_status,
      actions
    );
  }).join("") : card("Registry kosong", "Daftarkan calon verifikator melalui form.", "empty");

  const revoked = endorsements.filter(x => x.status === "revoked");
  const suspicious = registry.filter(x => Number(x.suspicious_activity_count || 0) > 0);
  revokedEl.innerHTML = revoked.concat(suspicious).length
    ? revoked.map(e => card(
      `Revoked: ${safe(e.target_id)}`,
      `${safe(e.verifier_display_name)}<br>Alasan: ${safe(e.revoke_reason)}`,
      "revoked"
    )).join("") + suspicious.map(v => card(
      `Suspicious: ${safe(v.display_name)}`,
      `Activity count: ${safe(v.suspicious_activity_count)}`,
      "review"
    )).join("")
    : card("Tidak ada temuan", "Belum ada endorsement dicabut atau aktivitas mencurigakan.", "ok");
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
    x => `Type: ${safe(x.node_type)}<br>Location: ${safe(x.location)}<br>Status: ${safe(x.verification_status)} ? ${safe(x.operational_status)}`,
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
    x => `Donor: ${safe(x.donor_name)} ? ${safe(x.donor_contact)}<br>Qty: ${safe(x.quantity)} ${safe(x.unit)}<br>Status: ${safe(x.status)}`,
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
  renderTrustedVerifier(ctx);

  statusMsg("Loaded: " + ctx.generated_at);
}

function setupTrustedVerifierActions() {
  const form = document.getElementById("verifierRegistrationForm");
  form?.addEventListener("submit", async e => {
    e.preventDefault();
    const data = new FormData(form);
    await api("/public/verifier-profiles", {
      method: "POST",
      body: JSON.stringify(Object.fromEntries(data.entries()))
    });
    form.reset();
    await loadVerification();
  });

  document.addEventListener("click", async e => {
    const approve = e.target.closest("[data-approve-verifier]");
    if (approve) {
      const type = approve.dataset.verifierType;
      const mapping = {
        community: ["community_verifier", 1],
        organization: ["organization_verifier", 2],
        government: ["government_verifier", 3],
        public_figure: ["trusted_public_verifier", 4],
        rn_admin: ["official_verifier", 5]
      };
      const [status, level] = mapping[type] || ["community_verifier", 1];
      await api(`/verifier-profiles/${approve.dataset.approveVerifier}/status`, {
        method: "PATCH",
        body: JSON.stringify({
          verifier_status: status,
          trust_level: level,
          allowed_verification_scope: ["identity", "organization_membership", "posko_identity", "location", "report_source"]
        })
      });
      await loadVerification();
    }
    const revoke = e.target.closest("[data-revoke-endorsement]");
    if (revoke) {
      const reason = prompt("Alasan mencabut endorsement") || "Dicabut oleh command center";
      await api(`/verification-endorsements/${revoke.dataset.revokeEndorsement}/revoke`, {
        method: "POST",
        body: JSON.stringify({ reason })
      });
      await loadVerification();
    }
  });

  const token = new URLSearchParams(location.search).get("token");
  const tokenPanel = document.getElementById("tokenVerificationPanel");
  const tokenForm = document.getElementById("tokenVerificationForm");
  if (token && tokenPanel && tokenForm) {
    tokenPanel.hidden = false;
    tokenForm.addEventListener("submit", async e => {
      e.preventDefault();
      const data = Object.fromEntries(new FormData(tokenForm).entries());
      await api(`/public/verification-requests/respond?token=${encodeURIComponent(token)}`, {
        method: "POST",
        body: JSON.stringify(data)
      });
      statusMsg("Keputusan verifikator tersimpan.");
      tokenForm.reset();
      await loadVerification();
    });
  }
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
  setupTrustedVerifierActions();
  const btn = document.getElementById("refreshVerification");
  if (btn) btn.addEventListener("click", () => loadVerification().catch(err => statusMsg(err.message)));

  loadVerification().catch(err => statusMsg(err.message));
});
