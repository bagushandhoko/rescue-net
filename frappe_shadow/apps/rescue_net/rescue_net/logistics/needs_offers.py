"""Logistics — posko logistics dashboard, logistic needs, stock observations, aid offers."""

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

from rescue_net.logistics.common import (  # noqa: F401
    _accessible_poskos,
    _can_contribute,
    _can_operate,
)


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def dashboard(posko=None):
    # RN_CANONICAL_REF posko = resolve_posko(posko)
    posko = resolve_posko(posko)
    actor = rn_actor(required=False)
    allowed = _accessible_poskos(actor)

    if posko:
        # Guests reading a specific posko get a public read-only view of
        # that one posko; the manager allow-list only gates authenticated
        # actors (same guest-read model used by the other *_board endpoints).
        if actor and posko not in allowed:
            frappe.throw(
                "Anda tidak memiliki akses ke Posko ini",
                frappe.PermissionError,
            )
        allowed = [posko]

    if not allowed:
        return {
            "poskos":[],
            "needs":[],
            "stocks":[],
            "offers":[],
            "flows":[],
            "transports":[],
        }

    poskos = frappe.get_all(
        "RN Posko",
        filters={"name":["in", allowed]},
        fields=[
            "name","title","organization","posko_type",
            "operational_status","verification_status",
            "public_detail","public_participation",
            "source_updated_at","observed_at",
            "freshness_policy_minutes","modified",
        ],
        order_by="title asc",
        limit_page_length=500,
    )

    needs = frappe.get_all(
        "RN Logistic Need",
        filters={"posko":["in", allowed]},
        fields=[
            "name","title","posko","item_name",
            "raw_item_text","quantity","unit",
            "quantity_mode","quantity_min","quantity_max",
            "estimate_text","canonical_category",
            "canonical_group","canonical_item",
            "urgency","need_status",
            "verification_status","observed_at",
            "source_updated_at","freshness_policy_minutes",
            "modified",
        ],
        order_by="creation desc",
        limit_page_length=1000,
    )

    stocks = frappe.get_all(
        "RN Stock Observation",
        filters={"posko":["in", allowed]},
        fields=[
            "name","title","posko","item_name",
            "raw_item_text","quantity","unit",
            "quantity_mode","quantity_min","quantity_max",
            "estimate_text","stock_state",
            "canonical_category","canonical_group",
            "canonical_item","verification_status",
            "observed_at","source_updated_at",
            "freshness_policy_minutes","modified",
        ],
        order_by="observed_at desc",
        limit_page_length=1000,
    )

    offers = frappe.get_all(
        "RN Aid Offer",
        filters={"target_posko":["in", allowed]},
        fields=[
            "name","title","target_posko","donor_name",
            "item_name","raw_item_text","quantity","unit",
            "quantity_mode","quantity_min","quantity_max",
            "canonical_category","canonical_group",
            "canonical_item","offer_status",
            "verification_status","observed_at",
            "source_updated_at","freshness_policy_minutes",
            "modified",
        ],
        order_by="creation desc",
        limit_page_length=1000,
    )

    transports = frappe.get_all(
        "RN Transport Space",
        filters={"coordination_posko":["in", allowed]},
        fields=[
            "name","title","coordination_posko",
            "provider_name","transport_type",
            "route_origin","route_destination",
            "capacity_weight_kg","capacity_volume_m3",
            "departure_time","eta","transport_status",
            "current_location","handover_location",
            "handover_contact_person","handover_contact_phone",
            "coordination_notes",
            "verification_status","observed_at",
            "source_updated_at","freshness_policy_minutes",
            "modified",
        ],
        order_by="creation desc",
        limit_page_length=1000,
    )

    flows = frappe.get_all(
        "RN Distribution Flow",
        filters=[
            ["RN Distribution Flow","destination_posko","in",allowed],
        ],
        fields=[
            "name","title","source_posko","destination_posko",
            "item_name","quantity","unit","quantity_mode",
            "canonical_group","flow_status","eta_final",
            "transport_space",
            "received_quantity","received_unit",
            "source_updated_at","observed_at",
            "freshness_policy_minutes","modified",
        ],
        order_by="creation desc",
        limit_page_length=1000,
    )

    for collection, kind in [
        (needs, "need"),
        (stocks, "stock"),
        (offers, "stock"),
        (transports, "stock"),
        (flows, "stock"),
    ]:
        for row in collection:
            row["freshness"] = freshness(
                row.get("source_updated_at"),
                row.get("observed_at"),
                None,
                row.get("freshness_policy_minutes"),
                kind,
            )

    return {
        "poskos":poskos,
        "needs":needs,
        "stocks":stocks,
        "offers":offers,
        "transports":transports,
        "flows":flows,
    }


