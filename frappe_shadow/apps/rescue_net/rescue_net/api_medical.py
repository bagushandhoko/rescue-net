from collections import defaultdict

import frappe
from rescue_net.reference_resolver import resolve_disaster_event, resolve_posko
from frappe.utils import flt, now_datetime

from rescue_net.access_policy import (
    can_manage_organization,
    can_manage_posko,
    is_system_manager,
    rn_actor,
)


OPERATOR_ROLES = {
    "posko_operator",
    "medical_operator",
}


CASE_TRANSITIONS = {
    "active": {
        "stabilized",
        "referred",
        "evacuating",
        "discharged",
        "deceased",
        "closed",
    },
    "stabilized": {
        "referred",
        "evacuating",
        "admitted",
        "discharged",
        "closed",
    },
    "referred": {
        "evacuating",
        "admitted",
        "closed",
    },
    "evacuating": {
        "admitted",
        "discharged",
        "deceased",
        "closed",
    },
    "admitted": {
        "discharged",
        "deceased",
        "closed",
    },
    "discharged": {"closed"},
    "deceased": {"closed"},
    "closed": set(),
}


EVAC_TRANSITIONS = {
    "requested": {
        "assigned",
        "cancelled",
    },
    "assigned": {
        "en_route_pickup",
        "patient_on_board",
        "cancelled",
    },
    "en_route_pickup": {
        "patient_on_board",
        "cancelled",
    },
    "patient_on_board": {
        "arrived_hospital",
        "cancelled",
    },
    "arrived_hospital": {
        "handover_complete",
    },
    "handover_complete": set(),
    "cancelled": set(),
}


def _member_orgs(actor):
    if not actor or not actor.name:
        return []

    result = frappe.get_all(
        "RN Organization Membership",
        filters={
            "user_account": actor.name,
            "status": "approved",
        },
        pluck="organization",
        limit_page_length=500,
    )

    if getattr(
        actor,
        "organization",
        None,
    ):
        result.append(actor.organization)

    return list(
        set(x for x in result if x)
    )


def _accessible_poskos(actor):
    if is_system_manager():
        return frappe.get_all(
            "RN Posko",
            pluck="name",
            limit_page_length=5000,
        )

    result = set()

    for org in _member_orgs(actor):
        result.update(
            frappe.get_all(
                "RN Posko",
                filters={
                    "organization": org
                },
                pluck="name",
                limit_page_length=1000,
            )
        )

    if actor and actor.name:
        result.update(
            frappe.get_all(
                "RN Posko Assignment",
                filters={
                    "user_account": actor.name,
                    "status": "approved",
                },
                pluck="posko",
                limit_page_length=500,
            )
        )

    if actor and getattr(
        actor,
        "posko",
        None,
    ):
        result.add(actor.posko)

    return sorted(result)


def _can_operate(actor, posko):
    if is_system_manager():
        return True

    if not actor:
        return False

    if can_manage_posko(
        actor,
        posko,
    ):
        return True

    organization = frappe.db.get_value(
        "RN Posko",
        posko,
        "organization",
    )

    return bool(
        organization
        and can_manage_organization(
            actor,
            organization,
        )
    )


def _assert_medical_access(actor, posko):
    if not _can_operate(
        actor,
        posko,
    ):
        frappe.throw(
            "Akses medis Posko ditolak",
            frappe.PermissionError,
        )

    posko_type = frappe.db.get_value(
        "RN Posko",
        posko,
        "posko_type",
    )

    if posko_type != "medical":
        frappe.throw(
            "Posko ini bukan Posko Medis",
            frappe.ValidationError,
        )


@frappe.whitelist()
def dashboard(posko=None):
    # RN_CANONICAL_REF posko = resolve_posko(posko)
    posko = resolve_posko(posko)
    actor = rn_actor()
    allowed = _accessible_poskos(actor)

    allowed = [
        p
        for p in allowed
        if _can_operate(actor, p)
        and frappe.db.get_value(
            "RN Posko",
            p,
            "posko_type",
        ) == "medical"
    ]

    if posko:
        if posko not in allowed:
            frappe.throw(
                "Akses Posko Medis ditolak",
                frappe.PermissionError,
            )

        allowed = [posko]

    if not allowed:
        return {
            "poskos": [],
            "cases": [],
            "supply_uses": [],
            "evacuations": [],
        }

    poskos = frappe.get_all(
        "RN Posko",
        filters={
            "name": ["in", allowed]
        },
        fields=[
            "name",
            "title",
            "posko_type",
            "verification_status",
            "officer_in_charge_phone",
        ],
        order_by="title asc",
        limit_page_length=500,
    )

    cases = frappe.get_all(
        "RN Medical Case",
        filters={
            "posko": ["in", allowed]
        },
        fields=[
            "name",
            "posko",
            "patient_code",
            "age_group",
            "gender",
            "complaint",
            "severity",
            "triage_status",
            "case_status",
            "treatment_notes",
            "verification_status",
            "observed_at",
            "source_updated_at",
        ],
        order_by="creation desc",
        limit_page_length=1000,
    )

    supply_uses = frappe.get_all(
        "RN Medical Supply Use",
        filters={
            "posko": ["in", allowed]
        },
        fields=[
            "name",
            "posko",
            "medical_case",
            "item_name",
            "quantity",
            "unit",
            "notes",
            "used_at",
            "verification_status",
        ],
        order_by="creation desc",
        limit_page_length=1000,
    )

    evacuations = frappe.get_all(
        "RN Medical Evacuation",
        filters={
            "posko": ["in", allowed]
        },
        fields=[
            "name",
            "posko",
            "medical_case",
            "provider_name",
            "transport_reference",
            "vehicle_contact",
            "destination_facility",
            "evacuation_status",
            "requested_at",
            "departed_at",
            "arrived_at",
            "handover_at",
            "verification_status",
        ],
        order_by="creation desc",
        limit_page_length=1000,
    )

    return {
        "poskos": poskos,
        "cases": cases,
        "supply_uses": supply_uses,
        "evacuations": evacuations,
    }


