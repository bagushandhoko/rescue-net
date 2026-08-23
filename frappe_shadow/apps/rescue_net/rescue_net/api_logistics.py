from collections import defaultdict

import frappe
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

    if actor.name:
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


@frappe.whitelist()
def dashboard(posko=None):
    actor = rn_actor()
    allowed = _accessible_poskos(actor)

    if posko:
        if posko not in allowed:
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

    flows = frappe.get_all(
        "RN Distribution Flow",
        filters=[
            ["RN Distribution Flow","destination_posko","in",allowed],
        ],
        fields=[
            "name","title","source_posko","destination_posko",
            "item_name","quantity","unit","quantity_mode",
            "canonical_group","flow_status","eta_final",
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
        (flows, "stock"),
    ]:
        for row in collection:
            row["freshness"] = freshness(
                row.get("source_updated_at"),
                row.get("observed_at"),
                row.get("modified"),
                row.get("freshness_policy_minutes"),
                kind,
            )

    return {
        "poskos":poskos,
        "needs":needs,
        "stocks":stocks,
        "offers":offers,
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
):
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
    eta_final=None,
):
    actor = rn_actor()

    if not _can_operate(actor, destination_posko):
        if not source_posko or not _can_operate(actor, source_posko):
            frappe.throw(
                "Anda tidak dapat membuat flow untuk Posko ini",
                frappe.PermissionError,
            )

    doc = frappe.new_doc("RN Distribution Flow")
    doc.title = item_text
    doc.destination_posko = destination_posko
    doc.source_posko = source_posko
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
    doc.eta_final = eta_final
    doc.flow_status = "planned"
    doc.insert(ignore_permissions=True)

    return {
        "flow":doc.name,
        "flow_status":doc.flow_status,
        "canonical_group":doc.canonical_group,
    }


TRANSITIONS = {
    "planned":{"assigned_pickup","cancelled"},
    "assigned_pickup":{"dispatched","in_transit","cancelled"},
    "dispatched":{"in_transit","arrived_at_posko","cancelled"},
    "in_transit":{"arrived_at_posko","cancelled"},
    "arrived_at_posko":{"partially_received","received","cancelled"},
    "partially_received":{"partially_received","received"},
    "received":set(),
    "cancelled":set(),
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

    return {
        "flow":doc.name,
        "previous_status":current,
        "flow_status":doc.flow_status,
        "received_quantity":doc.received_quantity,
        "received_unit":doc.received_unit,
        "stock_created":False,
        "note":"Penerimaan tidak otomatis menjadi stok; stok harus diperbarui melalui Stock Observation.",
    }


ALLOWED_EVIDENCE_DOCTYPES = {
    "RN Logistic Need",
    "RN Aid Offer",
    "RN Distribution Flow",
    "RN Stock Observation",
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
            row.modified,
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
        key = (row.posko, group, row.unit or "")
        if key not in latest:
            latest[key] = row

    grouped = defaultdict(list)

    for row in latest.values():
        group = row.canonical_group or row.canonical_item or "Belum Dikelompokkan"
        grouped[(group, row.unit or "")].append(row)

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
                row.modified,
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
        "important_rule":(
            "Aid Offer, Distribution Flow, Received goods, and Stock Observation "
            "are separate states. Received flow never creates available stock automatically."
        ),
    }
