"""Frontend bridge — disaster resources, resource requests, ecosystem members."""

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
    _canonical_event,
)


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


def _can_decide_resource_request(doc):
    """The resource's owner decides: its posko's operators, its organisation's
    managers, the individual owner; System Manager always."""
    from rescue_net.access_policy import can_manage_organization, is_system_manager, rn_actor
    from rescue_net.api_logistics import _can_operate
    from rescue_net.reference_resolver import resolve_organization, resolve_posko

    if is_system_manager():
        return True
    actor = rn_actor()
    profile = doc.resource_profile and frappe.db.get_value(
        "RN Resource Profile", doc.resource_profile, ["owner_type", "owner_id"], as_dict=True)
    if not profile or not profile.owner_id:
        return False
    if profile.owner_type == "posko":
        posko = resolve_posko(profile.owner_id)
        return bool(posko) and _can_operate(actor, posko)
    if profile.owner_type == "organization":
        org = resolve_organization(profile.owner_id)
        return bool(org) and can_manage_organization(actor, org)
    if profile.owner_type == "individual":
        return bool(actor and actor.name) and profile.owner_id in (actor.name, actor.frappe_user)
    return False


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

    if not _can_decide_resource_request(doc):   # L-24
        frappe.throw(
            "Hanya pemilik/pengelola sumber daya ini yang dapat menyetujui permintaan.",
            frappe.PermissionError,
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