@frappe.whitelist()
def create_case(
    posko,
    patient_code,
    complaint,
    age_group="unknown",
    gender="unknown",
    severity="mild",
    triage_status="green",
    treatment_notes=None,
):
    # RN_CANONICAL_REF posko = resolve_posko(posko)
    posko = resolve_posko(posko)
    actor = rn_actor()

    _assert_medical_access(
        actor,
        posko,
    )

    if not patient_code:
        frappe.throw(
            "Kode pasien wajib diisi"
        )

    if not complaint:
        frappe.throw(
            "Keluhan / kondisi wajib diisi"
        )

    doc = frappe.new_doc(
        "RN Medical Case"
    )

    doc.posko = posko
    doc.patient_code = patient_code
    doc.complaint = complaint
    doc.age_group = age_group
    doc.gender = gender
    doc.severity = severity
    doc.triage_status = triage_status
    doc.case_status = "active"
    doc.treatment_notes = (
        treatment_notes
    )
    doc.verification_status = (
        "self_reported"
    )

    doc.insert(
        ignore_permissions=True
    )

    return {
        "medical_case": doc.name,
        "patient_code": doc.patient_code,
        "triage_status": doc.triage_status,
        "case_status": doc.case_status,
    }


@frappe.whitelist()
def update_case_status(
    medical_case,
    new_status,
    treatment_notes=None,
):
    actor = rn_actor()

    doc = frappe.get_doc(
        "RN Medical Case",
        medical_case,
    )

    _assert_medical_access(
        actor,
        doc.posko,
    )

    current = doc.case_status

    if new_status not in (
        CASE_TRANSITIONS.get(
            current,
            set(),
        )
    ):
        frappe.throw(
            f"Transisi kasus tidak valid: "
            f"{current} -> {new_status}"
        )

    doc.case_status = new_status

    if treatment_notes:
        doc.treatment_notes = (
            treatment_notes
        )

    doc.source_updated_at = (
        now_datetime()
    )

    doc.save(
        ignore_permissions=True
    )

    return {
        "medical_case": doc.name,
        "previous_status": current,
        "case_status": doc.case_status,
    }


@frappe.whitelist()
def record_supply_use(
    posko,
    item_name,
    quantity,
    unit,
    medical_case=None,
    notes=None,
):
    # RN_CANONICAL_REF posko = resolve_posko(posko)
    posko = resolve_posko(posko)
    actor = rn_actor()

    _assert_medical_access(
        actor,
        posko,
    )

    qty = flt(quantity)

    if qty <= 0:
        frappe.throw(
            "Jumlah pemakaian harus lebih dari 0"
        )

    if medical_case:
        case_posko = frappe.db.get_value(
            "RN Medical Case",
            medical_case,
            "posko",
        )

        if case_posko != posko:
            frappe.throw(
                "Medical Case berasal dari "
                "Posko yang berbeda"
            )

    doc = frappe.new_doc(
        "RN Medical Supply Use"
    )

    doc.posko = posko
    doc.medical_case = (
        medical_case
    )
    doc.item_name = item_name
    doc.quantity = qty
    doc.unit = unit
    doc.notes = notes

    doc.insert(
        ignore_permissions=True
    )

    return {
        "medical_supply_use": doc.name,
        "quantity": doc.quantity,
        "unit": doc.unit,
        "stock_updated": False,
        "note": (
            "Pemakaian medis tidak otomatis "
            "mengubah Stock Observation."
        ),
    }


