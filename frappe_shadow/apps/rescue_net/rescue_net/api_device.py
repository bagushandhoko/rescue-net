"""Offline app (apps/rescue-net-app) endpoints that had no Frappe equivalent
when FastAPI was retired (phase 3): device registration and the unit
catalogue / normaliser. Everything else the app needs already exists in
Frappe; the app's own router maps its calls onto those."""

import json

import frappe
from frappe.rate_limiter import rate_limit
from frappe.utils import cint, flt, now_datetime

from rescue_net.access_policy import can_manage_posko, rn_actor


def _profile(payload):
    if isinstance(payload, str):
        payload = json.loads(payload or "{}")
    return frappe._dict(payload or {})


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=60, seconds=60 * 60)
def register_device(payload=None):
    """Record the device of the logged-in user (RN Device, one per device id)
    with its registration profile. A device never creates an organisation or
    a posko by itself any more — that goes through the web's Registrasi &
    Verifikasi Posko flow (org membership + approval). The answer tells the
    app which posko this user already runs for the chosen event."""
    actor = rn_actor(required=True)
    p = _profile(payload)
    device_id = (p.device_id or "").strip()[:140]
    if not device_id:
        frappe.throw("device_id wajib diisi")

    # RN Device is named by legacy_id: one row per device id
    name = frappe.db.exists("RN Device", "device-" + device_id)
    doc = frappe.get_doc("RN Device", name) if name else frappe.new_doc("RN Device")
    doc.legacy_id = "device-" + device_id
    if name and doc.owner_user and doc.owner_user != actor.name:
        frappe.throw("Perangkat ini terdaftar atas akun lain.", frappe.PermissionError)
    doc.title = device_id
    doc.device_type = (p.device_type or p.platform or "mobile")[:140]
    doc.owner_user = actor.name
    doc.owner_organization = actor.get("organization")
    doc.last_seen_at = str(now_datetime())
    doc.status = "active"
    keep = {k: p.get(k) for k in ("member_name", "role", "organization_name", "posko_name", "notes",
                                   "location_text", "province_name", "city_name", "district_name",
                                   "village_name", "admin_area_id", "disaster_event_id")}
    doc.legacy_payload = json.dumps(keep, default=str)
    doc.save(ignore_permissions=True) if name else doc.insert(ignore_permissions=True)

    posko = None
    event = p.disaster_event_id if p.disaster_event_id not in (None, "", "pending-event-link") else None
    if event:
        from rescue_net.reference_resolver import resolve_disaster_event

        event = resolve_disaster_event(event)
        for row in frappe.get_all("RN Posko", filters={"disaster_event": event},
                                  fields=["name", "title", "identity_verification_status"], limit_page_length=500):
            if can_manage_posko(actor, row.name):
                posko = row
                break
    return {
        "device": doc.name,
        "organization": {"id": actor.get("organization")} if actor.get("organization") else None,
        "posko": {"id": posko.name, "title": posko.title,
                  "identity_verification_status": posko.identity_verification_status or "unverified"}
        if posko else None,
        "verification_request": None,
        "verification_url": None if posko else "../rescue-net/pages/registrasi-posko.html",
    }


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def unit_catalog():
    """Enabled unit conversions ({conversions: [...]}) for the app's unit page."""
    rows = frappe.get_all(
        "RN Unit Conversion", filters={"enabled": 1},
        fields=["canonical_item", "canonical_group", "from_unit", "to_base_unit", "factor", "certainty", "notes"],
        order_by="priority desc, canonical_item asc", limit_page_length=1000,
    )
    return {"conversions": [{
        "item_name": r.canonical_item or r.canonical_group,
        "from_unit": r.from_unit, "to_unit": r.to_base_unit, "multiplier": flt(r.factor),
        "confidence_level": r.certainty or "rule", "notes": r.notes,
    } for r in rows]}


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=120, seconds=60)
def unit_normalize(item_name=None, quantity=0, unit=None):
    """Item + unit -> canonical item / group and unit, plus the base-unit
    quantity when an enabled conversion matches (deterministic rules)."""
    from rescue_net.intelligence.normalization import classify_text, normalize_unit

    cls = classify_text(item_name or "")
    canon_unit = normalize_unit(unit)
    qty = flt(quantity)
    conv = None
    for filters in ({"canonical_item": cls.get("canonical_item")}, {"canonical_group": cls.get("canonical_group")},
                    {"scope_type": "global"}):
        if not any(filters.values()):
            continue
        conv = frappe.db.get_value("RN Unit Conversion", {**filters, "enabled": 1, "from_unit": canon_unit},
                                   ["to_base_unit", "factor", "certainty"], as_dict=True)
        if conv:
            break
    return {
        "item_name": item_name,
        "canonical_item": cls.get("canonical_item"),
        "canonical_group": cls.get("canonical_group"),
        "canonical_category": cls.get("canonical_category"),
        "unit": unit,
        "canonical_unit": canon_unit,
        "quantity": qty,
        "base_quantity": qty * flt(conv.factor) if conv else None,
        "base_unit": conv.to_base_unit if conv else None,
        "confidence": conv.certainty if conv else cint(cls.get("normalization_confidence")),
    }
