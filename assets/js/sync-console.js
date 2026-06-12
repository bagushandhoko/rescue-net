const RN_API_BASE = "http://192.168.100.32:8092";
const LOCAL_KEY = "rn_sync_console_drafts";
const APP_QUEUE_KEY = "rn_sync_pending_events_v1";

function statusMsg(msg) {
  const el = document.getElementById("syncStatus");
  if (el) el.textContent = msg;
  console.log("[SyncConsole]", msg);
}

function uid(prefix) {
  return prefix + "-" + Date.now() + "-" + Math.random().toString(16).slice(2, 8);
}

function readJson(key) {
  try {
    return JSON.parse(localStorage.getItem(key) || "[]");
  } catch (e) {
    return [];
  }
}

function writeJson(key, items) {
  localStorage.setItem(key, JSON.stringify(items));
}

function getDrafts() {
  return readJson(LOCAL_KEY);
}

function saveDrafts(items) {
  writeJson(LOCAL_KEY, items);
}

function getAppQueue() {
  return readJson(APP_QUEUE_KEY);
}

function saveAppQueue(items) {
  writeJson(APP_QUEUE_KEY, items);
}

function queueCounts(items) {
  return items.reduce((acc, item) => {
    const status = item.sync_status || "unknown";
    acc[status] = (acc[status] || 0) + 1;
    return acc;
  }, {});
}

function countsLine(items) {
  const counts = queueCounts(items);
  return ["pending_sync", "conflict", "synced", "unknown"]
    .filter(k => counts[k])
    .map(k => `${k}: ${counts[k]}`)
    .join(" | ") || "empty";
}

function eventTitle(item) {
  return item.payload_json?.resource_id || item.object_id || item.event_id || "local event";
}

function eventBody(item, sourceLabel) {
  const payload = item.payload_json || {};
  const actor = payload.requested_by_id || item.source_organization_id || item.source_user_id || "n/a";
  const reason = payload.request_reason || item.sync_error || item.server_rejection?.error || "";
  const attempt = item.last_sync_attempt_at ? `<br>last attempt: ${item.last_sync_attempt_at}` : "";
  return `${sourceLabel}<br>${item.object_type || "object"} | ${item.operation || "operation"} | ${actor}<br>${reason}${attempt}`;
}

