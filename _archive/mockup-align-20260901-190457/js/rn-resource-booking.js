function rnBookingStatus(msg) {
  const el =
    document.querySelector(
      "[data-rn-booking-status]"
    ) ||
    document.getElementById(
      "rnBookingStatus"
    ) ||
    document.getElementById(
      "warRoomStatus"
    ) ||
    document.getElementById(
      "rnSyncStatus"
    );

  if (el) {
    el.textContent = msg;
  }
}


async function rnCreateResourceRequestOfflineReady(
  payload = {}
) {
  if (!window.RN_FRAPPE) {
    throw new Error(
      "Frappe client tidak tersedia"
    );
  }

  rnBookingStatus(
    "Saving Work Tool Request..."
  );

  const result =
    await RN_FRAPPE.call(
      "rescue_net.api_resource_tools." +
      "create_work_tool_request",
      {
        tool_name:
          payload.tool_name ||
          payload.resource_name ||
          payload.item_name ||
          "Resource",

        requested_by_type:
          payload.requested_by_type ||
          payload.owner_type ||
          "posko",

        requested_by_id:
          payload.requested_by_id ||
          payload.owner_id ||
          payload.posko ||
          null,

        disaster_event:
          payload.disaster_event ||
          payload.disaster_event_id ||
          payload.event_id ||
          null,

        tool_type:
          payload.tool_type ||
          payload.resource_type ||
          null,

        quantity:
          Number(
            payload.quantity ||
            payload.quantity_requested ||
            1
          ),

        unit:
          payload.unit ||
          "unit",

        location:
          payload.location ||
          payload.destination_location ||
          null,

        needed_for:
          payload.needed_for ||
          payload.purpose ||
          null,

        priority:
          payload.priority ||
          "normal",

        required_operator_skill:
          payload.required_operator_skill ||
          payload.operator_skill ||
          null,

        notes:
          payload.notes ||
          null
      },
      {
        method: "POST"
      }
    );

  rnBookingStatus(
    "Resource request saved in Frappe."
  );

  return result;
}


window.rnCreateResourceRequestOfflineReady =
  rnCreateResourceRequestOfflineReady;
