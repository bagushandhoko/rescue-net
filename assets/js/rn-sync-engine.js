const RN_SYNC_API_BASE = window.RN_API_BASE || "http://192.168.100.32:8092";
const RN_SYNC_QUEUE_KEY = "rn_sync_pending_events_v1";
const RN_SYNC_DEVICE_KEY = "rn_device_id_v1";

let RN_SYNC_RUNNING = false;
let RN_LAST_SYNC_AT = 0;

function rnSyncStatus(message) {
  const el =
    document.querySelector("[data-rn-sync-status]") ||
    document.getElementById("rnSyncStatus") ||
    document.getElementById("warRoomStatus") ||
    document.getElementById("syncStatus");

  if (el) el.textContent = message;
  console.log("[RN Sync]", message);
}

function rnGetDeviceId() {
  let id = localStorage.getItem(RN_SYNC_DEVICE_KEY);
  if (!id) {
    id = "device-" + Math.random().toString(16).slice(2) + "-" + Date.now();
    localStorage.setItem(RN_SYNC_DEVICE_KEY, id);
  }
  return id;
}

function rnGetEventId(defaultEventId = "event-aceh-2025") {
  const params = new URLSearchParams(window.location.search);
  return params.get("event") || params.get("id") || defaultEventId;
}

function rnGetQueue() {
  try {
    return JSON.parse(localStorage.getItem(RN_SYNC_QUEUE_KEY) || "[]");
  } catch {
    return [];
  }
}

function rnSaveQueue(items) {
  localStorage.setItem(RN_SYNC_QUEUE_KEY, JSON.stringify(items));
}

function rnQueueEvent(event) {
  const queue = rnGetQueue();

  const now = new Date().toISOString();
  const deviceId = rnGetDeviceId();

  queue.unshift({
    event_id: event.event_id || "local-" + Date.now() + "-" + Math.random().toString(16).slice(2),
    object_type: event.object_type,
    object_id: event.object_id || null,
    operation: event.operation || "create",
    payload_json: event.payload_json || {},
    source_device_id: event.source_device_id || deviceId,
    source_user_id: event.source_user_id || "field-user-demo",
    source_organization_id: event.source_organization_id || null,
    created_local_at: now,
    sync_status: "pending_sync"
  });

  rnSaveQueue(queue);
  rnSyncStatus(`Saved locally. Pending sync: ${queue.length}`);

  if (navigator.onLine) {
    rnTriggerSync("local-event-created");
  }

  return queue[0];
}

async function rnFetch(path, options = {}) {
  const res = await fetch(RN_SYNC_API_BASE + path, {
    headers: { "Content-Type": "application/json" },
    ...options
  });

  if (!res.ok) {
    throw new Error(await res.text());
  }

  return await res.json();
}

async function rnPushPending() {
  const queue = rnGetQueue();
  const pending = queue.filter(x => x.sync_status !== "synced");

  if (!pending.length) {
    return { accepted_count: 0, rejected_count: 0, message: "No pending events" };
  }

  const payload = {
    source_device_id: rnGetDeviceId(),
    source_server_id: "local-device",
    events: pending.map(x => ({
      event_id: x.event_id,
      object_type: x.object_type,
      object_id: x.object_id,
      operation: x.operation,
      payload_json: x.payload_json,
      source_device_id: x.source_device_id || rnGetDeviceId(),
      source_user_id: x.source_user_id || "field-user-demo",
      source_organization_id: x.source_organization_id || null
    }))
  };

  const result = await rnFetch("/sync/push", {
    method: "POST",
    body: JSON.stringify(payload)
  });

  const accepted = new Set((result.accepted || []).map(x => x.event_id));

  const updated = queue.map(x => {
    if (accepted.has(x.event_id)) {
      return {
        ...x,
        sync_status: "synced",
        synced_at: new Date().toISOString()
      };
    }
    return x;
  });

  rnSaveQueue(updated);

  return result;
}

async function rnPullLatest(eventId) {
  const data = await rnFetch(`/sync/pull/${eventId}`);
  localStorage.setItem(`rn_sync_cache_${eventId}`, JSON.stringify({
    cached_at: new Date().toISOString(),
    data
  }));
  return data;
}

async function rnTriggerSync(reason = "manual") {
  const now = Date.now();

  if (RN_SYNC_RUNNING) {
    rnSyncStatus("Sync already running, skipped.");
    return;
  }

  // anti double trigger: jangan sync berkali-kali dalam 3 detik
  if (now - RN_LAST_SYNC_AT < 3000) {
    rnSyncStatus("Sync recently triggered, skipped.");
    return;
  }

  if (!navigator.onLine) {
    rnSyncStatus("Offline. Sync pending until online.");
    return;
  }

  RN_SYNC_RUNNING = true;
  RN_LAST_SYNC_AT = now;

  const eventId = rnGetEventId();

  try {
    rnSyncStatus(`Sync started: ${reason}`);

    const pushResult = await rnPushPending();
    const pullData = await rnPullLatest(eventId);

    const pendingCount = rnGetQueue().filter(x => x.sync_status !== "synced").length;

    rnSyncStatus(
      `Synced. accepted=${pushResult.accepted_count || 0}, rejected=${pushResult.rejected_count || 0}, pending=${pendingCount}`
    );

    window.dispatchEvent(new CustomEvent("rn:sync-complete", {
      detail: {
        reason,
        event_id: eventId,
        push_result: pushResult,
        pull_data: pullData
      }
    }));

  } catch (err) {
    rnSyncStatus(`Sync failed: ${err.message}`);
  } finally {
    RN_SYNC_RUNNING = false;
  }
}

function rnSetupAutoSync() {
  rnSyncStatus(navigator.onLine ? "Online. Ready to sync." : "Offline. Local mode.");

  // Saat halaman dibuka dan online: sync sekali
  if (navigator.onLine) {
    setTimeout(() => rnTriggerSync("page-open"), 800);
  }

  // Saat internet kembali: sync otomatis
  window.addEventListener("online", () => {
    rnSyncStatus("Back online. Auto sync triggered.");
    rnTriggerSync("back-online");
  });

  // Saat offline: ubah status saja
  window.addEventListener("offline", () => {
    rnSyncStatus("Offline. New input will be saved locally.");
  });

  // Saat user balik ke tab/app: sync, tapi tidak terlalu sering
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden && navigator.onLine) {
      rnTriggerSync("app-visible");
    }
  });

  // Saat window focus lagi
  window.addEventListener("focus", () => {
    if (navigator.onLine) {
      rnTriggerSync("window-focus");
    }
  });

  // Tombol manual optional
  document.addEventListener("click", e => {
    const btn = e.target.closest("[data-rn-sync-now]");
    if (btn) {
      rnTriggerSync("manual-button");
    }
  });
}

window.RNSync = {
  queueEvent: rnQueueEvent,
  triggerSync: rnTriggerSync,
  getQueue: rnGetQueue,
  saveQueue: rnSaveQueue,
  getDeviceId: rnGetDeviceId,
  getEventId: rnGetEventId
};

document.addEventListener("DOMContentLoaded", rnSetupAutoSync);
