"""Logistics — guest aid offers and public transport bookings with edit codes."""

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
    _GUEST_AID_FIELDS,
    _GUEST_BOOKING_STATUS_LABEL,
)
from rescue_net.logistics.transport import (  # noqa: F401
    _recompute_transport_committed,
)
from rescue_net.logistics.user_aid import (  # noqa: F401
    _resolve_user_aid_event,
    _resolve_user_aid_posko,
)


import hashlib as _hashlib


def _guest_code_hash(code):
    return _hashlib.sha256(
        ("rn-guest-aid:" + str(code or "").strip().upper()).encode("utf-8")
    ).hexdigest()


def _norm_contact(v):
    return "".join(ch for ch in str(v or "") if ch.isdigit())


def _load_guest_offer(aid_offer, edit_code, donor_contact=None):
    doc = frappe.get_doc("RN Aid Offer", aid_offer)
    if (doc.get("submitted_channel") or "account") != "guest" or not doc.get("edit_code_hash"):
        frappe.throw("Bantuan ini tidak dikelola lewat Kode Edit.", frappe.PermissionError)
    if _guest_code_hash(edit_code) != doc.edit_code_hash:
        frappe.throw("Aid ID atau Kode Edit salah.", frappe.PermissionError)
    if donor_contact and _norm_contact(donor_contact) and _norm_contact(donor_contact) != _norm_contact(doc.donor_contact):
        frappe.throw("Nomor HP tidak cocok dengan data bantuan ini.", frappe.PermissionError)
    return doc


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=20, seconds=3600)
def submit_guest_aid_offer_multi(
    disaster_event,
    donor_name,
    donor_contact,
    items_json,
    handling_mode="need_pickup",
    target_posko=None,
    pickup_location=None,
    pickup_latitude=None,
    pickup_longitude=None,
    ready_at=None,
    notes=None,
):
    """One guest "Kirim Bantuan" carrying several barang, no account needed.
    Returns the Aid IDs plus ONE Edit Code (shown once) covering all rows."""
    import json as _json

    lat = flt(pickup_latitude) if pickup_latitude not in (None, "") else None
    lng = flt(pickup_longitude) if pickup_longitude not in (None, "") else None

    donor_name = str(donor_name or "").strip()
    donor_contact = str(donor_contact or "").strip()
    if not donor_name:
        frappe.throw("Nama donatur wajib diisi.")
    if len(_norm_contact(donor_contact)) < 7:
        frappe.throw("Nomor HP/WhatsApp wajib diisi (untuk edit bantuan nanti).")

    try:
        items = _json.loads(items_json) if isinstance(items_json, str) else items_json
    except Exception:
        frappe.throw("Format daftar barang tidak valid.")
    if not isinstance(items, list) or not items:
        frappe.throw("Tambahkan minimal satu barang bantuan.")
    if len(items) > 30:
        frappe.throw("Maksimal 30 baris barang per pengiriman.")

    event = _resolve_user_aid_event(disaster_event)
    if not event:
        frappe.throw("Disaster Event tidak ditemukan: " + str(disaster_event))

    posko = _resolve_user_aid_posko(target_posko) if target_posko else None
    if target_posko and not posko:
        frappe.throw("Posko tidak ditemukan: " + str(target_posko))
    if posko:
        allowed = (
            public_posko_allowed(posko)
            and cint(frappe.db.get_value("RN Posko", posko, "public_participation") or 0)
            and cint(frappe.db.get_value("RN Posko", posko, "accept_goods") or 0)
        )
        if not allowed:
            frappe.throw("Posko ini tidak membuka penerimaan bantuan publik.", frappe.PermissionError)

    handling_mode = "need_pickup" if handling_mode not in ("need_pickup", "self_deliver") else handling_mode
    code = frappe.utils.random_string(8).upper().replace("O", "A").replace("0", "9").replace("I", "K").replace("L", "M")
    code_hash = _guest_code_hash(code)
    batch = "guest-" + frappe.generate_hash(length=10)

    created = []
    for row in items:
        row = row or {}
        it = str(row.get("item_text") or "").strip()
        if not it:
            continue
        qraw = row.get("quantity")
        qty = flt(qraw) if qraw not in (None, "") else None
        if qty is not None and qty <= 0:
            frappe.throw('Jumlah untuk "%s" harus lebih dari 0.' % it)

        doc = frappe.new_doc("RN Aid Offer")
        doc.title = f"{it} - {donor_name}"
        doc.disaster_event = event
        doc.target_posko = posko
        doc.donor_user = None
        doc.donor_name = donor_name
        doc.donor_contact = donor_contact
        doc.item_name = it
        doc.raw_item_text = it
        if qty is not None:
            doc.quantity = qty
        doc.unit = row.get("unit")
        doc.quantity_mode = row.get("quantity_mode") or "exact"
        doc.pickup_location = pickup_location
        doc.pickup_latitude = lat
        doc.pickup_longitude = lng
        doc.ready_at = (str(row.get("ready_at")).strip() if row.get("ready_at") else None) or ready_at
        doc.notes = notes
        doc.handling_mode = "need_pickup"
        doc.offer_status = "need_pickup" if handling_mode == "need_pickup" else "available"
        doc.submitted_channel = "guest"
        doc.guest_batch = batch
        doc.edit_code_hash = code_hash
        doc.verification_status = "self_reported"
        now = now_datetime()
        doc.observed_at = now
        doc.source_updated_at = now
        doc.insert(ignore_permissions=True)
        created.append({
            "aid_offer": doc.name, "item": it,
            "quantity": doc.quantity, "unit": doc.unit,
            "canonical_group": doc.get("canonical_group"),
        })

    if not created:
        frappe.throw("Tidak ada barang valid untuk disimpan.")

    return {
        "aid_offers": created,
        "count": len(created),
        "guest_batch": batch,
        "edit_code": code,          # shown once, never stored in the clear
        "donor_name": donor_name,
        "handling_mode": handling_mode,
        "target_posko": posko,
        "notice": "Simpan Aid ID + Kode Edit ini. Kode hanya ditampilkan sekali.",
    }


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=15, seconds=3600)
def get_guest_aid_offer(aid_offer, edit_code, donor_contact=None):
    """Fetch one guest offer (+ its batch siblings) for the edit form."""
    doc = _load_guest_offer(aid_offer, edit_code, donor_contact)
    out = {k: doc.get(k) for k in _GUEST_AID_FIELDS}
    siblings = []
    if doc.get("guest_batch"):
        for r in frappe.get_all(
            "RN Aid Offer",
            filters={"guest_batch": doc.guest_batch},
            fields=["name", "item_name", "quantity", "unit", "offer_status", "canonical_group"],
            order_by="creation asc", limit_page_length=50,
        ):
            siblings.append(r)
    out["batch_items"] = siblings
    return out


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=20, seconds=3600)
def edit_guest_aid_offer(
    aid_offer,
    edit_code,
    donor_contact=None,
    item_text=None,
    quantity=None,
    unit=None,
    pickup_location=None,
    ready_at=None,
    notes=None,
    cancel=None,
):
    """Edit / cancel one guest aid offer using Aid ID + Edit Code (+ HP)."""
    doc = _load_guest_offer(aid_offer, edit_code, donor_contact)

    if str(cancel).lower() in ("1", "true", "yes"):
        doc.offer_status = "cancelled"
        doc.source_updated_at = now_datetime()
        doc.save(ignore_permissions=True)
        return {"aid_offer": doc.name, "offer_status": doc.offer_status}

    if item_text is not None and str(item_text).strip():
        doc.item_name = str(item_text).strip()
        doc.raw_item_text = doc.item_name
    if quantity not in (None, ""):
        q = flt(quantity)
        if q <= 0:
            frappe.throw("Jumlah bantuan harus lebih dari 0.")
        doc.quantity = q
    if unit is not None:
        doc.unit = unit
    if pickup_location is not None:
        doc.pickup_location = pickup_location
    if ready_at is not None:
        doc.ready_at = ready_at
    if notes is not None:
        doc.notes = notes

    doc.source_updated_at = now_datetime()
    doc.save(ignore_permissions=True)
    return {
        "aid_offer": doc.name,
        "item_name": doc.item_name,
        "quantity": doc.quantity,
        "unit": doc.unit,
        "offer_status": doc.offer_status,
        "canonical_group": doc.get("canonical_group"),
    }


