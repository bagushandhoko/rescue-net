from collections import defaultdict

import frappe
from frappe.rate_limiter import rate_limit
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


# the rules live in the match controller (phase 2)
from rescue_net.rescue_net.doctype.rn_search_found_match.rn_search_found_match import (  # noqa: E402
    MATCH_TRANSITIONS,
)


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


def _reporter_identity(actor, posko, reporter_name=None, reporter_contact=None):
    """Who to call back to confirm a report. Owner rule (2026-09-26): a
    report that is not tied to a posko may be opened by any operator, so the
    reporter must be reachable — the typed contact, else the account's phone
    or email; refuse the report when there is none."""
    name = str(reporter_name or "").strip() or None
    contact = str(reporter_contact or "").strip() or None
    account = getattr(actor, "name", None)
    if account and not (name and contact):
        row = frappe.db.get_value(
            "RN User Account", account, ["title", "phone", "email"], as_dict=True,
        ) or {}
        name = name or row.get("title")
        contact = contact or row.get("phone") or row.get("email")
    if not contact and not posko:
        frappe.throw("Kontak pelapor wajib diisi agar laporan bisa dikonfirmasi.")
    return name, contact


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
    reporter_name=None,
    reporter_contact=None,
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
    doc.reporter_name, doc.reporter_contact = _reporter_identity(
        actor, posko, reporter_name, reporter_contact,
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
    reporter_name=None,
    reporter_contact=None,
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
    doc.reporter_name, doc.reporter_contact = _reporter_identity(
        actor, posko, reporter_name, reporter_contact,
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

    # transitions, one confirmed match per report and the report status
    # sync are enforced by RNSearchFoundMatch (validate / on_update)
    doc.match_status = new_status
    doc.review_notes = review_notes
    doc.reviewed_by_user = (
        _actor_name(actor)
    )
    doc.reviewed_at = now_datetime()

    if new_status == "confirmed":
        doc.verification_status = "reviewed"
    elif new_status == "reunited":
        doc.verification_status = "verified"
    elif new_status == "rejected":
        doc.verification_status = "rejected"

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


# SECURITY: returns unmasked person_name — must stay login + manager
# gated. Never add allow_guest=True here.
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
        # to confirm the report with whoever filed it
        "reporter": {
            "name": doc.get("reporter_name"),
            "contact": doc.get("reporter_contact"),
            "account": doc.created_by_user,
        },
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


# Public listing: person_name/NIK are never in the `fields=` lists below
# (only person_code + masked description/clothing), so this is safe to open
# to Guest. Full identity stays behind restricted_record(), which is not
# guest-accessible and still requires a manager role.
@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def dashboard(disaster_event=None):
    # RN_CANONICAL_REF disaster_event = resolve_disaster_event(disaster_event)
    disaster_event = resolve_disaster_event(disaster_event)
    actor = rn_actor(required=False)

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

    if actor:
        # Unchanged existing behaviour for any logged-in actor.
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
    else:
        # Guest: the masked `fields=` lists above (person_code + generic
        # description/clothing only, no person_name/NIK) are what make this
        # safe to expose, so the network-wide list is shown unfiltered by
        # posko/org — that scoping is an operational-management check, not
        # a privacy one, and a citizen searching for missing family has no
        # posko/org affiliation to scope by in the first place.
        allowed_missing = missing
        allowed_found = found

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
            else ("viewer" if actor else "public")
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
