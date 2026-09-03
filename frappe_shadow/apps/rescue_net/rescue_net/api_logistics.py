from collections import defaultdict

import frappe
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


@frappe.whitelist(allow_guest=True)
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



@frappe.whitelist()
def create_transport_space(
    coordination_posko,
    provider_name,
    transport_type=None,
    route_origin=None,
    route_destination=None,
    capacity_weight_kg=None,
    capacity_volume_m3=None,
    departure_time=None,
    eta=None,
    current_location=None,
    handover_location=None,
    handover_contact_person=None,
    handover_contact_phone=None,
    coordination_notes=None,
    disaster_event=None,
    departure_at=None,
    eta_at=None,
    service_mode=None,
    booking_policy=None,
):
    """Register an armada distribusi (kendaraan darat / kapal / pesawat) a
    posko puts on offer. Besides capacity + jadwal (berangkat / ETA) the
    posko records where the armada is now (`current_location`), where the
    barang will be handed over (`handover_location`), and who to call to
    coordinate the serah-terima (`handover_contact_person` /
    `handover_contact_phone`). Matches the DMS blueprint's Management
    Distribusi: "Link dengan pihak lain, kapasitas, pihak yang dihubungi".

    `service_mode` (space_only / courier_pickup / both) says whether the
    armada only lends space or also does the pickup+delivery (kurir).
    `departure_at` / `eta_at` are real Datetime so the slot can be booked,
    and confirmed bookings block capacity via `capacity_committed_*`.
    """
    # RN_CANONICAL_REF coordination_posko = resolve_posko(coordination_posko)
    coordination_posko = resolve_posko(coordination_posko)
    actor = rn_actor()

    if not _can_contribute(actor, coordination_posko):
        frappe.throw(
            "Anda tidak dapat menambahkan transport untuk Posko ini",
            frappe.PermissionError,
        )

    doc = frappe.new_doc("RN Transport Space")
    doc.title = provider_name
    doc.coordination_posko = coordination_posko
    doc.provider_name = provider_name
    doc.transport_type = transport_type
    doc.route_origin = route_origin
    doc.route_destination = route_destination

    if capacity_weight_kg not in (None, ""):
        doc.capacity_weight_kg = flt(capacity_weight_kg)

    if capacity_volume_m3 not in (None, ""):
        doc.capacity_volume_m3 = flt(capacity_volume_m3)

    doc.departure_time = departure_time
    doc.eta = eta
    if departure_at:
        doc.departure_at = departure_at
    if eta_at:
        doc.eta_at = eta_at
    if service_mode in ("space_only", "courier_pickup", "both"):
        doc.service_mode = service_mode
    if booking_policy in ("pin_verify", "open"):
        doc.booking_policy = booking_policy
    doc.current_location = current_location
    doc.handover_location = handover_location
    doc.handover_contact_person = handover_contact_person
    doc.handover_contact_phone = handover_contact_phone
    doc.coordination_notes = coordination_notes

    if disaster_event:
        try:
            doc.disaster_event = resolve_disaster_event(disaster_event)
        except Exception:
            doc.disaster_event_legacy_id = disaster_event

    doc.transport_status = "available"
    doc.insert(ignore_permissions=True)

    return {
        "transport": doc.name,
        "transport_status": doc.transport_status,
        "provider_name": doc.provider_name,
    }


