from collections import defaultdict

import frappe
from rescue_net.reference_resolver import resolve_disaster_event, resolve_posko
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


MATCH_TRANSITIONS = {
    "proposed": {
        "confirmed",
        "rejected",
    },
    "confirmed": {
        "reunited",
        "rejected",
    },
    "rejected": set(),
    "reunited": set(),
}


def _role(actor):
    return getattr(actor, "role", None)


def _is_manager(actor):
    return bool(
        is_system_manager()
        or _role(actor) in MANAGER_ROLES
    )


def _can_operate_posko(actor, posko):
    if not posko:
        return True

    if is_system_manager():
        return True

    if can_manage_posko(actor, posko):
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


def _assert_manager(actor):
    if not _is_manager(actor):
        frappe.throw(
            "Hak operator diperlukan",
            frappe.PermissionError,
        )


def _assert_record_access(actor, doctype, name):
    posko = frappe.db.get_value(
        doctype,
        name,
        "posko",
    )

    if posko and not _can_operate_posko(
        actor,
        posko,
    ):
        frappe.throw(
            "Akses laporan ditolak",
            frappe.PermissionError,
        )


def _actor_name(actor):
    return getattr(actor, "name", None)


@frappe.whitelist()
def create_missing_report(
    person_code,
    person_name=None,
    disaster_event=None,
    posko=None,
    last_seen_location=None,
    last_seen_time=None,
    description=None,
    clothing_description=None,
):
    # RN_CANONICAL_REF disaster_event = resolve_disaster_event(disaster_event)
    disaster_event = resolve_disaster_event(disaster_event)
    # RN_CANONICAL_REF posko = resolve_posko(posko)
    posko = resolve_posko(posko)
    actor = rn_actor()

    if posko and not _can_operate_posko(
        actor,
        posko,
    ):
        frappe.throw(
            "Akses Posko ditolak",
            frappe.PermissionError,
        )

    doc = frappe.new_doc(
        "RN Missing Person Report"
    )

    doc.disaster_event = (
        _resolve_disaster_event(
            disaster_event
        )
    )
    doc.posko = posko
    doc.person_code = person_code
    doc.person_name = person_name
    doc.last_seen_location = (
        last_seen_location
    )
    doc.last_seen_time = last_seen_time
    doc.description = description
    doc.clothing_description = (
        clothing_description
    )
    doc.report_status = "missing"
    doc.observed_at = now_datetime()
    doc.created_by_user = _actor_name(
        actor
    )
    doc.verification_status = (
        "self_reported"
    )

    doc.insert(ignore_permissions=True)

    return {
        "missing_report": doc.name,
        "person_code": doc.person_code,
        "status": doc.report_status,
    }


@frappe.whitelist()
def create_found_report(
    person_code,
    person_name=None,
    disaster_event=None,
    posko=None,
    found_location=None,
    found_time=None,
    description=None,
    clothing_description=None,
):
    # RN_CANONICAL_REF disaster_event = resolve_disaster_event(disaster_event)
    disaster_event = resolve_disaster_event(disaster_event)
    # RN_CANONICAL_REF posko = resolve_posko(posko)
    posko = resolve_posko(posko)
    actor = rn_actor()

    if posko and not _can_operate_posko(
        actor,
        posko,
    ):
        frappe.throw(
            "Akses Posko ditolak",
            frappe.PermissionError,
        )

    doc = frappe.new_doc(
        "RN Found Person Report"
    )

    doc.disaster_event = (
        _resolve_disaster_event(
            disaster_event
        )
    )
    doc.posko = posko
    doc.person_code = person_code
    doc.person_name = person_name
    doc.found_location = found_location
    doc.found_time = found_time
    doc.description = description
    doc.clothing_description = (
        clothing_description
    )
    doc.report_status = "found"
    doc.observed_at = now_datetime()
    doc.created_by_user = _actor_name(
        actor
    )
    doc.verification_status = (
        "self_reported"
    )

    doc.insert(ignore_permissions=True)

    return {
        "found_report": doc.name,
        "person_code": doc.person_code,
        "status": doc.report_status,
    }


@frappe.whitelist()
def propose_match(
    missing_report,
    found_report,
    match_basis=None,
):
    actor = rn_actor()
    _assert_manager(actor)

    _assert_record_access(
        actor,
        "RN Missing Person Report",
        missing_report,
    )

    _assert_record_access(
        actor,
        "RN Found Person Report",
        found_report,
    )

    if frappe.db.exists(
        "RN Search Found Match",
        {
            "missing_report": missing_report,
            "found_report": found_report,
            "match_status": [
                "in",
                [
                    "proposed",
                    "confirmed",
                    "reunited",
                ],
            ],
        },
    ):
        frappe.throw(
            "Pasangan laporan ini sudah memiliki match aktif"
        )

    doc = frappe.new_doc(
        "RN Search Found Match"
    )

    doc.missing_report = missing_report
    doc.found_report = found_report
    doc.match_status = "proposed"
    doc.match_basis = match_basis
    doc.verification_status = "pending"

    doc.insert(ignore_permissions=True)

    return {
        "match": doc.name,
        "status": doc.match_status,
    }


