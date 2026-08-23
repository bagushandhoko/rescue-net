import frappe

from frappe.utils import flt, now_datetime

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
    actor = rn_actor()

    owner_type = _owner_type(
        owner_type
    )

    _assert_owner(
        actor,
        owner_type,
        owner_id,
    )

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
