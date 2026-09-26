"""Logistics — my aid offers, receiving flows / offers into stock."""

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
    _AID_OFFER_UNRECEIVABLE_STATUSES,
    _can_operate,
)
from rescue_net.logistics.flows import (  # noqa: F401
    update_flow_status,
)
from rescue_net.logistics.user_aid import (  # noqa: F401
    _require_user_aid_actor,
)


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

    from rescue_net.services.stock import receive_into_stock

    stock, previous_quantity, used = receive_into_stock(
        destination, item_name, unit, qty, doc.disaster_event,
        lambda prev, used: (
            f"Verified receipt from Distribution Flow {flow}. "
            f"Received {qty} {unit}. Previous stock {prev} {unit}"
            + (f" (after {used} {unit} kitchen usage)." if used else ".")
        ),
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


@frappe.whitelist()
def receive_aid_offer_and_update_stock(
    aid_offer,
    received_quantity=None,
    received_unit=None,
    receipt_note=None,
):
    """
    Mark a direct-to-posko RN Aid Offer ("Kiriman Masyarakat" — a
    community/donor shipment that never went through the Distribution
    Flow matching engine) as received, and fold it into the destination
    posko's RN Stock Observation, mirroring
    receive_flow_and_update_stock's stock-merge logic.
    """
    actor = rn_actor()

    locked_offer = frappe.db.sql(
        """
        SELECT name
        FROM `tabRN Aid Offer`
        WHERE name=%s
        FOR UPDATE
        """,
        (aid_offer,),
        as_dict=True,
    )
    if not locked_offer:
        frappe.throw("Aid Offer tidak ditemukan")

    doc = frappe.get_doc("RN Aid Offer", aid_offer)

    destination = doc.target_posko
    if not destination:
        frappe.throw(
            "Aid Offer ini tidak menuju satu Posko spesifik "
            "(bukan kiriman langsung)"
        )

    if not _can_operate(actor, destination):
        frappe.throw(
            "Anda tidak dapat menerima kiriman ini",
            frappe.PermissionError,
        )

    current_status = str(doc.offer_status or "").lower()
    if current_status in _AID_OFFER_UNRECEIVABLE_STATUSES:
        frappe.throw(
            f"Kiriman ini sudah berstatus '{doc.offer_status}'."
        )

    qty = flt(received_quantity) if received_quantity not in (None, "") else flt(doc.quantity)
    if qty <= 0:
        frappe.throw("Jumlah diterima harus lebih dari 0")

    unit = (received_unit or doc.unit or "").strip()
    if not unit:
        frappe.throw("Unit penerimaan wajib tersedia")

    item_name = (doc.item_name or "").strip()
    if not item_name:
        frappe.throw("Item Aid Offer tidak tersedia")

    # L-3: an offer carried by a Distribution Flow is counted into stock by
    # the flow receipt — receiving it here too would add the goods twice.
    if current_status == "delivered" or frappe.db.exists("RN Distribution Flow", {
        "aid_offer": doc.name, "flow_status": ["!=", "cancelled"],
    }):
        frappe.throw(
            "Kiriman ini dikirim lewat Distribution Flow — terima melalui flow tersebut."
        )

    from rescue_net.services.stock import receive_into_stock

    stock, previous_quantity, used = receive_into_stock(
        destination, item_name, unit, qty, doc.disaster_event,
        lambda prev, used: (
            f"Diterima dari kiriman masyarakat {doc.donor_name or 'donatur'} "
            f"({aid_offer}). Diterima {qty} {unit}. Stok sebelumnya {prev} {unit}"
            + (f" (setelah pemakaian dapur {used} {unit})." if used else ".")
            + (f" Catatan: {receipt_note}" if receipt_note else "")
        ),
        what="menerima kiriman ini",
    )

    doc.offer_status = "received"
    doc.save(ignore_permissions=True)

    return {
        "aid_offer": doc.name,
        "offer_status": doc.offer_status,
        "stock_observation": stock.name,
        "previous_quantity": previous_quantity,
        "received_quantity": qty,
        "current_quantity": stock.quantity,
        "unit": unit,
        "destination_posko": destination,
    }
