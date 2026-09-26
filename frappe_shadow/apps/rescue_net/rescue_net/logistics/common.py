"""Logistics — shared access helpers (who operates / contributes to a posko)."""

from collections import defaultdict

import frappe
from frappe.rate_limiter import rate_limit
from rescue_net.reference_resolver import resolve_disaster_event, resolve_posko
from frappe.utils import cint, flt, now_datetime

from rescue_net.access_policy import (
    approved_member,
    can_manage_organization,
    can_manage_posko,
    is_system_manager,
    public_posko_allowed,
    rn_actor,
)
from rescue_net.intelligence.freshness import freshness
from rescue_net.rn_logistics.doctype.rn_distribution_flow.rn_distribution_flow import TRANSITIONS
from rescue_net.intelligence.normalization import normalize_unit


OPERATOR_ROLES = {
    "posko_operator",
    "medical_operator",
    "shelter_operator",
}


def _member_orgs(actor):
    if not actor or not actor.name:
        return []

    orgs = frappe.get_all(
        "RN Organization Membership",
        filters={
            "user_account":actor.name,
            "status":"approved",
        },
        pluck="organization",
        limit_page_length=500,
    )

    if getattr(actor, "organization", None):
        orgs.append(actor.organization)

    return list(set(x for x in orgs if x))


def _accessible_poskos(actor):
    if is_system_manager():
        return frappe.get_all(
            "RN Posko",
            pluck="name",
            limit_page_length=5000,
        )

    result = set()

    for org in _member_orgs(actor):
        result.update(
            frappe.get_all(
                "RN Posko",
                filters={"organization":org},
                pluck="name",
                limit_page_length=1000,
            )
        )

    if actor and actor.name:
        result.update(
            frappe.get_all(
                "RN Posko Assignment",
                filters={
                    "user_account":actor.name,
                    "status":"approved",
                },
                pluck="posko",
                limit_page_length=500,
            )
        )

    if getattr(actor, "posko", None):
        result.add(actor.posko)

    return sorted(result)


def _can_operate(actor, posko):
    if is_system_manager():
        return True

    if can_manage_posko(actor, posko):
        return True

    org = frappe.db.get_value(
        "RN Posko",
        posko,
        "organization",
    )

    return bool(
        org and can_manage_organization(actor, org)
    )


def _can_contribute(actor, posko):
    if _can_operate(actor, posko):
        return True

    org = frappe.db.get_value(
        "RN Posko",
        posko,
        "organization",
    )

    return bool(
        org
        and actor
        and actor.name
        and approved_member(actor.name, org)
    )


def _class_fields(prefix=""):
    return [
        prefix + "canonical_category",
        prefix + "canonical_group",
        prefix + "canonical_item",
        prefix + "quantity_mode",
        prefix + "quantity_min",
        prefix + "quantity_max",
        prefix + "estimate_text",
    ]


ALLOWED_EVIDENCE_DOCTYPES = {
    "RN Logistic Need",
    "RN Aid Offer",
    "RN Distribution Flow",
    "RN Stock Observation",
    "RN Transport Space",
}


_GUEST_AID_FIELDS = (
    "name", "item_name", "raw_item_text", "quantity", "unit", "quantity_mode",
    "pickup_location", "ready_at", "notes", "offer_status", "handling_mode",
    "donor_name", "donor_contact", "target_posko", "disaster_event",
    "guest_batch", "submitted_channel", "canonical_group", "base_quantity",
    "base_unit", "conversion_status",
)


_GUEST_BOOKING_STATUS_LABEL = {
    "requested": "Menunggu Konfirmasi", "confirmed": "Terkonfirmasi",
    "rejected": "Ditolak", "cancelled": "Dibatalkan", "completed": "Selesai",
}


_AID_OFFER_UNRECEIVABLE_STATUSES = {"received", "received_verified", "cancelled"}


_ITEM_GROUP_DOCTYPES = {
    "offer": ("RN Aid Offer", "target_posko", "item_name"),
    "need": ("RN Logistic Need", "posko", "item_name"),
    "stock": ("RN Stock Observation", "posko", "item_name"),
}