@frappe.whitelist()
def update_transport_space(
    transport_space,
    transport_status=None,
    current_location=None,
    departure_time=None,
    eta=None,
    departure_at=None,
    eta_at=None,
    service_mode=None,
    booking_policy=None,
    handover_location=None,
    handover_contact_person=None,
    handover_contact_phone=None,
    coordination_notes=None,
):
    """Let the coordinating posko keep an armada record current as the trip
    progresses (status, keberadaan, jam berangkat/ETA, titik & narahubung
    serah-terima). Only fields that are passed are changed."""
    doc = frappe.get_doc("RN Transport Space", transport_space)
    actor = rn_actor()

    if not _can_contribute(actor, doc.coordination_posko):
        frappe.throw(
            "Anda tidak dapat memperbarui armada untuk Posko ini",
            frappe.PermissionError,
        )

    valid_status = {
        "available", "reserved", "assigned",
        "in_transit", "arrived", "completed", "cancelled",
    }
    if transport_status:
        if transport_status not in valid_status:
            frappe.throw("Status armada tidak valid")
        doc.transport_status = transport_status

    if service_mode and service_mode not in ("space_only", "courier_pickup", "both"):
        frappe.throw("Mode layanan tidak valid")
    if booking_policy and booking_policy not in ("pin_verify", "open"):
        frappe.throw("Kebijakan booking tidak valid")

    for field, value in (
        ("current_location", current_location),
        ("departure_time", departure_time),
        ("eta", eta),
        ("departure_at", departure_at),
        ("eta_at", eta_at),
        ("service_mode", service_mode),
        ("booking_policy", booking_policy),
        ("handover_location", handover_location),
        ("handover_contact_person", handover_contact_person),
        ("handover_contact_phone", handover_contact_phone),
        ("coordination_notes", coordination_notes),
    ):
        if value is not None:
            doc.set(field, value)

    doc.observed_at = now_datetime()
    doc.save(ignore_permissions=True)

    return {
        "transport": doc.name,
        "transport_status": doc.transport_status,
    }


# --- Transport booking / space blocking + relawan-pickup matching -----------

_BOOKING_HOLD_STATES = {"requested", "confirmed"}


def _transport_capacity(space):
    """Return capacity + committed (confirmed) + held (requested) + available
    for one RN Transport Space doc/dict."""
    cap_kg = flt(space.get("capacity_weight_kg"))
    cap_m3 = flt(space.get("capacity_volume_m3"))

    agg = frappe.get_all(
        "RN Transport Booking",
        filters={"transport_space": space.get("name"),
                 "status": ["in", list(_BOOKING_HOLD_STATES)]},
        fields=["status", "qty_weight_kg", "qty_volume_m3"],
        limit_page_length=500,
    )
    used_kg = sum(flt(b.qty_weight_kg) for b in agg if b.status == "confirmed")
    used_m3 = sum(flt(b.qty_volume_m3) for b in agg if b.status == "confirmed")
    held_kg = sum(flt(b.qty_weight_kg) for b in agg if b.status == "requested")
    held_m3 = sum(flt(b.qty_volume_m3) for b in agg if b.status == "requested")

    avail_kg = max(0.0, cap_kg - used_kg - held_kg)
    avail_m3 = max(0.0, cap_m3 - used_m3 - held_m3)
    pct = round(100.0 * used_kg / cap_kg, 1) if cap_kg else 0
    return {
        "cap_kg": cap_kg, "cap_m3": cap_m3,
        "used_kg": used_kg, "used_m3": used_m3,
        "held_kg": held_kg, "held_m3": held_m3,
        "avail_kg": avail_kg, "avail_m3": avail_m3,
        "pct": pct, "booking_count": len(agg),
    }


def _recompute_transport_committed(space_name):
    rows = frappe.get_all(
        "RN Transport Booking",
        filters={"transport_space": space_name, "status": "confirmed"},
        fields=["qty_weight_kg", "qty_volume_m3"], limit_page_length=500,
    )
    frappe.db.set_value("RN Transport Space", space_name, {
        "capacity_committed_kg": sum(flt(r.qty_weight_kg) for r in rows),
        "capacity_committed_m3": sum(flt(r.qty_volume_m3) for r in rows),
    }, update_modified=False)


