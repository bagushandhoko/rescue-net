"""Frontend bridge — verification context, verifier status, endorsement revocation, verifier profile / action."""

import base64
import math
import uuid
from collections import defaultdict

import frappe
from frappe.utils import flt, now_datetime
from frappe.utils.file_manager import save_file

from rescue_net.access_policy import (
    can_edit_event,
    editable_disaster_events,
    is_system_manager,
    rn_actor,
)
from rescue_net.reference_resolver import (
    resolve_disaster_event,
    resolve_posko,
)

from rescue_net.frontend_bridge.common import (  # noqa: F401
    _actor,
    _canonical_event,
    _meta_fields,
    _row_value,
)


def _verification_rows(
    doctype,
):
    if not frappe.db.exists(
        "DocType",
        doctype,
    ):
        return []

    meta = frappe.get_meta(
        doctype
    )

    fields = [
        "name",
        *[
            df.fieldname
            for df in meta.fields
            if df.fieldname
            and df.fieldtype
            not in (
                "Section Break",
                "Column Break",
                "Tab Break",
                "HTML",
                "Button",
                "Table",
            )
        ],
    ]

    return [
        dict(x)
        for x in frappe.get_all(
            doctype,
            fields=fields,
            order_by="creation desc",
            limit_page_length=3000,
        )
    ]


@frappe.whitelist()
def verification_context(
    disaster_event=None,
):
    _actor()

    event = (
        _canonical_event(
            disaster_event
        )
        if disaster_event
        else None
    )

    profiles = _verification_rows(
        "RN Verifier Profile"
    )

    requests = _verification_rows(
        "RN Verification Request"
    )

    endorsements = _verification_rows(
        "RN Verification Endorsement"
    )

    actions = _verification_rows(
        "RN Verification Action"
    )

    if event:
        actions = [
            row
            for row in actions
            if (
                not row.get(
                    "disaster_event"
                )
                or row.get(
                    "disaster_event"
                ) == event
            )
        ]

    def status_of(
        row,
        *fields,
    ):
        return str(
            _row_value(
                row,
                *fields,
            )
            or ""
        ).lower()

    summary = {
        "candidate_verifier_count":
            sum(
                1
                for x in profiles
                if status_of(
                    x,
                    "verifier_status",
                    "status",
                )
                in (
                    "candidate_verifier",
                    "pending",
                    "candidate",
                )
            ),

        "pending_verifier_request_count":
            sum(
                1
                for x in requests
                if status_of(
                    x,
                    "status",
                    "request_status",
                )
                == "pending"
            ),

        "active_endorsement_count":
            sum(
                1
                for x in endorsements
                if status_of(
                    x,
                    "status",
                    "endorsement_status",
                )
                == "active"
            ),

        "revoked_endorsement_count":
            sum(
                1
                for x in endorsements
                if status_of(
                    x,
                    "status",
                    "endorsement_status",
                )
                == "revoked"
            ),
    }

    return {
        "verifier_profiles":
            profiles,

        "verification_requests":
            requests,

        "verification_endorsements":
            endorsements,

        "verification_actions":
            actions,

        "summary":
            summary,
    }


@frappe.whitelist()
def set_verifier_status(
    verifier,
    status,
):
    _actor()

    if not frappe.db.exists(
        "RN Verifier Profile",
        verifier,
    ):
        frappe.throw(
            "Verifier Profile tidak ditemukan"
        )

    doc = frappe.get_doc(
        "RN Verifier Profile",
        verifier,
    )

    fields = _meta_fields(
        "RN Verifier Profile"
    )

    field = (
        "verifier_status"
        if "verifier_status" in fields
        else (
            "status"
            if "status" in fields
            else None
        )
    )

    if not field:
        frappe.throw(
            "Field status verifier tidak tersedia"
        )

    doc.set(field, status)

    doc.save(
        ignore_permissions=True
    )

    return {
        "verifier": doc.name,
        "status": doc.get(field),
    }


@frappe.whitelist()
def revoke_verification_endorsement(
    endorsement,
):
    _actor()

    if not frappe.db.exists(
        "RN Verification Endorsement",
        endorsement,
    ):
        frappe.throw(
            "Verification Endorsement tidak ditemukan"
        )

    doc = frappe.get_doc(
        "RN Verification Endorsement",
        endorsement,
    )

    fields = _meta_fields(
        "RN Verification Endorsement"
    )

    field = (
        "status"
        if "status" in fields
        else (
            "endorsement_status"
            if "endorsement_status"
            in fields
            else None
        )
    )

    if not field:
        frappe.throw(
            "Field status endorsement tidak tersedia"
        )

    doc.set(
        field,
        "revoked",
    )

    doc.save(
        ignore_permissions=True
    )

    return {
        "endorsement": doc.name,
        "status": "revoked",
    }


def _dynamic_insert(
    doctype,
    payload,
):
    meta = frappe.get_meta(
        doctype
    )

    valid = {
        df.fieldname
        for df in meta.fields
        if df.fieldname
    }

    doc = frappe.new_doc(
        doctype
    )

    for key, value in payload.items():
        if (
            key in valid
            and value not in (
                None,
                "",
            )
        ):
            doc.set(
                key,
                value,
            )

    doc.insert(
        ignore_permissions=True
    )

    return doc


@frappe.whitelist()
def create_verifier_profile(
    **payload,
):
    _actor()

    doc = _dynamic_insert(
        "RN Verifier Profile",
        payload,
    )

    return {
        "id": doc.name,
        "verifier": doc.name,
        "status":
            getattr(
                doc,
                "verifier_status",
                None,
            )
            or getattr(
                doc,
                "status",
                None,
            ),
    }


@frappe.whitelist()
def create_verification_action(
    **payload,
):
    _actor()

    doc = _dynamic_insert(
        "RN Verification Action",
        payload,
    )

    return {
        "id": doc.name,
        "verification_action":
            doc.name,
    }
