import base64
import uuid

import frappe
from frappe.utils import flt, now_datetime
from frappe.utils.file_manager import save_file

from rescue_net.access_policy import rn_actor
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


def _resolve_resource(value):
    value = (
        str(value or "").strip()
    )

    if not value:
        frappe.throw(
            "Resource ID wajib diisi"
        )

    if frappe.db.exists(
        "RN Resource Profile",
        value,
    ):
        return value

    for candidate in (
        value,
        "resource_profiles:" + value,
    ):
        name = frappe.db.get_value(
            "RN Resource Profile",
            {
                "legacy_id":
                    candidate
            },
            "name",
        )

        if name:
            return name

    frappe.throw(
        "RN Resource Profile tidak ditemukan: "
        + value
    )


def _resource_rows(
    disaster_event=None,
):
    filters = {}

    if disaster_event:
        filters[
            "disaster_event"
        ] = disaster_event

    rows = frappe.get_all(
        "RN Resource Profile",
        filters=filters,
        fields=[
            "name",
            "legacy_id",
            "disaster_event",
            "owner_type",
            "owner_id",
            "resource_name",
            "resource_type",
            "category",
            "quantity",
            "unit",
            "capacity_description",
            "availability_status",
            "current_location",
            "coverage_area",
            "verification_status",
        ],
        order_by="creation desc",
        limit_page_length=3000,
    )

    result = []

    for row in rows:
        item = dict(row)
        item["id"] = (
            row.legacy_id
            or row.name
        )
        result.append(item)

    return result


def _request_rows(
    disaster_event=None,
):
    rows = frappe.get_all(
        "RN Resource Request",
        fields=[
            "name",
            "sync_event_id",
            "source_object_id",
            "resource_profile",
            "requested_by_type",
            "requested_by_id",
            "request_reason",
            "requested_quantity",
            "requested_time",
            "request_status",
            "source_user_id",
            "creation",
            "modified",
        ],
        order_by="creation desc",
        limit_page_length=3000,
    )

    result = []

    for row in rows:
        resource = frappe.db.get_value(
            "RN Resource Profile",
            row.resource_profile,
            [
                "resource_name",
                "resource_type",
                "legacy_id",
                "disaster_event",
            ],
            as_dict=True,
        )

        if not resource:
            continue

        if (
            disaster_event
            and resource.disaster_event
            != disaster_event
        ):
            continue

        result.append({
            "id":
                row.name,
            "request_id":
                row.name,
            "sync_event_id":
                row.sync_event_id,
            "resource_id":
                (
                    resource.legacy_id
                    or row.resource_profile
                ),
            "resource_profile":
                row.resource_profile,
            "resource_name":
                resource.resource_name,
            "resource_type":
                resource.resource_type,
            "requested_by_type":
                row.requested_by_type,
            "requested_by_id":
                row.requested_by_id,
            "request_reason":
                row.request_reason,
            "requested_quantity":
                row.requested_quantity,
            "requested_time":
                row.requested_time,
            "status":
                row.request_status,
            "request_status":
                row.request_status,
            "created_at":
                row.creation,
            "updated_at":
                row.modified,
        })

    return result


@frappe.whitelist()
def disaster_resources(
    disaster_event,
):
    _actor()

    event = _canonical_event(
        disaster_event
    )

    return _resource_rows(
        event
    )


@frappe.whitelist()
def disaster_resource_requests(
    disaster_event,
):
    _actor()

    event = _canonical_event(
        disaster_event
    )

    return _request_rows(
        event
    )