@frappe.whitelist()
def book_transport_space(
    transport_space,
    cargo_desc=None,
    qty_weight_kg=None,
    qty_volume_m3=None,
    pickup_location=None,
    dropoff_location=None,
    contact_person=None,
    contact_phone=None,
    aid_offer=None,
    logistic_need=None,
    booked_by_type="posko",
    booked_by_id=None,
    notes=None,
    delivery_method="use_transporter",
    requested_window=None,
):
    """Reserve space on an armada. Any logged-in RN actor may request one.
    If the armada's `booking_policy` is `open` the booking is confirmed
    immediately (and blocks capacity); otherwise it is `requested` and a
    verification PIN is returned for the coordinator to confirm with (DMS
    blueprint: "notifikasi pin untuk verifikasi ketika akan pake").

    `delivery_method`: `use_transporter` (the armada's posko courier picks the
    cargo up) or `self_deliver` (the booker brings it to the pickup point).
    `use_transporter` is only valid on a courier-capable armada."""
    actor = rn_actor()
    space = frappe.get_doc("RN Transport Space", transport_space)

    if delivery_method not in ("use_transporter", "self_deliver"):
        delivery_method = "use_transporter"
    if delivery_method == "use_transporter" and (space.service_mode or "both") == "space_only":
        frappe.throw(
            "Armada ini hanya menyediakan space (bukan kurir). Pilih 'antar sendiri' "
            "atau pesan armada bermode kurir."
        )

    w = flt(qty_weight_kg) if qty_weight_kg not in (None, "") else 0.0
    v = flt(qty_volume_m3) if qty_volume_m3 not in (None, "") else 0.0
    if w <= 0 and v <= 0:
        frappe.throw("Isi berat (kg) atau volume (m3) muatan.")

    cap = _transport_capacity(space.as_dict())
    if space.capacity_weight_kg and w > cap["avail_kg"] + 0.001:
        frappe.throw(
            f"Kapasitas berat tidak cukup: sisa {cap['avail_kg']:.0f} kg, diminta {w:.0f} kg."
        )
    if space.capacity_volume_m3 and v > cap["avail_m3"] + 0.001:
        frappe.throw(
            f"Kapasitas volume tidak cukup: sisa {cap['avail_m3']:.1f} m3, diminta {v:.1f} m3."
        )

    policy = space.booking_policy or "pin_verify"
    pin = None
    if policy != "open":
        import random
        pin = "%04d" % random.randint(1000, 9999)

    doc = frappe.new_doc("RN Transport Booking")
    doc.transport_space = space.name
    doc.disaster_event = space.disaster_event
    doc.booked_by_type = booked_by_type if booked_by_type in (
        "posko", "organization", "individu", "relawan") else "posko"
    doc.booked_by_id = booked_by_id
    doc.booker_name = _actor_display_name(actor)
    doc.aid_offer = aid_offer or None
    doc.logistic_need = logistic_need or None
    doc.cargo_desc = cargo_desc
    doc.qty_weight_kg = w
    doc.qty_volume_m3 = v
    doc.pickup_location = pickup_location
    doc.dropoff_location = dropoff_location
    doc.contact_person = contact_person
    doc.contact_phone = contact_phone
    doc.delivery_method = delivery_method
    doc.requested_window = requested_window
    doc.notes = notes
    doc.verification_pin = pin
    doc.status = "confirmed" if policy == "open" else "requested"
    if doc.status == "confirmed":
        doc.confirmed_at = now_datetime()
    doc.created_by_user = actor.name if actor else None
    doc.insert(ignore_permissions=True)

    if doc.status == "confirmed":
        _recompute_transport_committed(space.name)

    return {
        "booking": doc.name,
        "status": doc.status,
        "verification_pin": pin,
        "policy": policy,
    }


def _actor_display_name(actor):
    if not actor:
        return "Tamu"
    fu = actor.get("frappe_user") if hasattr(actor, "get") else None
    if fu:
        full = frappe.db.get_value("User", fu, "full_name")
        if full:
            return full
        return fu
    return actor.get("name") or "Aktor"


def _can_manage_booking(actor, booking):
    space = frappe.get_value(
        "RN Transport Space", booking.transport_space, "coordination_posko"
    )
    return bool(space and _can_contribute(actor, space))


@frappe.whitelist()
def confirm_transport_booking(booking, pin=None):
    """Coordinator of the armada's posko confirms a `requested` booking. When
    the armada's policy is `pin_verify` the PIN must match."""
    actor = rn_actor()
    doc = frappe.get_doc("RN Transport Booking", booking)
    if not _can_manage_booking(actor, doc):
        frappe.throw("Hanya koordinator posko armada yang dapat mengonfirmasi.",
                     frappe.PermissionError)
    if doc.status != "requested":
        frappe.throw(f"Booking sudah berstatus '{doc.status}'.")

    space = frappe.get_doc("RN Transport Space", doc.transport_space)
    policy = space.booking_policy or "pin_verify"
    if policy == "pin_verify":
        if not pin or str(pin).strip().upper() != (doc.verification_pin or ""):
            frappe.throw("PIN verifikasi salah.")

    # capacity was reserved as "held" at request time; confirming just moves
    # the same qty from held -> used, so no extra capacity check is needed.
    doc.status = "confirmed"
    doc.confirmed_at = now_datetime()
    doc.save(ignore_permissions=True)
    _recompute_transport_committed(space.name)
    return {"booking": doc.name, "status": doc.status}


