from collections import defaultdict

import frappe
from rescue_net.reference_resolver import resolve_disaster_event, resolve_posko
from frappe.utils import cint, flt, now_datetime

from rescue_net.access_policy import (
    can_manage_organization,
    can_manage_posko,
    is_system_manager,
    rn_actor,
)


CONTROL_ROLES = {
    "command_center",
    "posko_operator",
    "shelter_operator",
}


HOUSEHOLD_TRANSITIONS = {
    "checked_in": {
        "moved",
        "checked_out",
    },
    "moved": set(),
    "checked_out": set(),
}


NEED_TRANSITIONS = {
    "open": {
        "partially_met",
        "met",
        "cancelled",
    },
    "partially_met": {
        "met",
        "cancelled",
    },
    "met": set(),
    "cancelled": set(),
}


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


def _assert_shelter_access(actor, posko):
    if not _can_operate(
        actor,
        posko,
    ):
        frappe.throw(
            "Akses Shelter ditolak",
            frappe.PermissionError,
        )

    posko_type = frappe.db.get_value(
        "RN Posko",
        posko,
        "posko_type",
    )

    if posko_type != "shelter":
        frappe.throw(
            "Posko ini bukan Shelter",
            frappe.ValidationError,
        )


def _accessible_shelters(actor):
    result = []

    for posko in _candidate_poskos(actor):
        if not _can_operate(
            actor,
            posko,
        ):
            continue

        if frappe.db.get_value(
            "RN Posko",
            posko,
            "posko_type",
        ) != "shelter":
            continue

        result.append(posko)

    return result


def _all_shelters():
    return frappe.get_all(
        "RN Posko",
        filters={
            "posko_type": "shelter",
        },
        pluck="name",
        limit_page_length=5000,
    )


