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
  function esc(s) { return window.RNUI.esc(s); }
  function fmt(n) { return window.RNUI.fmt(n); }
  function getEventId() { return window.RNUI.eventId(); }
  function fmtTime(t) { return window.RNUI.fmtTime(t); }

  var PAGE_SIZE = 8;
  var state = { queue: [], filtered: [], kind: "Semua", page: 0, selected: null, q: "", status: "", risk: "" };
  var QUEUE_CACHE = null;

  function statusPillClass(status) {
    var l = String(status || "").toLowerCase();
    if (["verified", "official_verified", "community_verified", "approved"].indexOf(l) !== -1) return "ok";
    if (l === "rejected") return "danger";
    if (l === "escalated" || l === "needs_correction") return "warning";
    return "";
  }

  var KIND_ICON = { user: "user", organisasi: "building", posko: "posko", needs: "alert-circle", expense: "scale", evidence: "camera" };
  var STATUS_LABEL = { pending: "Menunggu", self_reported: "Menunggu", needs_correction: "Revisi", escalated: "Dieskalasi", approved: "Disetujui",
    verified: "Terverifikasi", official_verified: "Terverifikasi", community_verified: "Terverifikasi", rejected: "Ditolak" };
  function riskChip(r) {
    var tone = r === "Tinggi" ? "danger" : r === "Sedang" ? "warning" : r === "Rendah" ? "good" : "";
    return r ? '<span class="chip ' + tone + '">' + esc(r) + "</span>" : "-";
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
    var q = state.q.trim().toLowerCase();
    state.filtered = state.queue.filter(function (r) {
      if (state.kind !== "Semua" && r.kind !== state.kind) return false;
      if (state.status && String(r.status || "") !== state.status) return false;
      if (state.risk && String(r.risk || "") !== state.risk) return false;
      if (q && [r.title, r.owner, r.kind, r.name, r.status].join(" ").toLowerCase().indexOf(q) === -1) return false;
      return true;
    });
    state.page = 0;
    renderQueue();
  }

  // search + status + risk bar above the queue (Pengajuan Verifikasi > Antrian Persetujuan)
  function setupQueueFilters() {
    var map = { "#vxQueueQ": "q", "#vxQueueStatus": "status", "#vxQueueRisk": "risk" };
    Object.keys(map).forEach(function (sel) {
      var el = $(sel);
      if (!el) return;
      el.addEventListener(el.tagName === "INPUT" ? "input" : "change", function () { state[map[sel]] = el.value; applyFilter(); });
    });
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
      body.innerHTML = '<tr><td colspan="7"><em class="rn-muted">Tidak ada item.</em></td></tr>';
    } else {
      body.innerHTML = slice.map(function (r) {
        var isSel = state.selected && state.selected.kind === r.kind && state.selected.name === r.name;
        return (
          '<tr class="rn-ba-row' + (isSel ? " is-selected" : "") + '" data-kind="' + esc(r.kind) + '" data-name="' + esc(r.name) + '">' +
          '<td><span class="rn-vax-kind"><i data-icon="' + (KIND_ICON[r.kind] || "dot") + '"></i>' + esc(KIND_LABELS[r.kind] || r.kind) + "</span></td>" +
          "<td><b>" + esc(r.title) + "</b><small>" + fmtTime(r.creation) + "</small></td>" +
          "<td>" + esc(r.owner) + "</td>" +
          "<td>" + fmt(r.evidence_count) + "</td>" +
          "<td>" + riskChip(r.risk) + "</td>" +
          '<td><span class="chip ' + statusPillClass(r.status) + '">' + esc(STATUS_LABEL[r.status] || r.status) + "</span></td>" +
          '<td class="rn-vax-go">›</td></tr>'
        );
      }).join("");
      if (window.RNIconFill) window.RNIconFill(body);
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

  function ring(score) {
    var R = 34, C = 2 * Math.PI * R, len = (Math.max(0, Math.min(100, score)) / 100) * C;
    var col = score >= 75 ? "#2fa66a" : score >= 50 ? "#f59e0b" : "#e04b3a";
    return '<svg viewBox="0 0 84 84" class="rn-vax-ring"><circle cx="42" cy="42" r="' + R + '" fill="none" stroke="#eadfd9" stroke-width="8"/>' +
      '<circle cx="42" cy="42" r="' + R + '" fill="none" stroke="' + col + '" stroke-width="8" stroke-linecap="round" stroke-dasharray="' + len.toFixed(1) + " " + C.toFixed(1) +
      '" transform="rotate(-90 42 42)"/><text x="42" y="46" text-anchor="middle" class="rn-vax-ringn">' + esc(score) + "</text></svg>";
  }

  function renderDetail(detail) {
    $("#detailKindChip").textContent = KIND_LABELS[detail.kind] || detail.kind;
    var fields = Object.assign({ "Dibuat pada": fmtTime(detail.creation) }, detail.fields || {});
    var fieldsHtml = Object.keys(fields).map(function (k) {
      var v = fields[k];
      return v == null || v === "" ? "" : "<dt>" + esc(k) + "</dt><dd>" + esc(v) + "</dd>";
    }).join("");

    var evidenceHtml = (detail.evidence || []).length
      ? '<div class="rn-dp-evidence-strip">' + detail.evidence.map(function (e) {
          return '<a class="rn-bukti-thumb" href="' + esc(e.evidence_url) + '" target="_blank" rel="noopener"><img src="' + esc(e.evidence_url) + '" alt="" loading="lazy"></a>';
        }).join("") + "</div>"
      : '<p class="rn-muted">Belum ada evidence terkait.</p>';

    var trustHtml = "";
    if (detail.risk_score != null) {
      trustHtml = '<h3 class="rn-sub-h">Trust / Risk Score</h3><div class="rn-vax-trust">' + ring(detail.risk_score) +
        '<div><span class="rn-vax-risk ' + esc((detail.risk || "").toLowerCase()) + '">' + esc(detail.risk) + "</span><ul>" +
        (detail.signals || []).map(function (g) { return "<li><span>" + esc(g.label) + "</span><b>" + esc(g.value) + "%</b></li>"; }).join("") +
        '</ul></div></div><p class="rn-muted rn-vax-basis">Rata-rata tiga sinyal nyata: identitas pembuat, rekam jejak keputusan sebelumnya, dan bukti terlampir.' +
        (detail.trust && detail.trust.trusted_verifier_count != null ? " Verifier terpercaya: " + fmt(detail.trust.trusted_verifier_count) + "." : "") + "</p>";
    }

    var isNew = !/^(approved|verified|official_verified|community_verified|rejected)$/.test(String(detail.status || ""));
    $("#detailBody").innerHTML =
      '<div class="rn-vax-dhead"><span class="rn-vax-dicon"><i data-icon="' + (KIND_ICON[detail.kind] || "dot") + '"></i></span><div><b>' + esc(detail.title) +
      (isNew ? ' <span class="chip good">Baru</span>' : "") + "</b><small>ID: " + esc(detail.name) + "</small></div></div>" +
      "<dl class=\"rn-vax-dl\">" + fieldsHtml + "</dl>" +
      '<h3 class="rn-sub-h">Evidence (' + (detail.evidence || []).length + ")</h3>" + evidenceHtml + trustHtml;

    renderSteps(detail.flow);
    renderTimeline(detail.audit || detail.timeline || []);
    if (window.RNIconFill) window.RNIconFill($("#detailBody"));
  }

  function renderSteps(flow) {
    $("#approvalSteps").innerHTML = (flow || []).map(function (st) {
      return '<li class="is-' + esc(st.state) + '"><span class="rn-va-step-num">' + st.n + "</span><span class=\"rn-vax-steptext\"><b>" + esc(st.label) + "</b><small>" + esc(st.role) +
        "</small></span><em>" + esc(st.actor || st.note || (st.state === "todo" ? "Menunggu" : "")) + "</em></li>";
    }).join("");
  }

  function renderTimeline(items) {
    $("#auditTimeline").innerHTML = items.length
      ? items.map(function (it) {
          return '<li><b>' + fmtTime(it.time) + "</b><span>" + esc(it.label) + (it.actor ? " — " + esc(it.actor) : "") + "</span>" +
            (it.note ? "<small>" + esc(it.note) + "</small>" : "") + "</li>";
        }).join("")
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
    setupQueueFilters();
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

/* One table for every verifiable object (replaces five separate lists). */
function renderObjectsTable(ctx) {
  const body = document.getElementById("vxObjectsBody");
  if (!body) return;
  const rows = [];
  const add = (type, label, x, name, detail, status) => rows.push({ type, label, id: x.id, name, detail, status: String(status || "") });
  (ctx.organizations || []).forEach(x => add("organization", "Organisasi", x, x.name || x.id, `${x.organization_type || "-"} · trust ${x.trust_level ?? "-"}`, x.status || x.trust_level));
  (ctx.poskos || []).forEach(x => add("posko", "Posko", x, x.name || x.id, `${x.node_type || "-"} · ${x.location || "-"}`, x.verification_status));
  (ctx.volunteers || []).forEach(x => add("volunteer", "Relawan", x, x.volunteer_name || x.id, `Keahlian: ${x.skill_tags || "-"}`, x.verification_status || x.availability_status));
  (ctx.aid_offers || []).forEach(x => add("aid_offer", "Tawaran Bantuan", x, x.item_name || x.id, `${x.donor_name || "-"} · ${x.quantity ?? ""} ${x.unit || ""}`, x.status));
  (ctx.work_tool_requests || []).forEach(x => add("work_tool_request", "Alat Kerja", x, x.tool_name || x.id, `${x.location || "-"} · untuk ${x.needed_for || "-"} · prioritas ${x.priority || "-"}`, x.status));
  const group = st => /verified|approved|trusted/i.test(st) && !/un|not/i.test(st) ? "verified" : /reject|ditolak/i.test(st) ? "rejected" : "pending";
  body.innerHTML = rows.length ? rows.map(r => {
    const g = group(r.status);
    const verified = g === "verified";
    return `<tr class="vx-row" data-type="${safe(r.type)}" data-vgroup="${g}"><td>${safe(r.label)}</td>
      <td><b>${safe(r.name)}</b><br><small>${safe(r.id)}</small></td><td>${safe(r.detail)}</td>
      <td><span class="chip ${verified ? "ok" : g === "rejected" ? "danger" : "warning"}">${safe(r.status || "belum")}</span></td>
      <td class="vx-actions-cell">${verified ? "" : verifyButton(r.type, r.id, r.type === "posko" ? "official_verified" : "verified", "trusted")}${evidenceButton(r.type, r.id)}</td></tr>`;
  }).join("") : `<tr><td colspan="5"><em class="rn-muted">Belum ada objek untuk event ini.</em></td></tr>`;
  const c = document.getElementById("vxObjectsCount");
  if (c) c.textContent = rows.length + " objek";
  window.dispatchEvent(new Event("vx:objects"));
}

async function loadVerification() {
  statusMsg("Loading verification context...");
  const ctx = await api(`/verification-context/${DISASTER_ID}`);
  VERIFY_CONTEXT = ctx;

  renderSummary(ctx.summary || {});

  renderObjectsTable(ctx);

  renderActions(ctx.verification_actions || []);

  statusMsg("Loaded: " + ctx.generated_at);
}

function setupTrustedVerifierActions() {
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
