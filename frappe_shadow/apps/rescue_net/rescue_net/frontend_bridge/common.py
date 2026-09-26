"""Frontend bridge — actor / event / posko resolution and field helpers."""

import base64
import math
import uuid
from collections import defaultdict

import frappe
from frappe.utils import flt, now_datetime
from frappe.utils.file_manager import save_file

from rescue_net.access_policy import (
    can_edit_event,
    editable_disaster_events,
    is_system_manager,
    rn_actor,
)
from rescue_net.reference_resolver import (
    resolve_disaster_event,
    resolve_posko,
)


OBJECT_DOCTYPE_MAP = {
    "aid_offer":
        "RN Aid Offer",
    "distribution_flow":
        "RN Distribution Flow",
    "medical_case":
        "RN Medical Case",
    "medical_supply_use":
        "RN Medical Supply Use",
    "shelter_need":
        "RN Shelter Need",
    "shelter_occupancy":
        "RN Shelter Occupancy",
    "volunteer_assignment":
        "RN Volunteer Assignment",
    "volunteer":
        "RN Volunteer Profile",
    "resource":
        "RN Resource Profile",
    "resource_profile":
        "RN Resource Profile",
    "resource_request":
        "RN Resource Request",
    "meal_production":
        "RN Kitchen Production",
}


def _actor():
    actor = rn_actor()

    if not actor:
        frappe.throw(
            "Login Rescue-Net diperlukan",
            frappe.PermissionError,
        )

    return actor


def _require_event_edit(event):
    """Gate for Data Konsolidasi WRITE actions: logged in AND the actor's
    organisation actually operates a posko in this disaster event (or the
    actor is a System Manager, who may edit every event). Viewing is open
    to guests (see the guest-safe read endpoints below) — this only gates
    writes."""
    actor = _actor()

    if not can_edit_event(actor, event):
        frappe.throw(
            "Anda tidak punya akses edit untuk bencana ini — "
            "organisasi Anda tidak menangani bencana ini.",
            frappe.PermissionError,
        )

    return actor


def _canonical_event(value):
    if not value:
        return None

    resolved = resolve_disaster_event(
        value
    )

    if not resolved:
        frappe.throw(
            "Disaster Event tidak ditemukan"
        )

    return resolved


def _canonical_posko(value):
    if not value:
        return None

    resolved = resolve_posko(
        value
    )

    return resolved or None


def _meta_fields(doctype):
    meta = frappe.get_meta(doctype)
    return {
        df.fieldname
        for df in meta.fields
        if df.fieldname
    }


def _safe_fields(doctype, wanted):
    valid = _meta_fields(doctype)

    return [
        x
        for x in wanted
        if x == "name" or x in valid
    ]


def _row_value(row, *names):
    for name in names:
        value = (
            row.get(name)
            if isinstance(row, dict)
            else getattr(row, name, None)
        )

        if value not in (
            None,
            "",
        ):
            return value

    return None


DUPLICATE_RADIUS_KM = 3.0
