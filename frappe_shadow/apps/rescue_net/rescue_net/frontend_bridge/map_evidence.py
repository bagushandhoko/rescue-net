"""Frontend bridge — map context and points, evidence context and upload."""

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
    OBJECT_DOCTYPE_MAP,
    _actor,
    _canonical_event,
    _canonical_posko,
)


@frappe.whitelist()
def map_context(
    disaster_event,
):
    _actor()

    event = _canonical_event(
        disaster_event
    )

    rows = frappe.get_all(
        "RN Map Point",
        filters={
            "disaster_event":
                event
        },
        fields=[
            "name",
            "disaster_event",
            "object_type",
            "object_id",
            "label",
            "description",
            "latitude",
            "longitude",
            "location_text",
            "point_status",
            "priority",
            "creation",
            "modified",
        ],
        order_by="creation desc",
        limit_page_length=3000,
    )

    points = []

    for row in rows:
        item = dict(row)
        item["id"] = row.name
        item["created_at"] = (
            row.creation
        )
        item["updated_at"] = (
            row.modified
        )
        points.append(item)

    summary = {
        "total_points":
            len(points),
        "active_points":
            sum(
                1
                for p in points
                if (
                    p.get(
                        "point_status"
                    )
                    in (
                        "active",
                        "open",
                        None,
                        "",
                    )
                )
            ),
        "urgent_points":
            sum(
                1
                for p in points
                if p.get("priority")
                in (
                    "urgent",
                    "critical",
                )
            ),
    }

    return {
        "disaster_event_id":
            event,
        "points":
            points,
        "map_points":
            points,
        "summary":
            summary,
        "generated_at":
            now_datetime(),
    }


@frappe.whitelist()
def create_map_point(
    disaster_event,
    object_type=None,
    object_id=None,
    label=None,
    description=None,
    latitude=None,
    longitude=None,
    location_text=None,
    point_status="active",
    priority="normal",
):
    actor = _actor()

    event = _canonical_event(
        disaster_event
    )

    label = (
        str(label or "").strip()
    )

    if not label:
        frappe.throw(
            "Label map point wajib diisi"
        )

    doc = frappe.new_doc(
        "RN Map Point"
    )

    doc.disaster_event = event
    doc.object_type = object_type
    doc.object_id = object_id
    doc.label = label
    doc.description = description
    doc.latitude = flt(latitude)
    doc.longitude = flt(longitude)
    doc.location_text = location_text
    doc.point_status = (
        point_status or "active"
    )
    doc.priority = (
        priority or "normal"
    )
    doc.observed_at = now_datetime()

    if getattr(
        actor,
        "name",
        None,
    ):
        doc.created_by_user = (
            actor.name
        )

    doc.insert(
        ignore_permissions=True
    )

    return {
        "id":
            doc.name,
        "map_point":
            doc.name,
        "disaster_event_id":
            doc.disaster_event,
        "label":
            doc.label,
        "point_status":
            doc.point_status,
        "priority":
            doc.priority,
    }


def _set_if(
    doc,
    fieldname,
    value,
):
    if (
        value is not None
        and doc.meta.has_field(
            fieldname
        )
    ):
        doc.set(
            fieldname,
            value,
        )


def _evidence_rows(
    disaster_event=None,
):
    meta = frappe.get_meta(
        "RN Evidence File"
    )

    wanted = [
        "name",
        "disaster_event",
        "posko",
        "node_id",
        "reference_doctype",
        "reference_name",
        "linked_doctype",
        "linked_name",
        "linked_object_type",
        "linked_object_id",
        "object_type",
        "object_id",
        "file_url",
        "file_name",
        "evidence_type",
        "caption",
        "verification_status",
        "uploaded_by",
        "created_by_user",
        "observed_at",
        "creation",
        "modified",
    ]

    valid = set(
        meta.get_valid_columns()
    )

    fields = [
        x
        for x in wanted
        if (
            x == "name"
            or x in valid
        )
    ]

    filters = {}

    if (
        disaster_event
        and "disaster_event" in valid
    ):
        filters["disaster_event"] = (
            disaster_event
        )

    rows = frappe.get_all(
        "RN Evidence File",
        filters=filters,
        fields=fields,
        order_by="creation desc",
        limit_page_length=3000,
    )

    result = []

    for row in rows:
        item = dict(row)

        item["id"] = row.name

        item.setdefault(
            "linked_object_type",
            item.get(
                "object_type"
            )
            or item.get(
                "reference_doctype"
            )
            or item.get(
                "linked_doctype"
            ),
        )

        item.setdefault(
            "linked_object_id",
            item.get(
                "object_id"
            )
            or item.get(
                "reference_name"
            )
            or item.get(
                "linked_name"
            ),
        )

        item.setdefault(
            "created_at",
            item.get("creation"),
        )

        result.append(item)

    return result


