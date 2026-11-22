"""Federation projections and record eligibility. Unlisted types and values stay local."""

import json
from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from uuid import UUID

import frappe
from frappe.utils import cint

from rescue_net.access_policy import public_posko_allowed
from rescue_net.rn_logistics.doctype.rn_distribution_flow.rn_distribution_flow import VALID_STATES
from rescue_net.services.admin_area_codes import CODE_RE
from rescue_net.services.drill import is_simulation_event

NEVER, AGGREGATE, FULL = "never", "aggregate", "full"
EVENT, POSKO = "RN Disaster Event", "RN Posko"
NEED, OFFER, FLOW, AREA = "RN Logistic Need", "RN Aid Offer", "RN Distribution Flow", "RN Admin Area"


@dataclass(frozen=True)
class Policy:
    fields: dict
    classification: str = FULL
    status_field: str = ""

    def field_classification(self, field):
        return self.classification if field in self.fields else NEVER


def choice(*allowed):
    return lambda value: value if isinstance(value, str) and value in allowed else None


def number(value):
    if isinstance(value, (float, int)) and isfinite(value) and 0 <= value <= 10**12:
        return value
    return None


def area_code(value):
    return value if isinstance(value, str) and CODE_RE.fullmatch(value) else None


def uid(value):
    try:
        return str(UUID(value))
    except (ValueError, TypeError, AttributeError):
        return None


def reference(doctype):
    def project(name):
        return uid(frappe.db.get_value(doctype, name, "uid")) if name else None
    return project


_EVENT_REF = {"disaster_event": reference(EVENT)}
_LOGISTICS = {"quantity": number, "quantity_min": number, "quantity_max": number,
              "quantity_mode": choice("exact", "estimated", "range", "unknown"),
              "unit": choice("kg", "g", "ton", "l", "liter", "ml", "pcs", "unit", "paket", "dus", "karung", "botol")}
POLICIES = {
    EVENT: Policy({
        "event_status": choice("active", "closed", "resolved", "archived", "monitoring"),
        "severity": choice("low", "medium", "high", "critical"),
        "event_type": choice("earthquake", "flood", "landslide", "drought", "fire", "tsunami", "volcano",
                             "gempa", "banjir", "longsor", "kekeringan", "kebakaran"),
    }, status_field="event_status"),
    POSKO: Policy({
        **_EVENT_REF,
        "admin_area_id": area_code,
        "posko_type": choice("shelter", "distribution", "logistics", "kitchen", "medical", "volunteer", "transport", "recovery",
                             "command_center", "equipment"),
        "operational_status": choice("active", "open", "closed", "inactive", "standby"),
    }, status_field="operational_status"),
    NEED: Policy({
        **_EVENT_REF, **_LOGISTICS, "posko": reference(POSKO),
        "need_kind": choice("obat", "alat", "logistik", "makanan_air", "sanitasi", "lainnya"),
        "need_status": choice("open", "partial", "fulfilled", "closed", "cancelled"),
        "urgency": choice("low", "medium", "high", "critical", "urgent", "normal"),
    }, status_field="need_status"),
    OFFER: Policy({
        **_EVENT_REF, **_LOGISTICS, "target_posko": reference(POSKO),
        "offer_status": choice("available", "need_pickup", "reserved", "pickup_claimed", "in_transit", "delivered", "cancelled"),
    }, status_field="offer_status"),
    FLOW: Policy({
        **_EVENT_REF, "source_posko": reference(POSKO), "destination_posko": reference(POSKO),
        "flow_status": choice(*VALID_STATES),
    }, status_field="flow_status"),
    AREA: Policy({"code": area_code, "parent_code": area_code,
                  "level": choice("province", "city", "district", "village"), "enabled": choice("0", "1")}),
}


def _event_allowed(event):
    return bool(event and cint(event.federation_share) and not cint(event.is_drill)
                and POLICIES[EVENT].fields["event_status"](event.event_status)
                and not is_simulation_event(event.name))


def _posko_allowed(name, event):
    if not name or not public_posko_allowed(name):
        return False
    row = frappe.db.get_value(POSKO, name, ["disaster_event", "federation_share"], as_dict=True)
    return bool(row and cint(row.federation_share) and row.disaster_event == event)


def eligible(doc):
    if doc.doctype == AREA:
        return bool(area_code(doc.code))
    if not cint(doc.get("federation_share")):
        return False
    if doc.doctype == EVENT:
        return _event_allowed(doc)
    event = doc.get("disaster_event")
    event_row = frappe.db.get_value(
        EVENT, event, ["name", "federation_share", "is_drill", "event_status"], as_dict=True,
    ) if event else None
    if not _event_allowed(event_row):
        return False
    if doc.doctype == POSKO:
        return doc.public_detail == "public" and _posko_allowed(doc.name, event)
    if doc.doctype == NEED:
        return _posko_allowed(doc.posko, event)
    if doc.doctype == OFFER:
        return _posko_allowed(doc.target_posko, event)
    if doc.doctype == FLOW:
        return _posko_allowed(doc.destination_posko, event) and (
            not doc.source_posko or _posko_allowed(doc.source_posko, event)
        )
    return False


def project(doc):
    policy = POLICIES.get(doc.doctype)
    if not policy or policy.classification != FULL:
        return {}
    result = {}
    for field, convert in policy.fields.items():
        value = doc.get(field)
        if doc.doctype == AREA and field == "enabled":
            value = str(cint(value))
        value = convert(value)
        if value is not None:
            result[field] = value
    return result


# This snapshot ships with Frappe because the web catalog is deployed
# separately. Update it with the TERBUKA entries and template_tambahan.
OPEN_MENUS = json.loads(Path(__file__).with_name("open_menus.json").read_text(encoding="utf-8"))
CATEGORIES = ("pangan", "air", "kesehatan", "shelter", "sanitasi", "transportasi", "lainnya")


def _count(value):
    return type(value) is int and 0 <= value <= 10_000_000


def _positive(value):
    return _count(value) and value > 0


def _category(value):
    return value in CATEGORIES


def _counts(value):
    return isinstance(value, dict) and all(_category(k) and _count(n) for k, n in value.items())


def organization_key(value):
    return isinstance(value, str) and 0 < len(value) <= 140 and value.isprintable()


def _description(value):
    return isinstance(value, str) and 0 < len(value.strip()) <= len(value) <= 280 and value.isprintable()


def _menu_key(value):
    return isinstance(value, str) and value in OPEN_MENUS


INBOUND = {
    "assistance.request": {"destination": organization_key, "category": _category, "quantity": _positive,
                           "description": _description},
    "org.summary": {"active_posts": _count, "personnel": _count, "open_needs": _counts},
    "sitrep.summary": {"active_posts": _count, "open_needs": _counts},
    "need.published": {"category": _category, "quantity": _positive, "description": _description},
    "menu.record": {"menu_id": _menu_key, "record_count": _count},
}


def inbound_error(event_type, payload, template):
    rules = INBOUND.get(event_type)
    if rules is None:
        return "event_type_denied"
    if not isinstance(payload, dict) or set(payload) != set(rules):
        return "invalid_payload_fields"
    if event_type == "menu.record":
        menu = payload["menu_id"]
        allowed = OPEN_MENUS.get(menu, []) if isinstance(menu, str) else []
        if "bersama" not in allowed and template not in allowed:
            return "menu_denied"
    if not all(check(payload[field]) for field, check in rules.items()):
        return "invalid_payload_value"
    return None