async function api(path, options = {}) {
  const res = await fetch(RN_API_BASE + path, {
    headers: { "Content-Type": "application/json" },
    ...options
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error("API " + res.status + ": " + text);
  }

  return await res.json();
}

function card(title, body, chip) {
  return `
    <article class="event-card">
      <div class="event-main">
        <div>
          <h4>${title}</h4>
          <p>${body}</p>
        </div>
        <div class="chips">
          <span class="chip warning">${chip}</span>
        </div>
      </div>
    </article>
  `;
}

function retryConflicts() {
  const drafts = getDrafts();
  const updated = drafts.map(d => {
    if (d.sync_status !== "conflict") return d;
    return {
      ...d,
      sync_status: "pending_sync",
      local_status: "retry_pending",
      retry_requested_at: new Date().toISOString()
    };
  });

  const appQueue = getAppQueue();
  const updatedQueue = appQueue.map(d => {
    if (d.sync_status !== "conflict") return d;
    return {
      ...d,
      sync_status: "pending_sync",
      conflict_status: "retry_pending",
      retry_requested_at: new Date().toISOString()
    };
  });

  saveDrafts(updated);
  saveAppQueue(updatedQueue);
  renderLocal();
  statusMsg("Conflict drafts and app queue events moved back to pending sync.");
}

function renderLocal() {
  const el = document.getElementById("localDrafts");
  if (!el) return;

  const drafts = getDrafts();
  const appQueue = getAppQueue();

  if (!drafts.length && !appQueue.length) {
    el.innerHTML = card("Belum ada local draft", "Klik Save Offline Draft untuk simulasi data offline.", "empty");
    return;
  }

  const summary = card(
    "Local Queue Summary",
    `console drafts: ${countsLine(drafts)}<br>app offline queue: ${countsLine(appQueue)}`,
    "local"
  );

  const draftCards = drafts.map(d => card(
    eventTitle(d),
    eventBody(d, "Sync Console draft"),
    d.sync_status
  ));

  const queueCards = appQueue.map(d => card(
    eventTitle(d),
    eventBody(d, "RN app offline queue"),
    d.sync_status
  ));

  el.innerHTML = [summary, ...draftCards, ...queueCards].join("");
}

async function syncPush() {
  const drafts = getDrafts();
  const pending = drafts.filter(d => d.sync_status !== "synced");

  if (!pending.length) {
    if (window.RNSync) {
      statusMsg("No Sync Console drafts. Triggering RN app queue sync...");
      await window.RNSync.triggerSync("sync-console");
      renderLocal();
      return;
    }

    statusMsg("No pending drafts.");
    return;
  }

  statusMsg("Pushing " + pending.length + " event(s)...");

  const payload = {
    source_device_id: pending[0].source_device_id || "device-demo",
    source_server_id: "local-device",
    events: pending.map(d => ({
      event_id: d.event_id,
      object_type: d.object_type,
      object_id: d.object_id,
      operation: d.operation,
      payload_json: d.payload_json,
      source_device_id: d.source_device_id,
      source_user_id: d.source_user_id,
      source_organization_id: d.source_organization_id
    }))
  };

  const result = await api("/sync/push", {
    method: "POST",
    body: JSON.stringify(payload)
  });

  const accepted = new Set((result.accepted || []).map(x => x.event_id));
  const rejected = new Map((result.rejected || []).map(x => [x.event_id, x]));
  const now = new Date().toISOString();

  const updated = drafts.map(d => {
    if (accepted.has(d.event_id)) {
      return {
        ...d,
        sync_status: "synced",
        local_status: "synced",
        synced_at: now,
        sync_error: null
      };
    }

    if (rejected.has(d.event_id)) {
      const rejection = rejected.get(d.event_id);
      return {
        ...d,
        sync_status: "conflict",
        local_status: "needs_review",
        sync_error: rejection.error || "Server rejected this sync event.",
        last_sync_attempt_at: now,
        server_rejection: rejection
      };
    }

    return {
      ...d,
      last_sync_attempt_at: now
    };
  });

  saveDrafts(updated);
  renderLocal();

  statusMsg("Push done. accepted=" + result.accepted_count + ", rejected=" + result.rejected_count);
  if (window.RNSync) {
    await window.RNSync.triggerSync("sync-console-after-draft-push");
    renderLocal();
  }
  await syncPull();
  await refreshServerReview();
}

async function syncPull() {
  const input = document.querySelector('input[name="disaster_event_id"]');
  const disasterId = input ? input.value.trim() : "event-aceh-2025";

  statusMsg("Pulling latest data for " + disasterId + "...");

  const data = await api("/sync/pull/" + disasterId);

  const reqEl = document.getElementById("serverRequests");
  const assignEl = document.getElementById("serverAssignments");
  const eventEl = document.getElementById("syncEvents");

  if (reqEl) {
    reqEl.innerHTML = (data.resource_requests || []).map(r => card(
      r.resource_name || r.resource_id,
      `requested by: ${r.requested_by_type}/${r.requested_by_id}<br>status: ${r.status}<br>${r.request_reason || ""}`,
      r.id
    )).join("") || card("Belum ada server request", "No data.", "empty");
  }

  if (assignEl) {
    assignEl.innerHTML = (data.resource_assignments || []).map(a => card(
      a.resource_name || a.resource_id,
      `assigned to: ${a.assigned_to_type}/${a.assigned_to_id}<br>status: ${a.status}<br>${a.assignment_notes || ""}`,
      a.id
    )).join("") || card("Belum ada assignment", "No data.", "empty");
  }

  if (eventEl) {
    eventEl.innerHTML = (data.sync_events || []).slice(0, 20).map(e => card(
      e.event_id,
      `${e.object_type}/${e.object_id}<br>operation: ${e.operation}<br>apply: ${e.apply_status}`,
      e.source_device_id || "server"
    )).join("") || card("Belum ada sync event", "No data.", "empty");
  }

  statusMsg("Pull complete: " + data.generated_at);
}

async function loadServerConflicts() {
  const el = document.getElementById("serverConflicts");
  if (!el) return;

  const items = await api("/sync-conflicts?limit=20");
  if (!items.length) {
    el.innerHTML = card("No server conflicts", "Belum ada conflict tercatat di server.", "ok");
    return;
  }

  el.innerHTML = items.map(c => `
    <article class="event-card">
      <div class="event-main">
        <div>
          <h4>${c.conflict_id || c.id || "conflict"}</h4>
          <p>
            ${c.object_type || "object"} / ${c.object_id || "n/a"}<br>
            Status: ${c.status || c.conflict_status || "needs_review"}<br>
            Reason: ${c.reason || c.conflict_reason || c.sync_error || "n/a"}
          </p>
        </div>
        <div class="chips">
          <span class="chip warning">${c.status || c.conflict_status || "conflict"}</span>
          <button class="btn" type="button" data-resolve-conflict="${c.conflict_id || c.id || ""}">Resolve</button>
        </div>
      </div>
    </article>
  `).join("");
}

async function loadAuditEvents() {
  const el = document.getElementById("auditEvents");
  if (!el) return;

  const items = await api("/audit-events?limit=20");
  if (!items.length) {
    el.innerHTML = card("No audit event", "Belum ada audit event terbaru.", "empty");
    return;
  }

  el.innerHTML = items.map(a => card(
    a.action || a.event_type || "audit",
    `${a.object_table || a.table_name || "object"} / ${a.object_id || "n/a"}<br>Actor: ${a.actor_user_id || "system"}<br>Time: ${a.created_at || a.event_time || "n/a"}`,
    a.disaster_event_id || "audit"
  )).join("");
}

async function refreshServerReview() {
  await Promise.all([
    loadServerConflicts(),
    loadAuditEvents()
  ]);
}

async function resolveServerConflict(conflictId) {
  if (!conflictId) {
    statusMsg("Conflict ID missing.");
    return;
  }

  statusMsg("Resolving conflict " + conflictId + "...");
  await api(`/sync-conflicts/${encodeURIComponent(conflictId)}/resolve`, {
    method: "POST",
    body: JSON.stringify({
      resolution_status: "resolved",
      resolution_note: "Resolved from Sync Console",
      resolved_by_user_id: "sync-console"
    })
  });

  statusMsg("Conflict resolved: " + conflictId);
  await refreshServerReview();
}

function saveOfflineDraft() {
  const form = document.getElementById("offlineForm");
  if (!form) {
    statusMsg("ERROR: offlineForm not found.");
    return;
  }

  const draft = {
    event_id: uid("offline-booking"),
    object_type: "resource_request",
    object_id: uid("local-req"),
    operation: "create",
    source_device_id: form.source_device_id.value.trim(),
    source_user_id: "field-user-demo",
    source_organization_id: form.requested_by_id.value.trim(),
    sync_status: "pending_sync",
    local_status: "draft_local",
    created_local_at: new Date().toISOString(),
    payload_json: {
      disaster_event_id: form.disaster_event_id.value.trim(),
      resource_id: form.resource_id.value.trim(),
      requested_by_type: form.requested_by_type.value.trim(),
      requested_by_id: form.requested_by_id.value.trim(),
      request_reason: form.request_reason.value.trim(),
      requested_quantity: Number(form.requested_quantity.value || 1),
      requested_time: form.requested_time.value.trim(),
      local_status: "pending_sync"
    }
  };

  const drafts = getDrafts();
  drafts.unshift(draft);
  saveDrafts(drafts);

  renderLocal();
  statusMsg("Offline draft saved: " + draft.event_id);
}

async function loadFederation() {
  const nodesEl = document.getElementById("federationNodes");
  const logsEl = document.getElementById("federationLogs");
  if (!nodesEl && !logsEl) return;

  try {
    const [nodes, repos, logs] = await Promise.all([
      api("/federation/nodes?disaster_event_id=event-sim-001"),
      api("/federation/repositories"),
      api("/federation/sync-logs")
    ]);

    if (nodesEl) {
      const nodeCards = nodes.length ? nodes.map(n => card(
        n.node_name,
        `${n.node_type} ?? ${n.trust_level}<br>${n.base_url || "no remote url"}<br>${n.notes || ""}`,
        n.status
      )) : [card("Belum ada federation node", "Tambahkan node partner dulu. Auto-pull eksternal belum aktif sampai credential jelas.", "empty")];

      const repoCards = repos.map(r => card(
        `Repository ?? ${r.repository_name}`,
        `${r.node_name || r.node_id}<br>${r.repository_type} ?? ${r.direction} ?? policy ${r.conflict_policy}`,
        r.status
      ));

      nodesEl.innerHTML = [...nodeCards, ...repoCards].join("");
    }

    if (logsEl) {
      logsEl.innerHTML = logs.length ? logs.map(l => card(
        `${l.direction} ?? ${l.status}`,
        `${l.node_id || "local"} / ${l.repository_id || "manifest"}<br>${l.notes || ""}<br>${l.created_at || ""}`,
        "federation"
      )).join("") : card("No federation log", "Manifest export/import akan tercatat di sini.", "empty");
    }
  } catch (err) {
    if (nodesEl) nodesEl.innerHTML = card("Federation endpoint belum aktif", "Jalankan rebuild API untuk mengaktifkan /federation/*.", "pending");
    if (logsEl) logsEl.innerHTML = card("Federation logs menunggu rebuild", err.message, "pending");
  }
}

async function addFederationNode() {
  const form = document.getElementById("federationNodeForm");
  if (!form) return;
  const node = await api("/federation/nodes", {
    method: "POST",
    body: JSON.stringify({
      node_name: form.node_name.value.trim(),
      node_type: form.node_type.value,
      base_url: form.base_url.value.trim(),
      trust_level: form.trust_level.value,
      disaster_event_id: "event-sim-001",
      notes: "Created from Sync Console"
    })
  });

  await api("/federation/repositories", {
    method: "POST",
    body: JSON.stringify({
      node_id: node.federation_node.id,
      repository_name: "Event Sync Manifest",
      repository_type: "federation_manifest",
      endpoint_path: "/federation/manifest/event-sim-001",
      direction: "bidirectional",
      conflict_policy: "manual_review",
      notes: "Uses consolidated needs and duplicate warnings."
    })
  });

  statusMsg("Federation node added: " + node.federation_node.id);
  await loadFederation();
}

async function exportFederationManifest() {
  statusMsg("Exporting federation manifest...");
  const manifest = await api("/federation/manifest/event-sim-001");
  await api("/federation/sync-logs", {
    method: "POST",
    body: JSON.stringify({
      direction: "export",
      status: "manifest_created",
      manifest_json: manifest,
      notes: "Manifest exported from Sync Console. Raw reports are not final; use consolidated needs."
    })
  });
  statusMsg(`Manifest exported: ${manifest.schema}, event ${manifest.disaster_event_id}`);
  await loadFederation();
}

document.addEventListener("DOMContentLoaded", () => {
  statusMsg("JS loaded. Sync Console ready.");

  const form = document.getElementById("offlineForm");
  const clearBtn = document.getElementById("clearLocal");
  const pushBtn = document.getElementById("syncPush");
  const pullBtn = document.getElementById("syncPull");
  const retryBtn = document.getElementById("retryConflicts");
  const federationForm = document.getElementById("federationNodeForm");
  const federationManifestBtn = document.getElementById("exportFederationManifest");

  if (form) {
    form.addEventListener("submit", e => {
      e.preventDefault();
      saveOfflineDraft();
    });
  } else {
    statusMsg("ERROR: offlineForm not found.");
  }

  if (clearBtn) {
    clearBtn.addEventListener("click", () => {
      localStorage.removeItem(LOCAL_KEY);
      renderLocal();
      statusMsg("Sync Console demo drafts cleared. RN app offline queue preserved.");
    });
  }

  if (retryBtn) {
    retryBtn.addEventListener("click", retryConflicts);
  }

  const refreshConflicts = document.getElementById("refreshConflicts");
  if (refreshConflicts) {
    refreshConflicts.addEventListener("click", () => {
      statusMsg("Refreshing server conflicts and audit events...");
      refreshServerReview().catch(err => statusMsg(err.message));
    });
  }

  document.addEventListener("click", e => {
    const btn = e.target.closest("[data-resolve-conflict]");
    if (btn) {
      resolveServerConflict(btn.dataset.resolveConflict).catch(err => statusMsg(err.message));
    }
  });

  if (pushBtn) {
    pushBtn.addEventListener("click", () => {
      statusMsg("Sync Push clicked.");
      syncPush().catch(err => statusMsg(err.message));
    });
  }

  if (pullBtn) {
    pullBtn.addEventListener("click", () => {
      statusMsg("Sync Pull clicked.");
      syncPull().catch(err => statusMsg(err.message));
    });
  }

  if (federationForm) {
    federationForm.addEventListener("submit", e => {
      e.preventDefault();
      addFederationNode().catch(err => statusMsg(err.message));
    });
  }

  if (federationManifestBtn) {
    federationManifestBtn.addEventListener("click", () => {
      exportFederationManifest().catch(err => statusMsg(err.message));
    });
  }

  renderLocal();
  syncPull().catch(err => statusMsg(err.message));
  refreshServerReview().catch(err => statusMsg(err.message));
  loadFederation().catch(err => statusMsg(err.message));
});

