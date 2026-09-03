import math
from collections import defaultdict

import frappe
from rescue_net.reference_resolver import resolve_disaster_event
from rescue_net.intelligence.normalization import classify_text, normalize_unit
from frappe.utils import (
    flt,
    get_datetime,
    now_datetime,
    nowdate,
    time_diff_in_hours,
)

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

DEPLOYMENT_TRANSITIONS = {
    "reserved": {
        "deployed",
        "cancelled",
    },
    "deployed": {
        "in_use",
        "completed",
        "cancelled",
    },
    "in_use": {
        "completed",
        "cancelled",
    },
    "completed": set(),
    "cancelled": set(),
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

    if new_status not in (
        DEPLOYMENT_TRANSITIONS.get(
            current,
            set(),
        )
    ):
        frappe.throw(
            f"Transisi deployment tidak valid: "
            f"{current} -> {new_status}"
        )

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


@frappe.whitelist(allow_guest=True)
def dashboard(disaster_event=None):
    # RN_CANONICAL_EVENT disaster_event = resolve_disaster_event(disaster_event)
    disaster_event = resolve_disaster_event(disaster_event)
    actor = rn_actor(required=False)

    resource_filters = {}
    request_filters = {}

    if disaster_event:
        resource_filters[
            "disaster_event"
        ] = disaster_event

        request_filters[
            "disaster_event"
        ] = disaster_event

    resources = frappe.get_all(
        "RN Resource Profile",
        filters=resource_filters,
        fields=[
            "name",
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

    requests = frappe.get_all(
        "RN Work Tool Request",
        filters=request_filters,
        fields=[
            "name",
            "disaster_event",
            "requested_by_type",
            "requested_by_id",
            "tool_name",
            "tool_type",
            "quantity",
            "unit",
            "location",
            "needed_for",
            "priority",
            "required_operator_skill",
            "request_status",
            "verification_status",
        ],
        order_by="creation desc",
        limit_page_length=3000,
    )

    visible_resources = [
        x
        for x in resources
        if _visible_resource(
            actor,
            x,
        )
    ]

    visible_requests = [
        x
        for x in requests
        if _visible_request(
            actor,
            x,
        )
    ]

    resource_names = {
        x.name
        for x in visible_resources
    }

    request_names = {
        x.name
        for x in visible_requests
    }

    deployments = frappe.get_all(
        "RN Work Tool Deployment",
        fields=[
            "name",
            "work_tool_request",
            "resource_profile",
            "quantity_assigned",
            "unit",
            "deployment_status",
            "destination_location",
            "operator_skill",
            "deployed_at",
            "completed_at",
            "verification_status",
        ],
        order_by="creation desc",
        limit_page_length=3000,
    )

    visible_deployments = [
        x
        for x in deployments
        if (
            _is_control_manager(actor)
            or x.resource_profile
            in resource_names
            or x.work_tool_request
            in request_names
        )
    ]

    resource_output = []

    for row in visible_resources:
        item = dict(row)

        capacity = _resource_capacity(
            row.name
        )

        item[
            "active_allocated"
        ] = capacity[
            "active_allocated"
        ]

        item[
            "available_quantity"
        ] = capacity[
            "available_quantity"
        ]

        # PIC deliberately omitted.
        resource_output.append(item)

    return {
        "mode": (
            "control"
            if _is_control_manager(actor)
            else (
                "manager"
                if _is_manager(actor)
                else "viewer"
            )
        ),
        "resources": resource_output,
        "requests": visible_requests,
        "deployments":
            visible_deployments,
        "privacy": (
            "PIC phone tidak dikirim melalui dashboard. "
            "Gunakan restricted_resource bila berwenang."
        ),
    }


@frappe.whitelist()
def control_centre_resources():
    actor = rn_actor()

    if not _is_control_manager(actor):
        frappe.throw(
            "Akses Control Centre ditolak",
            frappe.PermissionError,
        )

    resources = frappe.get_all(
        "RN Resource Profile",
        fields=[
            "resource_type",
            "availability_status",
            "quantity",
        ],
        limit_page_length=5000,
    )

    requests = frappe.get_all(
        "RN Work Tool Request",
        fields=[
            "priority",
            "request_status",
        ],
        limit_page_length=5000,
    )

    deployments = frappe.get_all(
        "RN Work Tool Deployment",
        fields=[
            "deployment_status",
            "quantity_assigned",
        ],
        limit_page_length=5000,
    )

    resource_status = defaultdict(int)
    request_status = defaultdict(int)
    deployment_status = defaultdict(int)

    for row in resources:
        resource_status[
            row.availability_status
        ] += 1

    for row in requests:
        request_status[
            row.request_status
        ] += 1

    for row in deployments:
        deployment_status[
            row.deployment_status
        ] += 1

    urgent_open = sum(
        1
        for row in requests
        if (
            row.priority in {
                "urgent",
                "critical",
            }
            and row.request_status
            not in {
                "fulfilled",
                "cancelled",
            }
        )
    )

    return {
        "resource_count":
            len(resources),
        "request_count":
            len(requests),
        "deployment_count":
            len(deployments),
        "urgent_open":
            urgent_open,
        "resource_status":
            dict(resource_status),
        "request_status":
            dict(request_status),
        "deployment_status":
            dict(deployment_status),
        "privacy": (
            "Aggregate only. Tidak ada PIC/contact."
        ),
    }


_CATEGORY_LABELS = {
    "ekskavator": "Ekskavator",
    "genset": "Genset",
    "pompa_air": "Pompa Air",
    "forklift": "Forklift",
    "chainsaw": "Chainsaw",
    "perahu_karet": "Perahu Karet",
}

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


def _fuel_status(qty, basis):
    if qty is None:
        return "tidak diketahui"
    if qty <= 0:
        return "kritis"
    if basis:
        ratio = flt(qty) / flt(basis)
        if ratio < 0.34:
            return "kritis"
        if ratio < 0.6:
            return "waspada"
    return "aman"


def _tb_drill(title, sub, href=""):
    return {"title": title, "sub": sub, "href": href}


@frappe.whitelist(allow_guest=True)
def tools_board(disaster_event=None):
    """Manajemen Alat Kerja dashboard (matches the DMS mock-up), guest read-only.

    One payload built from real RN Resource Profile / RN Work Tool Request /
    RN Work Tool Deployment rows plus a keyword-matched BBM/fuel slice of
    RN Stock Observation (same pattern as Dapur Umum's gas_bbm). PIC phone
    numbers are never included here — use restricted_resource() when
    authorized.
    """
    event = resolve_disaster_event(disaster_event)

    res_filters = {"disaster_event": event} if event else {}

    resources = frappe.get_all(
        "RN Resource Profile",
        filters=res_filters,
        fields=[
            "name", "resource_name", "resource_type", "category", "quantity",
            "unit", "availability_status", "current_location", "coverage_area",
            "verification_status", "modified", "owner_type", "owner_id",
            "canonical_category", "canonical_group", "canonical_item",
            "normalization_source", "normalization_confidence",
        ],
        order_by="category asc, resource_name asc",
        limit_page_length=2000,
    )

    requests = frappe.get_all(
        "RN Work Tool Request",
        filters=res_filters,
        fields=[
            "name", "tool_name", "tool_type", "quantity", "unit", "location",
            "needed_for", "priority", "required_operator_skill",
            "request_status", "verification_status",
        ],
        order_by="creation desc",
        limit_page_length=2000,
    )

    resource_names = {r.name for r in resources}
    request_names = {r.name for r in requests}

    all_deployments = frappe.get_all(
        "RN Work Tool Deployment",
        fields=[
            "name", "work_tool_request", "resource_profile", "quantity_assigned",
            "deployment_status", "destination_location", "operator_name",
            "operator_skill", "deployed_at", "completed_at",
        ],
        order_by="deployed_at desc, creation desc",
        limit_page_length=3000,
    )

    deployments = [
        d for d in all_deployments
        if d.resource_profile in resource_names or d.work_tool_request in request_names
    ]

    resource_by_name = {r.name: r for r in resources}
    request_by_name = {r.name: r for r in requests}

    # --- Totals / KPI ---
    alat_tersedia = [r for r in resources if r.availability_status == "available"]
    kebutuhan_alat = [r for r in requests if r.request_status not in ("fulfilled", "cancelled")]
    dispatch_berjalan = [d for d in deployments if d.deployment_status in ("deployed", "in_use")]
    alat_rusak = [r for r in resources if r.availability_status in ("maintenance", "unavailable")]

    active_operators = {}
    for d in deployments:
        if d.operator_name and d.deployment_status in ACTIVE_DEPLOYMENT:
            active_operators[d.operator_name] = d

    # --- Categories (6 tile inventory) ---
    cat_map = {}
    for r in resources:
        cat = cat_map.setdefault(r.category, {
            "category": r.category,
            "label": _CATEGORY_LABELS.get(r.category, r.category or "Lainnya"),
            "total": 0, "ready": 0, "assigned": 0, "maintenance": 0, "critical": 0,
        })
        cat["total"] += 1
        key = _LEGEND_BY_STATUS.get(r.availability_status)
        if key:
            cat[key] += 1
    categories = sorted(
        cat_map.values(),
        key=lambda c: _CATEGORY_ORDER.index(c["category"]) if c["category"] in _CATEGORY_ORDER else 99,
    )

    # --- BBM & Support Operasional (fuel) ---
    fuel_rows = frappe.get_all(
        "RN Stock Observation",
        filters=res_filters,
        fields=["item_name", "unit", "quantity", "quantity_max", "stock_state", "observed_at"],
        order_by="observed_at desc",
        limit_page_length=500,
    )
    seen_fuel = set()
    fuel = []
    for row in fuel_rows:
        key = (row.item_name, row.unit or "")
        if key in seen_fuel or not any(k in (row.item_name or "").lower() for k in _FUEL_KEYWORDS):
            continue
        seen_fuel.add(key)
        status = _fuel_status(flt(row.quantity) if row.quantity is not None else None, row.quantity_max)
        fuel.append({
            "item_name": row.item_name,
            "unit": row.unit,
            "stok": row.quantity,
            "kapasitas": row.quantity_max,
            "status": status,
            "observed_at": row.observed_at,
        })
    bbm_kritis = [f for f in fuel if f["status"] == "kritis"]

    totals = {
        "alat_tersedia": len(alat_tersedia),
        "kebutuhan_alat": len(kebutuhan_alat),
        "operator_aktif": len(active_operators),
        "dispatch_berjalan": len(dispatch_berjalan),
        "bbm_kritis": len(bbm_kritis),
        "alat_rusak": len(alat_rusak),
    }

    kpi_items = {
        "alat_tersedia_items": [
            _tb_drill(r.resource_name, f"{_CATEGORY_LABELS.get(r.category, r.category)} · {r.current_location or '-'}")
            for r in alat_tersedia
        ],
        "kebutuhan_alat_items": [
            _tb_drill(r.tool_name, f"{r.location or '-'} · {_PRIORITY_LABEL.get(r.priority, r.priority)} · {r.request_status}")
            for r in kebutuhan_alat
        ],
        "operator_aktif_items": [
            _tb_drill(name, f"{d.operator_skill or '-'} · {d.destination_location or '-'} · {_DEPLOY_STATUS_LABEL.get(d.deployment_status, d.deployment_status)}")
            for name, d in active_operators.items()
        ],
        "dispatch_berjalan_items": [
            _tb_drill(
                (resource_by_name.get(d.resource_profile) or {}).get("resource_name") or "Alat",
                f"{d.destination_location or '-'} · operator {d.operator_name or '-'}",
            )
            for d in dispatch_berjalan
        ],
        "bbm_kritis_items": [
            _tb_drill(f["item_name"], f"Stok {f['stok']} {f['unit']} tersisa")
            for f in bbm_kritis
        ],
        "alat_rusak_items": [
            _tb_drill(r.resource_name, f"{r.current_location or '-'} · {r.availability_status}")
            for r in alat_rusak
        ],
    }

    # --- Operator & Tenaga Teknis ---
    operators = []
    seen_ops = set()
    for d in deployments:
        if not d.operator_name or d.operator_name in seen_ops:
            continue
        seen_ops.add(d.operator_name)
        operators.append({
            "name": d.operator_name,
            "skill": d.operator_skill or "-",
            "status": d.deployment_status,
            "status_label": _DEPLOY_STATUS_LABEL.get(d.deployment_status, d.deployment_status),
            "location": d.destination_location or "-",
        })

    # --- Matching Kebutuhan Alat ---
    open_requests = sorted(
        [r for r in requests if r.request_status == "requested"],
        key=lambda r: _PRIORITY_RANK.get(r.priority, 3),
    )
    matches = []
    for r in open_requests:
        candidates = [
            x for x in resources
            if x.category == r.tool_type and x.availability_status == "available"
        ]
        matches.append({
            "request": r.name,
            "tool_name": r.tool_name,
            "location": r.location,
            "priority": r.priority,
            "priority_label": _PRIORITY_LABEL.get(r.priority, r.priority),
            "quantity": r.quantity,
            "needed_for": r.needed_for,
            "candidate_count": len(candidates),
            "candidate_resource": candidates[0].resource_name if candidates else None,
            "candidate_location": candidates[0].current_location if candidates else None,
        })

    # --- Jadwal Dispatch Alat ---
    dispatch = []
    for d in deployments:
        res = resource_by_name.get(d.resource_profile)
        req = request_by_name.get(d.work_tool_request)
        dispatch.append({
            "deployment": d.name,
            "tool_name": (res.resource_name if res else None) or (req.tool_name if req else "Alat"),
            "operator": d.operator_name or "-",
            "destination": d.destination_location or "-",
            "status": d.deployment_status,
            "status_label": _DEPLOY_STATUS_LABEL.get(d.deployment_status, d.deployment_status),
            "deployed_at": d.deployed_at,
            "completed_at": d.completed_at,
        })

    # --- Lokasi Kerja & Produktivitas ---
    by_loc = defaultdict(list)
    for d in deployments:
        if d.destination_location:
            by_loc[d.destination_location].append(d)
    sites = []
    for loc, rows in by_loc.items():
        total = len(rows)
        completed = sum(1 for x in rows if x.deployment_status == "completed")
        sites.append({
            "location": loc,
            "total": total,
            "completed": completed,
            "progress_pct": round(100.0 * completed / total, 1) if total else 0,
        })
    sites.sort(key=lambda s: -s["total"])

    # --- Hambatan Alat Kerja ---
    blockers = []
    for r in requests:
        if r.priority in ("critical", "urgent") and r.request_status == "requested":
            blockers.append({
                "type": "kebutuhan_belum_terpenuhi",
                "label": r.tool_name,
                "detail": f"{r.location or '-'} · prioritas {_PRIORITY_LABEL.get(r.priority, r.priority)}",
                "severity": r.priority,
            })
    for f in bbm_kritis:
        blockers.append({
            "type": "bbm_kritis",
            "label": f["item_name"],
            "detail": f"Stok {f['stok']} {f['unit']} tersisa",
            "severity": "critical",
        })
    for r in alat_rusak:
        if r.availability_status == "unavailable":
            blockers.append({
                "type": "alat_rusak",
                "label": r.resource_name,
                "detail": f"{r.current_location or '-'} · perlu perbaikan",
                "severity": "urgent",
            })
    blockers.sort(key=lambda b: _PRIORITY_RANK.get(b["severity"], 3))

    # --- Ringkasan Hari Ini ---
    today_str = nowdate()
    dispatch_selesai_today = sum(
        1 for d in deployments
        if d.deployment_status == "completed" and d.completed_at
        and str(d.completed_at)[:10] == today_str
    )
    kerusakan_baru = sum(
        1 for r in resources
        if r.availability_status in ("maintenance", "unavailable")
        and r.modified and str(r.modified)[:10] == today_str
    )
    total_hours = 0.0
    for d in deployments:
        if d.deployment_status == "completed" and d.deployed_at and d.completed_at \
                and str(d.completed_at)[:10] == today_str:
            try:
                total_hours += time_diff_in_hours(get_datetime(d.completed_at), get_datetime(d.deployed_at))
            except Exception:
                pass
    penggunaan_pct = round(
        100.0 * len(dispatch_berjalan) / len(resources), 1
    ) if resources else 0.0

    summary = {
        "penggunaan_pct": penggunaan_pct,
        "jam_operasional": round(total_hours, 1),
        "dispatch_selesai": dispatch_selesai_today,
        "kerusakan_baru": kerusakan_baru,
    }

    # --- Kelompok Alat (AI Normalisasi Lintas Posko) ---
    # Groups every resource (any owner_type — organization/posko/individual)
    # by a canonical group name so the same equipment scattered across many
    # posko/owners with different raw names or units still rolls up into one
    # line. Uses the stored canonical_* fields when a human/manager already
    # set them (normalization_status=accepted); otherwise falls back to the
    # same rule-based classify_text() used for RN Community Need/RN Stock
    # Observation elsewhere in the app, honestly labelled "rule"/"ai" per
    # normalization_source (this app never claims a black-box "AI" call —
    # the rules are deterministic keyword matches).
    equip_groups = defaultdict(lambda: {
        "total_qty": 0.0, "unit_breakdown": defaultdict(float),
        "locations": set(), "confidence_scores": [], "sources": set(),
        "item_count": 0, "category": None,
    })
    for r in resources:
        if r.canonical_group:
            group_key = r.canonical_group
            cat_label = r.canonical_category or _CATEGORY_LABELS.get(r.category, r.category)
            source = r.normalization_source or "rule"
            confidence = r.normalization_confidence
        else:
            guess = classify_text(r.resource_name or r.category or "")
            group_key = guess["canonical_group"] or _CATEGORY_LABELS.get(r.category, r.category) or "Lainnya"
            cat_label = guess["canonical_category"] or _CATEGORY_LABELS.get(r.category, r.category)
            source = "rule" if guess["canonical_group"] else "tidak_diketahui"
            confidence = guess["normalization_confidence"] if guess["canonical_group"] else None

        g = equip_groups[group_key]
        g["category"] = cat_label
        g["total_qty"] += flt(r.quantity)
        g["unit_breakdown"][normalize_unit(r.unit)] += flt(r.quantity)
        if r.current_location:
            g["locations"].add(r.current_location)
        if confidence:
            g["confidence_scores"].append(confidence)
        g["sources"].add(source)
        g["item_count"] += 1

    groups = []
    for group_key, g in equip_groups.items():
        same_unit = len(g["unit_breakdown"]) == 1
        groups.append({
            "group": group_key,
            "category": g["category"],
            "item_count": g["item_count"],
            "total_qty": round(g["total_qty"], 1) if same_unit else None,
            "unit_breakdown": [
                {"unit": u, "qty": round(q, 1)} for u, q in g["unit_breakdown"].items()
            ],
            "same_unit": same_unit,
            "posko_spread": len(g["locations"]),
            "avg_confidence": (
                round(sum(g["confidence_scores"]) / len(g["confidence_scores"]))
                if g["confidence_scores"] else None
            ),
            "source": (
                "manual" if "manual" in g["sources"]
                else "ai" if "ai" in g["sources"]
                else "rule" if "rule" in g["sources"]
                else "tidak_diketahui"
            ),
        })
    groups.sort(key=lambda x: -x["item_count"])

    return {
        "disaster_event": event,
        "generated_at": now_datetime(),
        "totals": totals,
        "kpi_items": kpi_items,
        "categories": categories,
        "operators": operators,
        "matches": matches,
        "dispatch": dispatch,
        "sites": sites,
        "fuel": fuel,
        "blockers": blockers,
        "summary": summary,
        "groups": groups,
        "groups_note": (
            "Pengelompokan otomatis lintas posko/pemilik berdasarkan nama alat "
            "(aturan kata kunci, ditandai 'rule', atau ditetapkan manual oleh "
            "operator, ditandai 'manual'). Alat dengan satuan berbeda "
            "ditampilkan terpisah per satuan, tidak dijumlahkan langsung."
        ),
        "asset_registry": [
            {
                "code": r.name,
                "resource_name": r.resource_name,
                "category": _CATEGORY_LABELS.get(r.category, r.category),
                "status": r.availability_status,
                "location": r.current_location or "-",
            }
            for r in resources
        ],
        "privacy": (
            "Aggregate only. PIC/contact tidak dikirim melalui board publik."
        ),
    }


DEFAULT_DEMO_PROFILE_USER = "SIM-VOL-YUSUF"

_PERSONAL_CATEGORIES = ("kendaraan", "fasilitas", "barang_bantuan")


def _split_lines(text):
    return [line.strip() for line in (text or "").split("\n") if line.strip()]


@frappe.whitelist(allow_guest=True)
def resource_profile_board(user_account=None):
    """Profil Sumber Daya (matches the DMS mock-up) — a single volunteer/
    member's own profile: verified-contact chips, skills, personally-owned
    vehicles/facilities/aid items (RN Resource Profile, owner_type=
    individual), service areas + availability schedule (RN Volunteer
    Profile), and open personal support needs (RN Work Tool Request,
    requested_by_type=other). Guest-read; falls back to a seeded demo
    profile when no session/param identifies a user, same convention as
    every other board defaulting to event-sim-001 when no event is given.
    """
    actor = rn_actor(required=False)
    target = user_account or _actor_name(actor) or DEFAULT_DEMO_PROFILE_USER

    ua = frappe.db.get_value(
        "RN User Account", target,
        ["name", "title", "username", "phone", "email", "role", "organization", "posko", "status", "creation"],
        as_dict=True,
    )
    if not ua:
        frappe.throw("Akun tidak ditemukan", frappe.DoesNotExistError)

    org_title = (
        frappe.db.get_value("RN Organization", ua.organization, "title")
        if ua.organization else None
    )

    vp = frappe.db.get_value(
        "RN Volunteer Profile", {"user_account": target},
        ["name", "volunteer_name", "contact", "main_skill", "skill_tags", "availability_status",
         "duration_available", "current_location", "assigned_posko", "skill_category", "preferences",
         "equipment_owned", "needs_transport", "notes", "verification_status",
         "service_areas", "availability_schedule"],
        as_dict=True,
    )

    resources = frappe.get_all(
        "RN Resource Profile",
        filters={"owner_type": "individual", "owner_id": target},
        fields=["name", "resource_name", "category", "resource_type", "quantity", "unit",
                "capacity_description", "availability_status", "current_location", "notes"],
        order_by="creation desc",
        limit_page_length=200,
    )

    needs = frappe.get_all(
        "RN Work Tool Request",
        filters={"requested_by_type": "other", "requested_by_id": target},
        fields=["name", "tool_name", "tool_type", "quantity", "unit", "priority",
                "request_status", "needed_for", "location"],
        order_by="creation desc",
        limit_page_length=200,
    )

    by_cat = {c: [] for c in _PERSONAL_CATEGORIES}
    for r in resources:
        by_cat.setdefault(r.category or "lainnya", []).append(r)

    skills = []
    if vp:
        if vp.main_skill:
            skills.append(vp.main_skill)
        skills += [
            s.strip() for s in (vp.skill_tags or "").split(",")
            if s.strip() and s.strip() not in skills
        ]

    verified = bool(vp and vp.verification_status == "verified")
    name_display = (vp.volunteer_name if vp else None) or ua.title or ua.username

    can_edit = bool(actor and _actor_name(actor) == target)

    return {
        "target": target,
        "volunteer_profile": vp.name if vp else None,
        "generated_at": now_datetime(),
        "can_edit": can_edit,
        "identity": {
            "name": name_display,
            "role": (vp.main_skill if vp else None) or ua.role,
            "organization": org_title,
            "location": (vp.current_location if vp else None) or "-",
            "email": ua.email,
            "phone": ua.phone or (vp.contact if vp else None),
            "about": (vp.notes if vp else None) or "-",
            "joined_at": ua.creation,
            "aktif": (vp.availability_status != "unavailable") if vp else (ua.status == "active"),
        },
        "chips": {
            "peran_utama": ((vp.main_skill if vp else None) or ua.role or "-"),
            "peran_tipe": "Relawan" if vp else "Anggota Organisasi",
            "trust_label": "Terverifikasi" if verified else "Belum Terverifikasi",
            "email_verified": bool(ua.email),
            "phone_verified": bool(ua.phone or (vp.contact if vp else None)),
            "id_verified": verified,
        },
        "skills": [
            {"label": s, "status_label": "Tersertifikasi" if verified else "Belum Tersertifikasi"}
            for s in skills
        ],
        "kendaraan": by_cat.get("kendaraan", []),
        "fasilitas": by_cat.get("fasilitas", []),
        "barang_bantuan": by_cat.get("barang_bantuan", []),
        "service_areas": _split_lines(vp.service_areas if vp else None),
        "schedule": _split_lines(vp.availability_schedule if vp else None),
        "support_needs": needs,
        "raw": {
            "skill_tags": (vp.skill_tags if vp else None) or "",
            "service_areas": (vp.service_areas if vp else None) or "",
            "availability_schedule": (vp.availability_schedule if vp else None) or "",
            "current_location": (vp.current_location if vp else None) or "",
            "notes": (vp.notes if vp else None) or "",
        },
    }


@frappe.whitelist()
def add_personal_resource(
    resource_name,
    category,
    resource_type=None,
    quantity=1,
    unit="unit",
    capacity_description=None,
    availability_status="available",
    current_location=None,
    notes=None,
    disaster_event=None,
):
    """Self-service add for Profil Sumber Daya's Kendaraan/Fasilitas/Bantuan
    Barang cards — an individual manages their own RN Resource Profile rows
    without needing a MANAGER_ROLES operator role (unlike
    create_resource_profile, which is for org/posko-owned equipment)."""
    disaster_event = resolve_disaster_event(disaster_event)
    actor = rn_actor()
    owner_id = _actor_name(actor)

    if not owner_id:
        frappe.throw("Akun Rescue-Net aktif tidak ditemukan", frappe.PermissionError)

    if category not in _PERSONAL_CATEGORIES:
        frappe.throw("Kategori tidak valid")

    doc = frappe.new_doc("RN Resource Profile")
    doc.disaster_event = disaster_event
    doc.owner_type = "individual"
    doc.owner_id = owner_id
    doc.resource_name = resource_name
    doc.resource_type = resource_type or category
    doc.category = category
    doc.quantity = flt(quantity or 1)
    doc.unit = unit
    doc.capacity_description = capacity_description
    doc.availability_status = availability_status
    doc.current_location = current_location
    doc.notes = notes
    doc.verification_status = "self_reported"
    doc.insert(ignore_permissions=True)

    return {
        "resource_profile": doc.name,
        "category": doc.category,
        "availability_status": doc.availability_status,
    }


@frappe.whitelist()
def add_personal_support_need(
    tool_name,
    tool_type=None,
    quantity=1,
    unit="unit",
    location=None,
    needed_for=None,
    priority="normal",
    notes=None,
    disaster_event=None,
):
    """Self-service "Ajukan Kebutuhan" for Profil Sumber Daya's Kebutuhan
    Support card — creates a real RN Work Tool Request for the logged-in
    individual (requested_by_type="other", the closest fit the doctype's
    own validate() allows for a non-posko/non-organization requester)."""
    disaster_event = resolve_disaster_event(disaster_event)
    actor = rn_actor()
    owner_id = _actor_name(actor)

    if not owner_id:
        frappe.throw("Akun Rescue-Net aktif tidak ditemukan", frappe.PermissionError)

    doc = frappe.new_doc("RN Work Tool Request")
    doc.disaster_event = disaster_event
    doc.requested_by_type = "other"
    doc.requested_by_id = owner_id
    doc.tool_name = tool_name
    doc.tool_type = tool_type
    doc.quantity = flt(quantity or 1)
    doc.unit = unit
    doc.location = location
    doc.needed_for = needed_for
    doc.priority = priority
    doc.request_status = "requested"
    doc.notes = notes
    doc.created_by_user = owner_id
    doc.verification_status = "self_reported"
    doc.insert(ignore_permissions=True)

    return {
        "work_tool_request": doc.name,
        "status": doc.request_status,
    }


_OBJECT_TYPE_LABELS = {
    "longsoran": "Longsoran",
    "jembatan_putus": "Jembatan Putus",
    "puing_berat": "Puing Berat",
    "pohon_tumbang": "Pohon Tumbang",
    "akses_terendam": "Akses Terendam",
    "lainnya": "Lainnya",
}

# Each entry: (equipment category, size-per-unit divisor, plain-language basis).
# qty = max(1, ceil(size_value / divisor)). Deliberately a simple, documented
# heuristic — not an engineering calculation — used to give a starting-point
# estimate of equipment demand from a reported work object's rough size.
_EQUIP_PREDICTION_RULES = {
    "longsoran": [
        ("ekskavator", 150, "1 ekskavator per ~150 m³ material longsor"),
    ],
    "jembatan_putus": [
        ("perahu_karet", 25, "1 perahu karet per ~25 m bentang sebagai jalur alternatif"),
        ("genset", 50, "1 genset per ~50 m bentang untuk penerangan area kerja malam"),
    ],
    "puing_berat": [
        ("chainsaw", 100, "1 chainsaw per ~100 m² puing berpohon/berkayu"),
        ("forklift", 300, "1 forklift per ~300 m² puing untuk angkut material berat"),
    ],
    "pohon_tumbang": [
        ("chainsaw", 5, "1 chainsaw per ~5 pohon tumbang"),
    ],
    "akses_terendam": [
        ("pompa_air", 200, "1 pompa air per ~200 m² area tergenang"),
    ],
    "lainnya": [],
}


def _predict_equipment(object_type, size_value, ready_by_category):
    rules = _EQUIP_PREDICTION_RULES.get(object_type, [])
    size = flt(size_value)
    out = []
    for category, divisor, basis in rules:
        qty = max(1, math.ceil(size / divisor)) if size > 0 else 1
        ready = ready_by_category.get(category, 0)
        out.append({
            "category": category,
            "label": _CATEGORY_LABELS.get(category, category),
            "predicted_qty": qty,
            "basis": basis,
            "ready_available": ready,
            "gap": max(0, qty - ready),
        })
    return out


@frappe.whitelist(allow_guest=True)
def work_objects_board(disaster_event=None):
    """Object Kerja & Prediksi Kebutuhan Alat — real reported incident/damage
    objects (longsoran/jembatan putus/puing berat/...) with a heuristic
    equipment-need prediction per object, cross-referenced against real
    ready-available counts per category (same categories as tools_board's
    Inventari Alat per Kategori) so a gap is visible immediately.
    """
    event = resolve_disaster_event(disaster_event)
    filters = {"disaster_event": event} if event else {}

    objects = frappe.get_all(
        "RN Work Object",
        filters=filters,
        fields=[
            "name", "title", "object_type", "location", "size_value",
            "size_unit", "status", "reported_by", "notes", "observed_at",
        ],
        order_by="creation desc",
        limit_page_length=200,
    )

    resources = frappe.get_all(
        "RN Resource Profile",
        filters=filters,
        fields=["category", "availability_status"],
        limit_page_length=2000,
    )
    ready_by_category = defaultdict(int)
    for r in resources:
        if r.availability_status == "available":
            ready_by_category[r.category] += 1

    rows = []
    for o in objects:
        predictions = _predict_equipment(o.object_type, o.size_value, ready_by_category)
        rows.append({
            "name": o.name,
            "title": o.title,
            "object_type": o.object_type,
            "object_type_label": _OBJECT_TYPE_LABELS.get(o.object_type, o.object_type),
            "location": o.location,
            "size_value": o.size_value,
            "size_unit": o.size_unit,
            "status": o.status,
            "reported_by": o.reported_by,
            "notes": o.notes,
            "observed_at": o.observed_at,
            "predictions": predictions,
            "total_gap": sum(p["gap"] for p in predictions),
        })

    return {
        "disaster_event": event,
        "generated_at": now_datetime(),
        "objects": rows,
        "open_count": sum(1 for r in rows if r["status"] == "open"),
        "method_note": (
            "Prediksi kebutuhan alat adalah estimasi heuristik dari ukuran "
            "object kerja (bukan perhitungan teknik/rekayasa resmi) — "
            "gunakan sebagai titik awal perencanaan, bukan keputusan akhir."
        ),
    }


@frappe.whitelist()
def create_work_object(
    title,
    object_type,
    size_value,
    size_unit=None,
    location=None,
    notes=None,
    disaster_event=None,
):
    disaster_event = resolve_disaster_event(disaster_event)
    actor = rn_actor()

    doc = frappe.new_doc("RN Work Object")
    doc.disaster_event = disaster_event
    doc.title = title
    doc.object_type = object_type
    doc.size_value = flt(size_value)
    doc.size_unit = size_unit
    doc.location = location
    doc.status = "open"
    doc.reported_by = _actor_name(actor) or "Guest"
    doc.notes = notes
    doc.verification_status = "self_reported"
    doc.insert(ignore_permissions=True)

    return {
        "work_object": doc.name,
        "predictions": _predict_equipment(doc.object_type, doc.size_value, {}),
    }


@frappe.whitelist()
def update_work_object_status(work_object, status):
    actor = rn_actor()

    if not _is_manager(actor):
        frappe.throw("Hak operator diperlukan", frappe.PermissionError)

    if status not in ("open", "in_progress", "resolved"):
        frappe.throw("Status tidak valid")

    doc = frappe.get_doc("RN Work Object", work_object)
    doc.status = status
    doc.save(ignore_permissions=True)

    return {"work_object": doc.name, "status": doc.status}