def _assert_no_confirmed_conflict(doc):
    conflicts = frappe.get_all(
        "RN Search Found Match",
        filters=[
            [
                "name",
                "!=",
                doc.name,
            ],
            [
                "match_status",
                "in",
                [
                    "confirmed",
                    "reunited",
                ],
            ],
        ],
        fields=[
            "name",
            "missing_report",
            "found_report",
        ],
        limit_page_length=5000,
    )

    for row in conflicts:
        if (
            row.missing_report
            == doc.missing_report
            or row.found_report
            == doc.found_report
        ):
            frappe.throw(
                "Salah satu laporan sudah mempunyai "
                "match terkonfirmasi"
            )


@frappe.whitelist()
def update_match_status(
    match,
    new_status,
    review_notes=None,
):
    actor = rn_actor()
    _assert_manager(actor)

    doc = frappe.get_doc(
        "RN Search Found Match",
        match,
    )

    _assert_record_access(
        actor,
        "RN Missing Person Report",
        doc.missing_report,
    )

    _assert_record_access(
        actor,
        "RN Found Person Report",
        doc.found_report,
    )

    current = doc.match_status

    if new_status not in (
        MATCH_TRANSITIONS.get(
            current,
            set(),
        )
    ):
        frappe.throw(
            f"Transisi match tidak valid: "
            f"{current} -> {new_status}"
        )

    if new_status in {
        "confirmed",
        "reunited",
    }:
        _assert_no_confirmed_conflict(doc)

    doc.match_status = new_status
    doc.review_notes = review_notes
    doc.reviewed_by_user = (
        _actor_name(actor)
    )
    doc.reviewed_at = now_datetime()

    if new_status == "confirmed":
        doc.verification_status = (
            "reviewed"
        )

    elif new_status == "reunited":
        doc.verification_status = (
            "verified"
        )

        frappe.db.set_value(
            "RN Missing Person Report",
            doc.missing_report,
            "report_status",
            "reunited",
            update_modified=False,
        )

        frappe.db.set_value(
            "RN Found Person Report",
            doc.found_report,
            "report_status",
            "reunited",
            update_modified=False,
        )

    elif new_status == "rejected":
        doc.verification_status = (
            "rejected"
        )

        frappe.db.set_value(
            "RN Missing Person Report",
            doc.missing_report,
            "report_status",
            "missing",
            update_modified=False,
        )

        frappe.db.set_value(
            "RN Found Person Report",
            doc.found_report,
            "report_status",
            "found",
            update_modified=False,
        )

    doc.save(ignore_permissions=True)

    return {
        "match": doc.name,
        "previous_status": current,
        "status": doc.match_status,
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
        "RN Missing Person Report",
        "RN Found Person Report",
        "RN Search Found Match",
    }

    if linked_doctype not in supported:
        frappe.throw(
            "Objek Search & Found tidak didukung"
        )

    if not frappe.db.exists(
        linked_doctype,
        linked_name,
    ):
        frappe.throw(
            "Objek tidak ditemukan"
        )

    if not (
        file_url or ""
    ).startswith(
        "/private/files/"
    ):
        frappe.throw(
            "Evidence Search & Found wajib private"
        )

    actor = rn_actor()

    if linked_doctype in {
        "RN Missing Person Report",
        "RN Found Person Report",
    }:
        _assert_record_access(
            actor,
            linked_doctype,
            linked_name,
        )

        posko = frappe.db.get_value(
            linked_doctype,
            linked_name,
            "posko",
        )

    else:
        match = frappe.get_doc(
            "RN Search Found Match",
            linked_name,
        )

        _assert_record_access(
            actor,
            "RN Missing Person Report",
            match.missing_report,
        )

        posko = frappe.db.get_value(
            "RN Missing Person Report",
            match.missing_report,
            "posko",
        )

    now = now_datetime()

    ev = frappe.new_doc(
        "RN Operational Evidence"
    )

    ev.linked_doctype = linked_doctype
    ev.linked_name = linked_name
    ev.posko = posko
    ev.file_url = file_url
    ev.evidence_type = evidence_type
    ev.caption = caption
    ev.observed_at = now
    ev.uploaded_at = now
    ev.uploader_user = _actor_name(
        actor
    )
    ev.verification_status = "pending"

    ev.insert(ignore_permissions=True)

    return {
        "evidence": ev.name,
        "private": True,
        "verification_status": (
            ev.verification_status
        ),
    }


