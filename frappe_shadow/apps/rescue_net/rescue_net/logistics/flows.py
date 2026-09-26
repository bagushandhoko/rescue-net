"""Logistics — distribution flows, flow status, evidence, public/Control Centre logistics views."""

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
from rescue_net.rescue_net.doctype.rn_distribution_flow.rn_distribution_flow import TRANSITIONS
from rescue_net.intelligence.normalization import normalize_unit

from rescue_net.logistics.common import (  # noqa: F401
    ALLOWED_EVIDENCE_DOCTYPES,
    OPERATOR_ROLES,
    _can_contribute,
    _can_operate,
)


@frappe.whitelist()
def create_flow(
    destination_posko,
    item_text,
    quantity=None,
    unit=None,
    quantity_mode="unknown",
    source_posko=None,
    logistic_need=None,
    aid_offer=None,
    transport_reference=None,
    transport_provider=None,
    transport_space=None,
    eta_final=None,
):
    # RN_CANONICAL_REF destination_posko = resolve_posko(destination_posko)
    destination_posko = resolve_posko(destination_posko)
    # RN_CANONICAL_REF source_posko = resolve_posko(source_posko)
    source_posko = resolve_posko(source_posko)
    actor = rn_actor()

    if not _can_operate(actor, destination_posko):
        if not source_posko or not _can_operate(actor, source_posko):
            frappe.throw(
                "Anda tidak dapat membuat flow untuk Posko ini",
                frappe.PermissionError,
            )

    transport_doc = None

    if transport_space:
        locked = frappe.db.sql(
            """
            SELECT name, transport_status
            FROM `tabRN Transport Space`
            WHERE name=%s
            FOR UPDATE
            """,
            (transport_space,),
            as_dict=True,
        )

        if not locked:
            frappe.throw("Transport tidak ditemukan")

        if locked[0].transport_status != "available":
            frappe.throw(
                "Transport sudah dipakai atau tidak tersedia"
            )

        transport_doc = frappe.get_doc(
            "RN Transport Space",
            transport_space,
        )

        if not _can_contribute(
            actor,
            transport_doc.coordination_posko,
        ):
            frappe.throw(
                "Anda tidak dapat menggunakan transport ini",
                frappe.PermissionError,
            )

    aid_doc = None

    if aid_offer:
        locked_aid = frappe.db.sql(
            """
            SELECT name, offer_status
            FROM `tabRN Aid Offer`
            WHERE name=%s
            FOR UPDATE
            """,
            (aid_offer,),
            as_dict=True,
        )

        if not locked_aid:
            frappe.throw("Aid Offer tidak ditemukan")

        if locked_aid[0].offer_status not in (
            "available",
            "need_pickup",
        ):
            frappe.throw(
                "Aid Offer sudah dialokasikan atau tidak tersedia"
            )

        aid_doc = frappe.get_doc(
            "RN Aid Offer",
            aid_offer,
        )

        if (
            aid_doc.target_posko
            and aid_doc.target_posko != destination_posko
        ):
            frappe.throw(
                "Aid Offer ditujukan ke Posko yang berbeda"
            )

    need_doc = None

    if logistic_need:
        need_doc = frappe.get_doc(
            "RN Logistic Need",
            logistic_need,
        )

        if (
            need_doc.posko
            and need_doc.posko != destination_posko
        ):
            frappe.throw(
                "Kebutuhan berasal dari Posko yang berbeda"
            )

        # L-20: no new flow for a need that is already closed
        from rescue_net.api_control_centre import _DRILL_CLOSED_NEED
        if str(need_doc.need_status or "open").lower() in _DRILL_CLOSED_NEED:
            frappe.throw(
                f"Kebutuhan ini sudah ditutup ({need_doc.need_status})."
            )

    doc = frappe.new_doc("RN Distribution Flow")
    doc.title = item_text
    doc.destination_posko = destination_posko
    doc.source_posko = source_posko
    # event-scope the flow so it shows on the event dashboards / pickup queue
    doc.disaster_event = (
        frappe.db.get_value("RN Posko", source_posko, "disaster_event")
        or frappe.db.get_value("RN Posko", destination_posko, "disaster_event")
    )
    doc.item_name = item_text
    doc.raw_item_text = item_text

    if quantity not in (None, ""):
        doc.quantity = flt(quantity)

    doc.unit = unit
    doc.quantity_mode = quantity_mode or "unknown"
    doc.logistic_need = logistic_need
    doc.aid_offer = aid_offer
    doc.transport_reference = transport_reference
    doc.transport_provider = transport_provider
    doc.transport_space = transport_space
    doc.eta_final = eta_final
    doc.flow_status = "planned"
    doc.insert(ignore_permissions=True)

    if transport_doc:
        frappe.db.set_value(
            "RN Transport Space",
            transport_doc.name,
            {
                "transport_status":"reserved",
                "source_updated_at":now_datetime(),
            },
            update_modified=False,
        )

    if aid_doc:
        frappe.db.set_value(
            "RN Aid Offer",
            aid_doc.name,
            {
                "offer_status":"reserved",
                "source_updated_at":now_datetime(),
            },
            update_modified=False,
        )

    if (
        need_doc
        and (need_doc.need_status or "open") == "open"
    ):
        frappe.db.set_value(
            "RN Logistic Need",
            need_doc.name,
            "need_status",
            "in_progress",
            update_modified=False,
        )

    return {
        "flow":doc.name,
        "flow_status":doc.flow_status,
        "canonical_group":doc.canonical_group,
    }