@frappe.whitelist()
def reject_transport_booking(booking, reason=None):
    actor = rn_actor()
    doc = frappe.get_doc("RN Transport Booking", booking)
    if not _can_manage_booking(actor, doc):
        frappe.throw("Hanya koordinator posko armada yang dapat menolak.",
                     frappe.PermissionError)
    if doc.status not in ("requested", "confirmed"):
        frappe.throw(f"Booking sudah berstatus '{doc.status}'.")
    was_confirmed = doc.status == "confirmed"
    doc.status = "rejected"
    doc.reject_reason = reason
    doc.save(ignore_permissions=True)
    if was_confirmed:
        _recompute_transport_committed(doc.transport_space)
    return {"booking": doc.name, "status": doc.status}


@frappe.whitelist()
def cancel_transport_booking(booking):
    """Booker (or the armada coordinator) cancels. Frees any blocked space."""
    actor = rn_actor()
    doc = frappe.get_doc("RN Transport Booking", booking)
    is_booker = actor and doc.created_by_user and actor.name == doc.created_by_user
    if not is_booker and not _can_manage_booking(actor, doc):
        frappe.throw("Anda tidak dapat membatalkan booking ini.",
                     frappe.PermissionError)
    if doc.status not in ("requested", "confirmed"):
        frappe.throw(f"Booking sudah berstatus '{doc.status}'.")
    was_confirmed = doc.status == "confirmed"
    doc.status = "cancelled"
    doc.save(ignore_permissions=True)
    if was_confirmed:
        _recompute_transport_committed(doc.transport_space)
    return {"booking": doc.name, "status": doc.status}


@frappe.whitelist()
def assign_pickup_volunteer(transport_space, volunteer_profile=None, volunteer_name=None):
    """Link a relawan (RN Volunteer Profile) as the pickup courier for an
    armada — the "kurir pick up" side of Manajemen Distribusi. Pass an empty
    `volunteer_profile` to clear the assignment."""
    actor = rn_actor()
    doc = frappe.get_doc("RN Transport Space", transport_space)
    if not _can_contribute(actor, doc.coordination_posko):
        frappe.throw("Hanya koordinator posko armada yang dapat menugaskan relawan.",
                     frappe.PermissionError)
    if volunteer_profile:
        vp = frappe.get_value("RN Volunteer Profile", volunteer_profile,
                              ["name", "volunteer_name"], as_dict=True)
        if not vp:
            frappe.throw("Relawan tidak ditemukan.")
        doc.pickup_volunteer = vp.name
        doc.pickup_volunteer_name = volunteer_name or vp.volunteer_name
    else:
        doc.pickup_volunteer = None
        doc.pickup_volunteer_name = None
    doc.save(ignore_permissions=True)
    return {"transport": doc.name, "pickup_volunteer": doc.pickup_volunteer}


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

    if doc.transport_space:
        transport_status = {
            "assigned_pickup":"assigned",
            "dispatched":"assigned",
            "in_transit":"in_transit",
            "arrived_at_posko":"arrived",
            "partially_received":"arrived",
            "received":"completed",
            "cancelled":"available",
        }.get(new_status)

        if transport_status:
            frappe.db.set_value(
                "RN Transport Space",
                doc.transport_space,
                {
                    "transport_status":transport_status,
                    "source_updated_at":now,
                },
                update_modified=False,
            )

    if doc.aid_offer:
        offer_status = {
            "assigned_pickup":"reserved",
            "dispatched":"in_transit",
            "in_transit":"in_transit",
            "arrived_at_posko":"in_transit",
            "partially_received":"in_transit",
            "received":"delivered",
            "cancelled":"available",
        }.get(new_status)

        if offer_status:
            frappe.db.set_value(
                "RN Aid Offer",
                doc.aid_offer,
                {
                    "offer_status":offer_status,
                    "source_updated_at":now,
                },
                update_modified=False,
            )

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
    "RN Transport Space",
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