@frappe.whitelist()
def dashboard(posko=None):
    # RN_CANONICAL_REF posko = resolve_posko(posko)
    posko = resolve_posko(posko)
    actor = rn_actor()

    allowed = _accessible_shelters(
        actor
    )

    if posko:
        if posko not in allowed:
            frappe.throw(
                "Akses Shelter ditolak",
                frappe.PermissionError,
            )

        allowed = [posko]

    if not allowed:
        return {
            "poskos": [],
            "occupancies": [],
            "households": [],
            "needs": [],
        }

    poskos = frappe.get_all(
        "RN Posko",
        filters={
            "name": ["in", allowed],
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

    occupancies = frappe.get_all(
        "RN Shelter Occupancy",
        filters={
            "posko": ["in", allowed],
        },
        fields=[
            "name",
            "posko",
            "shelter_name",
            "capacity_total",
            "current_occupancy",
            "families_count",
            "infants_count",
            "children_count",
            "elderly_count",
            "pregnant_count",
            "disability_count",
            "observed_at",
            "verification_status",
        ],
        order_by="observed_at desc, creation desc",
        limit_page_length=2000,
    )

    households = frappe.get_all(
        "RN Shelter Household",
        filters={
            "posko": ["in", allowed],
        },
        fields=[
            "name",
            "posko",
            "household_code",
            "members_count",
            "infants_count",
            "children_count",
            "elderly_count",
            "pregnant_count",
            "disability_count",
            "household_status",
            "check_in_at",
            "moved_at",
            "checked_out_at",
            "destination",
            "notes",
            "verification_status",
        ],
        order_by="creation desc",
        limit_page_length=2000,
    )

    needs = frappe.get_all(
        "RN Shelter Need",
        filters={
            "posko": ["in", allowed],
        },
        fields=[
            "name",
            "posko",
            "item_name",
            "quantity_mode",
            "quantity_needed",
            "quantity_min",
            "quantity_max",
            "quantity_text",
            "unit",
            "priority",
            "need_status",
            "needed_before",
            "observed_at",
            "verification_status",
        ],
        order_by="creation desc",
        limit_page_length=2000,
    )

    return {
        "poskos": poskos,
        "occupancies": occupancies,
        "households": households,
        "needs": needs,
    }


@frappe.whitelist()
def create_occupancy(
    posko,
    shelter_name,
    capacity_total=0,
    current_occupancy=0,
    families_count=0,
    infants_count=0,
    children_count=0,
    elderly_count=0,
    pregnant_count=0,
    disability_count=0,
):
    # RN_CANONICAL_REF posko = resolve_posko(posko)
    posko = resolve_posko(posko)
    actor = rn_actor()

    _assert_shelter_access(
        actor,
        posko,
    )

    doc = frappe.new_doc(
        "RN Shelter Occupancy"
    )

    doc.posko = posko
    doc.shelter_name = shelter_name
    doc.capacity_total = cint(
        capacity_total
    )
    doc.current_occupancy = cint(
        current_occupancy
    )
    doc.families_count = cint(
        families_count
    )
    doc.infants_count = cint(
        infants_count
    )
    doc.children_count = cint(
        children_count
    )
    doc.elderly_count = cint(
        elderly_count
    )
    doc.pregnant_count = cint(
        pregnant_count
    )
    doc.disability_count = cint(
        disability_count
    )
    doc.observed_at = now_datetime()
    doc.source_updated_at = (
        doc.observed_at
    )
    doc.verification_status = (
        "self_reported"
    )

    doc.insert(
        ignore_permissions=True
    )

    capacity = cint(
        doc.capacity_total
    )

    current = cint(
        doc.current_occupancy
    )

    pct = None

    if capacity > 0:
        pct = round(
            current * 100 / capacity,
            1,
        )

    return {
        "occupancy": doc.name,
        "capacity_total": capacity,
        "current_occupancy": current,
        "occupancy_percent": pct,
        "over_capacity": bool(
            capacity > 0
            and current > capacity
        ),
    }


@frappe.whitelist()
def check_in_household(
    posko,
    household_code,
    members_count,
    infants_count=0,
    children_count=0,
    elderly_count=0,
    pregnant_count=0,
    disability_count=0,
    notes=None,
):
    actor = rn_actor()

    _assert_shelter_access(
        actor,
        posko,
    )

    doc = frappe.new_doc(
        "RN Shelter Household"
    )

    doc.posko = posko
    doc.household_code = household_code
    doc.members_count = cint(
        members_count
    )
    doc.infants_count = cint(
        infants_count
    )
    doc.children_count = cint(
        children_count
    )
    doc.elderly_count = cint(
        elderly_count
    )
    doc.pregnant_count = cint(
        pregnant_count
    )
    doc.disability_count = cint(
        disability_count
    )
    doc.household_status = (
        "checked_in"
    )
    doc.notes = notes
    doc.verification_status = (
        "self_reported"
    )

    doc.insert(
        ignore_permissions=True
    )

    return {
        "household": doc.name,
        "household_code": (
            doc.household_code
        ),
        "members_count": (
            doc.members_count
        ),
        "status": (
            doc.household_status
        ),
    }


@frappe.whitelist()
def update_household_status(
    household,
    new_status,
    destination=None,
):
    actor = rn_actor()

    doc = frappe.get_doc(
        "RN Shelter Household",
        household,
    )

    _assert_shelter_access(
        actor,
        doc.posko,
    )

    current = doc.household_status

    if new_status not in (
        HOUSEHOLD_TRANSITIONS.get(
            current,
            set(),
        )
    ):
        frappe.throw(
            f"Transisi keluarga tidak valid: "
            f"{current} -> {new_status}"
        )

    if (
        new_status == "moved"
        and not destination
    ):
        frappe.throw(
            "Tujuan perpindahan wajib diisi"
        )

    now = now_datetime()

    doc.household_status = (
        new_status
    )

    if new_status == "moved":
        doc.destination = (
            destination
        )
        doc.moved_at = now

    if new_status == "checked_out":
        doc.destination = (
            destination
            or doc.destination
        )
        doc.checked_out_at = now

    doc.save(
        ignore_permissions=True
    )

    return {
        "household": doc.name,
        "previous_status": current,
        "status": (
            doc.household_status
        ),
    }


@frappe.whitelist()
def create_need(
    posko,
    item_name,
    quantity_mode="unknown",
    quantity_needed=None,
    quantity_min=None,
    quantity_max=None,
    quantity_text=None,
    unit=None,
    priority="normal",
    needed_before=None,
    notes=None,
):
    # RN_CANONICAL_REF posko = resolve_posko(posko)
    posko = resolve_posko(posko)
    actor = rn_actor()

    _assert_shelter_access(
        actor,
        posko,
    )

    doc = frappe.new_doc(
        "RN Shelter Need"
    )

    doc.posko = posko
    doc.item_name = item_name
    doc.quantity_mode = (
        quantity_mode
    )

    if quantity_needed not in (
        None,
        "",
    ):
        doc.quantity_needed = flt(
            quantity_needed
        )

    if quantity_min not in (
        None,
        "",
    ):
        doc.quantity_min = flt(
            quantity_min
        )

    if quantity_max not in (
        None,
        "",
    ):
        doc.quantity_max = flt(
            quantity_max
        )

    doc.quantity_text = (
        quantity_text
    )
    doc.unit = unit
    doc.priority = priority
    doc.need_status = "open"
    doc.needed_before = (
        needed_before
    )
    doc.notes = notes
    doc.observed_at = (
        now_datetime()
    )
    doc.verification_status = (
        "self_reported"
    )

    doc.insert(
        ignore_permissions=True
    )

    return {
        "shelter_need": doc.name,
        "item_name": doc.item_name,
        "quantity_mode": (
            doc.quantity_mode
        ),
        "status": doc.need_status,
    }


@frappe.whitelist()
def update_need_status(
    shelter_need,
    new_status,
):
    actor = rn_actor()

    doc = frappe.get_doc(
        "RN Shelter Need",
        shelter_need,
    )

    _assert_shelter_access(
        actor,
        doc.posko,
    )

    current = doc.need_status

    if new_status not in (
        NEED_TRANSITIONS.get(
            current,
            set(),
        )
    ):
        frappe.throw(
            f"Transisi kebutuhan tidak valid: "
            f"{current} -> {new_status}"
        )

    doc.need_status = new_status

    doc.save(
        ignore_permissions=True
    )

    return {
        "shelter_need": doc.name,
        "previous_status": current,
        "status": doc.need_status,
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
        "RN Shelter Occupancy",
        "RN Shelter Household",
        "RN Shelter Need",
    }

    if linked_doctype not in supported:
        frappe.throw(
            "Objek evidence Shelter tidak didukung"
        )

    if not frappe.db.exists(
        linked_doctype,
        linked_name,
    ):
        frappe.throw(
            "Objek evidence tidak ditemukan"
        )

    if not (
        file_url or ""
    ).startswith(
        "/private/files/"
    ):
        frappe.throw(
            "Evidence Shelter wajib private"
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

    actor = rn_actor()

    posko = frappe.db.get_value(
        linked_doctype,
        linked_name,
        "posko",
    )

    _assert_shelter_access(
        actor,
        posko,
    )

    now = now_datetime()

    doc = frappe.new_doc(
        "RN Operational Evidence"
    )

    doc.linked_doctype = (
        linked_doctype
    )
    doc.linked_name = linked_name
    doc.posko = posko
    doc.file_url = file_url
    doc.evidence_type = (
        evidence_type
    )
    doc.caption = caption
    doc.observed_at = now
    doc.uploaded_at = now
    doc.uploader_user = actor.name
    doc.verification_status = (
        "pending"
    )

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


def _latest_occupancies(allowed):
    rows = frappe.get_all(
        "RN Shelter Occupancy",
        filters={
            "posko": ["in", allowed],
        },
        fields=[
            "name",
            "posko",
            "shelter_name",
            "capacity_total",
            "current_occupancy",
            "families_count",
            "infants_count",
            "children_count",
            "elderly_count",
            "pregnant_count",
            "disability_count",
            "observed_at",
        ],
        order_by=(
            "observed_at desc, "
            "creation desc"
        ),
        limit_page_length=5000,
    )

    latest = {}

    for row in rows:
        key = (
            row.posko,
            row.shelter_name,
        )

        if key not in latest:
            latest[key] = row

    return list(
        latest.values()
    )


@frappe.whitelist()
def control_centre_shelter():
    actor = rn_actor()

    role = getattr(
        actor,
        "role",
        None,
    )

    if (
        not is_system_manager()
        and role not in CONTROL_ROLES
    ):
        frappe.throw(
            "Akses Control Centre Shelter ditolak",
            frappe.PermissionError,
        )

    if (
        is_system_manager()
        or role == "command_center"
    ):
        allowed = _all_shelters()
    else:
        allowed = _accessible_shelters(
            actor
        )

    if not allowed:
        return {
            "shelter_count": 0,
            "snapshot": {},
            "registered_households": {},
            "needs": {},
            "capacity_alerts": [],
            "privacy": (
                "Aggregate only."
            ),
        }

    latest = _latest_occupancies(
        allowed
    )

    snapshot_capacity = 0
    snapshot_people = 0
    snapshot_families = 0

    vulnerable = defaultdict(int)

    capacity_alerts = []

    for row in latest:
        capacity = cint(
            row.capacity_total
        )
        current = cint(
            row.current_occupancy
        )

        snapshot_capacity += capacity
        snapshot_people += current
        snapshot_families += cint(
            row.families_count
        )

        for fieldname in (
            "infants_count",
            "children_count",
            "elderly_count",
            "pregnant_count",
            "disability_count",
        ):
            vulnerable[
                fieldname
            ] += cint(
                row.get(fieldname)
            )

        if capacity > 0:
            pct = (
                current
                * 100
                / capacity
            )

            if pct >= 90:
                capacity_alerts.append({
                    "posko": row.posko,
                    "shelter_name": (
                        row.shelter_name
                    ),
                    "capacity_total": (
                        capacity
                    ),
                    "current_occupancy": (
                        current
                    ),
                    "occupancy_percent": round(
                        pct,
                        1,
                    ),
                })

    active_households = frappe.get_all(
        "RN Shelter Household",
        filters={
            "posko": ["in", allowed],
            "household_status": "checked_in",
        },
        fields=[
            "members_count",
            "infants_count",
            "children_count",
            "elderly_count",
            "pregnant_count",
            "disability_count",
        ],
        limit_page_length=5000,
    )

    registered_people = sum(
        cint(x.members_count)
        for x in active_households
    )

    open_needs = frappe.get_all(
        "RN Shelter Need",
        filters={
            "posko": ["in", allowed],
            "need_status": [
                "in",
                [
                    "open",
                    "partially_met",
                ],
            ],
        },
        fields=[
            "priority",
            "need_status",
        ],
        limit_page_length=5000,
    )

    critical_needs = sum(
        1
        for x in open_needs
        if x.priority == "critical"
    )

    return {
        "shelter_count": len(
            set(
                row.posko
                for row in latest
            )
        ),
        "snapshot": {
            "capacity_total": (
                snapshot_capacity
            ),
            "current_occupancy": (
                snapshot_people
            ),
            "families_count": (
                snapshot_families
            ),
            "vulnerable": dict(
                vulnerable
            ),
        },
        "registered_households": {
            "active_households": len(
                active_households
            ),
            "registered_people": (
                registered_people
            ),
        },
        "needs": {
            "open_or_partial": len(
                open_needs
            ),
            "critical": critical_needs,
        },
        "capacity_alerts": (
            capacity_alerts
        ),
        "privacy": (
            "Occupancy snapshot dan "
            "registrasi keluarga adalah "
            "dua sumber berbeda dan tidak "
            "dijumlahkan otomatis. "
            "Tidak ada identitas korban "
            "dalam agregat Control Centre."
        ),
    }
