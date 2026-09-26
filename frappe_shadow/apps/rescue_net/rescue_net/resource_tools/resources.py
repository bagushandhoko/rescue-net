"""Resource tools — resource profiles, work-tool requests, deployments, evidence."""

import math
from collections import defaultdict

import frappe
from frappe.rate_limiter import rate_limit
from rescue_net.reference_resolver import resolve_disaster_event, resolve_posko
from rescue_net.intelligence.normalization import normalize_unit
# classify_text via the registry so the live "Kelompok Alat" fallback honours
# the editable RN Normalization Rule records, same as the record-insert hooks.
from rescue_net.intelligence.normalization_registry import classify_text
from frappe.utils import (
    cint,
    flt,
    get_datetime,
    now_datetime,
    nowdate,
    time_diff_in_hours,
)

from rescue_net.services import tool_needs
from rescue_net.access_policy import (
    can_manage_organization,
    can_manage_posko,
    is_system_manager,
    rn_actor,
)

from rescue_net.resource_tools.common import (  # noqa: F401
    ACTIVE_DEPLOYMENT,
    _actor_name,
    _assert_reference_access,
    _can_manage_reference,
    _is_control_manager,
    _is_manager,
    _refresh_request_status,
    _request_access,
    _resource_access,
    _resource_capacity,
)


@frappe.whitelist()
def create_resource_profile(
    resource_name,
    resource_type,
    owner_type="organization",
    owner_id=None,
    disaster_event=None,
    category=None,
    quantity=1,
    unit="unit",
    capacity_description=None,
    availability_status="available",
    current_location=None,
    coverage_area=None,
    pic_name=None,
    pic_phone=None,
    notes=None,
):
    # RN_CANONICAL_EVENT disaster_event = resolve_disaster_event(disaster_event)
    disaster_event = resolve_disaster_event(disaster_event)
    actor = rn_actor()

    if not _is_manager(actor):
        frappe.throw(
            "Hak operator diperlukan",
            frappe.PermissionError,
        )

    _assert_reference_access(
        actor,
        owner_type,
        owner_id,
    )

    doc = frappe.new_doc(
        "RN Resource Profile"
    )

    doc.disaster_event = disaster_event
    doc.owner_type = owner_type
    doc.owner_id = owner_id
    doc.resource_name = resource_name
    doc.resource_type = resource_type
    doc.category = category
    doc.quantity = flt(quantity)
    doc.unit = unit
    doc.capacity_description = (
        capacity_description
    )
    doc.availability_status = (
        availability_status
    )
    doc.current_location = (
        current_location
    )
    doc.coverage_area = coverage_area
    doc.pic_name = pic_name
    doc.pic_phone = pic_phone
    doc.notes = notes
    doc.verification_status = (
        "self_reported"
    )

    doc.insert(ignore_permissions=True)

    return {
        "resource_profile": doc.name,
        "availability_status":
            doc.availability_status,
        "quantity": flt(doc.quantity),
        "unit": doc.unit,
    }


@frappe.whitelist()
def update_resource_profile(
    resource_profile,
    availability_status=None,
    current_location=None,
    capacity_description=None,
    coverage_area=None,
    pic_name=None,
    pic_phone=None,
    notes=None,
):
    actor = rn_actor()

    if not _resource_access(
        actor,
        resource_profile,
    ):
        frappe.throw(
            "Akses Resource Profile ditolak",
            frappe.PermissionError,
        )

    doc = frappe.get_doc(
        "RN Resource Profile",
        resource_profile,
    )

    updates = {
        "availability_status":
            availability_status,
        "current_location":
            current_location,
        "capacity_description":
            capacity_description,
        "coverage_area":
            coverage_area,
        "pic_name":
            pic_name,
        "pic_phone":
            pic_phone,
        "notes":
            notes,
    }

    for field, value in updates.items():
        if value is not None:
            setattr(doc, field, value)

    doc.save(ignore_permissions=True)

    return {
        "resource_profile": doc.name,
        "availability_status":
            doc.availability_status,
    }


