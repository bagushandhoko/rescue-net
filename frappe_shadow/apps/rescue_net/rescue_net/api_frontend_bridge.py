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


# ============================================================
# GROUP E — Community Report / Consolidation / Verification
# ============================================================

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


@frappe.whitelist()
def community_reports(
    disaster_event=None,
    status=None,
):
    _actor()

    event = (
        _canonical_event(disaster_event)
        if disaster_event
        else None
    )

    filters = {}

    if event:
        filters["disaster_event"] = event

    meta_fields = _meta_fields(
        "RN Community Report"
    )

    if (
        status
        and "status" in meta_fields
    ):
        filters["status"] = status

    fields = _safe_fields(
        "RN Community Report",
        [
            "name",
            "legacy_id",
            "title",
            "description",
            "report_type",
            "priority",
            "status",
            "verification_status",
            "disaster_event",
            "location_text",
            "latitude",
            "longitude",
            "affected_people_count",
            "urgent_needs",
            "province_name",
            "city_name",
            "district_name",
            "village_name",
            "area_level",
            "consolidation_status",
            "trust_score",
            "consent_to_contact",
            "reporter_name",
            "reporter_phone",
            "reporter_email",
            "creation",
            "modified",
        ],
    )

    rows = frappe.get_all(
        "RN Community Report",
        filters=filters,
        fields=fields,
        order_by="creation desc",
        limit_page_length=3000,
    )

    result = []

    for row in rows:
        item = dict(row)

        item["id"] = (
            item.get("legacy_id")
            or item["name"]
        )

        item["created_at"] = (
            item.get("creation")
        )

        item["updated_at"] = (
            item.get("modified")
        )

        result.append(item)

    return result


@frappe.whitelist()
def set_community_report_status(
    report,
    status,
):
    _actor()

    if not frappe.db.exists(
        "RN Community Report",
        report,
    ):
        report = frappe.db.get_value(
            "RN Community Report",
            {"legacy_id": report},
            "name",
        )

    if not report:
        frappe.throw(
            "Community Report tidak ditemukan"
        )

    meta_fields = _meta_fields(
        "RN Community Report"
    )

    if "status" not in meta_fields:
        frappe.throw(
            "RN Community Report tidak memiliki field status"
        )

    doc = frappe.get_doc(
        "RN Community Report",
        report,
    )

    doc.status = status
    doc.save(ignore_permissions=True)

    return {
        "id": doc.name,
        "status": doc.status,
    }


@frappe.whitelist()
def convert_community_report(
    report,
):
    _actor()

    if not frappe.db.exists(
        "RN Community Report",
        report,
    ):
        report = frappe.db.get_value(
            "RN Community Report",
            {"legacy_id": report},
            "name",
        )

    if not report:
        frappe.throw(
            "Community Report tidak ditemukan"
        )

    existing = frappe.db.get_value(
        "RN Community Need",
        {"source_report": report},
        "name",
    )

    if existing:
        return {
            "report": report,
            "community_need": existing,
            "created": False,
        }

    source = frappe.get_doc(
        "RN Community Report",
        report,
    )

    need = frappe.new_doc(
        "RN Community Need"
    )

    fields = _meta_fields(
        "RN Community Need"
    )

    def set_if(field, value):
        if (
            field in fields
            and value not in (None, "")
        ):
            need.set(field, value)

    set_if(
        "source_report",
        source.name,
    )

    set_if(
        "disaster_event",
        getattr(
            source,
            "disaster_event",
            None,
        ),
    )

    set_if(
        "title",
        "Kebutuhan - "
        + (
            getattr(
                source,
                "title",
                None,
            )
            or source.name
        ),
    )

    set_if(
        "need_type",
        getattr(
            source,
            "report_type",
            None,
        )
        or "community_report",
    )

    set_if(
        "description",
        getattr(
            source,
            "urgent_needs",
            None,
        )
        or getattr(
            source,
            "description",
            None,
        ),
    )

    set_if(
        "urgency",
        getattr(
            source,
            "priority",
            None,
        )
        or "normal",
    )

    set_if(
        "status",
        "open",
    )

    set_if(
        "verification_status",
        getattr(
            source,
            "verification_status",
            None,
        )
        or "unverified",
    )

    need.insert(
        ignore_permissions=True
    )

    return {
        "report": source.name,
        "community_need": need.name,
        "created": True,
    }