@frappe.whitelist()
def update_flow_status(
    flow,
    new_status,
    received_quantity=None,
    received_unit=None,
    receipt_note=None,
):
    actor = rn_actor()
    doc = frappe.get_doc("RN Distribution Flow", flow)

    allowed_actor = (
        (doc.source_posko and _can_operate(actor, doc.source_posko))
        or
        (doc.destination_posko and _can_operate(actor, doc.destination_posko))
    )

    if not allowed_actor:
        frappe.throw(
            "Anda tidak dapat memperbarui flow ini",
            frappe.PermissionError,
        )

    current = doc.flow_status or "planned"

    if new_status not in TRANSITIONS.get(current, set()):
        frappe.throw(
            f"Transisi {current} → {new_status} tidak diperbolehkan"
        )

    now = now_datetime()

    doc.flow_status = new_status
    doc.source_updated_at = now
    doc.last_updated_by_user = actor.name

    field_map = {
        "assigned_pickup":"assigned_pickup_at",
        "dispatched":"dispatched_at",
        "in_transit":"in_transit_at",
        "arrived_at_posko":"arrived_at",
        "received":"received_at",
        "cancelled":"cancelled_at",
    }

    if new_status in field_map:
        setattr(doc, field_map[new_status], now)

    if received_quantity not in (None, ""):
        doc.received_quantity = flt(received_quantity)

    if received_unit:
        doc.received_unit = received_unit

    if receipt_note:
        doc.receipt_note = receipt_note

    doc.save(ignore_permissions=True)

    # armada + aid offer follow in RNDistributionFlow.on_update (L-11)

    return {
        "flow":doc.name,
        "previous_status":current,
        "flow_status":doc.flow_status,
        "received_quantity":doc.received_quantity,
        "received_unit":doc.received_unit,
        "stock_created":False,
        "note":"Penerimaan tidak otomatis menjadi stok; stok harus diperbarui melalui Stock Observation.",
    }


@frappe.whitelist()
def add_evidence(
    linked_doctype,
    linked_name,
    file_url,
    evidence_type="photo",
    caption=None,
    observed_at=None,
):
    actor = rn_actor()

    if linked_doctype not in ALLOWED_EVIDENCE_DOCTYPES:
        frappe.throw("Jenis objek evidence tidak didukung")

    if not frappe.db.exists(linked_doctype, linked_name):
        frappe.throw("Objek evidence tidak ditemukan")

    posko = None

    if linked_doctype == "RN Logistic Need":
        posko = frappe.db.get_value(linked_doctype, linked_name, "posko")
    elif linked_doctype == "RN Aid Offer":
        posko = frappe.db.get_value(linked_doctype, linked_name, "target_posko")
    elif linked_doctype == "RN Distribution Flow":
        posko = frappe.db.get_value(linked_doctype, linked_name, "destination_posko")
    elif linked_doctype == "RN Stock Observation":
        posko = frappe.db.get_value(linked_doctype, linked_name, "posko")
    elif linked_doctype == "RN Transport Space":
        posko = frappe.db.get_value(
            linked_doctype,
            linked_name,
            "coordination_posko",
        )

    if posko and not _can_contribute(actor, posko):
        frappe.throw(
            "Anda tidak dapat menambahkan evidence ke data ini",
            frappe.PermissionError,
        )

    doc = frappe.new_doc("RN Operational Evidence")
    doc.linked_doctype = linked_doctype
    doc.linked_name = linked_name
    doc.posko = posko
    doc.file_url = file_url
    doc.evidence_type = evidence_type
    doc.caption = caption
    doc.observed_at = observed_at or now_datetime()
    doc.uploaded_at = now_datetime()
    doc.uploader_user = actor.name
    doc.verification_status = "pending"
    doc.insert(ignore_permissions=True)

    return {
        "evidence":doc.name,
        "verification_status":doc.verification_status,
    }


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def public_dashboard(posko):
    if not public_posko_allowed(posko):
        frappe.throw(
            "Detail Posko tidak dibuka untuk publik",
            frappe.PermissionError,
        )

    posko_row = frappe.db.get_value(
        "RN Posko",
        posko,
        [
            "name","title","posko_type",
            "public_participation","accept_goods",
            "accept_volunteers","accept_donations",
            "accept_partners","public_service_access",
        ],
        as_dict=True,
    )

    latest_stock = frappe.get_all(
        "RN Stock Observation",
        filters={
            "posko":posko,
            "stock_state":"available",
        },
        fields=[
            "canonical_group","canonical_item",
            "quantity","unit","quantity_mode",
            "quantity_min","quantity_max",
            "observed_at","source_updated_at",
            "freshness_policy_minutes","modified",
        ],
        order_by="observed_at desc",
        limit_page_length=100,
    )

    for row in latest_stock:
        row["freshness"] = freshness(
            row.source_updated_at,
            row.observed_at,
            None,
            row.freshness_policy_minutes,
            "stock",
        )

    return {
        "posko":posko_row,
        "stock_observations":latest_stock,
    }