# RN_USER_AID_OFFER_V1

def _resolve_user_aid_event(value):
    value = str(value or "").strip()

    if not value:
        return None

    if frappe.db.exists(
        "RN Disaster Event",
        value,
    ):
        return value

    for legacy_id in (
        value,
        "disaster_events:" + value,
    ):
        name = frappe.db.get_value(
            "RN Disaster Event",
            {"legacy_id": legacy_id},
            "name",
        )

        if name:
            return name

    return None


def _resolve_user_aid_posko(value):
    value = str(value or "").strip()

    if not value:
        return None

    if frappe.db.exists(
        "RN Posko",
        value,
    ):
        return value

    for legacy_id in (
        value,
        "posko_nodes:" + value,
    ):
        name = frappe.db.get_value(
            "RN Posko",
            {"legacy_id": legacy_id},
            "name",
        )

        if name:
            return name

    return None


def _require_user_aid_actor():
    actor = rn_actor()

    if not actor:
        frappe.throw(
            "Login diperlukan untuk "
            "Kirim Bantuan melalui akun.",
            frappe.PermissionError,
        )

    if getattr(actor, "name", None):
        return actor

    # System Manager dan privileged Frappe users
    # dapat mempunyai pseudo actor tanpa RN identity.
    # Untuk operasi ownership, resolve RN User Account
    # yang terhubung ke frappe.session.user tanpa
    # menurunkan role/privilege actor global.
    account = frappe.db.get_value(
        "RN User Account",
        {
            "frappe_user": frappe.session.user,
            "status": "active",
        },
        [
            "name",
            "organization",
            "posko",
        ],
        as_dict=True,
    )

    if account:
        actor = frappe._dict(dict(actor))
        actor.name = account.name

        if not getattr(
            actor,
            "organization",
            None,
        ):
            actor.organization = (
                account.organization
            )

        if not getattr(
            actor,
            "posko",
            None,
        ):
            actor.posko = account.posko

        return actor

    frappe.throw(
        "Akun Rescue-Net aktif diperlukan "
        "untuk operasi bantuan berbasis ownership.",
        frappe.PermissionError,
    )


def _user_aid_posko_allowed(
    actor,
    posko,
):
    if not posko:
        return True

    if _can_contribute(
        actor,
        posko,
    ):
        return True

    return bool(
        public_posko_allowed(posko)
        and cint(
            frappe.db.get_value(
                "RN Posko",
                posko,
                "public_participation",
            ) or 0
        )
        and cint(
            frappe.db.get_value(
                "RN Posko",
                posko,
                "accept_goods",
            ) or 0
        )
    )


