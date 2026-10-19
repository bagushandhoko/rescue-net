"""Offline outbox replay (owner 2026-10-19: field forms must work without signal).

A field form saved without a connection is kept on the phone by
assets/js/rn-offline-outbox.js with a client id, and sent here when the
signal returns. `replay` runs the SAME whitelisted method the form would
have called, as the logged-in user (all permission checks stay in that
method), exactly once per client id: the id is the unique `event_id` of an
RN Sync Log row written in the same transaction, so a second send of the
same item (flaky signal, two tabs) returns the stored result instead of
recording it twice. Only the field-form methods below may be replayed.
"""

import json
import re

import frappe
from frappe.utils import now_datetime

# dotted path the page calls -> short label for the sync log / outbox list
OFFLINE_METHODS = {
    "rescue_net.api_logistics.create_need": "Kebutuhan posko",
    "rescue_net.api_logistics.create_stock_observation": "Catat stok",
    "rescue_net.api_logistics.receive_aid_offer_and_update_stock": "Terima kiriman",
    "rescue_net.api_logistics.confirm_reported_need": "Konfirmasi kebutuhan",
    "rescue_net.api_control_centre.set_posko_beneficiary": "Jiwa dilayani",
    "rescue_net.api_medical.create_case": "Pasien baru",
    "rescue_net.api_medical.update_case_status": "Status pasien",
    "rescue_net.api_medical.record_supply_use": "Pemakaian obat/alat",
    "rescue_net.api_shelter.create_occupancy": "Okupansi shelter",
    "rescue_net.api_shelter.create_need": "Kebutuhan shelter",
    "rescue_net.api_kitchen.create_production": "Produksi dapur",
    "rescue_net.api_resource_tools.create_work_object": "Kondisi lapangan",
    "rescue_net.api_recovery.create_update": "Progres recovery",
}

_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{8,120}$")


def _json(value):
    try:
        return json.dumps(value, default=str, ensure_ascii=False)
    except Exception:
        return json.dumps(str(value))


@frappe.whitelist(methods=["POST"])
def replay(method, args=None, client_event_id=None, device_id=None, created_local_at=None):
    user = frappe.session.user
    if not user or user == "Guest":
        frappe.throw("Login diperlukan untuk mengirim data offline.", frappe.PermissionError)
    if method not in OFFLINE_METHODS:
        frappe.throw("Formulir ini tidak bisa dikirim lewat antrean offline.", frappe.PermissionError)
    eid = str(client_event_id or "").strip()
    if not _ID_RE.match(eid):
        frappe.throw("ID antrean offline tidak valid.")
    eid = "offline:" + eid

    done = frappe.db.get_value("RN Sync Log", {"event_id": eid},
                               ["source_user_id", "apply_result_json"], as_dict=True)
    if done:
        if done.source_user_id != user:
            frappe.throw("ID antrean offline milik pengguna lain.", frappe.PermissionError)
        try:
            result = json.loads(done.apply_result_json or "null")
        except ValueError:
            result = None
        return {"duplicate": True, "result": result}

    if isinstance(args, str):
        args = json.loads(args or "{}")
    if not isinstance(args, dict):
        frappe.throw("Isi antrean offline tidak valid.")
    args = {k: v for k, v in args.items() if k not in ("cmd", "csrf_token")}

    # claim the id first: the unique event_id makes a concurrent second send
    # fail here, and an error in the method rolls the claim back with it
    log = frappe.get_doc({
        "doctype": "RN Sync Log",
        "event_id": eid,
        "object_type": "offline_call",
        "operation": method,
        "source_user_id": user,
        "source_device_id": str(device_id or "")[:140] or None,
        "payload_json": _json(args),
        "apply_status": "accepted",
        "received_at": now_datetime(),
    })
    log.insert(ignore_permissions=True)

    fn = frappe.get_attr(method)
    frappe.is_whitelisted(fn)
    frappe.local.form_dict = frappe._dict(args)
    result = frappe.call(fn, **args)

    log.db_set({"apply_status": "applied", "apply_result_json": _json(result),
                "applied_at": now_datetime()}, update_modified=False)
    return {"duplicate": False, "result": result}

