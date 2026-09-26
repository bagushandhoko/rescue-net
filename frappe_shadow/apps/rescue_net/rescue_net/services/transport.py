"""Armada capacity (phase 2: L-6, L-12).

One model: an armada's trip state (`transport_status`) is shared by every flow
riding it, and its kg / m3 space is shared by every booking. A booking holds
space from the moment it is requested; the check runs under a row lock on the
armada so two bookings cannot both take the last space.
"""

import frappe
from frappe.utils import flt

HOLD_STATES = {"requested", "confirmed"}
# an armada takes new bookings / flows only before it leaves
BOOKABLE = {"available", "reserved", "assigned"}
LIVE_FLOW_EXCLUDED = ["received", "cancelled", "rejected"]


def lock_space(space_name):
    row = frappe.db.sql(
        """SELECT name, transport_status, capacity_weight_kg, capacity_volume_m3,
                  own_load_kg, own_load_m3
           FROM `tabRN Transport Space` WHERE name=%s FOR UPDATE""",
        (space_name,), as_dict=True,
    )
    if not row:
        frappe.throw("Armada tidak ditemukan.")
    return row[0]


def assert_bookable(space):
    if (space.transport_status or "available") not in BOOKABLE:
        frappe.throw(f"Armada berstatus '{space.transport_status}' — tidak menerima muatan baru.")


def hold_capacity(booking):
    """Refuse a booking that does not fit the armada's free space.

    Every dimension the booking uses and the armada declares is checked; a
    booking that only uses a dimension the armada does not declare, or an
    armada with no declared capacity at all, is refused instead of letting
    the check silently pass."""
    space = lock_space(booking.transport_space)
    assert_bookable(space)

    w, v = flt(booking.qty_weight_kg), flt(booking.qty_volume_m3)
    if w <= 0 and v <= 0:
        frappe.throw("Isi berat (kg) atau volume (m3) muatan.")

    cap_kg, cap_m3 = flt(space.capacity_weight_kg), flt(space.capacity_volume_m3)
    if cap_kg <= 0 and cap_m3 <= 0:
        frappe.throw("Armada ini belum mencantumkan kapasitas — belum bisa dipesan.")
    checked = (w > 0 and cap_kg > 0) or (v > 0 and cap_m3 > 0)
    if not checked:
        frappe.throw("Isi muatan dalam " + ("kg" if cap_kg > 0 else "m3")
                     + " — satuan kapasitas armada ini.")

    others = frappe.get_all(
        "RN Transport Booking",
        filters={"transport_space": space.name, "status": ["in", list(HOLD_STATES)],
                 "name": ["!=", booking.name or ""]},
        fields=["qty_weight_kg", "qty_volume_m3"],
        limit_page_length=0,
    )
    free_kg = cap_kg - flt(space.own_load_kg) - sum(flt(b.qty_weight_kg) for b in others)
    free_m3 = cap_m3 - flt(space.own_load_m3) - sum(flt(b.qty_volume_m3) for b in others)
    if cap_kg > 0 and w > max(0.0, free_kg) + 0.001:
        frappe.throw(f"Kapasitas berat tidak cukup: sisa {max(0.0, free_kg):.0f} kg, diminta {w:.0f} kg.")
    if cap_m3 > 0 and v > max(0.0, free_m3) + 0.001:
        frappe.throw(f"Kapasitas volume tidak cukup: sisa {max(0.0, free_m3):.1f} m3, diminta {v:.1f} m3.")


def other_live_flows(space_name, flow_name):
    return frappe.get_all(
        "RN Distribution Flow",
        filters={"transport_space": space_name, "name": ["!=", flow_name],
                 "flow_status": ["not in", LIVE_FLOW_EXCLUDED]},
        pluck="name",
        limit_page_length=1,
    )


def armada_status_after_flow(space_name, flow_name, proposed):
    """The armada status a flow change should leave behind: a flow that ends
    (cancelled / received) frees the armada only when no other flow still
    rides it. Returns None when the armada status must not change."""
    if proposed in ("available", "completed") and other_live_flows(space_name, flow_name):
        return None
    return proposed