@frappe.whitelist()
def disaster_ecosystem_members(
    disaster_event,
):
    _actor()

    event = _canonical_event(
        disaster_event
    )

    organizations = frappe.get_all(
        "RN Organization",
        fields=[
            "name",
            "title",
            "organization_type",
            "verification_status",
        ],
        limit_page_length=3000,
    )

    poskos = frappe.get_all(
        "RN Posko",
        filters={
            "disaster_event":
                event
        },
        fields=[
            "name",
            "legacy_id",
            "title",
            "organization",
            "posko_type",
            "operational_status",
            "verification_status",
        ],
        limit_page_length=3000,
    )

    used_orgs = {
        p.organization
        for p in poskos
        if p.organization
    }

    result = []

    for org in organizations:
        if (
            used_orgs
            and org.name not in used_orgs
        ):
            continue

        result.append({
            "id":
                org.name,
            "member_type":
                "organization",
            "type":
                "organization",
            "name":
                org.title or org.name,
            "title":
                org.title or org.name,
            "organization_type":
                org.organization_type,
            "status":
                org.verification_status,
        })

    for posko in poskos:
        result.append({
            "id":
                (
                    posko.legacy_id
                    or posko.name
                ),
            "member_type":
                "posko",
            "type":
                "posko",
            "name":
                posko.title
                or posko.name,
            "title":
                posko.title
                or posko.name,
            "organization_id":
                posko.organization,
            "posko_type":
                posko.posko_type,
            "status":
                (
                    posko.operational_status
                    or
                    posko.verification_status
                ),
        })

    return result


@frappe.whitelist()
def resource_assignments(
    disaster_event=None,
):
    _actor()

    # Tidak ada canonical
    # RN Resource Assignment.
    # Jangan fabrikasi assignment.
    return []


@frappe.whitelist()
def create_resource_request(
    resource_id,
    requested_by_type,
    requested_by_id,
    request_reason=None,
    requested_quantity=0,
    requested_time=None,
    disaster_event=None,
):
    actor = _actor()

    resource = _resolve_resource(
        resource_id
    )

    resource_event = frappe.db.get_value(
        "RN Resource Profile",
        resource,
        "disaster_event",
    )

    if disaster_event:
        requested_event = (
            _canonical_event(
                disaster_event
            )
        )

        if (
            resource_event
            and requested_event
            != resource_event
        ):
            frappe.throw(
                "Resource bukan milik "
                "Disaster Event tersebut"
            )

    sync_event_id = (
        "frontend-"
        + uuid.uuid4().hex
    )

    doc = frappe.new_doc(
        "RN Resource Request"
    )

    doc.sync_event_id = (
        sync_event_id
    )
    doc.source_object_id = (
        "resource-request-"
        + uuid.uuid4().hex[:16]
    )
    doc.resource_profile = resource
    doc.requested_by_type = (
        requested_by_type
    )
    doc.requested_by_id = (
        requested_by_id
    )
    doc.request_reason = (
        request_reason
    )
    doc.requested_quantity = flt(
        requested_quantity or 0
    )
    doc.requested_time = (
        requested_time
    )
    doc.request_status = "requested"

    if getattr(
        actor,
        "name",
        None,
    ):
        doc.source_user_id = actor.name
    else:
        doc.source_user_id = (
            frappe.session.user
        )

    doc.insert(
        ignore_permissions=True
    )

    return {
        "id":
            doc.name,
        "request_id":
            doc.name,
        "sync_event_id":
            doc.sync_event_id,
        "resource_profile":
            doc.resource_profile,
        "resource_id":
            resource_id,
        "request_status":
            doc.request_status,
        "status":
            doc.request_status,
    }


@frappe.whitelist()
def approve_resource_request(
    resource_request,
    assignment_notes=None,
):
    _actor()

    if not frappe.db.exists(
        "RN Resource Request",
        resource_request,
    ):
        frappe.throw(
            "Resource Request tidak ditemukan"
        )

    doc = frappe.get_doc(
        "RN Resource Request",
        resource_request,
    )

    if doc.request_status not in (
        "requested",
        "approved",
    ):
        frappe.throw(
            "Request dengan status "
            + str(doc.request_status)
            + " tidak dapat di-approve"
        )

    doc.request_status = "approved"
    doc.save(
        ignore_permissions=True
    )

    return {
        "id":
            doc.name,
        "request_id":
            doc.name,
        "request_status":
            doc.request_status,
        "status":
            doc.request_status,
        "assignment":
            None,
        "note":
            (
                assignment_notes
                or
                "Approved tanpa "
                "fabricated assignment."
            ),
    }


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