@frappe.whitelist()
def create_need(
    posko,
    item_text,
    quantity=None,
    unit=None,
    quantity_mode="unknown",
    quantity_min=None,
    quantity_max=None,
    estimate_text=None,
    urgency="normal",
    needed_before=None,
    jiwa_terdampak=None,
):
    # RN_CANONICAL_REF posko = resolve_posko(posko)
    posko = resolve_posko(posko)
    actor = rn_actor()

    if not _can_contribute(actor, posko):
        frappe.throw(
            "Anda tidak dapat menambahkan kebutuhan ke Posko ini",
            frappe.PermissionError,
        )

    doc = frappe.new_doc("RN Logistic Need")
    doc.title = item_text
    doc.posko = posko
    doc.item_name = item_text
    doc.raw_item_text = item_text

    if quantity not in (None, ""):
        doc.quantity = flt(quantity)

    doc.unit = unit
    doc.quantity_mode = quantity_mode or "unknown"

    if quantity_min not in (None, ""):
        doc.quantity_min = flt(quantity_min)

    if quantity_max not in (None, ""):
        doc.quantity_max = flt(quantity_max)

    doc.estimate_text = estimate_text
    doc.urgency = urgency
    doc.needed_before = needed_before
    if jiwa_terdampak not in (None, ""):
        doc.jiwa_terdampak = max(0, int(flt(jiwa_terdampak)))
    doc.need_status = "open"
    doc.insert(ignore_permissions=True)

    return {
        "need":doc.name,
        "canonical_group":doc.canonical_group,
        "quantity_mode":doc.quantity_mode,
    }


@frappe.whitelist()
def create_stock_observation(
    posko,
    item_text,
    quantity=None,
    unit=None,
    quantity_mode="unknown",
    quantity_min=None,
    quantity_max=None,
    estimate_text=None,
    stock_state="available",
    notes=None,
):
    # RN_CANONICAL_REF posko = resolve_posko(posko)
    posko = resolve_posko(posko)
    actor = rn_actor()

    if not _can_operate(actor, posko):
        frappe.throw(
            "Hanya operator/owner Posko yang dapat memperbarui stok",
            frappe.PermissionError,
        )

    doc = frappe.new_doc("RN Stock Observation")
    doc.title = item_text
    doc.posko = posko
    doc.item_name = item_text
    doc.raw_item_text = item_text

    if quantity not in (None, ""):
        doc.quantity = flt(quantity)

    doc.unit = unit
    doc.quantity_mode = quantity_mode or "unknown"

    if quantity_min not in (None, ""):
        doc.quantity_min = flt(quantity_min)

    if quantity_max not in (None, ""):
        doc.quantity_max = flt(quantity_max)

    doc.estimate_text = estimate_text
    doc.stock_state = stock_state
    doc.notes = notes
    doc.observed_at = now_datetime()
    doc.source_updated_at = doc.observed_at
    doc.insert(ignore_permissions=True)

    return {
        "stock":doc.name,
        "canonical_group":doc.canonical_group,
        "quantity_mode":doc.quantity_mode,
        "observed_at":doc.observed_at,
    }


@frappe.whitelist()
def create_aid_offer(
    target_posko,
    donor_name,
    item_text,
    quantity=None,
    unit=None,
    quantity_mode="unknown",
    estimate_text=None,
    pickup_location=None,
    donor_contact=None,
):
    # RN_CANONICAL_REF target_posko = resolve_posko(target_posko)
    target_posko = resolve_posko(target_posko)
    actor = rn_actor()

    internal = _can_contribute(actor, target_posko)

    public_ok = (
        public_posko_allowed(target_posko)
        and cint(
            frappe.db.get_value(
                "RN Posko",
                target_posko,
                "public_participation",
            ) or 0
        )
        and cint(
            frappe.db.get_value(
                "RN Posko",
                target_posko,
                "accept_goods",
            ) or 0
        )
    )

    if not internal and not public_ok:
        frappe.throw(
            "Posko ini tidak membuka penerimaan bantuan untuk akun Anda",
            frappe.PermissionError,
        )

    doc = frappe.new_doc("RN Aid Offer")
    doc.title = f"{item_text} - {donor_name}"
    doc.target_posko = target_posko
    doc.donor_name = donor_name
    doc.item_name = item_text
    doc.raw_item_text = item_text

    if quantity not in (None, ""):
        doc.quantity = flt(quantity)

    doc.unit = unit
    doc.quantity_mode = quantity_mode or "unknown"
    doc.estimate_text = estimate_text
    doc.pickup_location = pickup_location
    doc.donor_contact = donor_contact
    doc.offer_status = "available"
    doc.insert(ignore_permissions=True)

    return {
        "aid_offer":doc.name,
        "canonical_group":doc.canonical_group,
        "offer_status":doc.offer_status,
    }
