"""Chain of custody for aid shipments: every QR scan (dispatch / transit /
handover / arrive / receive) is appended to RN Custody Scan and, where it
maps to a status, advances the RN Distribution Flow through the SAME graph
(TRANSITIONS) the rest of the app uses. `receive` goes through
receive_flow_and_update_stock, never a shortcut.

Scans may arrive late from an offline queue: `offline_id` makes a replay
idempotent and `scanned_at` keeps the real scan time.
"""

import frappe
from frappe.rate_limiter import rate_limit
from frappe.utils import flt, get_datetime, now_datetime

from rescue_net.access_policy import rn_actor
from rescue_net.control_centre.distribusi import _resolve_flow_by_trace
from rescue_net.logistics.common import _can_operate
from rescue_net.logistics.flows import update_flow_status
from rescue_net.logistics.receipts import receive_flow_and_update_stock
from rescue_net.rn_logistics.doctype.rn_distribution_flow.rn_distribution_flow import TRANSITIONS

SCAN_STATUS = {
    "dispatch": "dispatched",
    "transit": "in_transit",
    "arrive": "arrived_at_posko",
    "receive": "received",
    "handover": None,  # custody change only, no status change
}

# statuses at or past each target — a replayed scan must not fail or regress
_PAST = {
    "dispatched": {"dispatched", "in_transit", "arrived_at_posko", "partially_received", "received"},
    "in_transit": {"in_transit", "arrived_at_posko", "partially_received", "received"},
    "arrived_at_posko": {"arrived_at_posko", "partially_received", "received"},
    "received": {"received"},
}


def _scan_row(d):
    return {
        "name": d.name, "scan_type": d.scan_type, "outcome": d.outcome,
        "actor": d.actor, "scanned_at": str(d.scanned_at or ""),
        "status_before": d.status_before, "status_after": d.status_after,
        "note": d.note,
    }


@frappe.whitelist()
@rate_limit(limit=120, seconds=60)
def record_scan(flow=None, trace=None, scan_type=None, offline_id=None,
                scanned_at=None, latitude=None, longitude=None, note=None,
                received_quantity=None, received_unit=None):
    """Record one custody scan for a shipment. Operators of the source or
    destination posko only (same rule as update_flow_status)."""
    actor = rn_actor()
    if scan_type not in SCAN_STATUS:
        frappe.throw("Jenis scan tidak dikenal.")

    name = str(flow or "").strip() or (_resolve_flow_by_trace(trace) if trace else None)
    if not name or not frappe.db.exists("RN Distribution Flow", name):
        frappe.throw("Kiriman tidak ditemukan.", frappe.DoesNotExistError)

    offline_id = (str(offline_id).strip()[:140] or None) if offline_id else None
    if offline_id:
        prev = frappe.db.get_value("RN Custody Scan", {"offline_id": offline_id}, "name")
        if prev:  # idempotent replay
            return {"ok": True, "duplicate": True,
                    "scan": _scan_row(frappe.get_doc("RN Custody Scan", prev))}

    f = frappe.db.get_value(
        "RN Distribution Flow", name,
        ["source_posko", "destination_posko", "flow_status"], as_dict=True)
    posko = None
    for p in (f.source_posko, f.destination_posko):
        if p and _can_operate(actor, p):
            posko = p
            break
    if not posko:
        frappe.throw("Anda tidak dapat memindai kiriman ini", frappe.PermissionError)
    if scan_type == "receive" and not (f.destination_posko and _can_operate(actor, f.destination_posko)):
        frappe.throw("Hanya posko tujuan yang dapat mencatat penerimaan", frappe.PermissionError)

    before = f.flow_status or "planned"
    target = SCAN_STATUS[scan_type]
    outcome, after, reason = "recorded", before, None

    if target:
        if before in _PAST[target]:
            outcome = "already"
        elif target not in TRANSITIONS.get(before, set()):
            outcome = "rejected"
            reason = f"Transisi {before} → {target} tidak diperbolehkan"
        else:
            if scan_type == "receive":
                receive_flow_and_update_stock(
                    name, received_quantity, received_unit, note)
            else:
                update_flow_status(name, target)
            outcome = "applied"
            after = frappe.db.get_value("RN Distribution Flow", name, "flow_status")

    try:
        when = get_datetime(scanned_at) if scanned_at else now_datetime()
    except Exception:
        when = now_datetime()

    doc = frappe.get_doc({
        "doctype": "RN Custody Scan", "flow": name, "scan_type": scan_type,
        "outcome": outcome, "actor": actor.name, "posko": posko,
        "scanned_at": when, "received_at_server": now_datetime(),
        "latitude": flt(latitude) or None, "longitude": flt(longitude) or None,
        "offline_id": offline_id, "status_before": before, "status_after": after,
        "note": ((note or "") + ((" | " + reason) if reason else ""))[:1000] or None,
    })
    doc.insert(ignore_permissions=True)
    return {"ok": outcome != "rejected", "duplicate": False,
            "reason": reason, "scan": _scan_row(doc)}


@frappe.whitelist()
def custody_chain(flow=None, trace=None):
    """Full custody log of one shipment for its operators (source/destination)."""
    actor = rn_actor()
    name = str(flow or "").strip() or (_resolve_flow_by_trace(trace) if trace else None)
    if not name or not frappe.db.exists("RN Distribution Flow", name):
        frappe.throw("Kiriman tidak ditemukan.", frappe.DoesNotExistError)
    f = frappe.db.get_value("RN Distribution Flow", name,
                            ["source_posko", "destination_posko"], as_dict=True)
    if not any(p and _can_operate(actor, p) for p in (f.source_posko, f.destination_posko)):
        frappe.throw("Tidak diizinkan", frappe.PermissionError)
    rows = frappe.get_all(
        "RN Custody Scan", filters={"flow": name},
        fields=["name", "scan_type", "outcome", "actor", "scanned_at",
                "status_before", "status_after", "note"],
        order_by="scanned_at asc, creation asc", limit_page_length=200)
    return {"flow": name, "scans": rows}