def _require_control_centre():
    actor = rn_actor()

    if not (
        is_system_manager()
        or actor.role in OPERATOR_ROLES
    ):
        frappe.throw(
            "Akses Control Centre diperlukan",
            frappe.PermissionError,
        )

    return actor


@frappe.whitelist()
def control_centre_logistics():
    _require_control_centre()

    # Latest AVAILABLE stock per distinct Posko + canonical group + unit.
    rows = frappe.get_all(
        "RN Stock Observation",
        filters={"stock_state":"available"},
        fields=[
            "name","posko","canonical_group",
            "canonical_item","quantity","unit",
            "quantity_mode","quantity_min","quantity_max",
            "observed_at","source_updated_at",
            "freshness_policy_minutes","modified",
        ],
        order_by="observed_at desc",
        limit_page_length=5000,
    )

    latest = {}
    for row in rows:
        group = row.canonical_group or row.canonical_item or "Belum Dikelompokkan"
        key = (row.posko, group, normalize_unit(row.unit))
        if key not in latest:
            latest[key] = row

    grouped = defaultdict(list)

    for row in latest.values():
        group = row.canonical_group or row.canonical_item or "Belum Dikelompokkan"
        grouped[(group, normalize_unit(row.unit))].append(row)

    stock_summary = []

    for (group, unit), members in grouped.items():
        known = []
        estimated = []
        fresh_count = 0
        stale_count = 0

        for row in members:
            fr = freshness(
                row.source_updated_at,
                row.observed_at,
                None,
                row.freshness_policy_minutes,
                "stock",
            )

            if fr["status"] == "fresh":
                fresh_count += 1
            elif fr["status"] == "stale":
                stale_count += 1

            if row.quantity_mode == "exact":
                known.append(flt(row.quantity))
            elif row.quantity_mode == "estimated":
                estimated.append(flt(row.quantity))
            elif row.quantity_mode == "range":
                if row.quantity_min or row.quantity_max:
                    estimated.append(
                        flt(row.quantity_max or row.quantity_min)
                    )

        stock_summary.append({
            "canonical_group":group,
            "unit":unit or None,
            "posko_count":len(members),
            "exact_total":sum(known) if known else None,
            "estimated_component":sum(estimated) if estimated else None,
            "fresh_count":fresh_count,
            "stale_count":stale_count,
            "rule":"SUM only across distinct Posko scopes with same canonical group and unit",
        })

    flows = frappe.get_all(
        "RN Distribution Flow",
        filters={
            "flow_status":[
                "in",
                [
                    "assigned_pickup",
                    "dispatched",
                    "in_transit",
                    "arrived_at_posko",
                    "partially_received",
                ],
            ]
        },
        fields=[
            "flow_status","canonical_group",
            "quantity","unit","quantity_mode",
            "received_quantity","received_unit",
        ],
        limit_page_length=5000,
    )

    return {
        "available_stock":stock_summary,
        "pipeline_count":len(flows),
        "pipeline":flows,
        "available_transport_count":frappe.db.count(
            "RN Transport Space",
            {"transport_status":"available"},
        ),
        "important_rule":(
            "Aid Offer, Distribution Flow, Received goods, and Stock Observation "
            "are separate states. Received flow never creates available stock automatically."
        ),
    }
