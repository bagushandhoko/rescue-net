from collections import defaultdict

import frappe
from frappe.utils import now_datetime

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


ACTIVE_ASSIGNMENTS = {
    "planned",
    "accepted",
    "checked_in",
    "in_progress",
}


TRANSITIONS = {
    "planned": {
        "accepted",
        "cancelled",
    },
    "accepted": {
        "checked_in",
        "cancelled",
    },
    "checked_in": {
        "in_progress",
        "completed",
        "cancelled",
    },
    "in_progress": {
        "completed",
        "cancelled",
    },
    "completed": set(),
    "cancelled": set(),
}


def _role(actor):
    return getattr(
        actor,
        "role",
        None,
    )


def _is_manager(actor):
    return bool(
        is_system_manager()
        or _role(actor) in MANAGER_ROLES
    )


def _actor_profile(actor):
    if not actor:
        return None

    return frappe.db.get_value(
        "RN Volunteer Profile",
        {
            "user_account": actor.name,
        },
        "name",
    )


def _member_orgs(actor):
    if not actor or not actor.name:
        return []

    rows = frappe.get_all(
        "RN Organization Membership",
        filters={
            "user_account": actor.name,
            "status": "approved",
        },
        pluck="organization",
        limit_page_length=500,
    )

    organization = getattr(
        actor,
        "organization",
        None,
    )

    if organization:
        rows.append(organization)

    return list(
        set(x for x in rows if x)
    )