def _count_for_event(
    doctype,
    event,
):
    fields = _meta_fields(doctype)

    if "disaster_event" not in fields:
        return frappe.db.count(doctype)

    return frappe.db.count(
        doctype,
        {
            "disaster_event": event
        },
    )


@frappe.whitelist()
def consolidation_summary(
    disaster_event,
):
    _actor()

    event = _canonical_event(
        disaster_event
    )

    doctypes = {
        "community_report_count":
            "RN Community Report",

        "community_need_count":
            "RN Community Need",

        "logistic_need_count":
            "RN Logistic Need",

        "aid_offer_count":
            "RN Aid Offer",

        "distribution_flow_count":
            "RN Distribution Flow",

        "posko_count":
            "RN Posko",

        "stock_observation_count":
            "RN Stock Observation",

        "medical_case_count":
            "RN Medical Case",

        "shelter_occupancy_count":
            "RN Shelter Occupancy",

        "missing_person_count":
            "RN Missing Person Report",

        "found_person_count":
            "RN Found Person Report",
    }

    result = {}

    for key, doctype in doctypes.items():
        if frappe.db.exists(
            "DocType",
            doctype,
        ):
            result[key] = (
                _count_for_event(
                    doctype,
                    event,
                )
            )
        else:
            result[key] = 0

    return result


@frappe.whitelist()
def consolidation_raw_reports(
    disaster_event,
):
    return community_reports(
        disaster_event=disaster_event
    )


@frappe.whitelist()
def consolidated_needs(
    disaster_event,
):
    _actor()

    event = _canonical_event(
        disaster_event
    )

    result = []

    for doctype in (
        "RN Community Need",
        "RN Logistic Need",
    ):
        if not frappe.db.exists(
            "DocType",
            doctype,
        ):
            continue

        fields = _safe_fields(
            doctype,
            [
                "name",
                "title",
                "disaster_event",
                "description",
                "item_name",
                "quantity",
                "unit",
                "urgency",
                "status",
                "need_status",
                "verification_status",
                "canonical_category",
                "canonical_group",
                "canonical_item",
                "creation",
            ],
        )

        rows = frappe.get_all(
            doctype,
            filters={
                "disaster_event":
                    event
            },
            fields=fields,
            order_by="creation desc",
            limit_page_length=3000,
        )

        for row in rows:
            item = dict(row)

            item["id"] = item["name"]

            item["source_type"] = (
                "community"
                if doctype
                == "RN Community Need"
                else "logistic"
            )

            item["status"] = (
                item.get("status")
                or item.get(
                    "need_status"
                )
            )

            result.append(item)

    return result


@frappe.whitelist()
def duplicate_candidates(
    disaster_event,
):
    _actor()

    # Candidate duplicate tidak difabrikasi.
    # Return empty sampai canonical duplicate
    # model benar-benar tersedia.
    _canonical_event(disaster_event)

    return []


@frappe.whitelist()
def consolidation_auxiliary(
    disaster_event,
):
    _actor()

    event = _canonical_event(
        disaster_event
    )

    poskos = frappe.get_all(
        "RN Posko",
        filters={
            "disaster_event": event
        },
        fields=[
            "name",
            "title",
            "province_name",
            "city_name",
            "district_name",
            "village_name",
            "area_level",
        ],
        limit_page_length=3000,
    )

    operational_areas = []

    seen = set()

    for posko in poskos:
        key = (
            posko.province_name,
            posko.city_name,
            posko.district_name,
            posko.village_name,
        )

        if key in seen:
            continue

        seen.add(key)

        operational_areas.append({
            "id":
                "|".join(
                    str(x or "")
                    for x in key
                ),
            "province_name":
                posko.province_name,
            "city_name":
                posko.city_name,
            "district_name":
                posko.district_name,
            "village_name":
                posko.village_name,
            "area_level":
                posko.area_level,
        })

    return {
        "operational_areas":
            operational_areas,

        "beneficiary_groups":
            [],

        "evidence_requirements":
            [],
    }


