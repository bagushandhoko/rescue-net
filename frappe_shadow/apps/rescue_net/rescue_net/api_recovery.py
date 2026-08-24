import frappe
from frappe.utils import flt, now_datetime

from rescue_net.api_donor_program import (
    rn_actor,
    _actor_name,
    _assert_owner,
    _allowed_owner,
    _is_control,
    _owner_type,
)


PROJECT_FIELDS = [
    "name",
    "disaster_event",
    "project_name",
    "project_type",
    "owner_type",
    "owner_id",
    "target_description",
    "location",
    "priority",
    "target_amount",
    "current_amount",
    "progress_percent",
    "status",
    "start_date",
    "target_finish_date",
    "pic_name",
    "pic_phone",
    "notes",
    "created_by_user",
    "observed_at",
    "version",
    "creation",
    "modified",
]

UPDATE_FIELDS = [
    "name",
    "project",
    "disaster_event",
    "update_type",
    "progress_percent",
    "amount_spent",
    "update_title",
    "update_notes",
    "evidence_file_id",
    "verification_status",
    "created_by_user",
    "observed_at",
    "creation",
    "modified",
]

PATCHABLE = {
    "project_name",
    "project_type",
    "owner_type",
    "owner_id",
    "target_description",
    "location",
    "priority",
    "target_amount",
    "current_amount",
    "progress_percent",
    "status",
    "start_date",
    "target_finish_date",
    "pic_name",
    "pic_phone",
    "notes",
}


def _project(project_id):
    row = frappe.db.get_value(
        "RN Recovery Project",
        project_id,
        PROJECT_FIELDS + ["is_deleted"],
        as_dict=True,
    )

    if not row or row.is_deleted:
        frappe.throw("Recovery project not found")

    return row


@frappe.whitelist()
def create_project(
    disaster_event_id,
    project_name,
    project_type=None,
    owner_type="organization",
    owner_id=None,
    target_description=None,
    location=None,
    priority=None,
    target_amount=0,
    current_amount=0,
    progress_percent=0,
    status="planned",
    start_date=None,
    target_finish_date=None,
    pic_name=None,
    pic_phone=None,
    notes=None,
):
    actor = rn_actor()

    owner_type = _owner_type(owner_type)
    _assert_owner(actor, owner_type, owner_id)

    project_name = (project_name or "").strip()

    if not project_name:
        frappe.throw("Project Name wajib diisi")

    doc = frappe.new_doc("RN Recovery Project")

    doc.disaster_event = disaster_event_id
    doc.project_name = project_name
    doc.project_type = project_type
    doc.owner_type = owner_type
    doc.owner_id = owner_id

    doc.target_description = target_description
    doc.location = location
    doc.priority = priority

    doc.target_amount = flt(target_amount)
    doc.current_amount = flt(current_amount)
    doc.progress_percent = flt(progress_percent)

    doc.status = status or "planned"
    doc.start_date = start_date
    doc.target_finish_date = target_finish_date

    doc.pic_name = pic_name
    doc.pic_phone = pic_phone
    doc.notes = notes

    doc.created_by_user = _actor_name(actor)
    doc.observed_at = now_datetime()
    doc.version = 1

    doc.insert(ignore_permissions=True)

    return {
        "status": "created",
        "recovery_project": frappe.db.get_value(
            "RN Recovery Project",
            doc.name,
            PROJECT_FIELDS,
            as_dict=True,
        ),
    }


@frappe.whitelist()
def list_projects(
    disaster_event_id=None,
    status=None,
):
    actor = rn_actor()

    filters = {
        "is_deleted": 0,
    }

    if disaster_event_id:
        filters["disaster_event"] = disaster_event_id

    if status:
        filters["status"] = status

    rows = frappe.get_all(
        "RN Recovery Project",
        filters=filters,
        fields=PROJECT_FIELDS,
        order_by="modified desc, creation desc",
        limit_page_length=2000,
    )

    if not _is_control(actor):
        rows = [
            x for x in rows
            if _allowed_owner(
                actor,
                x.owner_type,
                x.owner_id,
            )
        ]

    return [dict(x) for x in rows]


@frappe.whitelist()
def get_project(project_id):
    actor = rn_actor()

    p = _project(project_id)

    _assert_owner(
        actor,
        p.owner_type,
        p.owner_id,
    )

    updates = frappe.get_all(
        "RN Recovery Project Update",
        filters={
            "project": p.name,
            "is_deleted": 0,
        },
        fields=UPDATE_FIELDS,
        order_by="creation desc",
        limit_page_length=2000,
    )

    return {
        "recovery_project": dict(p),
        "updates": [dict(x) for x in updates],
    }


