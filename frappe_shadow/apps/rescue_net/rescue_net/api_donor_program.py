from collections import defaultdict

import frappe
from rescue_net.reference_resolver import resolve_disaster_event

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
    new_current = (
        flt(p.current_amount)
        + amount
    )

    frappe.db.set_value(
        "RN Donor Program",
        p.name,
        "current_amount",
        new_current,
        update_modified=True,
    )

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


# ===== SPECIAL PROGRAM COMPATIBILITY =====

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
    new_budget_spent = (
        flt(p.budget_spent)
        + amount_spent
    )

    frappe.db.set_value(
        "RN Donor Program",
        p.name,
        {
            "budget_spent":
                new_budget_spent,
            "updated_by_user":
                _actor_name(actor),
        },
        update_modified=True,
    )

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


# ===== PROGRAM KHUSUS BOARD (guest, matches the DMS mock-up) =====

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


def _program_type_label(value):
    if not value:
        return "Lainnya"
    return _PROGRAM_TYPE_LABELS.get(value, value.replace("_", " ").title())


def _pk_drill(title, sub, href=""):
    return {"title": title, "sub": sub, "href": href}


@frappe.whitelist(allow_guest=True)
def program_board(disaster_event=None):
    """Program Khusus dashboard (matches the DMS mock-up), guest read-only.

    Shows every public RN Donor Program for the event regardless of
    program_type (program_type is just a category label, e.g.
    energy_support/water_sanitation/health — "special_program" was only
    ever the create-form's default value, not a real scoping filter).
    """
    event = resolve_disaster_event(disaster_event)

    filters = {"public_visibility": "summary_public"}
    if event:
        filters["disaster_event"] = event

    rows = frappe.get_all(
        "RN Donor Program",
        filters=filters,
        fields=SPECIAL_PROGRAM_FIELDS,
        order_by="creation desc",
        limit_page_length=1000,
        ignore_permissions=True,
    )

    names = [r.name for r in rows]
    updates = frappe.get_all(
        "RN Donor Program Update",
        filters={"program": ["in", names], "public_visibility": "summary_public"},
        fields=["program", "progress_percent", "update_type", "observed_at", "creation"],
        order_by="creation desc",
        limit_page_length=3000,
    ) if names else []

    updates_by_program = defaultdict(list)
    for u in updates:
        updates_by_program[u.program].append(u)

    # "Project base" vs "cash base": a program that funds a real
    # RN Procurement Tender (design/RAB/pelaksana, already built for
    # Pengadaan & Tender) is project-based; everything else is a plain
    # cash campaign. One donation list (program_donations) works for both.
    tender_by_program = {}
    if names:
        for t in frappe.get_all(
            "RN Procurement Tender", filters={"donor_program": ["in", names]},
            fields=["name", "donor_program", "status", "title"],
            order_by="creation asc", limit_page_length=2000,
        ):
            tender_by_program.setdefault(t.donor_program, t)

    today = nowdate()
    programs = []
    for r in rows:
        prog_updates = updates_by_program.get(r.name, [])
        if prog_updates:
            progress = flt(prog_updates[0].progress_percent)
        elif flt(r.target_amount) > 0:
            progress = round(min(100.0, 100.0 * flt(r.current_amount) / flt(r.target_amount)), 1)
        else:
            progress = 0.0

        location = r.target_location or r.location or "-"
        is_late = bool(
            r.status == "active"
            and r.end_date
            and str(r.end_date) < str(today)
        )

        tender = tender_by_program.get(r.name)
        programs.append({
            "name": r.name,
            "program_name": r.program_name,
            "category": _program_type_label(r.program_type),
            "location": location,
            "status": r.status,
            "priority": r.priority,
            "progress_percent": progress,
            "target_description": r.target_description,
            "target_beneficiaries": r.target_beneficiaries,
            "budget_target": flt(r.budget_target),
            "budget_received": flt(r.budget_received),
            "budget_spent": flt(r.budget_spent),
            "start_date": r.start_date,
            "end_date": r.end_date,
            "update_count": len(prog_updates),
            "is_late": is_late,
            "program_kind": "project" if tender else "cash",
            "tender": tender.name if tender else None,
            "tender_status": tender.status if tender else None,
        })

    active = [p for p in programs if p["status"] == "active"]
    critical = [
        p for p in programs
        if (p["priority"] or "").lower() in _PRIORITY_CRITICAL and p["status"] != "completed"
    ]
    completed = [p for p in programs if p["status"] == "completed"]
    late = [p for p in programs if p["is_late"]]
    underserved_locations = {
        p["location"] for p in active
        if p["update_count"] == 0 and p["location"] != "-"
    }
    needs_support = [
        p for p in active
        if (p["priority"] or "").lower() in _PRIORITY_CRITICAL and p["progress_percent"] < 50
    ]

    totals = {
        "program_aktif": len(active),
        "program_critical": len(critical),
        "program_selesai": len(completed),
        "milestone_terlambat": len(late),
        "lokasi_belum_terlayani": len(underserved_locations),
        "butuh_support": len(needs_support),
    }

    kpi_items = {
        "program_aktif_items": [
            _pk_drill(p["program_name"], p["category"] + " · " + p["location"]) for p in active
        ],
        "program_critical_items": [
            _pk_drill(p["program_name"], p["location"] + " · prioritas " + (p["priority"] or "-"))
            for p in critical
        ],
        "program_selesai_items": [
            _pk_drill(p["program_name"], p["location"]) for p in completed
        ],
        "milestone_terlambat_items": [
            _pk_drill(p["program_name"], "Target selesai " + str(p["end_date"])) for p in late
        ],
        "lokasi_belum_terlayani_items": [
            _pk_drill(loc, "Belum ada update program") for loc in underserved_locations
        ],
        "butuh_support_items": [
            _pk_drill(p["program_name"], f"Progress {p['progress_percent']}% · prioritas {p['priority'] or '-'}")
            for p in needs_support
        ],
    }

    return {
        "disaster_event": event,
        "generated_at": now_datetime(),
        "totals": totals,
        "kpi_items": kpi_items,
        "programs": programs,
    }


