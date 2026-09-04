/* ============================================================
 * New dashboard (matches verification & Approval.png): calls
 * rescue_net.api_verification.approval_queue / approval_item_detail /
 * approval_action (guest read, login-required write). The legacy
 * "Trusted Verifier Network" panels below (a distinct identity/
 * endorsement concept, kept in <details>) still use
 * api_frontend_bridge.* unchanged.
 * ============================================================ */
(function () {
  "use strict";

  var $ = function (sel, root) { return (root || document).querySelector(sel); };
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function fmt(n) { return Number(n || 0).toLocaleString("id-ID"); }
  function getEventId() { return new URLSearchParams(window.location.search).get("event") || "event-sim-001"; }
  function fmtTime(t) { return t ? String(t).slice(0, 16).replace("T", " ") : "-"; }

  var PAGE_SIZE = 8;
  var state = { queue: [], filtered: [], kind: "Semua", page: 0, selected: null };
  var QUEUE_CACHE = null;

  function statusPillClass(status) {
    var l = String(status || "").toLowerCase();
    if (["verified", "official_verified", "community_verified", "approved"].indexOf(l) !== -1) return "ok";
    if (l === "rejected") return "danger";
    if (l === "escalated" || l === "needs_correction") return "warning";
    return "";
  }

  var KIND_LABELS = { user: "User", organisasi: "Organisasi", posko: "Posko", needs: "Needs", expense: "Expense", evidence: "Evidence" };

  function renderKpi(t) {
    $("#kpiUser").textContent = fmt(t.user_pending);
    $("#kpiOrg").textContent = fmt(t.organisasi_pending);
    $("#kpiPosko").textContent = fmt(t.posko_pending);
    $("#kpiNeeds").textContent = fmt(t.needs_pending);
    $("#kpiExpense").textContent = fmt(t.expense_pending);
    $("#kpiEvidence").textContent = fmt(t.evidence_pending);
  }

  function applyFilter() {
    state.filtered = state.kind === "Semua" ? state.queue : state.queue.filter(function (r) { return r.kind === state.kind; });
    state.page = 0;
    renderQueue();
  }

  function setupTabs() {
    document.querySelectorAll("#queueTabs .rn-tab").forEach(function (tab) {
      tab.addEventListener("click", function () {
        document.querySelectorAll("#queueTabs .rn-tab").forEach(function (t) { t.classList.remove("is-active"); });
        tab.classList.add("is-active");
        state.kind = tab.getAttribute("data-kind");
        applyFilter();
      });
    });
    document.querySelectorAll(".rn-va-kpi .rn-kpi-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var kind = btn.getAttribute("data-kind");
        document.querySelectorAll("#queueTabs .rn-tab").forEach(function (t) { t.classList.toggle("is-active", t.getAttribute("data-kind") === kind); });
        state.kind = kind;
        applyFilter();
      });
    });
  }

  function renderQueue() {
    var total = state.filtered.length;
    $("#queueCount").textContent = fmt(state.queue.length);
    var pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
    state.page = Math.min(state.page, pages - 1);
    var slice = state.filtered.slice(state.page * PAGE_SIZE, state.page * PAGE_SIZE + PAGE_SIZE);

    var body = $("#queueBody");
    if (!slice.length) {
      body.innerHTML = '<tr><td colspan="5"><em class="rn-muted">Tidak ada item.</em></td></tr>';
    } else {
      body.innerHTML = slice.map(function (r) {
        var isSel = state.selected && state.selected.kind === r.kind && state.selected.name === r.name;
        return (
          '<tr class="rn-ba-row' + (isSel ? " is-selected" : "") + '" data-kind="' + esc(r.kind) + '" data-name="' + esc(r.name) + '">' +
          "<td><span class=\"chip\">" + esc(KIND_LABELS[r.kind] || r.kind) + "</span></td>" +
          "<td><b>" + esc(r.title) + "</b><small>" + fmtTime(r.creation) + "</small></td>" +
          "<td>" + esc(r.owner) + "</td>" +
          "<td>" + fmt(r.evidence_count) + "</td>" +
          '<td><span class="chip ' + statusPillClass(r.status) + '">' + esc(r.status) + "</span></td></tr>"
        );
      }).join("");
    }
    body.querySelectorAll("tr[data-name]").forEach(function (tr) {
      tr.addEventListener("click", function () { selectItem(tr.getAttribute("data-kind"), tr.getAttribute("data-name")); });
    });

    $("#queueShown").textContent = total
      ? "Menampilkan " + (state.page * PAGE_SIZE + 1) + "-" + Math.min(total, (state.page + 1) * PAGE_SIZE) + " dari " + total
      : "0 item";
    var pager = $("#queuePager");
    var btns = [];
    for (var i = 0; i < pages; i++) {
      btns.push('<button type="button" class="rn-ev-page' + (i === state.page ? " is-active" : "") + '" data-page="' + i + '">' + (i + 1) + "</button>");
    }
    pager.innerHTML = btns.join("");
    pager.querySelectorAll("button").forEach(function (btn) {
      btn.addEventListener("click", function () { state.page = Number(btn.getAttribute("data-page")); renderQueue(); });
    });
  }

  function renderDetail(detail) {
    $("#detailKindChip").textContent = KIND_LABELS[detail.kind] || detail.kind;
    var fieldsHtml = Object.keys(detail.fields || {}).map(function (k) {
      var v = detail.fields[k];
      return v == null || v === "" ? "" : "<div><span>" + esc(k) + "</span><b>" + esc(v) + "</b></div>";
    }).join("");

    var trustHtml = "";
    if (detail.trust) {
      trustHtml =
        '<div class="rn-va-trust"><span>Trust Level</span><b>' + esc(detail.trust.trust_level || "-") + "</b>" +
        "<span>Verifier Terpercaya</span><b>" + fmt(detail.trust.trusted_verifier_count) + "</b></div>";
    }

    var evidenceHtml = (detail.evidence || []).length
      ? '<div class="rn-dp-evidence-strip">' + detail.evidence.map(function (e) {
          return '<a class="rn-bukti-thumb" href="' + esc(e.evidence_url) + '" target="_blank" rel="noopener"><img src="' + esc(e.evidence_url) + '" alt="" loading="lazy"></a>';
        }).join("") + "</div>"
      : '<p class="rn-muted">Belum ada evidence terkait.</p>';

    $("#detailBody").innerHTML =
      "<h4>" + esc(detail.title) + "</h4>" +
      '<p class="rn-muted">' + esc(detail.name) + " · Diajukan " + fmtTime(detail.creation) + "</p>" +
      '<div class="rn-va-fields">' + fieldsHtml + "</div>" +
      trustHtml +
      '<h3 class="rn-sub-h">Evidence</h3>' + evidenceHtml;

    renderSteps(detail.status);
    renderTimeline(detail.timeline || []);
  }

  var STEP_LABELS = ["Diajukan", "Menunggu Verifikasi", "Diputuskan"];
  function renderSteps(status) {
    var l = String(status || "").toLowerCase();
    var closed = ["verified", "official_verified", "community_verified", "approved", "rejected"].indexOf(l) !== -1;
    var stepIndex = closed ? 2 : 1;
    $("#approvalSteps").innerHTML = STEP_LABELS.map(function (label, i) {
      var cls = i < stepIndex ? "is-done" : i === stepIndex ? "is-current" : "";
      return '<li class="' + cls + '"><span class="rn-va-step-num">' + (i + 1) + "</span>" + esc(label) + "</li>";
    }).join("");
  }

  function renderTimeline(items) {
    $("#auditTimeline").innerHTML = items.length
      ? items.map(function (it) { return "<li><b>" + fmtTime(it.time) + "</b><span>" + esc(it.label) + "</span></li>"; }).join("")
      : '<li class="rn-muted">Belum ada riwayat.</li>';
  }

  async function selectItem(kind, name) {
    state.selected = { kind: kind, name: name };
    renderQueue();
    $("#detailBody").innerHTML = '<p class="rn-muted">Memuat…</p>';
    document.querySelectorAll(".rn-va-action").forEach(function (b) { b.disabled = false; });
    $("#actionHint").textContent = "Tindakan akan diterapkan ke: " + name;
    try {
      var detail = await window.RN_FRAPPE.call("rescue_net.api_verification.approval_item_detail", { kind: kind, name: name });
      renderDetail(detail);
    } catch (err) {
      $("#detailBody").innerHTML = '<p class="rn-muted">Gagal memuat detail: ' + esc(err && err.message || err) + "</p>";
    }
  }

  function setupActions() {
    document.querySelectorAll(".rn-va-action").forEach(function (btn) {
      btn.addEventListener("click", async function () {
        if (!state.selected) return;
        var action = btn.getAttribute("data-action");
        var msg = $("#actionMsg");
        msg.textContent = "Memproses…";
        try {
          await window.RN_FRAPPE.call(
            "rescue_net.api_verification.approval_action",
            { kind: state.selected.kind, name: state.selected.name, action: action },
            { method: "POST" }
          );
          msg.textContent = "Berhasil: " + action;
          await loadQueue();
          await selectItem(state.selected.kind, state.selected.name);
        } catch (err) {
          msg.textContent = "Gagal: " + (err && err.message || err) +
            (/login|permission|akses|diperlukan/i.test(String(err && err.message)) ? " (perlu login sebagai operator verifikasi)" : "");
        }
      });
    });
  }

  async function loadQueue() {
    var data = await window.RN_FRAPPE.call("rescue_net.api_verification.approval_queue", { disaster_event: getEventId() });
    QUEUE_CACHE = data;
    state.queue = data.queue || [];
    $("#verifUpdated").textContent = "Verifikasi · Diperbarui " + fmtTime(data.generated_at).slice(11, 16);
    renderKpi(data.totals || {});
    applyFilter();
  }

  document.addEventListener("DOMContentLoaded", function () {
    if (!window.RN_FRAPPE) return;
    setupTabs();
    setupActions();
    loadQueue()
      .then(function () {
        if (state.filtered.length) selectItem(state.filtered[0].kind, state.filtered[0].name);
        var el = document.getElementById("verifStatus");
        if (el) el.textContent = "Dimuat " + state.queue.length + " item pending.";
      })
      .catch(function (err) {
        var el = document.getElementById("verifStatus");
        if (el) el.textContent = "Gagal memuat: " + (err && err.message || err);
      });
  });
})();

