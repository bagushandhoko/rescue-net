"""Donor programs — ownership / verification helpers and serialisers."""

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


PROGRAM_FIELDS = [
    "name",
    "disaster_event",
    "program_name",
    "program_type",
    "owner_type",
    "owner_id",
    "target_description",
    "target_amount",
    "target_unit",
    "current_amount",
    "status",
    "location",
    "contact_person",
    "contact_phone",
    "public_visibility",
    "created_by_user",
    "observed_at",
    "notes",
    "creation",
    "modified",
]


UPDATE_FIELDS = [
    "name",
    "program",
    "disaster_event",
    "update_type",
    "progress_percent",
    "amount_spent",
    "amount_unit",
    "update_title",
    "update_notes",
    "evidence_file_id",
    "evidence_required",
    "evidence_status",
    "officer_in_charge_name",
    "officer_in_charge_phone",
    "public_visibility",
    "created_by_user",
    "observed_at",
    "creation",
]


def _owner_type(value):
    value = (value or "organization").strip().lower()

    allowed = {
        "organization",
        "posko",
        "community_group",
    }

    if value not in allowed:
        frappe.throw(
            "Owner type tidak didukung"
        )

    return value


def _allowed_owner(actor, owner_type, owner_id):
    if _is_control(actor):
        return True

    if not owner_id:
        return False

    owner_type = _owner_type(owner_type)

    if owner_type == "posko":
        return owner_id in set(
            _allowed_poskos(actor) or []
        )

    allowed_poskos = list(
        _allowed_poskos(actor) or []
    )

    if not allowed_poskos:
        return False

    meta = frappe.get_meta("RN Posko")

    organization_field = None

    for fieldname in (
        "organization",
        "organization_id",
        "kelompok",
    ):
        if meta.has_field(fieldname):
            organization_field = fieldname
            break

    if not organization_field:
        return False

    rows = frappe.get_all(
        "RN Posko",
        filters={
            "name": ["in", allowed_poskos],
            organization_field: owner_id,
        },
        fields=["name"],
        limit_page_length=1,
    )

    return bool(rows)


def _assert_owner(actor, owner_type, owner_id):
    if not _allowed_owner(
        actor,
        owner_type,
        owner_id,
    ):
        frappe.throw(
            "Akses Donor Program ditolak",
            frappe.PermissionError,
        )


_VERIFIED_STATUSES = {"verified", "official_verified", "community_verified"}


def _owner_verified(owner_type, owner_id):
    """Only a verified organization/posko, or a verified individual, may
    have their donation program/tender appear publicly (owner request:
    campaign creation itself isn't blocked — an unverified owner's
    program is just kept off the public list until they clear the
    SAME verification queue every org/posko/user already goes through,
    see api_verification.approval_queue)."""
    if not owner_id:
        return False
    if owner_type == "organization":
        return frappe.db.get_value("RN Organization", owner_id, "verification_status") in _VERIFIED_STATUSES
    if owner_type == "posko":
        return frappe.db.get_value("RN Posko", owner_id, "verification_status") in _VERIFIED_STATUSES
    return False


def _actor_verified_person(actor):
    """A verified individual: either an active registered verifier, or a
    registrant whose own freely-chosen reference (see api_auth.register /
    RN User Reference) has actually been confirmed by a reviewer."""
    if not actor or not getattr(actor, "name", None):
        return False
    if frappe.db.exists("RN Verifier Profile", {"user": actor.name, "verifier_status": "active"}):
        return True
    if frappe.db.exists("RN User Reference", {"user_account": actor.name, "status": "confirmed"}):
        return True
    return False


def _campaign_owner_verified(actor, owner_type, owner_id):
    if owner_type in ("organization", "posko"):
        return _owner_verified(owner_type, owner_id)
    return _actor_verified_person(actor)


def _program(name):
    row = frappe.db.get_value(
        "RN Donor Program",
        name,
        PROGRAM_FIELDS,
        as_dict=True,
    )

    if not row:
        frappe.throw(
            "Donor Program tidak ditemukan"
        )

    return row


def _serialize_program(row, include_contact=True):
    result = dict(row)

    result["id"] = result["name"]

    if not include_contact:
        result.pop("contact_person", None)
        result.pop("contact_phone", None)
        result.pop("notes", None)

    return result


def _serialize_update(row, include_contact=True):
    result = dict(row)

    result["id"] = result["name"]
    result["program_id"] = result["program"]

    if not include_contact:
        result.pop(
            "officer_in_charge_name",
            None,
        )
        result.pop(
            "officer_in_charge_phone",
            None,
        )

    return result


def _program_updates(
    program,
    public_only=False,
):
    filters = {
        "program": program,
    }

    if public_only:
        filters["public_visibility"] = (
            "summary_public"
        )

    rows = frappe.get_all(
        "RN Donor Program Update",
        filters=filters,
        fields=UPDATE_FIELDS,
        order_by="creation desc",
        limit_page_length=2000,
    )

    return [
        _serialize_update(
            x,
            include_contact=not public_only,
        )
        for x in rows
    ]


def _build_context(
    programs,
    public_only=False,
):
    enriched = []
    all_updates = []

    for row in programs:
        program = _serialize_program(
            row,
            include_contact=(
                not public_only
                or row.public_visibility
                == "summary_public"
            ),
        )

        updates = _program_updates(
            row.name,
            public_only=public_only,
        )

        program["updates"] = updates
        program["update_count"] = len(updates)

        program["spent_amount"] = sum(
            flt(x.get("amount_spent"))
            for x in updates
        )

        enriched.append(program)
        all_updates.extend(updates)

    return {
        "programs": enriched,
        "updates": all_updates,
        "summary": {
            "program_count": len(enriched),
            "active_count": len([
                p
                for p in enriched
                if p.get("status") == "active"
            ]),
            "update_count": len(all_updates),
            "target_total": sum(
                flt(
                    p.get("target_amount")
                )
                for p in enriched
            ),
            "current_total": sum(
                flt(
                    p.get("current_amount")
                )
                for p in enriched
            ),
            "spent_total": sum(
                flt(
                    u.get("amount_spent")
                )
                for u in all_updates
            ),
        },
        "generated_at": str(
            now_datetime()
        ),
    }


SPECIAL_PROGRAM_FIELDS = PROGRAM_FIELDS + [
    "target_location",
    "target_node_id",
    "target_beneficiaries",
    "budget_target",
    "budget_received",
    "budget_spent",
    "priority",
    "start_date",
    "end_date",
    "description",
    "officer_in_charge_name",
    "officer_in_charge_phone",
    "evidence_file_id",
    "updated_by_user",
]


_PROGRAM_TYPE_LABELS = {
    "special_program": "Program Khusus",
    "energy_support": "Energi & Penerangan",
    "water_sanitation": "Air & Sanitasi",
    "shelter": "Shelter",
    "health": "Kesehatan",
    "nutrition": "Pangan & Gizi",
    "logistics": "Logistik & Pangan",
    "education": "Pendidikan",
    "psychosocial": "Psikososial",
    "livelihood": "Pemulihan Ekonomi",
    "wildlife": "Satwa & Lingkungan",
}


_PRIORITY_CRITICAL = {"critical", "urgent", "high", "tinggi", "darurat"}