# ============================================================
# Cash donations to a specific program ("lembaga penerima" = that
# program's owner). A donor may choose to appear anonymous on the public
# donation wall; the real identity always stays on record internally for
# accountability. A donation only counts toward the program's real
# budget_received (and only shows on the public wall) once the program's
# own owner actually confirms the money arrived — never on submission.
# ============================================================

@frappe.whitelist()
def create_cash_donation(donor_program, amount, is_anonymous=0, message=None,
                          donor_name=None, donor_contact=None):
    actor = rn_actor()
    row = _program(donor_program)

    amount = flt(amount)
    if amount <= 0:
        frappe.throw("Nominal donasi harus lebih dari 0.")
    is_anonymous = 1 if str(is_anonymous).lower() in ("1", "true", "yes", "on") else 0

    acct = None
    if actor and actor.name:
        acct = frappe.db.get_value(
            "RN User Account", actor.name, ["title", "phone", "email"], as_dict=True
        )
    name_val = (donor_name or "").strip() or (acct and acct.title) or _actor_name(actor) or "Donatur"
    contact_val = (donor_contact or "").strip() or (acct and (acct.phone or acct.email)) or None

    doc = frappe.new_doc("RN Cash Donation")
    doc.disaster_event = row.disaster_event
    doc.donor_program = donor_program
    doc.donor_user = actor.name if actor and actor.name else None
    doc.donor_name = name_val
    doc.donor_contact = contact_val
    doc.is_anonymous = is_anonymous
    doc.amount = amount
    doc.message = (message or "").strip() or None
    doc.status = "pending"
    doc.insert(ignore_permissions=True)

    return {"donation": doc.name, "status": doc.status, "amount": doc.amount}


@frappe.whitelist(allow_guest=True)
def program_donations(donor_program):
    """Public donation wall (received only, donor masked if anonymous) for
    one program. If the caller manages that program's owner, also returns
    the real pending queue for them to confirm/reject."""
    row = _program(donor_program)

    received = frappe.get_all(
        "RN Cash Donation",
        filters={"donor_program": donor_program, "status": "received"},
        fields=["name", "donor_name", "is_anonymous", "amount", "message", "confirmed_at"],
        order_by="confirmed_at desc", limit_page_length=200,
    )
    public_rows = [{
        "name": r.name,
        "donor_name": "Donatur Anonim" if r.is_anonymous else r.donor_name,
        "amount": flt(r.amount),
        "message": r.message,
        "confirmed_at": r.confirmed_at,
    } for r in received]

    can_manage = False
    pending = []
    try:
        actor = rn_actor(required=False)
    except Exception:
        actor = None
    if actor:
        try:
            can_manage = bool(_is_control(actor) or _allowed_owner(actor, row.owner_type, row.owner_id))
        except Exception:
            can_manage = False
    if can_manage:
        pending = [
            dict(r) for r in frappe.get_all(
                "RN Cash Donation",
                filters={"donor_program": donor_program, "status": "pending"},
                fields=["name", "donor_name", "donor_contact", "is_anonymous", "amount", "message", "creation"],
                order_by="creation desc", limit_page_length=200,
            )
        ]

    return {
        "donor_program": donor_program,
        "public": public_rows,
        "total_received": sum(flt(r.amount) for r in received),
        "donor_count": len(public_rows),
        "can_manage": can_manage,
        "pending": pending,
    }