@frappe.whitelist()
def create_work_tool_request(
    tool_name,
    requested_by_type="posko",
    requested_by_id=None,
    disaster_event=None,
    tool_type=None,
    quantity=1,
    unit="unit",
    location=None,
    needed_for=None,
    priority="normal",
    required_operator_skill=None,
    notes=None,
):
    # RN_CANONICAL_EVENT disaster_event = resolve_disaster_event(disaster_event)
    disaster_event = resolve_disaster_event(disaster_event)
    actor = rn_actor()

    if not _is_manager(actor):
        frappe.throw(
            "Hak operator diperlukan",
            frappe.PermissionError,
        )

    _assert_reference_access(
        actor,
        requested_by_type,
        requested_by_id,
    )

    doc = frappe.new_doc(
        "RN Work Tool Request"
    )

    doc.disaster_event = disaster_event
    doc.requested_by_type = (
        requested_by_type
    )
    doc.requested_by_id = (
        requested_by_id
    )
    doc.tool_name = tool_name
    doc.tool_type = tool_type
    doc.quantity = flt(quantity)
    doc.unit = unit
    doc.location = location
    doc.needed_for = needed_for
    doc.priority = priority
    doc.required_operator_skill = (
        required_operator_skill
    )
    doc.request_status = "requested"
    doc.notes = notes
    doc.created_by_user = (
        _actor_name(actor)
    )
    doc.verification_status = (
        "self_reported"
    )

    doc.insert(ignore_permissions=True)

    return {
        "work_tool_request": doc.name,
        "status": doc.request_status,
        "quantity": flt(doc.quantity),
        "unit": doc.unit,
    }


@frappe.whitelist()
def cancel_work_tool_request(
    work_tool_request,
    notes=None,
):
    actor = rn_actor()

    if not _request_access(
        actor,
        work_tool_request,
    ):
        frappe.throw(
            "Akses Work Tool Request ditolak",
            frappe.PermissionError,
        )

    active = frappe.db.exists(
        "RN Work Tool Deployment",
        {
            "work_tool_request":
                work_tool_request,
            "deployment_status": [
                "in",
                list(ACTIVE_DEPLOYMENT),
            ],
        },
    )

    if active:
        frappe.throw(
            "Request masih memiliki deployment aktif"
        )

    doc = frappe.get_doc(
        "RN Work Tool Request",
        work_tool_request,
    )

    if doc.request_status == "fulfilled":
        frappe.throw(
            "Request fulfilled tidak dapat dibatalkan"
        )

    doc.request_status = "cancelled"

    if notes is not None:
        doc.notes = notes

    doc.save(ignore_permissions=True)

    return {
        "work_tool_request": doc.name,
        "status": doc.request_status,
    }


@frappe.whitelist()
def create_deployment(
    work_tool_request,
    resource_profile,
    quantity_assigned=1,
    unit=None,
    destination_location=None,
    operator_name=None,
    operator_skill=None,
    notes=None,
):
    actor = rn_actor()

    if not _is_control_manager(actor):
        frappe.throw(
            "Allocation resource hanya untuk Control Centre",
            frappe.PermissionError,
        )

    req = frappe.get_doc(
        "RN Work Tool Request",
        work_tool_request,
    )

    if req.request_status in {
        "fulfilled",
        "cancelled",
    }:
        frappe.throw(
            "Request sudah terminal"
        )

    resource = frappe.get_doc(
        "RN Resource Profile",
        resource_profile,
    )

    if resource.availability_status in {
        "unavailable",
        "maintenance",
    }:
        frappe.throw(
            "Resource sedang tidak tersedia"
        )

    qty = flt(quantity_assigned)

    if qty <= 0:
        frappe.throw(
            "Quantity allocation harus lebih dari 0"
        )

    # Lock resource row during capacity check.
    frappe.db.sql(
        """
        SELECT name
        FROM `tabRN Resource Profile`
        WHERE name = %s
        FOR UPDATE
        """,
        (resource_profile,),
    )

    capacity = _resource_capacity(
        resource_profile
    )

    if qty > capacity[
        "available_quantity"
    ]:
        frappe.throw(
            "Resource tidak cukup / sudah dialokasikan"
        )

    doc = frappe.new_doc(
        "RN Work Tool Deployment"
    )

    doc.work_tool_request = (
        work_tool_request
    )
    doc.resource_profile = (
        resource_profile
    )
    doc.quantity_assigned = qty
    doc.unit = (
        unit
        or req.unit
        or resource.unit
        or "unit"
    )
    doc.deployment_status = "reserved"
    doc.destination_location = (
        destination_location
        or req.location
    )
    doc.operator_name = operator_name
    doc.operator_skill = operator_skill
    doc.notes = notes
    doc.created_by_user = (
        _actor_name(actor)
    )
    doc.verification_status = "pending"

    doc.insert(ignore_permissions=True)

    request_status = (
        _refresh_request_status(
            work_tool_request
        )
    )

    capacity = _resource_capacity(
        resource_profile
    )

    return {
        "deployment": doc.name,
        "status": doc.deployment_status,
        "request_status":
            request_status,
        "available_quantity":
            capacity[
                "available_quantity"
            ],
    }


