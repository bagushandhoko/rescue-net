"""Donor programs — programs, updates, evidence, context, Control Centre view."""

from collections import defaultdict

import frappe
from frappe.rate_limiter import rate_limit
from rescue_net.reference_resolver import resolve_disaster_event
from rescue_net.access_policy import is_system_manager

from frappe.utils import flt, now_datetime, nowdate

from rescue_net.api_kitchen import (
    rn_actor,
    _actor_name,
    _allowed_poskos,
    _is_control,
    _assert_operate,
)

from rescue_net.donor_program.common import (  # noqa: F401
    PROGRAM_FIELDS,
    _allowed_owner,
    _assert_owner,
    _build_context,
    _campaign_owner_verified,
    _owner_type,
    _program,
    _program_updates,
    _serialize_program,
)


@frappe.whitelist()
def create_program(
    disaster_event,
    program_name,
    program_type="general_relief",
    owner_type="organization",
    owner_id=None,
    target_description=None,
    target_amount=0,
    target_unit="IDR",
    location=None,
    contact_person=None,
    contact_phone=None,
    notes=None,
    public_visibility="summary_public",
):
    # RN_CANONICAL_EVENT disaster_event = resolve_disaster_event(disaster_event)
    disaster_event = resolve_disaster_event(disaster_event)
    actor = rn_actor()

    owner_type = _owner_type(
        owner_type
    )

    _assert_owner(
        actor,
        owner_type,
        owner_id,
    )

    if not _campaign_owner_verified(actor, owner_type, owner_id):
        public_visibility = "restricted"

    program_name = (
        program_name or ""
    ).strip()

    if not program_name:
        frappe.throw(
            "Program Name wajib diisi"
        )

    target_amount = flt(
        target_amount
    )

    if target_amount < 0:
        frappe.throw(
            "Target Amount tidak boleh negatif"
        )

    doc = frappe.new_doc(
        "RN Donor Program"
    )

    doc.disaster_event = disaster_event
    doc.program_name = program_name
    doc.program_type = (
        program_type
        or "general_relief"
    )
    doc.owner_type = owner_type
    doc.owner_id = owner_id
    doc.target_description = (
        target_description
    )
    doc.target_amount = target_amount
    doc.target_unit = (
        target_unit or "IDR"
    )
    doc.current_amount = 0
    doc.status = "active"
    doc.location = location
    doc.contact_person = contact_person
    doc.contact_phone = contact_phone
    doc.public_visibility = (
        public_visibility
        or "summary_public"
    )
    doc.created_by_user = (
        _actor_name(actor)
    )
    doc.observed_at = now_datetime()
    doc.notes = notes

    doc.insert(
        ignore_permissions=True
    )

    return {
        "program": doc.name,
        "id": doc.name,
        "status": doc.status,
        "current_amount":
            flt(doc.current_amount),
    }


@frappe.whitelist()
def create_update(
    program,
    update_title,
    update_type="progress",
    progress_percent=0,
    amount_spent=0,
    amount_unit=None,
    update_notes=None,
    evidence_file_id=None,
    officer_in_charge_name=None,
    officer_in_charge_phone=None,
    public_visibility="summary_public",
    amount_used=None,
    description=None,
):
    actor = rn_actor()

    p = _program(program)

    _assert_owner(
        actor,
        p.owner_type,
        p.owner_id,
    )

    update_type = (
        update_type
        or "progress"
    ).strip().lower()

    if update_type not in {
        "progress",
        "spending",
        "handover",
        "completion",
    }:
        frappe.throw(
            "Update Type tidak didukung"
        )

    update_title = (
        update_title or ""
    ).strip()

    if not update_title:
        frappe.throw(
            "Update Title wajib diisi"
        )

    progress_percent = flt(
        progress_percent
    )

    if (
        progress_percent < 0
        or progress_percent > 100
    ):
        frappe.throw(
            "Progress harus 0 sampai 100"
        )

    # Compatibility dengan JS legacy lama.
    if amount_used not in (
        None,
        "",
    ):
        amount = flt(
            amount_used
        )
    else:
        amount = flt(
            amount_spent
        )

    if amount < 0:
        frappe.throw(
            "Amount tidak boleh negatif"
        )

    if (
        not update_notes
        and description
    ):
        update_notes = description

    evidence_required = (
        update_type
        in {
            "spending",
            "handover",
        }
    )

    if evidence_file_id:
        evidence_status = "provided"
    elif evidence_required:
        evidence_status = "pending"
    else:
        evidence_status = (
            "not_required"
        )

    doc = frappe.new_doc(
        "RN Donor Program Update"
    )

    doc.program = p.name
    doc.disaster_event = (
        p.disaster_event
    )
    doc.update_type = update_type
    doc.progress_percent = (
        progress_percent
    )
    doc.amount_spent = amount
    doc.amount_unit = (
        amount_unit
        or p.target_unit
        or "IDR"
    )
    doc.update_title = update_title
    doc.update_notes = update_notes
    doc.evidence_file_id = (
        evidence_file_id
    )
    doc.evidence_required = (
        1 if evidence_required else 0
    )
    doc.evidence_status = (
        evidence_status
    )
    doc.officer_in_charge_name = (
        officer_in_charge_name
    )
    doc.officer_in_charge_phone = (
        officer_in_charge_phone
    )
    doc.public_visibility = (
        public_visibility
        or "summary_public"
    )
    doc.created_by_user = (
        _actor_name(actor)
    )
    doc.observed_at = now_datetime()

    doc.insert(
        ignore_permissions=True
    )

    # Exact legacy semantic:
    # current_amount bertambah amount_spent
    # pada setiap update.
    from rescue_net.services.money import add_to_program
    new_current = add_to_program(p.name, "current_amount", amount)   # L-9

    return {
        "update": doc.name,
        "id": doc.name,
        "program": p.name,
        "program_id": p.name,
        "update_type":
            doc.update_type,
        "amount_spent":
            flt(doc.amount_spent),
        "amount_used":
            flt(doc.amount_spent),
        "current_amount":
            new_current,
        "evidence_required":
            bool(doc.evidence_required),
        "evidence_status":
            doc.evidence_status,
    }