@frappe.whitelist()
def decide_cash_donation(donation, action, note=None):
    """Program owner confirms money actually arrived, or rejects a bogus
    pledge. Confirming is the ONLY thing that moves a donation onto the
    public wall and into the program's real budget_received."""
    actor = rn_actor()
    doc = frappe.get_doc("RN Cash Donation", donation)
    if doc.status != "pending":
        frappe.throw("Donasi ini sudah diputuskan.")

    row = _program(doc.donor_program)
    if not (_is_control(actor) or _allowed_owner(actor, row.owner_type, row.owner_id)):
        frappe.throw("Anda bukan pengelola program/lembaga penerima ini.", frappe.PermissionError)

    action = str(action or "").strip().lower()
    if action not in ("confirm", "reject"):
        frappe.throw("Aksi tidak valid (confirm/reject)")

    doc.status = "received" if action == "confirm" else "rejected"
    doc.confirmed_by = actor.name if actor and getattr(actor, "name", None) else frappe.session.user
    doc.confirmed_at = now_datetime()
    if note is not None:
        doc.confirmation_note = str(note)[:500]
    doc.save(ignore_permissions=True)

    if action == "confirm":
        current = flt(frappe.db.get_value("RN Donor Program", doc.donor_program, "budget_received"))
        frappe.db.set_value("RN Donor Program", doc.donor_program, "budget_received", current + flt(doc.amount))

    return {"donation": doc.name, "status": doc.status}


@frappe.whitelist(allow_guest=True)
def program_detail(program):
    row = frappe.db.get_value(
        "RN Donor Program", program, SPECIAL_PROGRAM_FIELDS, as_dict=True,
    )

    if not row or row.public_visibility != "summary_public":
        frappe.throw("Program tidak ditemukan atau tidak publik", frappe.DoesNotExistError)

    updates = frappe.get_all(
        "RN Donor Program Update",
        filters={"program": program, "public_visibility": "summary_public"},
        fields=UPDATE_FIELDS,
        order_by="creation desc",
        limit_page_length=500,
    )

    if updates:
        progress = flt(updates[0].progress_percent)
    elif flt(row.target_amount) > 0:
        progress = round(min(100.0, 100.0 * flt(row.current_amount) / flt(row.target_amount)), 1)
    else:
        progress = 0.0

    bukti = []
    try:
        from rescue_net.api_control_centre import event_evidence

        title_l = (row.program_name or "").lower()
        loc_l = (row.target_location or row.location or "").lower()

        for ev in event_evidence(row.disaster_event, limit=150):
            loc = str(ev.get("location_text") or "").lower()
            hit = (
                (title_l and len(title_l) > 4 and title_l in loc)
                or (loc_l and len(loc_l) > 3 and loc_l in loc)
            )
            if hit:
                bukti.append(ev)

        bukti.sort(
            key=lambda r: str(r.get("created_at") or r.get("creation") or ""),
            reverse=True,
        )
        bukti = bukti[:8]
    except Exception:
        bukti = []

    try:
        donations = program_donations(program)
    except Exception:
        donations = {"public": [], "total_received": 0, "donor_count": 0, "can_manage": False, "pending": []}

    # Project-based program: the "design/RAB/pelaksana" detail already
    # modeled on Pengadaan & Tender, shown as part of this same donation
    # page per owner request instead of a separate disconnected page.
    project = None
    tender_row = frappe.db.get_value(
        "RN Procurement Tender", {"donor_program": program},
        ["name", "title", "scope_description", "location", "rab_total",
         "rab_document_url", "bidding_opens_at", "bidding_closes_at",
         "status", "awarded_bid", "contact_person", "contact_phone"],
        as_dict=True, order_by="creation asc",
    )
    if tender_row:
        from rescue_net.api_tender import _TENDER_STATUS

        pelaksana = None
        if tender_row.awarded_bid:
            pelaksana = frappe.db.get_value(
                "RN Tender Bid", tender_row.awarded_bid, ["bidder_name", "bidder_org"], as_dict=True,
            )
        project = {
            **dict(tender_row),
            "status_label": _TENDER_STATUS.get(tender_row.status, tender_row.status),
            "pelaksana": (pelaksana.bidder_org or pelaksana.bidder_name) if pelaksana else None,
        }

    return {
        "program": {
            **dict(row),
            "category": _program_type_label(row.program_type),
            "progress_percent": progress,
            "program_kind": "project" if project else "cash",
        },
        "updates": [dict(u) for u in updates],
        "bukti": bukti,
        "donations": donations,
        "project": project,
        "note": (
            "Rencana Kerja/Dokumen tidak dimodelkan sebagai daftar rinci "
            "terpisah — gunakan Anggaran (target/diterima/terpakai) dan "
            "Riwayat Update sebagai sumber kebenaran progres program."
        ),
    }