const DISASTER_ID =
  new URLSearchParams(location.search).get("event") ||
  (function () { try { return localStorage.getItem("rn_active_event"); } catch (e) { return null; } })() ||
  "event-sim-001";

let VERIFY_CONTEXT = null;

function safe(v) {
  return v === null || v === undefined || v === "" ? "n/a" : v;
}

function statusMsg(msg) {
  const el = document.getElementById("verificationStatus");
  if (el) el.textContent = msg;
}


async function api(path, options = {}) {
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
    url.pathname.startsWith(
      "/verification-context/"
    )
  ) {
    const eventId =
      decodeURIComponent(
        url.pathname.slice(
          "/verification-context/".length
        )
      );

    return await RN_FRAPPE.call(
      "rescue_net.api_frontend_bridge."
      + "verification_context",
      {
        disaster_event:
          eventId
      }
    );
  }

  if (
    url.pathname ===
      "/public/verifier-profiles"
    && method === "POST"
  ) {
    return await RN_FRAPPE.call(
      "rescue_net.api_frontend_bridge."
      + "create_verifier_profile",
      body,
      {
        method: "POST"
      }
    );
  }

  const verifierMatch =
    url.pathname.match(
      /^\/verifier-profiles\/([^/]+)\/status$/
    );

  if (
    verifierMatch
    && (
      method === "POST"
      || method === "PATCH"
    )
  ) {
    return await RN_FRAPPE.call(
      "rescue_net.api_frontend_bridge."
      + "set_verifier_status",
      {
        verifier:
          decodeURIComponent(
            verifierMatch[1]
          ),

        status:
          body.status
          || body.verifier_status
      },
      {
        method: "POST"
      }
    );
  }

  const endorsementMatch =
    url.pathname.match(
      /^\/verification-endorsements\/([^/]+)\/revoke$/
    );

  if (
    endorsementMatch
    && method === "POST"
  ) {
    return await RN_FRAPPE.call(
      "rescue_net.api_frontend_bridge."
      + "revoke_verification_endorsement",
      {
        endorsement:
          decodeURIComponent(
            endorsementMatch[1]
          )
      },
      {
        method: "POST"
      }
    );
  }

  if (
    url.pathname ===
      "/verification-actions"
    && method === "POST"
  ) {
    return await RN_FRAPPE.call(
      "rescue_net.api_frontend_bridge."
      + "create_verification_action",
      body,
      {
        method: "POST"
      }
    );
  }

  if (
    url.pathname ===
      "/public/verification-requests/respond"
    && method === "POST"
  ) {
    return await RN_FRAPPE.call(
      "rescue_net.api_frontend_bridge."
      + "reject_legacy_token_verification",
      {},
      {
        method: "POST"
      }
    );
  }

  throw new Error(
    "Unsupported Verification route: "
    + method
    + " "
    + url.pathname
  );
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
