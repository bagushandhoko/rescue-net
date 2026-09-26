"""Donor programs — special programs (Program Khusus) and their updates."""

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
    SPECIAL_PROGRAM_FIELDS,
    UPDATE_FIELDS,
    _allowed_owner,
    _assert_owner,
    _campaign_owner_verified,
    _owner_type,
)


@frappe.whitelist()
def create_special_program(
    disaster_event,
    program_name,
    owner_type="organization",
    owner_id=None,
    program_type="special_program",
    target_location=None,
    target_node_id=None,
    target_beneficiaries=None,
    budget_target=0,
    budget_received=0,
    budget_spent=0,
    status="planned",
    priority="normal",
    start_date=None,
    end_date=None,
    description=None,
    public_visibility="summary_public",
    officer_in_charge_name=None,
    officer_in_charge_phone=None,
    evidence_file_id=None,
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

    # Only a verified org/posko/person may run a PUBLIC campaign. Creation
    # itself is never blocked — an unverified owner's program is just kept
    # off the public donation list until they clear the SAME verification
    # queue every org/posko/user already goes through
    # (api_verification.approval_queue), not a separate new flow.
    owner_verified = _campaign_owner_verified(actor, owner_type, owner_id)
    if not owner_verified:
        public_visibility = "restricted"

    program_name = (
        program_name or ""
    ).strip()

    if not program_name:
        frappe.throw(
            "Program Name wajib diisi"
        )

    budget_target = flt(
        budget_target
    )
    budget_received = flt(
        budget_received
    )
    budget_spent = flt(
        budget_spent
    )

    if min(
        budget_target,
        budget_received,
        budget_spent,
    ) < 0:
        frappe.throw(
            "Budget tidak boleh negatif"
        )

    # L-9: money received / spent only grows through confirmed donations and
    # spending updates — a new program starts at 0 (System Manager may seed).
    if not is_system_manager():
        budget_received = budget_spent = 0.0

    doc = frappe.new_doc(
        "RN Donor Program"
    )

    doc.disaster_event = disaster_event
    doc.owner_type = owner_type
    doc.owner_id = owner_id
    doc.program_name = program_name
    doc.program_type = (
        program_type
        or "special_program"
    )

    doc.target_location = target_location
    doc.target_node_id = target_node_id
    doc.target_beneficiaries = (
        target_beneficiaries
    )

    doc.budget_target = budget_target
    doc.budget_received = budget_received
    doc.budget_spent = budget_spent

    doc.status = (
        status or "planned"
    )
    doc.priority = (
        priority or "normal"
    )

    doc.start_date = start_date
    doc.end_date = end_date
    doc.description = description

    doc.public_visibility = (
        public_visibility
        or "summary_public"
    )

    doc.officer_in_charge_name = (
        officer_in_charge_name
    )
    doc.officer_in_charge_phone = (
        officer_in_charge_phone
    )
    doc.evidence_file_id = (
        evidence_file_id
    )

    doc.created_by_user = (
        _actor_name(actor)
    )
    doc.observed_at = now_datetime()

    doc.insert(
        ignore_permissions=True
    )

    return {
        "program": doc.name,
        "id": doc.name,
        "program_name":
            doc.program_name,
        "status":
            doc.status,
        "budget_target":
            flt(doc.budget_target),
        "budget_received":
            flt(doc.budget_received),
        "budget_spent":
            flt(doc.budget_spent),
    }


@frappe.whitelist()
def create_special_program_update(
    program,
    update_title,
    update_type="progress",
    progress_percent=0,
    amount_spent=0,
    update_notes=None,
    evidence_file_id=None,
    officer_in_charge_name=None,
    officer_in_charge_phone=None,
    public_visibility="summary_public",
):
    actor = rn_actor()

    p = frappe.db.get_value(
        "RN Donor Program",
        program,
        [
            "name",
            "disaster_event",
            "owner_type",
            "owner_id",
            "budget_spent",
        ],
        as_dict=True,
    )

    if not p:
        frappe.throw(
            "Program not found"
        )

    _assert_owner(
        actor,
        p.owner_type,
        p.owner_id,
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

    amount_spent = flt(
        amount_spent
    )

    if amount_spent < 0:
        frappe.throw(
            "Amount Spent tidak boleh negatif"
        )

    doc = frappe.new_doc(
        "RN Donor Program Update"
    )

    doc.program = p.name
    doc.disaster_event = (
        p.disaster_event
    )
    doc.update_type = (
        update_type or "progress"
    )
    doc.progress_percent = (
        progress_percent
    )
    doc.amount_spent = (
        amount_spent
    )
    doc.update_title = (
        update_title
    )
    doc.update_notes = (
        update_notes
    )
    doc.evidence_file_id = (
        evidence_file_id
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

    # Exact special-program legacy semantic:
    # hanya budget_spent yang bertambah.
    from rescue_net.services.money import add_to_program
    new_budget_spent = add_to_program(p.name, "budget_spent", amount_spent,   # L-9
                                      updated_by_user=_actor_name(actor))

    return {
        "update": doc.name,
        "id": doc.name,
        "program": p.name,
        "program_id": p.name,
        "amount_spent":
            flt(doc.amount_spent),
        "budget_spent":
            new_budget_spent,
    }


@frappe.whitelist()
def list_special_programs(
    disaster_event=None,
):
    # RN_CANONICAL_EVENT disaster_event = resolve_disaster_event(disaster_event)
    disaster_event = resolve_disaster_event(disaster_event)
    actor = rn_actor()

    filters = {
        "program_type":
            "special_program",
    }

    if disaster_event:
        filters["disaster_event"] = (
            disaster_event
        )

    rows = frappe.get_all(
        "RN Donor Program",
        filters=filters,
        fields=SPECIAL_PROGRAM_FIELDS,
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

    return [
        dict(row)
        for row in rows
    ]


@frappe.whitelist()
def get_special_program(
    program,
):
    actor = rn_actor()

    p = frappe.db.get_value(
        "RN Donor Program",
        program,
        SPECIAL_PROGRAM_FIELDS,
        as_dict=True,
    )

    if not p:
        frappe.throw(
            "Program not found"
        )

    _assert_owner(
        actor,
        p.owner_type,
        p.owner_id,
    )

    updates = frappe.get_all(
        "RN Donor Program Update",
        filters={
            "program": p.name,
        },
        fields=UPDATE_FIELDS,
        order_by="creation desc",
        limit_page_length=2000,
    )

    return {
        "program": dict(p),
        "updates": [
            dict(x)
            for x in updates
        ],
    }