@frappe.whitelist()
def create_evacuation(
    posko,
    medical_case,
    destination_facility,
    provider_name=None,
    transport_reference=None,
    vehicle_contact=None,
    notes=None,
):
    actor = rn_actor()

    _assert_medical_access(
        actor,
        posko,
    )

    case = frappe.get_doc(
        "RN Medical Case",
        medical_case,
    )

    if case.posko != posko:
        frappe.throw(
            "Medical Case berasal dari "
            "Posko yang berbeda"
        )

    doc = frappe.new_doc(
        "RN Medical Evacuation"
    )

    doc.posko = posko
    doc.medical_case = (
        medical_case
    )
    doc.provider_name = (
        provider_name
    )
    doc.transport_reference = (
        transport_reference
    )
    doc.vehicle_contact = (
        vehicle_contact
    )
    doc.destination_facility = (
        destination_facility
    )
    doc.evacuation_status = (
        "requested"
    )
    doc.notes = notes

    doc.insert(
        ignore_permissions=True
    )

    if case.case_status in {
        "active",
        "stabilized",
    }:
        frappe.db.set_value(
            "RN Medical Case",
            case.name,
            {
                "case_status": "referred",
                "source_updated_at": (
                    now_datetime()
                ),
            },
            update_modified=False,
        )

    return {
        "medical_evacuation": doc.name,
        "evacuation_status": (
            doc.evacuation_status
        ),
    }


@frappe.whitelist()
def update_evacuation_status(
    evacuation,
    new_status,
):
    actor = rn_actor()

    doc = frappe.get_doc(
        "RN Medical Evacuation",
        evacuation,
    )

    _assert_medical_access(
        actor,
        doc.posko,
    )

    current = doc.evacuation_status

    if new_status not in (
        EVAC_TRANSITIONS.get(
            current,
            set(),
        )
    ):
        frappe.throw(
            f"Transisi evakuasi tidak valid: "
            f"{current} -> {new_status}"
        )

    now = now_datetime()

    doc.evacuation_status = (
        new_status
    )

    if new_status == "patient_on_board":
        doc.departed_at = now

        frappe.db.set_value(
            "RN Medical Case",
            doc.medical_case,
            {
                "case_status": "evacuating",
                "source_updated_at": now,
            },
            update_modified=False,
        )

    if new_status == "arrived_hospital":
        doc.arrived_at = now

    if new_status == "handover_complete":
        doc.handover_at = now

        frappe.db.set_value(
            "RN Medical Case",
            doc.medical_case,
            {
                "case_status": "admitted",
                "source_updated_at": now,
            },
            update_modified=False,
        )

    doc.save(
        ignore_permissions=True
    )

    return {
        "medical_evacuation": doc.name,
        "previous_status": current,
        "evacuation_status": (
            doc.evacuation_status
        ),
    }


@frappe.whitelist()
def add_evidence(
    reference_doctype,
    reference_name,
    file_url,
    evidence_type="other",
    caption=None,
):
    allowed = {
        "RN Medical Case",
        "RN Medical Evacuation",
    }

    if reference_doctype not in allowed:
        frappe.throw(
            "Jenis referensi evidence tidak valid"
        )

    if not (
        file_url or ""
    ).startswith(
        "/private/files/"
    ):
        frappe.throw(
            "Evidence medis wajib disimpan private"
        )

    actor = rn_actor()

    posko = frappe.db.get_value(
        reference_doctype,
        reference_name,
        "posko",
    )

    if not posko:
        frappe.throw(
            "Referensi medis tidak ditemukan"
        )

    _assert_medical_access(
        actor,
        posko,
    )

    doc = frappe.new_doc(
        "RN Medical Evidence"
    )

    doc.reference_doctype = (
        reference_doctype
    )
    doc.reference_name = (
        reference_name
    )
    doc.posko = posko
    doc.file_url = file_url
    doc.evidence_type = (
        evidence_type
    )
    doc.caption = caption
    doc.verification_status = "pending"

    doc.insert(
        ignore_permissions=True
    )

    return {
        "evidence": doc.name,
        "verification_status": (
            doc.verification_status
        ),
        "private": True,
    }


@frappe.whitelist()
def control_centre_medical():
    actor = rn_actor()

    role = getattr(
        actor,
        "role",
        None,
    )

    if (
        not is_system_manager()
        and role not in OPERATOR_ROLES
    ):
        frappe.throw(
            "Akses Control Centre medis ditolak",
            frappe.PermissionError,
        )

    allowed = _accessible_poskos(
        actor
    )

    cases = frappe.get_all(
        "RN Medical Case",
        filters={
            "posko": ["in", allowed]
        },
        fields=[
            "posko",
            "triage_status",
            "case_status",
            "severity",
        ],
        limit_page_length=5000,
    )

    triage = defaultdict(int)
    status = defaultdict(int)
    posko_counts = defaultdict(int)

    for row in cases:
        triage[
            row.triage_status
        ] += 1

        status[
            row.case_status
        ] += 1

        posko_counts[
            row.posko
        ] += 1

    return {
        "case_count": len(cases),
        "triage": dict(triage),
        "case_status": dict(status),
        "posko_case_count": (
            dict(posko_counts)
        ),
        "privacy": (
            "Aggregate only; patient code "
            "and complaint are not exposed."
        ),
    }
