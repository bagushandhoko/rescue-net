const RN_RESOURCE_API_BASE = window.RN_API_BASE || "http://192.168.100.32:8092";

function rnBookingStatus(msg) {
  const el =
    document.querySelector("[data-rn-booking-status]") ||
    document.getElementById("rnBookingStatus") ||
    document.getElementById("warRoomStatus") ||
    document.getElementById("rnSyncStatus");

  if (el) el.textContent = msg;
  console.log("[RN Booking]", msg);
}

async function rnBookingFetch(path, options = {}) {
  const res = await fetch(RN_RESOURCE_API_BASE + path, {
    headers: { "Content-Type": "application/json" },
    ...options
  });

  if (!res.ok) throw new Error(await res.text());
  return await res.json();
}

async function rnCreateResourceRequestOfflineReady(payload) {
  const eventId =
    payload.disaster_event_id ||
    (window.RNSync ? window.RNSync.getEventId() : "event-aceh-2025");

  const normalized = {
    disaster_event_id: eventId,
    resource_id: payload.resource_id,
    requested_by_type: payload.requested_by_type || "posko",
    requested_by_id: payload.requested_by_id,
    request_reason: payload.request_reason,
    related_need_id: payload.related_need_id || null,
    related_distribution_flow_id: payload.related_distribution_flow_id || null,
    requested_quantity: Number(payload.requested_quantity || 1),
    requested_time: payload.requested_time || "secepatnya"
  };

  if (!navigator.onLine) {
    if (!window.RNSync) throw new Error("RNSync engine not loaded");

    const draft = window.RNSync.queueEvent({
      object_type: "resource_request",
      object_id: "local-resource-request-" + Date.now(),
      operation: "create",
      payload_json: normalized,
      source_user_id: "field-user-demo",
      source_organization_id: normalized.requested_by_id
    });

    rnBookingStatus(`Offline booking saved. Will sync when online: ${draft.event_id}`);
    return { local_saved: true, draft };
  }

  try {
    const result = await rnBookingFetch("/resource-requests", {
      method: "POST",
      body: JSON.stringify(normalized)
    });

    rnBookingStatus("Booking sent to server.");
    return result;

  } catch (err) {
    if (!window.RNSync) throw err;

    const draft = window.RNSync.queueEvent({
      object_type: "resource_request",
      object_id: "local-resource-request-" + Date.now(),
      operation: "create",
      payload_json: normalized,
      source_user_id: "field-user-demo",
      source_organization_id: normalized.requested_by_id
    });

    rnBookingStatus(`Server failed. Saved locally for sync: ${draft.event_id}`);
    return { local_saved: true, draft, server_error: err.message };
  }
}

window.RNResourceBooking = {
  createResourceRequest: rnCreateResourceRequestOfflineReady
};
