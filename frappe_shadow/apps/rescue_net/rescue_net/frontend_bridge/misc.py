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


@frappe.whitelist()
def create_disaster_event(
    payload_json=None,
):
    _actor()

    import json

    try:
        payload = (
            json.loads(payload_json)
            if payload_json
            else {}
        )
    except Exception:
        frappe.throw(
            "Payload Disaster Event tidak valid"
        )

    if not isinstance(
        payload,
        dict,
    ):
        frappe.throw(
            "Payload Disaster Event harus object"
        )

    meta = frappe.get_meta(
        "RN Disaster Event"
    )

    valid = {
        df.fieldname
        for df in meta.fields
        if df.fieldname
    }

    aliases = {
        "name":
            "title",

        "disaster_name":
            "title",

        "event_name":
            "title",

        "disaster_type":
            "event_type",

        "type":
            "event_type",

        "location":
            "location_text",

        "status":
            "event_status",
    }

    values = {}

    for key, value in payload.items():
        target = aliases.get(
            key,
            key,
        )

        if (
            target in valid
            and value not in (
                None,
                "",
            )
        ):
            values[target] = value

    # Cari title dari beberapa nama legacy.
    if (
        "title" in valid
        and not values.get("title")
    ):
        for key in (
            "title",
            "name",
            "event_name",
            "disaster_name",
        ):
            if payload.get(key):
                values["title"] = (
                    payload[key]
                )
                break

    if (
        "title" in valid
        and not values.get("title")
    ):
        frappe.throw(
            "Nama Disaster Event wajib diisi"
        )

    doc = frappe.new_doc(
        "RN Disaster Event"
    )

    for key, value in values.items():
        doc.set(
            key,
            value,
        )

    doc.insert(
        ignore_permissions=True
    )

    return {
        "id":
            doc.name,

        "name":
            doc.name,

        "title":
            getattr(
                doc,
                "title",
                None,
            ),

        "event_status":
            getattr(
                doc,
                "event_status",
                None,
            ),
    }