def _guest_booking_code_hash(code):
    return _hashlib.sha256(
        ("rn-guest-transport-booking:" + str(code or "").strip().upper()).encode("utf-8")
    ).hexdigest()


def _new_guest_code():
    return (frappe.utils.random_string(8).upper()
            .replace("O", "A").replace("0", "9").replace("I", "K").replace("L", "M"))


def _load_guest_booking(booking, edit_code, contact_phone=None):
    doc = frappe.get_doc("RN Transport Booking", booking)
    if (doc.get("submitted_channel") or "account") != "guest" or not doc.get("edit_code_hash"):
        frappe.throw("Booking ini tidak dikelola lewat Kode Edit.", frappe.PermissionError)
    if _guest_booking_code_hash(edit_code) != doc.edit_code_hash:
        frappe.throw("Booking ID atau Kode Edit salah.", frappe.PermissionError)
    if contact_phone and _norm_contact(contact_phone) \
       and _norm_contact(contact_phone) != _norm_contact(doc.contact_phone):
        frappe.throw("Nomor HP tidak cocok dengan booking ini.", frappe.PermissionError)
    return doc


def _guest_booking_view(doc):
    sp = frappe.db.get_value(
        "RN Transport Space", doc.transport_space,
        ["provider_name", "transport_type", "booking_policy", "coordination_posko"],
        as_dict=True,
    ) or {}
    return {
        "booking": doc.name,
        "status": doc.status,
        "status_label": _GUEST_BOOKING_STATUS_LABEL.get(doc.status, doc.status),
        "armada": sp.get("provider_name") or doc.transport_space,
        "armada_type": sp.get("transport_type") or "",
        "cargo_desc": doc.cargo_desc or "",
        "qty_weight_kg": flt(doc.qty_weight_kg),
        "qty_volume_m3": flt(doc.qty_volume_m3),
        "delivery_method": doc.delivery_method or "self_deliver",
        "pickup_location": doc.pickup_location or "",
        "dropoff_location": doc.dropoff_location or "",
        "requested_window": doc.requested_window or "",
        "verification_pin": doc.verification_pin or "",
        "contact_person": doc.contact_person or "",
        "contact_phone": doc.contact_phone or "",
    }


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=20, seconds=3600)
def book_transport_space_public(
    transport_space,
    contact_person,
    contact_phone,
    cargo_desc=None,
    qty_weight_kg=None,
    qty_volume_m3=None,
    pickup_location=None,
    dropoff_location=None,
    requested_window=None,
    delivery_method="self_deliver",
):
    """Warga tanpa akun memesan ruang muat / titip barang ke posko transport
    yang membuka partisipasi publik. Mengembalikan Kode Edit (sekali tampil)
    untuk lacak / ubah / batalkan booking — pola sama dengan guest aid."""
    name = str(contact_person or "").strip()
    phone = str(contact_phone or "").strip()
    if not name:
        frappe.throw("Nama pemesan wajib diisi.")
    if len(_norm_contact(phone)) < 7:
        frappe.throw("Nomor HP/WhatsApp wajib diisi (untuk lacak / ubah booking nanti).")

    space = frappe.get_doc("RN Transport Space", transport_space)
    posko = space.coordination_posko
    allowed = bool(
        posko
        and cint(frappe.db.get_value("RN Posko", posko, "public_participation") or 0)
        and public_posko_allowed(posko)
    )
    if not allowed:
        frappe.throw(
            "Posko transport ini tidak membuka pemesanan ruang muat untuk publik.",
            frappe.PermissionError,
        )

    if delivery_method not in ("use_transporter", "self_deliver"):
        delivery_method = "self_deliver"
    if delivery_method == "use_transporter" and (space.service_mode or "both") == "space_only":
        frappe.throw(
            "Armada ini hanya menyediakan ruang muat (bukan kurir). Pilih 'antar sendiri'."
        )

    # fit + armada status: booking controller (services/transport.py)
    w = flt(qty_weight_kg) if qty_weight_kg not in (None, "") else 0.0
    v = flt(qty_volume_m3) if qty_volume_m3 not in (None, "") else 0.0

    policy = space.booking_policy or "pin_verify"
    pin = None
    if policy != "open":
        import random
        pin = "%04d" % random.randint(1000, 9999)

    code = _new_guest_code()

    doc = frappe.new_doc("RN Transport Booking")
    doc.transport_space = space.name
    doc.disaster_event = space.disaster_event
    doc.booked_by_type = "individu"
    doc.booker_name = name + " (tamu)"
    doc.cargo_desc = cargo_desc
    doc.qty_weight_kg = w
    doc.qty_volume_m3 = v
    doc.pickup_location = pickup_location
    doc.dropoff_location = dropoff_location
    doc.contact_person = name
    doc.contact_phone = phone
    doc.delivery_method = delivery_method
    doc.requested_window = requested_window
    doc.verification_pin = pin
    doc.submitted_channel = "guest"
    doc.edit_code_hash = _guest_booking_code_hash(code)
    doc.status = "confirmed" if policy == "open" else "requested"
    if doc.status == "confirmed":
        doc.confirmed_at = now_datetime()
    doc.insert(ignore_permissions=True)

    if doc.status == "confirmed":
        _recompute_transport_committed(space.name)

    return {
        "booking": doc.name,
        "status": doc.status,
        "status_label": _GUEST_BOOKING_STATUS_LABEL.get(doc.status, doc.status),
        "verification_pin": pin,
        "edit_code": code,          # shown once, never stored in the clear
        "policy": policy,
        "notice": "Simpan Booking ID + Kode Edit ini. Kode hanya ditampilkan sekali.",
    }


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=15, seconds=3600)
def get_public_transport_booking(booking, edit_code, contact_phone=None):
    """Lacak status booking tamu dengan Booking ID + Kode Edit (+ HP opsional)."""
    return _guest_booking_view(_load_guest_booking(booking, edit_code, contact_phone))


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=20, seconds=3600)
def update_public_transport_booking(
    booking,
    edit_code,
    contact_phone=None,
    cargo_desc=None,
    qty_weight_kg=None,
    qty_volume_m3=None,
    pickup_location=None,
    dropoff_location=None,
    requested_window=None,
    cancel=None,
):
    """Ubah / batalkan booking tamu selama masih 'requested' / 'confirmed'."""
    doc = _load_guest_booking(booking, edit_code, contact_phone)
    if doc.status not in ("requested", "confirmed"):
        frappe.throw("Booking berstatus '%s' tidak bisa diubah." % doc.status)

    if str(cancel).lower() in ("1", "true", "yes"):
        doc.status = "cancelled"
        doc.reject_reason = "Dibatalkan oleh pemesan (tamu)"
        doc.save(ignore_permissions=True)
        _recompute_transport_committed(doc.transport_space)
        return {"booking": doc.name, "status": "cancelled", "status_label": "Dibatalkan"}

    # a changed quantity is re-checked by the booking controller
    new_w = flt(qty_weight_kg) if qty_weight_kg not in (None, "") else flt(doc.qty_weight_kg)
    new_v = flt(qty_volume_m3) if qty_volume_m3 not in (None, "") else flt(doc.qty_volume_m3)

    for field, val in (
        ("cargo_desc", cargo_desc),
        ("pickup_location", pickup_location),
        ("dropoff_location", dropoff_location),
        ("requested_window", requested_window),
    ):
        if val is not None:
            doc.set(field, val)
    if qty_weight_kg not in (None, ""):
        doc.qty_weight_kg = new_w
    if qty_volume_m3 not in (None, ""):
        doc.qty_volume_m3 = new_v
    doc.save(ignore_permissions=True)
    if doc.status == "confirmed":
        _recompute_transport_committed(doc.transport_space)
    return _guest_booking_view(doc)
