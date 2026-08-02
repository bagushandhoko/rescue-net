import json
from datetime import datetime, timezone

import frappe


OPEN_NEED_STATUSES = {"open", "pending", "requested", "active", "needs_review", "self_reported"}
ACTIVE_POSKO_STATUSES = {"active", "open", "operational", "verified", "self_reported"}


def build_shadow_snapshot():
    payload = _build_payload()
    doc = _upsert_snapshot(payload)
    frappe.db.commit()
    return {
        "snapshot": doc.name,
        "active_posko_count": doc.active_posko_count,
        "open_need_count": doc.open_need_count,
        "aid_offer_count": doc.aid_offer_count,
        "distribution_flow_count": doc.distribution_flow_count,
        "payload": payload,
    }


def preview_shadow_snapshot():
    return _build_payload()


def _build_payload():
    events = frappe.get_all("RN Disaster Event", fields=["name", "title", "event_status", "severity"])
    event_rows = []
    for event in events:
        event_rows.append(
            {
                "name": event.name,
                "title": event.title,
                "event_status": event.event_status,
                "severity": event.severity,
            }
        )

    needs = frappe.get_all("RN Logistic Need", fields=["name", "need_status", "quantity", "unit", "item_name"])
    offers = frappe.get_all("RN Aid Offer", fields=["name", "offer_status", "quantity", "unit", "item_name"])
    flows = frappe.get_all("RN Distribution Flow", fields=["name", "flow_status"])
    poskos = frappe.get_all("RN Posko", fields=["name", "posko_type"])

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "shadow-p0",
        "events": event_rows,
        "counts": {
            "disaster_events": len(events),
            "organizations": frappe.db.count("RN Organization"),
            "poskos": len(poskos),
            "logistic_needs": len(needs),
            "aid_offers": len(offers),
            "distribution_flows": len(flows),
        },
        "metrics": {
            "active_posko_count": _active_posko_count(poskos),
            "open_need_count": _open_need_count(needs),
            "aid_offer_count": len(offers),
            "distribution_flow_count": len(flows),
        },
        "breakdowns": {
            "need_status": _count_by(needs, "need_status"),
            "offer_status": _count_by(offers, "offer_status"),
            "flow_status": _count_by(flows, "flow_status"),
            "posko_type": _count_by(poskos, "posko_type"),
        },
    }


def _upsert_snapshot(payload):
    legacy_id = "shadow-war-room:p0"
    existing = frappe.db.exists("RN War Room Snapshot", {"legacy_id": legacy_id})
    doc = frappe.get_doc("RN War Room Snapshot", existing) if existing else frappe.new_doc("RN War Room Snapshot")
    doc.legacy_id = legacy_id
    doc.legacy_source = "frappe-shadow"
    doc.migration_status = "Shadow Imported"
    doc.title = "Shadow P0 War Room Snapshot"
    doc.active_posko_count = payload["metrics"]["active_posko_count"]
    doc.open_need_count = payload["metrics"]["open_need_count"]
    doc.aid_offer_count = payload["metrics"]["aid_offer_count"]
    doc.distribution_flow_count = payload["metrics"]["distribution_flow_count"]
    doc.snapshot_json = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)
    doc.flags.ignore_permissions = True
    doc.save()
    return doc


def _active_posko_count(poskos):
    # RN Posko currently has no operational status field in the minimal P0 schema.
    return len(poskos)


def _open_need_count(needs):
    count = 0
    for need in needs:
        status = (need.need_status or "").lower()
        if not status or status in OPEN_NEED_STATUSES:
            count += 1
    return count


def _count_by(rows, fieldname):
    result = {}
    for row in rows:
        key = row.get(fieldname) or "unknown"
        result[key] = result.get(key, 0) + 1
    return result
