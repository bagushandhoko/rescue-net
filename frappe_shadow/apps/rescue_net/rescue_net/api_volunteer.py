from collections import defaultdict

import frappe
from rescue_net.reference_resolver import resolve_disaster_event, resolve_posko
from frappe.utils import now_datetime
from frappe.rate_limiter import rate_limit

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


@frappe.whitelist(allow_guest=True)
@rate_limit(key="contact", limit=10, seconds=60 * 60)
def register_volunteer(
    volunteer_name,
    contact,
    disaster_event=None,
    skill_category=None,
    main_skill=None,
    skill_tags=None,
    duration_available=None,
    current_location=None,
    preferences=None,
    equipment_owned=None,
    needs_transport=0,
    notes=None,
):
    """Public self-service "Daftar Jadi Relawan" (no login required) — the
    "sarana pendaftaran relawan yang mau berangkat" from the blueprint's
    Management Relawan section. Unlike create_profile() this does not
    require an authenticated RN User Account: it creates a standalone
    RN Volunteer Profile (user_account left empty, same as most existing
    sim/community volunteer records), self_reported, immediately visible on
    the Manajemen Relawan board with the fields the blueprint calls for:
    kategori keahlian, waktu tersedia, preferensi, dan fasilitas/peralatan
    yang dimiliki.
    """
    volunteer_name = (volunteer_name or "").strip()
    contact = (contact or "").strip()

    if not volunteer_name:
        frappe.throw("Nama relawan wajib diisi")

    if not contact:
        frappe.throw("Kontak / WhatsApp wajib diisi")

    if not main_skill and not skill_category:
        frappe.throw("Kategori atau skill utama wajib diisi")

    event = resolve_disaster_event(disaster_event)

    doc = frappe.new_doc("RN Volunteer Profile")
    doc.disaster_event = event
    doc.volunteer_name = volunteer_name
    doc.contact = contact
    doc.main_skill = main_skill or skill_category
    doc.skill_category = skill_category
    doc.skill_tags = skill_tags
    doc.availability_status = "available"
    doc.duration_available = duration_available
    doc.current_location = current_location
    doc.preferences = preferences
    doc.equipment_owned = equipment_owned
    doc.needs_transport = 1 if str(needs_transport) in ("1", "true", "True", "on") else 0
    doc.notes = notes
    doc.verification_status = "self_reported"
    doc.observed_at = now_datetime()
    doc.source_updated_at = doc.observed_at

    doc.insert(ignore_permissions=True)

    return {
        "volunteer": doc.name,
        "availability_status": doc.availability_status,
        "message": "Pendaftaran diterima. Posko akan menghubungi Anda untuk penugasan.",
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
    # RN_CANONICAL_REF posko = resolve_posko(posko)
    posko = resolve_posko(posko)
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


@frappe.whitelist(allow_guest=True)
def dashboard(posko=None):
    # RN_CANONICAL_REF posko = resolve_posko(posko)
    posko = resolve_posko(posko)
    actor = rn_actor(required=False)

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

    if actor and not _is_manager(actor):
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
        # Guests reading a specific posko get a public read-only view of
        # that one posko; the manager allow-list only gates authenticated
        # actors (same guest-read model as volunteer_board).
        if actor and posko not in allowed:
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


_SKILL_CATALOG = [
    ("Medis", ("medis", "medical", "triase", "triage", "perawat", "dokter", "ispa")),
    ("Evakuasi", ("evakuasi", "evacuation", "rescue", "assessment")),
    ("Search & Found", ("search", "found", "pencarian", "sar")),
    ("Pickup & Transport", ("transport", "pickup", "4x4", "driver", "sopir", "distribution", "distribusi")),
    ("Dapur & Logistik", ("dapur", "kitchen", "logistik", "logistics", "gudang")),
    ("Komunikasi", ("komunikasi", "radio", "data lapangan", "dokumentasi")),
    ("Shelter", ("shelter", "pengungsian")),
]

FATIGUE_HOURS_THRESHOLD = 12


def _skill_text(profile):
    return (str(profile.main_skill or "") + " " + str(profile.skill_tags or "")).lower()


def _skill_buckets(profiles):
    counts = defaultdict(int)
    for p in profiles:
        text = _skill_text(p)
        matched = False
        for label, keywords in _SKILL_CATALOG:
            if any(k in text for k in keywords):
                counts[label] += 1
                matched = True
        if not matched and text.strip():
            counts["Lainnya"] += 1
    return counts


def _org_titles_by_user():
    """user_account -> organization title, via RN Organization Membership."""
    memberships = frappe.get_all(
        "RN Organization Membership",
        filters={"status": "approved"},
        fields=["user_account", "organization"],
        limit_page_length=5000,
    )
    org_ids = {m.organization for m in memberships if m.organization}
    org_titles = {}
    if org_ids:
        for row in frappe.get_all(
            "RN Organization", filters={"name": ["in", list(org_ids)]},
            fields=["name", "title"], limit_page_length=len(org_ids),
        ):
            org_titles[row.name] = row.title
    out = {}
    for m in memberships:
        if m.user_account and m.organization in org_titles:
            out[m.user_account] = org_titles[m.organization]
    return out


def _drill(title, sub, href):
    return {"title": title, "sub": sub, "href": href}


def _num_i(v):
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


@frappe.whitelist(allow_guest=True)
def volunteer_board(disaster_event=None):
    """Manajemen Relawan dashboard (matches the DMS mock-up), guest read-only.

    Cross-volunteer overview for one disaster event: KPI totals + drill
    items, Daftar Relawan, Filter Keterampilan / Jenis Relawan (keyword
    buckets over real main_skill/skill_tags — not the mock-up's exact
    categories, since our data doesn't carry those labels), Papan Penugasan
    (assignments still "planned" — awaiting the assignee's acceptance; this
    schema binds one assignment to one volunteer at creation, so there is no
    "open slot needing N relawan" concept to draw from), and Fatigue Risk
    (checked-in/in-progress assignments running longer than
    FATIGUE_HOURS_THRESHOLD). "Akomodasi & Keselamatan" is backed by the new
    RN Volunteer Accommodation / RN Safety Briefing doctypes.
    """
    event = resolve_disaster_event(disaster_event) or disaster_event

    profiles = frappe.get_all(
        "RN Volunteer Profile",
        filters={"disaster_event": event} if event else {},
        fields=["name", "volunteer_name", "contact", "main_skill", "skill_tags",
                "skill_category", "preferences", "equipment_owned", "needs_transport",
                "availability_status", "duration_available", "current_location",
                "assigned_posko", "user_account", "verification_status"],
        order_by="availability_status asc, volunteer_name asc",
        limit_page_length=2000,
    )
    profile_names = [p.name for p in profiles]

    assignments = frappe.get_all(
        "RN Volunteer Assignment",
        filters={"disaster_event": event} if event else {},
        fields=["name", "volunteer", "posko", "assignment_type", "task_title",
                "priority", "assignment_status", "shift_start", "checked_in_at"],
        order_by="creation desc",
        limit_page_length=2000,
    )

    posko_names = list({p.assigned_posko for p in profiles if p.assigned_posko} |
                        {a.posko for a in assignments if a.posko})
    posko_titles = {}
    if posko_names:
        for row in frappe.get_all("RN Posko", filters={"name": ["in", posko_names]},
                                   fields=["name", "title"], limit_page_length=len(posko_names)):
            posko_titles[row.name] = row.title

    org_by_user = _org_titles_by_user()

    now = now_datetime()

    available = [p for p in profiles if p.availability_status == "available"]
    sedang_bertugas = [p for p in profiles if p.availability_status == "assigned"]
    planned_assignments = [a for a in assignments if a.assignment_status == "planned"]

    fatigue = []
    for a in assignments:
        if a.assignment_status in ("checked_in", "in_progress") and a.checked_in_at:
            hours = (now - a.checked_in_at).total_seconds() / 3600.0
            if hours >= FATIGUE_HOURS_THRESHOLD:
                fatigue.append((a, hours))

    daftar_relawan = []
    for p in profiles:
        skills = [s.strip() for s in (str(p.main_skill or "")).split(",") if s.strip()]
        skills += [s.strip() for s in (str(p.skill_tags or "")).split(",") if s.strip() and s.strip() not in skills]
        daftar_relawan.append({
            "name": p.name,
            "volunteer_name": p.volunteer_name,
            "organisasi": org_by_user.get(p.user_account) or "-",
            "skill_category": p.skill_category or "-",
            "skills": skills[:4],
            "lokasi": p.current_location or posko_titles.get(p.assigned_posko) or "-",
            "durasi": p.duration_available or "-",
            "preferensi": p.preferences or "-",
            "peralatan": p.equipment_owned or "-",
            "butuh_transport": bool(p.needs_transport),
            "status": p.availability_status,
            "href": None,
        })

    skill_counts = _skill_buckets(profiles)
    filter_keterampilan = [
        {"label": label, "count": skill_counts.get(label, 0)}
        for label, _ in _SKILL_CATALOG
        if skill_counts.get(label, 0) > 0
    ]
    filter_keterampilan.sort(key=lambda r: -r["count"])
    jenis_relawan = filter_keterampilan[:4]

    papan_penugasan = [
        {
            "task_title": a.task_title,
            "posko": posko_titles.get(a.posko) or a.posko,
            "priority": a.priority,
            "volunteer_name": next((p.volunteer_name for p in profiles if p.name == a.volunteer), a.volunteer),
            "href": "posko-detail.html?id=" + (a.posko or "") + "&event=" + (event or ""),
        }
        for a in planned_assignments
    ]

    accom_rows = frappe.get_all(
        "RN Volunteer Accommodation",
        filters={"disaster_event": event} if event else {},
        fields=["name", "location_name", "capacity_beds", "occupants_count",
                "is_safe_point", "safety_status", "posko"],
        limit_page_length=200,
    )
    today = frappe.utils.getdate()
    briefings = frappe.get_all(
        "RN Safety Briefing",
        filters={"disaster_event": event} if event else {},
        fields=["name", "title", "scheduled_at", "location", "briefing_status"],
        order_by="scheduled_at asc",
        limit_page_length=200,
    )
    briefings_today = [
        b for b in briefings
        if b.scheduled_at and frappe.utils.getdate(b.scheduled_at) == today
        and b.briefing_status != "cancelled"
    ]

    akomodasi_keselamatan = {
        "tempat_tidur_tersedia": sum(_num_i(a.capacity_beds) for a in accom_rows),
        "relawan_menginap": sum(_num_i(a.occupants_count) for a in accom_rows),
        "titik_aman": sum(1 for a in accom_rows if a.is_safe_point),
        "briefing_hari_ini": len(briefings_today),
        "akomodasi": [
            {
                "lokasi": a.location_name,
                "kapasitas": _num_i(a.capacity_beds),
                "terisi": _num_i(a.occupants_count),
                "pct": round(100.0 * _num_i(a.occupants_count) / _num_i(a.capacity_beds), 1)
                       if _num_i(a.capacity_beds) else 0,
                "is_safe_point": bool(a.is_safe_point),
                "safety_status": a.safety_status,
            }
            for a in accom_rows
        ],
        "briefing_list": [
            {"title": b.title, "waktu": str(b.scheduled_at)[11:16] if b.scheduled_at else "-",
             "lokasi": b.location or "-", "status": b.briefing_status}
            for b in briefings_today
        ],
    }

    return {
        "disaster_event": event,
        "generated_at": now,
        "totals": {
            "terdaftar": len(profiles),
            "available_hari_ini": len(available),
            "sedang_bertugas": len(sedang_bertugas),
            "butuh_penugasan": len(planned_assignments),
            "fatigue_risk": len(fatigue),
        },
        "kpi_items": {
            "terdaftar_items": [
                _drill(p.volunteer_name, (org_by_user.get(p.user_account) or p.main_skill or "-"), None)
                for p in profiles[:30]
            ],
            "available_items": [
                _drill(p.volunteer_name, p.main_skill or "-", None) for p in available[:30]
            ],
            "bertugas_items": [
                _drill(p.volunteer_name, "Bertugas di " + (posko_titles.get(p.assigned_posko) or "-"), None)
                for p in sedang_bertugas[:30]
            ],
            "butuh_items": [
                _drill(a["task_title"], a["posko"] + " · " + a["priority"], a["href"])
                for a in papan_penugasan
            ],
            "fatigue_items": [
                _drill(
                    next((p.volunteer_name for p in profiles if p.name == a.volunteer), a.volunteer),
                    f"Bertugas {round(hours)} jam nonstop di {posko_titles.get(a.posko) or a.posko}",
                    None,
                )
                for a, hours in fatigue
            ],
        },
        "daftar_relawan": daftar_relawan,
        "filter_keterampilan": filter_keterampilan,
        "jenis_relawan": jenis_relawan,
        "papan_penugasan": papan_penugasan,
        "akomodasi_keselamatan": akomodasi_keselamatan,
    }