@frappe.whitelist()
def create_user_aid_offer(
    disaster_event,
    donor_name,
    item_text,
    quantity=None,
    unit=None,
    quantity_mode="exact",
    handling_mode="need_pickup",
    target_posko=None,
    pickup_location=None,
    ready_at=None,
    donor_contact=None,
    notes=None,
    batch_no=None,
    expiry_date=None,
):
    actor = _require_user_aid_actor()

    handling_mode = str(
        handling_mode or ""
    ).strip().lower()

    if handling_mode not in {
        "active_booking",
        "need_pickup",
    }:
        frappe.throw(
            "Cara penanganan bantuan "
            "tidak valid."
        )

    item_text = str(
        item_text or ""
    ).strip()

    donor_name = str(
        donor_name or ""
    ).strip()

    if not item_text:
        frappe.throw(
            "Barang bantuan wajib diisi."
        )

    if not donor_name:
        frappe.throw(
            "Nama donatur/sumber "
            "wajib diisi."
        )

    event = _resolve_user_aid_event(
        disaster_event
    )

    if not event:
        frappe.throw(
            "Disaster Event tidak ditemukan: "
            + str(disaster_event)
        )

    posko = _resolve_user_aid_posko(
        target_posko
    )

    if (
        handling_mode == "active_booking"
        and not posko
    ):
        frappe.throw(
            "Aktif Booking memerlukan "
            "Posko tujuan."
        )

    if (
        target_posko
        and not posko
    ):
        frappe.throw(
            "Posko tidak ditemukan: "
            + str(target_posko)
        )

    if (
        posko
        and not _user_aid_posko_allowed(
            actor,
            posko,
        )
    ):
        frappe.throw(
            "Posko ini tidak membuka "
            "penerimaan bantuan "
            "untuk akun Anda.",
            frappe.PermissionError,
        )

    if posko:
        posko_event = frappe.db.get_value(
            "RN Posko",
            posko,
            "disaster_event",
        )

        if (
            posko_event
            and posko_event != event
        ):
            frappe.throw(
                "Posko tujuan tidak berada "
                "pada Disaster Event yang sama."
            )

    if quantity not in (
        None,
        "",
    ):
        qty = flt(quantity)

        if qty <= 0:
            frappe.throw(
                "Jumlah bantuan harus "
                "lebih dari 0."
            )
    else:
        qty = None

    doc = frappe.new_doc(
        "RN Aid Offer"
    )

    doc.title = (
        f"{item_text} - {donor_name}"
    )

    doc.disaster_event = event
    doc.target_posko = posko

    # Identitas authoritative berasal
    # dari session Frappe.
    doc.donor_user = actor.name

    doc.donor_name = donor_name
    doc.donor_contact = donor_contact

    doc.item_name = item_text
    doc.raw_item_text = item_text

    if qty is not None:
        doc.quantity = qty

    doc.unit = unit
    doc.quantity_mode = (
        quantity_mode or "exact"
    )

    doc.pickup_location = (
        pickup_location
    )

    doc.ready_at = ready_at
    doc.notes = notes
    doc.batch_no = batch_no
    doc.expiry_date = expiry_date

    doc.handling_mode = (
        handling_mode
    )

    if (
        handling_mode
        == "need_pickup"
    ):
        doc.offer_status = (
            "need_pickup"
        )
    else:
        doc.offer_status = (
            "available"
        )

    now = now_datetime()

    if not doc.observed_at:
        doc.observed_at = now

    if not doc.source_updated_at:
        doc.source_updated_at = now

    if not doc.verification_status:
        doc.verification_status = (
            "self_reported"
        )

    doc.insert(
        ignore_permissions=True
    )

    return {
        "aid_offer": doc.name,
        "donor_user": doc.donor_user,
        "handling_mode":
            doc.handling_mode,
        "offer_status":
            doc.offer_status,
        "target_posko":
            doc.target_posko,
        "distribution_link":
            "RN Distribution Flow.aid_offer",
    }