@frappe.whitelist()
def patch_project(project_id, **values):
    actor = rn_actor()

    p = _project(project_id)

    _assert_owner(
        actor,
        p.owner_type,
        p.owner_id,
    )

    data = {
        k: v
        for k, v in values.items()
        if k in PATCHABLE
    }

    if not data:
        frappe.throw("No fields to update")

    new_owner_type = data.get(
        "owner_type",
        p.owner_type,
    )

    new_owner_id = data.get(
        "owner_id",
        p.owner_id,
    )

    new_owner_type = _owner_type(
        new_owner_type
    )

    _assert_owner(
        actor,
        new_owner_type,
        new_owner_id,
    )

    data["owner_type"] = new_owner_type
    data["version"] = int(p.version or 1) + 1

    frappe.db.set_value(
        "RN Recovery Project",
        p.name,
        data,
        update_modified=True,
    )

    return {
        "status": "updated",
        "recovery_project": frappe.db.get_value(
            "RN Recovery Project",
            p.name,
            PROJECT_FIELDS,
            as_dict=True,
        ),
    }


@frappe.whitelist()
def delete_project(project_id):
    actor = rn_actor()

    p = _project(project_id)

    _assert_owner(
        actor,
        p.owner_type,
        p.owner_id,
    )

    frappe.db.set_value(
        "RN Recovery Project",
        p.name,
        {
            "is_deleted": 1,
            "deleted_at": now_datetime(),
            "version": int(p.version or 1) + 1,
        },
        update_modified=True,
    )

    return {
        "status": "deleted",
        "id": p.name,
    }


@frappe.whitelist()
def create_update(
    project_id,
    disaster_event_id=None,
    update_type="progress",
    progress_percent=0,
    amount_spent=0,
    update_title=None,
    update_notes=None,
    evidence_file_id=None,
    verification_status="self_reported",
):
    actor = rn_actor()

    p = _project(project_id)

    _assert_owner(
        actor,
        p.owner_type,
        p.owner_id,
    )

    update_title = (
        update_title or ""
    ).strip()

    if not update_title:
        frappe.throw("Update Title wajib diisi")

    doc = frappe.new_doc(
        "RN Recovery Project Update"
    )

    doc.project = p.name
    doc.disaster_event = (
        disaster_event_id
        or p.disaster_event
    )

    doc.update_type = (
        update_type or "progress"
    )

    doc.progress_percent = flt(
        progress_percent
    )

    doc.amount_spent = flt(
        amount_spent
    )

    doc.update_title = update_title
    doc.update_notes = update_notes
    doc.evidence_file_id = evidence_file_id

    doc.verification_status = (
        verification_status
        or "self_reported"
    )

    doc.created_by_user = (
        _actor_name(actor)
    )

    doc.observed_at = now_datetime()

    doc.insert(ignore_permissions=True)

    # Exact legacy semantics:
    # progress = GREATEST(existing, incoming)
    # current_amount += amount_spent
    new_progress = max(
        flt(p.progress_percent),
        flt(progress_percent),
    )

    new_current = (
        flt(p.current_amount)
        + flt(amount_spent)
    )

    frappe.db.set_value(
        "RN Recovery Project",
        p.name,
        {
            "progress_percent":
                new_progress,
            "current_amount":
                new_current,
            "version":
                int(p.version or 1) + 1,
        },
        update_modified=True,
    )

    return {
        "status": "created",
        "recovery_project_update":
            frappe.db.get_value(
                "RN Recovery Project Update",
                doc.name,
                UPDATE_FIELDS,
                as_dict=True,
            ),
    }


@frappe.whitelist()
def list_updates(
    project_id=None,
    disaster_event_id=None,
):
    actor = rn_actor()

    filters = {
        "is_deleted": 0,
    }

    if project_id:
        p = _project(project_id)

        _assert_owner(
            actor,
            p.owner_type,
            p.owner_id,
        )

        filters["project"] = p.name

    if disaster_event_id:
        filters["disaster_event"] = (
            disaster_event_id
        )

    rows = frappe.get_all(
        "RN Recovery Project Update",
        filters=filters,
        fields=UPDATE_FIELDS,
        order_by="creation desc",
        limit_page_length=2000,
    )

    if project_id or _is_control(actor):
        return [dict(x) for x in rows]

    project_ids = {
        x.project
        for x in rows
    }

    owners = {}

    for pid in project_ids:
        owners[pid] = frappe.db.get_value(
            "RN Recovery Project",
            pid,
            [
                "owner_type",
                "owner_id",
                "is_deleted",
            ],
            as_dict=True,
        )

    result = []

    for x in rows:
        owner = owners.get(x.project)

        if (
            owner
            and not owner.is_deleted
            and _allowed_owner(
                actor,
                owner.owner_type,
                owner.owner_id,
            )
        ):
            result.append(dict(x))

    return result
