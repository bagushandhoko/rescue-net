"""Logistics — transport spaces (armada), bookings, pickup volunteers and claims."""

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
    _can_contribute,
)


@frappe.whitelist()
def create_transport_space(
    coordination_posko,
    provider_name,
    transport_type=None,
    route_origin=None,
    route_destination=None,
    capacity_weight_kg=None,
    capacity_volume_m3=None,
    own_load_kg=None,
    own_load_m3=None,
    own_cargo_desc=None,
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

    if own_load_kg not in (None, ""):
        doc.own_load_kg = flt(own_load_kg)
    if own_load_m3 not in (None, ""):
        doc.own_load_m3 = flt(own_load_m3)
    if own_cargo_desc is not None:
        doc.own_cargo_desc = own_cargo_desc

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
    own_load_kg=None,
    own_load_m3=None,
    own_cargo_desc=None,
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
        ("own_load_kg", flt(own_load_kg) if own_load_kg not in (None, "") else None),
        ("own_load_m3", flt(own_load_m3) if own_load_m3 not in (None, "") else None),
        ("own_cargo_desc", own_cargo_desc),
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

    # the fit against the armada's free space is checked by the booking
    # controller under a lock on the armada (services/transport.py)
    w = flt(qty_weight_kg) if qty_weight_kg not in (None, "") else 0.0
    v = flt(qty_volume_m3) if qty_volume_m3 not in (None, "") else 0.0

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


def _posko_is_active_pickup(posko):
    """A Posko Distribusi is 'aktif pickup' if it has at least one armada
    whose service_mode is courier_pickup or both; otherwise it is 'pasif —
    hanya menyediakan space'."""
    modes = frappe.get_all(
        "RN Transport Space",
        filters={"coordination_posko": posko},
        pluck="service_mode",
    )
    return any((m or "both") in ("courier_pickup", "both") for m in modes)


@frappe.whitelist()
def claim_aid_pickup(transporter_posko, aid_offer, destination_posko,
                     eta=None, note=None):
    """An *active* Posko Distribusi (motor pick-up, Land Rover club, …) claims
    an open aid offer for pickup and commits to delivering it to a chosen
    posko. Creates an RN Distribution Flow (status `pickup_claimed`) linking
    the offer → destination, so the offer shows "Akan Dijemput oleh <posko>"
    on Manajemen Distribusi / Posko Logistik instead of sitting unmatched."""
    actor = rn_actor()
    transporter_posko = resolve_posko(transporter_posko)
    destination_posko = resolve_posko(destination_posko)

    if not _can_contribute(actor, transporter_posko):
        frappe.throw(
            "Anda bukan petugas / anggota posko distribusi ini.",
            frappe.PermissionError,
        )
    if not _posko_is_active_pickup(transporter_posko):
        frappe.throw(
            "Posko ini pasif (hanya menyediakan space). Daftarkan armada "
            "bermode kurir dulu untuk bisa menjemput bantuan."
        )

    offer = frappe.get_doc("RN Aid Offer", aid_offer)
    if str(offer.offer_status or "").lower() in (
        "pickup_claimed", "assigned_pickup", "in_transit", "delivered",
        "received", "received_verified", "stock_transferred", "cancelled",
    ):
        frappe.throw(f"Bantuan ini sudah berstatus '{offer.offer_status}'.")

    existing = frappe.get_all(
        "RN Distribution Flow",
        filters={"aid_offer": aid_offer,
                 "flow_status": ["not in", ["cancelled", "rejected"]]},
        limit_page_length=1,
    )
    if existing:
        frappe.throw("Bantuan ini sudah punya alur distribusi.")

    # L-19: aid goes where the donor sent it; an untargeted offer takes the
    # destination chosen here as its target
    if not destination_posko or not frappe.db.exists("RN Posko", destination_posko):
        frappe.throw("Posko tujuan tidak ditemukan.")
    if offer.target_posko and offer.target_posko != destination_posko:
        frappe.throw("Bantuan ini ditujukan ke posko lain — tujuan penjemputan harus posko itu.")
    offer.target_posko = destination_posko

    posko_title = frappe.db.get_value("RN Posko", transporter_posko, "title") or transporter_posko

    # the offer is claimed (and targeted) before its flow exists — once the
    # flow runs, the donor side of the offer is fixed (L-11)
    offer.offer_status = "pickup_claimed"
    offer.notes = ((offer.notes + " | ") if offer.notes else "") + \
        "Akan dijemput oleh " + posko_title + " → " + \
        (frappe.db.get_value("RN Posko", destination_posko, "title") or destination_posko)
    offer.save(ignore_permissions=True)

    flow = frappe.new_doc("RN Distribution Flow")
    flow.title = ((offer.item_name or offer.raw_item_text or "Bantuan")
                  + " — dijemput " + posko_title)
    flow.disaster_event = offer.disaster_event
    flow.aid_offer = aid_offer
    flow.destination_posko = destination_posko
    flow.item_name = offer.item_name or offer.raw_item_text
    if offer.quantity is not None:
        flow.quantity = offer.quantity
    flow.unit = offer.unit
    flow.quantity_mode = offer.quantity_mode or "unknown"
    flow.transport_provider = posko_title
    flow.transport_type = "darat"
    flow.flow_status = "pickup_claimed"
    if eta:
        flow.eta_final = eta
    flow.notes = ("Dijemput oleh " + posko_title
                  + (" — " + note if note else ""))
    for f in ("observed_at", "source_updated_at"):
        if hasattr(flow, f) and not flow.get(f):
            flow.set(f, now_datetime())
    flow.insert(ignore_permissions=True)

    return {
        "flow": flow.name,
        "aid_offer": aid_offer,
        "offer_status": offer.offer_status,
        "transporter": posko_title,
        "destination_posko": destination_posko,
    }


@frappe.whitelist()
def claim_distribution_flow(flow, transport_space=None, eta=None, note=None):
    """A Posko Distribusi operator claims an outgoing RN Distribution Flow
    that has no transporter yet (a collector posko dispatched stock and left
    "lewat" empty) and commits one of their armada to carry it. Mirrors
    claim_aid_pickup but for a flow. Any transport posko may claim — that's
    how "posko distribusi temennya" books it."""
    actor = rn_actor()
    doc = frappe.get_doc("RN Distribution Flow", flow)

    if doc.transport_space:
        frappe.throw("Alur ini sudah punya armada.")
    if "assigned_pickup" not in TRANSITIONS.get(doc.flow_status or "planned", set()):
        frappe.throw(f"Alur ini sudah berstatus '{doc.flow_status}'.")

    coord_posko = None
    if transport_space:
        from rescue_net.services.transport import assert_bookable, lock_space
        assert_bookable(lock_space(transport_space))
        space = frappe.get_doc("RN Transport Space", transport_space)
        coord_posko = space.coordination_posko
        if not _can_contribute(actor, coord_posko):
            frappe.throw(
                "Anda bukan petugas / anggota posko distribusi armada ini.",
                frappe.PermissionError,
            )
        doc.transport_space = space.name
        doc.transport_provider = space.provider_name or coord_posko
        doc.transport_type = space.transport_type or doc.transport_type
    else:
        frappe.throw("Pilih armada untuk mengangkut alur ini.")

    doc.flow_status = "assigned_pickup"
    if eta:
        doc.eta_final = eta
    if hasattr(doc, "assigned_pickup_at"):
        doc.assigned_pickup_at = now_datetime()
    doc.save(ignore_permissions=True)

    return {
        "flow": doc.name,
        "flow_status": doc.flow_status,
        "transport_space": doc.transport_space,
        "transport_provider": doc.transport_provider,
    }
