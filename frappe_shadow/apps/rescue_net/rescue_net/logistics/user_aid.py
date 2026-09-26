"""Logistics — aid offers by logged-in users (single / multi item, edits)."""

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
    _can_contribute,
)


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
def create_user_aid_offer_multi(
    disaster_event,
    donor_name,
    items_json,
    handling_mode="need_pickup",
    target_posko=None,
    pickup_location=None,
    ready_at=None,
    donor_contact=None,
    notes=None,
    expected_arrival_at=None,
):
    """One "Kirim Bantuan" submission carrying several barang. Creates one
    RN Aid Offer per item (the whole app models an aid offer as one
    item/qty/unit), sharing the donor + delivery details. `items_json` is a
    list of {item_text, quantity, unit, quantity_mode?, ready_at?}. Each item
    may have its own `ready_at` (barang bisa siap di waktu berbeda); rows
    without one fall back to the shared `ready_at`."""
    import json

    try:
        items = json.loads(items_json) if isinstance(items_json, str) else items_json
    except Exception:
        frappe.throw("Format daftar barang tidak valid.")

    if not isinstance(items, list) or not items:
        frappe.throw("Tambahkan minimal satu barang bantuan.")
    if len(items) > 30:
        frappe.throw("Maksimal 30 baris barang per pengiriman.")

    shared_notes = notes
    if expected_arrival_at:
        shared_notes = ((notes + " | ") if notes else "") + "Perkiraan sampai posko: " + str(expected_arrival_at)

    created = []
    first = None
    for row in items:
        row = row or {}
        it = str(row.get("item_text") or "").strip()
        if not it:
            continue
        res = create_user_aid_offer(
            disaster_event=disaster_event,
            donor_name=donor_name,
            item_text=it,
            quantity=row.get("quantity"),
            unit=row.get("unit"),
            quantity_mode=row.get("quantity_mode") or "exact",
            handling_mode=handling_mode,
            target_posko=target_posko,
            pickup_location=pickup_location,
            ready_at=(str(row.get("ready_at")).strip() if row.get("ready_at") else None) or ready_at,
            donor_contact=donor_contact,
            notes=shared_notes,
        )
        first = first or res
        created.append({
            "aid_offer": res["aid_offer"],
            "item": it,
            "quantity": row.get("quantity"),
            "unit": row.get("unit"),
            "ready_at": (str(row.get("ready_at")).strip() if row.get("ready_at") else None) or ready_at,
            "offer_status": res["offer_status"],
        })

    if not created:
        frappe.throw("Tidak ada barang valid untuk disimpan.")

    return {
        "aid_offers": created,
        "count": len(created),
        "donor_name": donor_name,
        "handling_mode": first["handling_mode"],
        "target_posko": first["target_posko"],
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