def _verification_rows(
    doctype,
):
    if not frappe.db.exists(
        "DocType",
        doctype,
    ):
        return []

    meta = frappe.get_meta(
        doctype
    )

    fields = [
        "name",
        *[
            df.fieldname
            for df in meta.fields
            if df.fieldname
            and df.fieldtype
            not in (
                "Section Break",
                "Column Break",
                "Tab Break",
                "HTML",
                "Button",
                "Table",
            )
        ],
    ]

    return [
        dict(x)
        for x in frappe.get_all(
            doctype,
            fields=fields,
            order_by="creation desc",
            limit_page_length=3000,
        )
    ]


@frappe.whitelist()
def verification_context(
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

    profiles = _verification_rows(
        "RN Verifier Profile"
    )

    requests = _verification_rows(
        "RN Verification Request"
    )

    endorsements = _verification_rows(
        "RN Verification Endorsement"
    )

    actions = _verification_rows(
        "RN Verification Action"
    )

    if event:
        actions = [
            row
            for row in actions
            if (
                not row.get(
                    "disaster_event"
                )
                or row.get(
                    "disaster_event"
                ) == event
            )
        ]

    def status_of(
        row,
        *fields,
    ):
        return str(
            _row_value(
                row,
                *fields,
            )
            or ""
        ).lower()

    summary = {
        "candidate_verifier_count":
            sum(
                1
                for x in profiles
                if status_of(
                    x,
                    "verifier_status",
                    "status",
                )
                in (
                    "candidate_verifier",
                    "pending",
                    "candidate",
                )
            ),

        "pending_verifier_request_count":
            sum(
                1
                for x in requests
                if status_of(
                    x,
                    "status",
                    "request_status",
                )
                == "pending"
            ),

        "active_endorsement_count":
            sum(
                1
                for x in endorsements
                if status_of(
                    x,
                    "status",
                    "endorsement_status",
                )
                == "active"
            ),

        "revoked_endorsement_count":
            sum(
                1
                for x in endorsements
                if status_of(
                    x,
                    "status",
                    "endorsement_status",
                )
                == "revoked"
            ),
    }

    return {
        "verifier_profiles":
            profiles,

        "verification_requests":
            requests,

        "verification_endorsements":
            endorsements,

        "verification_actions":
            actions,

        "summary":
            summary,
    }


@frappe.whitelist()
def set_verifier_status(
    verifier,
    status,
):
    _actor()

    if not frappe.db.exists(
        "RN Verifier Profile",
        verifier,
    ):
        frappe.throw(
            "Verifier Profile tidak ditemukan"
        )

    doc = frappe.get_doc(
        "RN Verifier Profile",
        verifier,
    )

    fields = _meta_fields(
        "RN Verifier Profile"
    )

    field = (
        "verifier_status"
        if "verifier_status" in fields
        else (
            "status"
            if "status" in fields
            else None
        )
    )

    if not field:
        frappe.throw(
            "Field status verifier tidak tersedia"
        )

    doc.set(field, status)

    doc.save(
        ignore_permissions=True
    )

    return {
        "verifier": doc.name,
        "status": doc.get(field),
    }


@frappe.whitelist()
def revoke_verification_endorsement(
    endorsement,
):
    _actor()

    if not frappe.db.exists(
        "RN Verification Endorsement",
        endorsement,
    ):
        frappe.throw(
            "Verification Endorsement tidak ditemukan"
        )

    doc = frappe.get_doc(
        "RN Verification Endorsement",
        endorsement,
    )

    fields = _meta_fields(
        "RN Verification Endorsement"
    )

    field = (
        "status"
        if "status" in fields
        else (
            "endorsement_status"
            if "endorsement_status"
            in fields
            else None
        )
    )

    if not field:
        frappe.throw(
            "Field status endorsement tidak tersedia"
        )

    doc.set(
        field,
        "revoked",
    )

    doc.save(
        ignore_permissions=True
    )

    return {
        "endorsement": doc.name,
        "status": "revoked",
    }


# ============================================================
# GROUP E — remaining write adapters
# ============================================================

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
def submit_community_report_bridge(
    title,
    description,
    report_type=None,
    priority=None,
    affected_people_count=0,
    urgent_needs=None,
    location_text=None,
    latitude=None,
    longitude=None,
    province_code=None,
    city_code=None,
    district_code=None,
    village_code=None,
    consent_to_contact=0,
    location_input_method=None,
    create_need=0,
):
    _actor()

    from rescue_net.api_reports import (
        submit_community_report,
    )

    return submit_community_report(
        title=title,
        description=description,
        report_type=report_type,
        priority=priority,
        affected_people_count=affected_people_count,
        urgent_needs=urgent_needs,
        location_text=location_text,
        latitude=latitude,
        longitude=longitude,
        province_code=province_code,
        city_code=city_code,
        district_code=district_code,
        village_code=village_code,
        consent_to_contact=consent_to_contact,
        location_input_method=location_input_method,
        create_need=create_need,
    )


def _dynamic_insert(
    doctype,
    payload,
):
    meta = frappe.get_meta(
        doctype
    )

    valid = {
        df.fieldname
        for df in meta.fields
        if df.fieldname
    }

    doc = frappe.new_doc(
        doctype
    )

    for key, value in payload.items():
        if (
            key in valid
            and value not in (
                None,
                "",
            )
        ):
            doc.set(
                key,
                value,
            )

    doc.insert(
        ignore_permissions=True
    )

    return doc


@frappe.whitelist()
def create_verifier_profile(
    **payload,
):
    _actor()

    doc = _dynamic_insert(
        "RN Verifier Profile",
        payload,
    )

    return {
        "id": doc.name,
        "verifier": doc.name,
        "status":
            getattr(
                doc,
                "verifier_status",
                None,
            )
            or getattr(
                doc,
                "status",
                None,
            ),
    }


@frappe.whitelist()
def create_verification_action(
    **payload,
):
    _actor()

    doc = _dynamic_insert(
        "RN Verification Action",
        payload,
    )

    return {
        "id": doc.name,
        "verification_action":
            doc.name,
    }


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


# ============================================================
# GROUP E — remaining write adapters
# ============================================================

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
def submit_community_report_bridge(
    title,
    description,
    report_type=None,
    priority=None,
    affected_people_count=0,
    urgent_needs=None,
    location_text=None,
    latitude=None,
    longitude=None,
    province_code=None,
    city_code=None,
    district_code=None,
    village_code=None,
    consent_to_contact=0,
    location_input_method=None,
    create_need=0,
):
    _actor()

    from rescue_net.api_reports import (
        submit_community_report,
    )

    return submit_community_report(
        title=title,
        description=description,
        report_type=report_type,
        priority=priority,
        affected_people_count=affected_people_count,
        urgent_needs=urgent_needs,
        location_text=location_text,
        latitude=latitude,
        longitude=longitude,
        province_code=province_code,
        city_code=city_code,
        district_code=district_code,
        village_code=village_code,
        consent_to_contact=consent_to_contact,
        location_input_method=location_input_method,
        create_need=create_need,
    )


def _dynamic_insert(
    doctype,
    payload,
):
    meta = frappe.get_meta(
        doctype
    )

    valid = {
        df.fieldname
        for df in meta.fields
        if df.fieldname
    }

    doc = frappe.new_doc(
        doctype
    )

    for key, value in payload.items():
        if (
            key in valid
            and value not in (
                None,
                "",
            )
        ):
            doc.set(
                key,
                value,
            )

    doc.insert(
        ignore_permissions=True
    )

    return doc


@frappe.whitelist()
def create_verifier_profile(
    **payload,
):
    _actor()

    doc = _dynamic_insert(
        "RN Verifier Profile",
        payload,
    )

    return {
        "id": doc.name,
        "verifier": doc.name,
        "status":
            getattr(
                doc,
                "verifier_status",
                None,
            )
            or getattr(
                doc,
                "status",
                None,
            ),
    }


@frappe.whitelist()
def create_verification_action(
    **payload,
):
    _actor()

    doc = _dynamic_insert(
        "RN Verification Action",
        payload,
    )

    return {
        "id": doc.name,
        "verification_action":
            doc.name,
    }


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


# ============================================================
# FINAL CLEANUP — Home Disaster API
# ============================================================

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