@frappe.whitelist()
def restricted_record(
    doctype,
    name,
):
    actor = rn_actor()
    _assert_manager(actor)

    if doctype not in {
        "RN Missing Person Report",
        "RN Found Person Report",
    }:
        frappe.throw(
            "Jenis record tidak didukung"
        )

    _assert_record_access(
        actor,
        doctype,
        name,
    )

    doc = frappe.get_doc(
        doctype,
        name,
    )

    return {
        "name": doc.name,
        "person_code": doc.person_code,
        "person_name": doc.person_name,
        "description": doc.description,
        "clothing_description": (
            doc.clothing_description
        ),
        "privacy": "restricted",
    }


def _resolve_disaster_event(value):
    if not value:
        return None

    value = str(value).strip()

    if not value:
        return None

    if frappe.db.exists(
        "RN Disaster Event",
        value,
    ):
        return value

    candidates = [value]

    if not value.startswith(
        "disaster_events:"
    ):
        candidates.append(
            "disaster_events:" + value
        )

    for legacy_id in candidates:
        name = frappe.db.get_value(
            "RN Disaster Event",
            {
                "legacy_id":
                    legacy_id
            },
            "name",
        )

        if name:
            return name

        if frappe.db.exists(
            "RN Disaster Event",
            legacy_id,
        ):
            return legacy_id

    return value


@frappe.whitelist()
def dashboard(disaster_event=None):
    # RN_CANONICAL_REF disaster_event = resolve_disaster_event(disaster_event)
    disaster_event = resolve_disaster_event(disaster_event)
    actor = rn_actor()

    resolved_event = (
        _resolve_disaster_event(
            disaster_event
        )
    )

    missing_filters = {}
    found_filters = {}

    if resolved_event:
        missing_filters[
            "disaster_event"
        ] = resolved_event

        found_filters[
            "disaster_event"
        ] = resolved_event

    missing = frappe.get_all(
        "RN Missing Person Report",
        filters=missing_filters,
        fields=[
            "name",
            "disaster_event",
            "posko",
            "person_code",
            "last_seen_location",
            "last_seen_time",
            "description",
            "clothing_description",
            "report_status",
            "observed_at",
            "verification_status",
        ],
        order_by="creation desc",
        limit_page_length=2000,
    )

    found = frappe.get_all(
        "RN Found Person Report",
        filters=found_filters,
        fields=[
            "name",
            "disaster_event",
            "posko",
            "person_code",
            "found_location",
            "found_time",
            "description",
            "clothing_description",
            "report_status",
            "observed_at",
            "verification_status",
        ],
        order_by="creation desc",
        limit_page_length=2000,
    )

    allowed_missing = []

    for row in missing:
        if _can_operate_posko(
            actor,
            row.posko,
        ):
            allowed_missing.append(row)

    allowed_found = []

    for row in found:
        if _can_operate_posko(
            actor,
            row.posko,
        ):
            allowed_found.append(row)

    missing_names = {
        x.name
        for x in allowed_missing
    }

    found_names = {
        x.name
        for x in allowed_found
    }

    matches = []

    if missing_names and found_names:
        raw_matches = frappe.get_all(
            "RN Search Found Match",
            fields=[
                "name",
                "missing_report",
                "found_report",
                "match_status",
                "match_basis",
                "reviewed_at",
                "verification_status",
            ],
            order_by="creation desc",
            limit_page_length=2000,
        )

        matches = [
            x
            for x in raw_matches
            if (
                x.missing_report
                in missing_names
                and x.found_report
                in found_names
            )
        ]

    return {
        "mode": (
            "manager"
            if _is_manager(actor)
            else "viewer"
        ),
        "missing": allowed_missing,
        "found": allowed_found,
        "matches": matches,
        "privacy": (
            "Nama lengkap tidak dikirim melalui dashboard. "
            "Operator berwenang harus membuka restricted_record."
        ),
    }


@frappe.whitelist()
def control_centre_search_found():
    actor = rn_actor()

    if not (
        is_system_manager()
        or _role(actor) == "command_center"
    ):
        frappe.throw(
            "Akses Control Centre ditolak",
            frappe.PermissionError,
        )

    missing_open = frappe.db.count(
        "RN Missing Person Report",
        {
            "report_status": "missing",
        },
    )

    found_open = frappe.db.count(
        "RN Found Person Report",
        {
            "report_status": "found",
        },
    )

    matches = frappe.get_all(
        "RN Search Found Match",
        fields=[
            "match_status",
        ],
        limit_page_length=5000,
    )

    status = defaultdict(int)

    for row in matches:
        status[row.match_status] += 1

    return {
        "missing_open": missing_open,
        "found_open": found_open,
        "match_status": dict(status),
        "reunited": status.get(
            "reunited",
            0,
        ),
        "privacy": (
            "Aggregate only. Tidak ada nama, "
            "kontak, atau ciri pribadi."
        ),
    }
