"""Resource tools — access helpers, capacity and request status."""

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


MANAGER_ROLES = {
    "command_center",
    "posko_operator",
    "medical_operator",
    "shelter_operator",
}


ACTIVE_DEPLOYMENT = {
    "reserved",
    "deployed",
    "in_use",
}


def _role(actor):
    return getattr(actor, "role", None)


def _actor_name(actor):
    return getattr(actor, "name", None)


def _is_manager(actor):
    return bool(
        is_system_manager()
        or _role(actor) in MANAGER_ROLES
    )


def _is_control_manager(actor):
    return bool(
        is_system_manager()
        or _role(actor) == "command_center"
    )


def _can_manage_reference(
    actor,
    reference_type,
    reference_id,
):
    if is_system_manager():
        return True

    if reference_type == "posko":
        return bool(
            reference_id
            and can_manage_posko(
                actor,
                reference_id,
            )
        )

    if reference_type == "organization":
        return bool(
            reference_id
            and can_manage_organization(
                actor,
                reference_id,
            )
        )

    if reference_type == "individual":
        return bool(
            reference_id
            and _actor_name(actor) == reference_id
        ) or _is_control_manager(actor)

    return _is_control_manager(actor)


def _assert_reference_access(
    actor,
    reference_type,
    reference_id,
):
    if not _can_manage_reference(
        actor,
        reference_type,
        reference_id,
    ):
        frappe.throw(
            "Akses pemilik/requester ditolak",
            frappe.PermissionError,
        )


def _resource_access(actor, name):
    row = frappe.db.get_value(
        "RN Resource Profile",
        name,
        [
            "owner_type",
            "owner_id",
        ],
        as_dict=True,
    )

    if not row:
        frappe.throw(
            "Resource Profile tidak ditemukan"
        )

    return _can_manage_reference(
        actor,
        row.owner_type,
        row.owner_id,
    )


def _request_access(actor, name):
    row = frappe.db.get_value(
        "RN Work Tool Request",
        name,
        [
            "requested_by_type",
            "requested_by_id",
        ],
        as_dict=True,
    )

    if not row:
        frappe.throw(
            "Work Tool Request tidak ditemukan"
        )

    return _can_manage_reference(
        actor,
        row.requested_by_type,
        row.requested_by_id,
    )


def _active_allocated(resource_profile):
    rows = frappe.get_all(
        "RN Work Tool Deployment",
        filters={
            "resource_profile":
                resource_profile,
            "deployment_status": [
                "in",
                list(ACTIVE_DEPLOYMENT),
            ],
        },
        fields=[
            "quantity_assigned",
        ],
        limit_page_length=5000,
    )

    return sum(
        flt(row.quantity_assigned)
        for row in rows
    )


def _resource_capacity(name):
    row = frappe.db.get_value(
        "RN Resource Profile",
        name,
        [
            "quantity",
            "availability_status",
        ],
        as_dict=True,
    )

    if not row:
        frappe.throw(
            "Resource Profile tidak ditemukan"
        )

    active = _active_allocated(name)

    return {
        "quantity": flt(row.quantity),
        "active_allocated": active,
        "available_quantity": max(
            flt(row.quantity) - active,
            0,
        ),
        "availability_status":
            row.availability_status,
    }


def _refresh_request_status(request_name):
    req = frappe.get_doc(
        "RN Work Tool Request",
        request_name,
    )

    if req.request_status == "cancelled":
        return req.request_status

    rows = frappe.get_all(
        "RN Work Tool Deployment",
        filters={
            "work_tool_request":
                request_name,
        },
        fields=[
            "deployment_status",
            "quantity_assigned",
        ],
        limit_page_length=5000,
    )

    completed = sum(
        flt(x.quantity_assigned)
        for x in rows
        if x.deployment_status == "completed"
    )

    active = sum(
        flt(x.quantity_assigned)
        for x in rows
        if x.deployment_status
        in ACTIVE_DEPLOYMENT
    )

    in_progress = any(
        x.deployment_status in {
            "deployed",
            "in_use",
        }
        for x in rows
    )

    if completed >= flt(req.quantity):
        status = "fulfilled"

    elif completed > 0:
        status = "partially_fulfilled"

    elif in_progress:
        status = "in_progress"

    elif active > 0:
        status = "matched"

    else:
        status = "requested"

    frappe.db.set_value(
        "RN Work Tool Request",
        request_name,
        "request_status",
        status,
        update_modified=False,
    )

    return status


_CATEGORY_LABELS = tool_needs.CATEGORY_LABELS


_CATEGORY_ORDER = list(_CATEGORY_LABELS.keys())


_LEGEND_BY_STATUS = {
    "available": "ready",
    "limited": "assigned",
    "maintenance": "maintenance",
    "unavailable": "critical",
}


_DEPLOY_STATUS_LABEL = {
    "reserved": "Dijadwalkan",
    "deployed": "Dikirim",
    "in_use": "Sedang Digunakan",
    "completed": "Selesai",
    "cancelled": "Dibatalkan",
}


_PRIORITY_LABEL = {
    "normal": "Normal",
    "urgent": "Urgent",
    "critical": "Kritis",
}


_PRIORITY_RANK = {"critical": 0, "urgent": 1, "normal": 2}


_FUEL_KEYWORDS = ("solar", "bensin", "pertalite", "pertamax", "bbm", "oli")


DEFAULT_DEMO_PROFILE_USER = "SIM-VOL-YUSUF"


_PERSONAL_CATEGORIES = ("kendaraan", "fasilitas", "barang_bantuan")


_OBJECT_TYPE_LABELS = {k: v["label"] for k, v in tool_needs.CONDITIONS.items()}


# requests that still count against a work object's estimate
_OPEN_REQUEST = ("requested", "matched", "in_progress", "partially_fulfilled", "fulfilled")
