"""Frontend bridge — admin areas, disaster event creation, legacy stubs."""

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

from rescue_net.frontend_bridge.common import (  # noqa: F401
    _actor,
)


@frappe.whitelist()
def admin_area_children(
    parent_code=None,
    level=None,
):
    _actor()

    from rescue_net import api_admin_areas

    import inspect

    fn = api_admin_areas.get_children
    params = inspect.signature(fn).parameters

    kwargs = {}

    for name in params:
        if name in (
            "parent_code",
            "parent",
            "code",
        ):
            kwargs[name] = parent_code

        elif name in (
            "level",
            "child_level",
        ):
            kwargs[name] = level

    return fn(**kwargs)


@frappe.whitelist()
def unsupported_consolidation_operation(
    operation=None,
):
    _actor()

    frappe.throw(
        "Operasi konsolidasi '"
        + str(operation or "unknown")
        + "' belum memiliki model canonical Frappe. "
        "Data tidak diubah.",
        frappe.ValidationError,
    )


@frappe.whitelist()
def reject_legacy_token_verification():
    _actor()

    frappe.throw(
        "Respons verification berbasis token legacy "
        "tidak dijalankan melalui bridge umum. "
        "Gunakan workflow verifier Frappe yang "
        "terautentikasi.",
        frappe.PermissionError,
    )


@frappe.whitelist(methods=["POST"])
def create_disaster_event(
    payload_json=None,
):
    """Legacy bridge (POST /disasters). Goes through the Kelola Bencana rules
    (SOP 2026-11-01): the caller can no longer choose the status — verified
    organisations / admins get an active event, everyone else a proposal."""
    actor = _actor()

    import json

    from rescue_net.api_disaster_admin import create_event_for

    try:
        payload = json.loads(payload_json) if payload_json else {}
    except Exception:
        frappe.throw("Payload Disaster Event tidak valid")
    if not isinstance(payload, dict):
        frappe.throw("Payload Disaster Event harus object")

    title = next((payload.get(k) for k in ("title", "name", "event_name", "disaster_name") if payload.get(k)), None)
    if not title:
        frappe.throw("Nama Disaster Event wajib diisi")
    res = create_event_for(
        actor, title,
        event_type=payload.get("event_type") or payload.get("disaster_type") or payload.get("type"),
        location_summary=payload.get("location_summary") or payload.get("location") or payload.get("location_text") or "-",
        latitude=payload.get("latitude"), longitude=payload.get("longitude"),
        started_at=payload.get("started_at"), severity=payload.get("severity"),
        organization=payload.get("organization"), force=payload.get("force") or 0,
    )
    if res.get("created"):
        res["id"] = res["name"]
    return res