@frappe.whitelist()
def update_user_aid_offer(
    aid_offer,
    item_text=None,
    quantity=None,
    unit=None,
    handling_mode=None,
    target_posko=None,
    pickup_location=None,
    ready_at=None,
    notes=None,
    batch_no=None,
    expiry_date=None,
):
    actor = _require_user_aid_actor()

    if not aid_offer:
        frappe.throw(
            "Aid Offer wajib diisi"
        )

    if not frappe.db.exists(
        "RN Aid Offer",
        aid_offer,
    ):
        frappe.throw(
            "Aid Offer tidak ditemukan"
        )

    doc = frappe.get_doc(
        "RN Aid Offer",
        aid_offer,
    )

    if doc.donor_user != actor.name:
        frappe.throw(
            "Anda tidak berwenang mengubah bantuan ini",
            frappe.PermissionError,
        )

    if handling_mode is not None:
        handling_mode = str(
            handling_mode or ""
        ).strip()

        if handling_mode not in {
            "active_booking",
            "need_pickup",
        }:
            frappe.throw(
                "Handling mode tidak valid"
            )

        doc.handling_mode = handling_mode

    if target_posko is not None:
        target_posko = str(
            target_posko or ""
        ).strip()

        if target_posko:
            resolved_posko = (
                _resolve_user_aid_posko(
                    target_posko
                )
            )

            if not resolved_posko:
                frappe.throw(
                    "Posko tujuan tidak ditemukan"
                )

            posko_event = frappe.db.get_value(
                "RN Posko",
                resolved_posko,
                "disaster_event",
            )

            if (
                doc.disaster_event
                and posko_event
                and posko_event
                != doc.disaster_event
            ):
                frappe.throw(
                    "Posko tujuan berbeda disaster event"
                )

            doc.target_posko = (
                resolved_posko
            )
        else:
            doc.target_posko = None

    if item_text is not None:
        item_text = str(
            item_text or ""
        ).strip()

        if item_text:
            doc.item_name = item_text
            doc.raw_item_text = item_text

    if quantity is not None:
        value = str(quantity).strip()

        if value:
            try:
                qty = float(value)
            except Exception:
                frappe.throw(
                    "Quantity tidak valid"
                )

            if qty < 0:
                frappe.throw(
                    "Quantity tidak boleh negatif"
                )

            doc.quantity = qty
            doc.quantity_mode = "exact"

    if unit is not None:
        value = str(unit or "").strip()
        if value:
            doc.unit = value

    if pickup_location is not None:
        doc.pickup_location = (
            str(
                pickup_location or ""
            ).strip()
            or None
        )

    if ready_at is not None:
        doc.ready_at = (
            str(
                ready_at or ""
            ).strip()
            or None
        )

    if notes is not None:
        doc.notes = (
            str(
                notes or ""
            ).strip()
            or None
        )

    if batch_no is not None:
        doc.batch_no = (
            str(
                batch_no or ""
            ).strip()
            or None
        )

    if expiry_date is not None:
        doc.expiry_date = (
            str(
                expiry_date or ""
            ).strip()
            or None
        )

    doc.source_updated_at = now_datetime()

    doc.save(
        ignore_permissions=True
    )

    return {
        "aid_offer": doc.name,
        "donor_user": doc.donor_user,
        "disaster_event":
            doc.disaster_event,
        "target_posko":
            doc.target_posko,
        "item_name":
            doc.item_name,
        "quantity":
            doc.quantity,
        "unit":
            doc.unit,
        "handling_mode":
            doc.handling_mode,
        "pickup_location":
            doc.pickup_location,
        "ready_at":
            doc.ready_at,
        "offer_status":
            doc.offer_status,
        "updated_at":
            doc.source_updated_at,
    }

@frappe.whitelist()
def my_aid_offers(
    limit=100,
):
    actor = _require_user_aid_actor()

    limit = max(
        1,
        min(
            cint(limit or 100),
            500,
        ),
    )

    offers = frappe.get_all(
        "RN Aid Offer",
        filters={
            "donor_user":
                actor.name,
        },
        fields=[
            "name",
            "title",
            "disaster_event",
            "target_posko",
            "donor_name",
            "item_name",
            "quantity",
            "unit",
            "quantity_mode",
            "pickup_location",
            "ready_at",
            "handling_mode",
            "offer_status",
            "verification_status",
            "creation",
            "modified",
        ],
        order_by="creation desc",
        limit_page_length=limit,
    )

    names = [
        x.name
        for x in offers
    ]

    by_offer = defaultdict(list)

    if names:
        flows = frappe.get_all(
            "RN Distribution Flow",
            filters={
                "aid_offer": [
                    "in",
                    names,
                ],
            },
            fields=[
                "name",
                "aid_offer",
                "destination_posko",
                "flow_status",
                "eta_final",
            ],
            order_by="creation desc",
            limit_page_length=1000,
        )

        for flow in flows:
            by_offer[
                flow.aid_offer
            ].append(flow)

    result = []

    for offer in offers:
        row = dict(offer)
        row["distribution_flows"] = (
            by_offer.get(
                offer.name,
                [],
            )
        )
        result.append(row)

    return {
        "user": actor.name,
        "offers": result,
    }