@frappe.whitelist()
def attach_evidence(
    update,
    file_url,
):
    actor = rn_actor()

    row = frappe.db.get_value(
        "RN Donor Program Update",
        update,
        [
            "name",
            "program",
        ],
        as_dict=True,
    )

    if not row:
        frappe.throw(
            "Donor Program Update tidak ditemukan"
        )

    p = _program(
        row.program
    )

    _assert_owner(
        actor,
        p.owner_type,
        p.owner_id,
    )

    file_url = (
        file_url or ""
    ).strip()

    if not file_url.startswith(
        "/private/files/"
    ):
        frappe.throw(
            "Evidence Donor Program wajib private"
        )

    frappe.db.set_value(
        "RN Donor Program Update",
        row.name,
        {
            "evidence_file_id":
                file_url,
            "evidence_status":
                "provided",
        },
        update_modified=True,
    )

    return {
        "update": row.name,
        "file_url": file_url,
        "private": True,
        "evidence_status":
            "provided",
    }


@frappe.whitelist()
def context(
    disaster_event=None,
):
    # RN_CANONICAL_EVENT disaster_event = resolve_disaster_event(disaster_event)
    disaster_event = resolve_disaster_event(disaster_event)
    actor = rn_actor()

    filters = {}

    if disaster_event:
        filters["disaster_event"] = (
            disaster_event
        )

    rows = frappe.get_all(
        "RN Donor Program",
        filters=filters,
        fields=PROGRAM_FIELDS,
        order_by="creation desc",
        limit_page_length=2000,
    )

    if not _is_control(actor):
        rows = [
            row
            for row in rows
            if _allowed_owner(
                actor,
                row.owner_type,
                row.owner_id,
            )
        ]

    result = _build_context(
        rows,
        public_only=False,
    )

    result["disaster_event_id"] = (
        disaster_event
    )

    return result


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def public_context(
    disaster_event=None,
):
    filters = {
        "public_visibility":
            "summary_public",
    }

    if disaster_event:
        filters["disaster_event"] = (
            disaster_event
        )

    rows = frappe.get_all(
        "RN Donor Program",
        filters=filters,
        fields=PROGRAM_FIELDS,
        order_by="creation desc",
        limit_page_length=2000,
        ignore_permissions=True,
    )

    result = _build_context(
        rows,
        public_only=True,
    )

    result["disaster_event_id"] = (
        disaster_event
    )

    return result


@frappe.whitelist()
def get_program(
    program,
):
    actor = rn_actor()

    p = _program(
        program
    )

    _assert_owner(
        actor,
        p.owner_type,
        p.owner_id,
    )

    return {
        "program":
            _serialize_program(
                p,
                include_contact=True,
            ),
        "updates":
            _program_updates(
                p.name,
                public_only=False,
            ),
    }


@frappe.whitelist()
def control_centre_donor():
    actor = rn_actor()

    if not _is_control(actor):
        frappe.throw(
            "Akses Control Centre ditolak",
            frappe.PermissionError,
        )

    rows = frappe.get_all(
        "RN Donor Program",
        fields=PROGRAM_FIELDS,
        limit_page_length=5000,
    )

    ctx = _build_context(
        rows,
        public_only=False,
    )

    return {
        "program_count":
            ctx["summary"][
                "program_count"
            ],
        "active_count":
            ctx["summary"][
                "active_count"
            ],
        "update_count":
            ctx["summary"][
                "update_count"
            ],
        "target_total":
            ctx["summary"][
                "target_total"
            ],
        "current_total":
            ctx["summary"][
                "current_total"
            ],
        "spent_total":
            ctx["summary"][
                "spent_total"
            ],
        "currency_note": (
            "Aggregate mempertahankan "
            "unit sumber; UI harus "
            "menghindari menjumlahkan "
            "unit berbeda sebagai "
            "satu mata uang."
        ),
    }