@frappe.whitelist()
def update_deployment_status(
    deployment,
    new_status,
    notes=None,
):
    actor = rn_actor()

    if not _is_control_manager(actor):
        frappe.throw(
            "Update deployment hanya untuk Control Centre",
            frappe.PermissionError,
        )

    doc = frappe.get_doc(
        "RN Work Tool Deployment",
        deployment,
    )

    current = doc.deployment_status

    # transition: RN Work Tool Deployment controller

    doc.deployment_status = new_status

    if notes is not None:
        doc.notes = notes

    if new_status == "deployed":
        doc.deployed_at = now_datetime()

    if new_status == "completed":
        doc.completed_at = now_datetime()
        doc.verification_status = "completed"

    elif new_status == "cancelled":
        doc.verification_status = "cancelled"

    doc.save(ignore_permissions=True)

    request_status = (
        _refresh_request_status(
            doc.work_tool_request
        )
    )

    capacity = _resource_capacity(
        doc.resource_profile
    )

    return {
        "deployment": doc.name,
        "previous_status": current,
        "status": doc.deployment_status,
        "request_status":
            request_status,
        "available_quantity":
            capacity[
                "available_quantity"
            ],
    }


@frappe.whitelist()
def add_evidence(
    linked_doctype,
    linked_name,
    file_url,
    evidence_type="verification",
    caption=None,
):
    supported = {
        "RN Resource Profile",
        "RN Work Tool Request",
        "RN Work Tool Deployment",
    }

    if linked_doctype not in supported:
        frappe.throw(
            "Objek Resource/Alat tidak didukung"
        )

    if not frappe.db.exists(
        linked_doctype,
        linked_name,
    ):
        frappe.throw(
            "Objek tidak ditemukan"
        )

    if not (
        file_url or ""
    ).startswith(
        "/private/files/"
    ):
        frappe.throw(
            "Evidence resource/alatan wajib private"
        )

    actor = rn_actor()

    if linked_doctype == (
        "RN Resource Profile"
    ):
        allowed = _resource_access(
            actor,
            linked_name,
        )

        posko = None

        row = frappe.db.get_value(
            linked_doctype,
            linked_name,
            [
                "owner_type",
                "owner_id",
            ],
            as_dict=True,
        )

        if (
            row
            and row.owner_type == "posko"
        ):
            posko = row.owner_id

    elif linked_doctype == (
        "RN Work Tool Request"
    ):
        allowed = _request_access(
            actor,
            linked_name,
        )

        row = frappe.db.get_value(
            linked_doctype,
            linked_name,
            [
                "requested_by_type",
                "requested_by_id",
            ],
            as_dict=True,
        )

        posko = (
            row.requested_by_id
            if row
            and row.requested_by_type
            == "posko"
            else None
        )

    else:
        allowed = _is_control_manager(
            actor
        )

        deployment = frappe.get_doc(
            "RN Work Tool Deployment",
            linked_name,
        )

        req = frappe.db.get_value(
            "RN Work Tool Request",
            deployment.work_tool_request,
            [
                "requested_by_type",
                "requested_by_id",
            ],
            as_dict=True,
        )

        posko = (
            req.requested_by_id
            if req
            and req.requested_by_type
            == "posko"
            else None
        )

    if not allowed:
        frappe.throw(
            "Akses evidence ditolak",
            frappe.PermissionError,
        )

    now = now_datetime()

    ev = frappe.new_doc(
        "RN Operational Evidence"
    )

    ev.linked_doctype = linked_doctype
    ev.linked_name = linked_name
    ev.posko = posko
    ev.file_url = file_url
    ev.evidence_type = evidence_type
    ev.caption = caption
    ev.observed_at = now
    ev.uploaded_at = now
    ev.uploader_user = (
        _actor_name(actor)
    )
    ev.verification_status = "pending"

    ev.insert(ignore_permissions=True)

    return {
        "evidence": ev.name,
        "private": True,
        "verification_status":
            ev.verification_status,
    }


@frappe.whitelist()
def restricted_resource(
    resource_profile,
):
    actor = rn_actor()

    if not (
        _resource_access(
            actor,
            resource_profile,
        )
        or _is_control_manager(actor)
    ):
        frappe.throw(
            "Akses PIC Resource ditolak",
            frappe.PermissionError,
        )

    doc = frappe.get_doc(
        "RN Resource Profile",
        resource_profile,
    )

    return {
        "resource_profile": doc.name,
        "pic_name": doc.pic_name,
        "pic_phone": doc.pic_phone,
        "privacy": "restricted",
    }


def _visible_resource(actor, row):
    if _is_control_manager(actor):
        return True

    return _can_manage_reference(
        actor,
        row.owner_type,
        row.owner_id,
    )


def _visible_request(actor, row):
    if _is_control_manager(actor):
        return True

    return _can_manage_reference(
        actor,
        row.requested_by_type,
        row.requested_by_id,
    )