@frappe.whitelist()
def receive_flow_and_update_stock(
    flow,
    received_quantity,
    received_unit=None,
    receipt_note=None,
):
    """
    Mark a Distribution Flow as received and create
    the resulting destination Stock Observation in
    the same database transaction.

    Stock Observation is the canonical Rescue-Net
    stock model; legacy Stock Movement is not
    recreated.
    """
    actor = rn_actor()

    qty = flt(received_quantity)

    if qty <= 0:
        frappe.throw(
            "Jumlah diterima harus lebih dari 0"
        )

    # Lock the flow so two receipt requests cannot
    # process the same flow concurrently.
    locked_flow = frappe.db.sql(
        """
        SELECT name
        FROM `tabRN Distribution Flow`
        WHERE name=%s
        FOR UPDATE
        """,
        (flow,),
        as_dict=True,
    )

    if not locked_flow:
        frappe.throw(
            "Distribution Flow tidak ditemukan"
        )

    doc = frappe.get_doc(
        "RN Distribution Flow",
        flow,
    )

    destination = doc.destination_posko

    if not destination:
        frappe.throw(
            "Distribution Flow tidak memiliki "
            "destination Posko"
        )

    if not _can_operate(
        actor,
        destination,
    ):
        frappe.throw(
            "Anda tidak dapat menerima flow ini",
            frappe.PermissionError,
        )

    current_status = (
        doc.flow_status or "planned"
    )

    if "received" not in TRANSITIONS.get(
        current_status,
        set(),
    ):
        frappe.throw(
            "Flow harus berada pada status "
            "arrived_at_posko atau "
            "partially_received sebelum "
            "dapat diterima. "
            f"Status saat ini: {current_status}"
        )

    unit = (
        received_unit
        or doc.unit
        or ""
    ).strip()

    if not unit:
        frappe.throw(
            "Unit penerimaan wajib tersedia"
        )

    item_name = (
        doc.item_name
        or doc.raw_item_text
        or ""
    ).strip()

    if not item_name:
        frappe.throw(
            "Item Distribution Flow tidak tersedia"
        )

    # Coarse lock on destination Posko serializes
    # stock updates even when no previous observation
    # exists yet.
    frappe.db.sql(
        """
        SELECT name
        FROM `tabRN Posko`
        WHERE name=%s
        FOR UPDATE
        """,
        (destination,),
    )

    latest = frappe.db.sql(
        """
        SELECT
            name,
            quantity,
            unit,
            quantity_mode
        FROM `tabRN Stock Observation`
        WHERE
            posko=%s
            AND item_name=%s
        ORDER BY
            observed_at DESC,
            creation DESC
        LIMIT 1
        FOR UPDATE
        """,
        (
            destination,
            item_name,
        ),
        as_dict=True,
    )

    previous_quantity = 0.0

    if latest:
        prev = latest[0]

        previous_unit = (
            prev.unit or ""
        ).strip()

        if (
            previous_unit
            and previous_unit != unit
        ):
            frappe.throw(
                "Unit stok terakhir berbeda: "
                f"{previous_unit} != {unit}. "
                "Normalisasi unit diperlukan "
                "sebelum penerimaan."
            )

        previous_mode = (
            prev.quantity_mode or "unknown"
        )

        if (
            previous_mode != "exact"
            and prev.quantity not in (
                None,
                "",
            )
        ):
            frappe.throw(
                "Stok terakhir bukan quantity "
                "exact. Verifikasi stok terlebih "
                "dahulu sebelum menerima flow."
            )

        previous_quantity = flt(
            prev.quantity or 0
        )

    # Preserve the existing lifecycle and all its
    # side effects for Transport Space / Aid Offer.
    flow_result = update_flow_status(
        flow=flow,
        new_status="received",
        received_quantity=qty,
        received_unit=unit,
        receipt_note=(
            receipt_note
            or "Diterima melalui Posko Detail"
        ),
    )

    now = now_datetime()

    stock = frappe.new_doc(
        "RN Stock Observation"
    )

    stock.title = (
        f"{item_name} - receipt"
    )

    stock.disaster_event = (
        doc.disaster_event
    )

    stock.posko = destination
    stock.item_name = item_name
    stock.raw_item_text = item_name

    stock.quantity = (
        previous_quantity + qty
    )

    stock.quantity_mode = "exact"
    stock.unit = unit
    stock.stock_state = "available"

    stock.notes = (
        "Verified receipt from "
        f"Distribution Flow {flow}. "
        f"Received {qty} {unit}. "
        f"Previous stock {previous_quantity} {unit}."
    )

    stock.observed_at = now
    stock.source_updated_at = now

    stock.insert(
        ignore_permissions=True
    )

    return {
        "flow": flow_result,
        "stock_observation": stock.name,
        "previous_quantity":
            previous_quantity,
        "received_quantity": qty,
        "current_quantity":
            stock.quantity,
        "unit": unit,
        "destination_posko":
            destination,
    }
