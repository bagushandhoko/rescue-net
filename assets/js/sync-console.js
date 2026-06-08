const RN_API_BASE = "http://192.168.100.32:8092";
const LOCAL_KEY = "rn_sync_console_drafts";

function statusMsg(msg) {
  const el = document.getElementById("syncStatus");
  if (el) el.textContent = msg;
  console.log("[SyncConsole]", msg);
}

function uid(prefix) {
  return prefix + "-" + Date.now() + "-" + Math.random().toString(16).slice(2, 8);
}

function getDrafts() {
  try {
    return JSON.parse(localStorage.getItem(LOCAL_KEY) || "[]");
  } catch (e) {
    return [];
  }
}

function saveDrafts(items) {
  localStorage.setItem(LOCAL_KEY, JSON.stringify(items));
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

function renderLocal() {
  const el = document.getElementById("localDrafts");
  if (!el) return;

  const drafts = getDrafts();

  if (!drafts.length) {
    el.innerHTML = card("Belum ada local draft", "Klik Save Offline Draft untuk simulasi data offline.", "empty");
    return;
  }

  el.innerHTML = drafts.map(d => card(
    d.payload_json.resource_id,
    `${d.object_type} · ${d.operation} · ${d.payload_json.requested_by_id}<br>${d.payload_json.request_reason}`,
    d.sync_status
  )).join("");
}

async function syncPush() {
  const drafts = getDrafts();
  const pending = drafts.filter(d => d.sync_status !== "synced");

  if (!pending.length) {
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

  const updated = drafts.map(d => {
    if (accepted.has(d.event_id)) {
      return {
        ...d,
        sync_status: "synced",
        local_status: "synced",
        synced_at: new Date().toISOString()
      };
    }
    return d;
  });

  saveDrafts(updated);
  renderLocal();

  statusMsg("Push done. accepted=" + result.accepted_count + ", rejected=" + result.rejected_count);
  await syncPull();
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

document.addEventListener("DOMContentLoaded", () => {
  statusMsg("JS loaded. Sync Console ready.");

  const form = document.getElementById("offlineForm");
  const clearBtn = document.getElementById("clearLocal");
  const pushBtn = document.getElementById("syncPush");
  const pullBtn = document.getElementById("syncPull");

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
      statusMsg("Local drafts cleared.");
    });
  }

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

  renderLocal();
  syncPull().catch(err => statusMsg(err.message));
});