def _candidate_poskos(actor):
    if is_system_manager():
        return frappe.get_all(
            "RN Posko",
            pluck="name",
            limit_page_length=5000,
        )

    result = set()

    for organization in _member_orgs(actor):
        result.update(
            frappe.get_all(
                "RN Posko",
                filters={
                    "organization": organization,
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

    actor_posko = getattr(
        actor,
        "posko",
        None,
    )

    if actor_posko:
        result.add(actor_posko)

    return sorted(result)


def _can_operate_posko(actor, posko):
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


def _assert_manager_posko(actor, posko):
    if not _is_manager(actor):
        frappe.throw(
            "Hak operator diperlukan",
            frappe.PermissionError,
        )

    if not _can_operate_posko(
        actor,
        posko,
    ):
        frappe.throw(
            "Akses Posko ditolak",
            frappe.PermissionError,
        )


def _refresh_profile_assignment_state(
    volunteer,
):
    active = frappe.db.exists(
        "RN Volunteer Assignment",
        {
            "volunteer": volunteer,
            "assignment_status": [
                "in",
                list(ACTIVE_ASSIGNMENTS),
            ],
        },
    )

    profile = frappe.get_doc(
        "RN Volunteer Profile",
        volunteer,
    )

    if active:
        assignment = frappe.get_all(
            "RN Volunteer Assignment",
            filters={
                "volunteer": volunteer,
                "assignment_status": [
                    "in",
                    list(ACTIVE_ASSIGNMENTS),
                ],
            },
            fields=[
                "posko",
            ],
            order_by="creation desc",
            limit_page_length=1,
        )

        profile.availability_status = (
            "assigned"
        )

        profile.assigned_posko = (
            assignment[0].posko
            if assignment
            else None
        )

    else:
        profile.availability_status = (
            "available"
        )
        profile.assigned_posko = None

    profile.source_updated_at = (
        now_datetime()
    )

    profile.save(
        ignore_permissions=True
    )


@frappe.whitelist()
def create_profile(
    volunteer_name,
    main_skill,
    contact=None,
    skill_tags=None,
    duration_available=None,
    current_location=None,
    notes=None,
):
    actor = rn_actor()

    existing = _actor_profile(
        actor
    )

    if existing:
        frappe.throw(
            "Profil relawan untuk akun ini sudah ada"
        )

    doc = frappe.new_doc(
        "RN Volunteer Profile"
    )

    doc.user_account = actor.name
    doc.volunteer_name = volunteer_name
    doc.contact = contact
    doc.main_skill = main_skill
    doc.skill_tags = skill_tags
    doc.availability_status = (
        "available"
    )
    doc.duration_available = (
        duration_available
    )
    doc.current_location = (
        current_location
    )
    doc.notes = notes
    doc.verification_status = (
        "self_reported"
    )
    doc.observed_at = now_datetime()
    doc.source_updated_at = (
        doc.observed_at
    )

    doc.insert(
        ignore_permissions=True
    )

    return {
        "volunteer": doc.name,
        "availability_status": (
            doc.availability_status
        ),
    }


@frappe.whitelist()
def update_profile(
    volunteer,
    main_skill=None,
    skill_tags=None,
    duration_available=None,
    current_location=None,
    notes=None,
):
    actor = rn_actor()

    doc = frappe.get_doc(
        "RN Volunteer Profile",
        volunteer,
    )

    own = (
        doc.user_account
        == actor.name
    )

    if (
        not own
        and not _is_manager(actor)
    ):
        frappe.throw(
            "Akses profil relawan ditolak",
            frappe.PermissionError,
        )

    if main_skill is not None:
        doc.main_skill = main_skill

    if skill_tags is not None:
        doc.skill_tags = skill_tags

    if duration_available is not None:
        doc.duration_available = (
            duration_available
        )

    if current_location is not None:
        doc.current_location = (
            current_location
        )

    if notes is not None:
        doc.notes = notes

    doc.source_updated_at = (
        now_datetime()
    )

    doc.save(
        ignore_permissions=True
    )

    return {
        "volunteer": doc.name,
        "updated": True,
    }


@frappe.whitelist()
def set_availability(
    volunteer,
    availability_status,
):
    actor = rn_actor()

    if availability_status not in {
        "available",
        "limited",
        "unavailable",
    }:
        frappe.throw(
            "Availability manual tidak valid"
        )

    doc = frappe.get_doc(
        "RN Volunteer Profile",
        volunteer,
    )

    own = (
        doc.user_account
        == actor.name
    )

    if (
        not own
        and not _is_manager(actor)
    ):
        frappe.throw(
            "Akses relawan ditolak",
            frappe.PermissionError,
        )

    active = frappe.db.exists(
        "RN Volunteer Assignment",
        {
            "volunteer": volunteer,
            "assignment_status": [
                "in",
                list(ACTIVE_ASSIGNMENTS),
            ],
        },
    )

    if active:
        frappe.throw(
            "Relawan masih memiliki penugasan aktif"
        )

    doc.availability_status = (
        availability_status
    )
    doc.assigned_posko = None
    doc.source_updated_at = (
        now_datetime()
    )

    doc.save(
        ignore_permissions=True
    )

    return {
        "volunteer": doc.name,
        "availability_status": (
            doc.availability_status
        ),
    }


@frappe.whitelist()
def create_assignment(
    volunteer,
    posko,
    task_title,
    assignment_type="posko",
    target_reference=None,
    required_skill=None,
    priority="normal",
    shift_start=None,
    shift_end=None,
    assignment_notes=None,
):
    actor = rn_actor()

    _assert_manager_posko(
        actor,
        posko,
    )

    profile = frappe.get_doc(
        "RN Volunteer Profile",
        volunteer,
    )

    if profile.availability_status in {
        "unavailable",
    }:
        frappe.throw(
            "Relawan sedang tidak tersedia"
        )

    active = frappe.db.exists(
        "RN Volunteer Assignment",
        {
            "volunteer": volunteer,
            "assignment_status": [
                "in",
                list(ACTIVE_ASSIGNMENTS),
            ],
        },
    )

    if active:
        frappe.throw(
            "Relawan sudah memiliki penugasan aktif"
        )

    doc = frappe.new_doc(
        "RN Volunteer Assignment"
    )

    doc.volunteer = volunteer
    doc.posko = posko
    doc.assignment_type = (
        assignment_type
    )
    doc.task_title = task_title
    doc.target_reference = (
        target_reference
    )
    doc.required_skill = (
        required_skill
    )
    doc.priority = priority
    doc.assignment_status = "planned"
    doc.shift_start = shift_start
    doc.shift_end = shift_end
    doc.assignment_notes = (
        assignment_notes
    )
    doc.created_by_user = actor.name
    doc.verification_status = (
        "self_reported"
    )

    doc.insert(
        ignore_permissions=True
    )

    _refresh_profile_assignment_state(
        volunteer
    )

    return {
        "assignment": doc.name,
        "status": (
            doc.assignment_status
        ),
        "volunteer": volunteer,
        "posko": posko,
    }


@frappe.whitelist()
def update_assignment_status(
    assignment,
    new_status,
    completion_notes=None,
):
    actor = rn_actor()

    doc = frappe.get_doc(
        "RN Volunteer Assignment",
        assignment,
    )

    profile = frappe.get_doc(
        "RN Volunteer Profile",
        doc.volunteer,
    )

    own_volunteer = (
        profile.user_account
        == actor.name
    )

    if new_status in {
        "accepted",
        "cancelled",
    }:
        if not (
            own_volunteer
            or _is_manager(actor)
        ):
            frappe.throw(
                "Akses assignment ditolak",
                frappe.PermissionError,
            )

    elif new_status in {
        "checked_in",
        "in_progress",
        "completed",
    }:
        if not (
            own_volunteer
            or _can_operate_posko(
                actor,
                doc.posko,
            )
        ):
            frappe.throw(
                "Akses assignment ditolak",
                frappe.PermissionError,
            )

    else:
        _assert_manager_posko(
            actor,
            doc.posko,
        )

    current = doc.assignment_status

    if new_status not in (
        TRANSITIONS.get(
            current,
            set(),
        )
    ):
        frappe.throw(
            f"Transisi assignment tidak valid: "
            f"{current} -> {new_status}"
        )

    now = now_datetime()

    doc.assignment_status = (
        new_status
    )

    if new_status == "accepted":
        doc.accepted_at = now

    if new_status == "checked_in":
        doc.checked_in_at = now

    if new_status == "completed":
        doc.completed_at = now
        doc.completion_notes = (
            completion_notes
        )

    if (
        completion_notes
        and new_status != "completed"
    ):
        doc.completion_notes = (
            completion_notes
        )

    doc.save(
        ignore_permissions=True
    )

    _refresh_profile_assignment_state(
        doc.volunteer
    )

    return {
        "assignment": doc.name,
        "previous_status": current,
        "status": (
            doc.assignment_status
        ),
    }


@frappe.whitelist()
def add_evidence(
    assignment,
    file_url,
    evidence_type="verification",
    caption=None,
):
    actor = rn_actor()

    doc = frappe.get_doc(
        "RN Volunteer Assignment",
        assignment,
    )

    profile = frappe.get_doc(
        "RN Volunteer Profile",
        doc.volunteer,
    )

    own = (
        profile.user_account
        == actor.name
    )

    if not (
        own
        or _can_operate_posko(
            actor,
            doc.posko,
        )
    ):
        frappe.throw(
            "Akses evidence relawan ditolak",
            frappe.PermissionError,
        )

    if not (
        file_url or ""
    ).startswith(
        "/private/files/"
    ):
        frappe.throw(
            "Evidence relawan wajib private"
        )

    allowed_types = {
        "photo",
        "document",
        "receipt",
        "handover",
        "transport",
        "verification",
        "other",
    }

    if evidence_type not in allowed_types:
        frappe.throw(
            "Evidence type tidak valid"
        )

    now = now_datetime()

    ev = frappe.new_doc(
        "RN Operational Evidence"
    )

    ev.linked_doctype = (
        "RN Volunteer Assignment"
    )
    ev.linked_name = doc.name
    ev.posko = doc.posko
    ev.file_url = file_url
    ev.evidence_type = (
        evidence_type
    )
    ev.caption = caption
    ev.observed_at = now
    ev.uploaded_at = now
    ev.uploader_user = actor.name
    ev.verification_status = (
        "pending"
    )

    ev.insert(
        ignore_permissions=True
    )

    return {
        "evidence": ev.name,
        "private": True,
        "verification_status": (
            ev.verification_status
        ),
    }


@frappe.whitelist()
def dashboard(posko=None):
    actor = rn_actor()

    role = _role(actor)

    if role == "volunteer":
        profile_name = _actor_profile(
            actor
        )

        if not profile_name:
            return {
                "mode": "self",
                "poskos": [],
                "profiles": [],
                "assignments": [],
            }

        profiles = frappe.get_all(
            "RN Volunteer Profile",
            filters={
                "name": profile_name,
            },
            fields=[
                "name",
                "volunteer_name",
                "contact",
                "main_skill",
                "skill_tags",
                "availability_status",
                "duration_available",
                "current_location",
                "assigned_posko",
                "verification_status",
            ],
        )

        assignments = frappe.get_all(
            "RN Volunteer Assignment",
            filters={
                "volunteer": profile_name,
            },
            fields=[
                "name",
                "volunteer",
                "posko",
                "assignment_type",
                "task_title",
                "target_reference",
                "required_skill",
                "priority",
                "assignment_status",
                "shift_start",
                "shift_end",
                "accepted_at",
                "checked_in_at",
                "completed_at",
                "assignment_notes",
                "completion_notes",
            ],
            order_by="creation desc",
            limit_page_length=500,
        )

        return {
            "mode": "self",
            "poskos": [],
            "profiles": profiles,
            "assignments": assignments,
        }

    if not _is_manager(actor):
        frappe.throw(
            "Akses Volunteer Operations ditolak",
            frappe.PermissionError,
        )

    allowed = [
        p
        for p in _candidate_poskos(actor)
        if _can_operate_posko(
            actor,
            p,
        )
    ]

    if posko:
        if posko not in allowed:
            frappe.throw(
                "Akses Posko ditolak",
                frappe.PermissionError,
            )

        allowed = [posko]

    poskos = []

    if allowed:
        poskos = frappe.get_all(
            "RN Posko",
            filters={
                "name": [
                    "in",
                    allowed,
                ],
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

    profiles = frappe.get_all(
        "RN Volunteer Profile",
        fields=[
            "name",
            "volunteer_name",
            "contact",
            "main_skill",
            "skill_tags",
            "availability_status",
            "duration_available",
            "current_location",
            "assigned_posko",
            "verification_status",
        ],
        order_by=(
            "availability_status asc, "
            "volunteer_name asc"
        ),
        limit_page_length=2000,
    )

    assignments = []

    if allowed:
        assignments = frappe.get_all(
            "RN Volunteer Assignment",
            filters={
                "posko": [
                    "in",
                    allowed,
                ],
            },
            fields=[
                "name",
                "volunteer",
                "posko",
                "assignment_type",
                "task_title",
                "target_reference",
                "required_skill",
                "priority",
                "assignment_status",
                "shift_start",
                "shift_end",
                "accepted_at",
                "checked_in_at",
                "completed_at",
                "assignment_notes",
                "completion_notes",
            ],
            order_by="creation desc",
            limit_page_length=2000,
        )

    return {
        "mode": "manager",
        "poskos": poskos,
        "profiles": profiles,
        "assignments": assignments,
    }


@frappe.whitelist()
def control_centre_volunteers():
    actor = rn_actor()

    if not (
        is_system_manager()
        or _role(actor)
        == "command_center"
    ):
        frappe.throw(
            "Akses Control Centre Relawan ditolak",
            frappe.PermissionError,
        )

    profiles = frappe.get_all(
        "RN Volunteer Profile",
        fields=[
            "main_skill",
            "skill_tags",
            "availability_status",
        ],
        limit_page_length=5000,
    )

    assignments = frappe.get_all(
        "RN Volunteer Assignment",
        fields=[
            "posko",
            "assignment_type",
            "assignment_status",
            "priority",
        ],
        limit_page_length=5000,
    )

    availability = defaultdict(int)
    skills = defaultdict(int)
    status = defaultdict(int)
    by_posko = defaultdict(int)

    for row in profiles:
        availability[
            row.availability_status
        ] += 1

        skill = (
            row.main_skill
            or "unknown"
        )

        skills[skill] += 1

    for row in assignments:
        status[
            row.assignment_status
        ] += 1

        if (
            row.assignment_status
            in ACTIVE_ASSIGNMENTS
        ):
            by_posko[
                row.posko
            ] += 1

    return {
        "volunteer_count": len(
            profiles
        ),
        "availability": dict(
            availability
        ),
        "skills": dict(
            skills
        ),
        "assignment_status": dict(
            status
        ),
        "active_by_posko": dict(
            by_posko
        ),
        "privacy": (
            "Control Centre hanya menerima "
            "agregat; nama dan kontak relawan "
            "tidak diekspos."
        ),
    }