@frappe.whitelist()
def evidence_context(
    disaster_event=None,
):
    _actor()

    event = (
        _canonical_event(
            disaster_event
        )
        if disaster_event
        else None
    )

    # Unified feed shared with the Control Centre "Bukti Lapangan" panel so
    # both surfaces show the same evidence records for an event.
    try:
        from rescue_net.api_control_centre import event_evidence

        if event:
            unified = event_evidence(event) or []

            if unified:
                return unified
    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            "evidence_context unified feed",
        )

    return _evidence_rows(
        event
    )


@frappe.whitelist()
def upload_evidence(
    filename,
    content_base64,
    disaster_event,
    node_id=None,
    linked_object_type=None,
    linked_object_id=None,
    evidence_type="photo",
    uploaded_by=None,
    caption=None,
):
    actor = _actor()

    event = _canonical_event(
        disaster_event
    )

    if not filename:
        frappe.throw(
            "Nama file wajib diisi"
        )

    if not content_base64:
        frappe.throw(
            "Isi file kosong"
        )

    try:
        content = base64.b64decode(
            content_base64
        )
    except Exception:
        frappe.throw(
            "Base64 evidence tidak valid"
        )

    if not content:
        frappe.throw(
            "File evidence kosong"
        )

    file_doc = save_file(
        filename,
        content,
        None,
        None,
        is_private=1,
    )

    evidence = frappe.new_doc(
        "RN Evidence File"
    )

    _set_if(
        evidence,
        "disaster_event",
        event,
    )

    posko = (
        _canonical_posko(node_id)
        if node_id
        else None
    )

    _set_if(
        evidence,
        "posko",
        posko,
    )

    _set_if(
        evidence,
        "node_id",
        node_id,
    )

    _set_if(
        evidence,
        "file_url",
        file_doc.file_url,
    )

    _set_if(
        evidence,
        "file_name",
        filename,
    )

    _set_if(
        evidence,
        "evidence_type",
        evidence_type,
    )

    _set_if(
        evidence,
        "caption",
        caption,
    )

    _set_if(
        evidence,
        "verification_status",
        "pending",
    )

    _set_if(
        evidence,
        "uploaded_by",
        uploaded_by,
    )

    if getattr(
        actor,
        "name",
        None,
    ):
        _set_if(
            evidence,
            "created_by_user",
            actor.name,
        )

    ref_doctype = (
        OBJECT_DOCTYPE_MAP.get(
            linked_object_type
        )
    )

    for fieldname in (
        "linked_object_type",
        "object_type",
    ):
        _set_if(
            evidence,
            fieldname,
            linked_object_type,
        )

    for fieldname in (
        "linked_object_id",
        "object_id",
    ):
        _set_if(
            evidence,
            fieldname,
            linked_object_id,
        )

    if ref_doctype:
        _set_if(
            evidence,
            "reference_doctype",
            ref_doctype,
        )

        _set_if(
            evidence,
            "linked_doctype",
            ref_doctype,
        )

    _set_if(
        evidence,
        "reference_name",
        linked_object_id,
    )

    _set_if(
        evidence,
        "linked_name",
        linked_object_id,
    )

    _set_if(
        evidence,
        "observed_at",
        now_datetime(),
    )

    evidence.insert(
        ignore_permissions=True
    )

    return {
        "id":
            evidence.name,
        "evidence":
            evidence.name,
        "file_url":
            file_doc.file_url,
        "private":
            True,
        "verification_status":
            getattr(
                evidence,
                "verification_status",
                None,
            ),
    }
