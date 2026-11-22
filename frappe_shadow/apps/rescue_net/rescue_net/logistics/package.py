"""Paket multi-barang (owner 2026-10-26): one shipment carrying several items.

The first item is the package's main flow ("kiriman utama"): it holds the
booking, the armada, the resi and the one label. Every other item is its own
RN Distribution Flow (stock is checked and received per item) with
`package_flow` = the main flow, and follows the main flow's armada and status
until it arrives; each item is then received on its own."""

import json

import frappe
from frappe.utils import flt

# what members copy from the main flow while the package travels together
_FOLLOW_FIELDS = ("flow_status", "transport_space", "transport_provider", "first_mile_space",
                  "assigned_pickup_at", "dispatched_at", "in_transit_at", "arrived_at", "cancelled_at")
# a member decides these itself (each item is received with its own quantity)
_OWN_STATES = {"partially_received", "received", "cancelled"}
_LEAD_STOPS = {"partially_received", "received"}   # the lead's receipt is not the members'


def package_members(lead):
    if not lead or not frappe.db.has_column("RN Distribution Flow", "package_flow"):
        return []
    return frappe.get_all("RN Distribution Flow", filters={"package_flow": lead},
                          fields=["name", "flow_status"], order_by="creation asc", limit_page_length=100)


def sync_package(lead):
    """Copy the main flow's armada / status / timestamps onto its members that
    are still travelling with it."""
    members = package_members(lead)
    if not members:
        return
    src = frappe.db.get_value("RN Distribution Flow", lead, list(_FOLLOW_FIELDS), as_dict=True) or {}
    values = {k: src.get(k) for k in _FOLLOW_FIELDS}
    if (values.get("flow_status") or "") in _LEAD_STOPS:
        values["flow_status"] = "arrived_at_posko"      # members wait to be received one by one
    for m in members:
        if (m.flow_status or "") in _OWN_STATES:
            continue
        frappe.db.set_value("RN Distribution Flow", m.name, values, update_modified=True)


def assert_member_change(doc, new_status):
    """Members move with the package; on their own they are only received or
    cancelled."""
    if doc.get("package_flow") and new_status not in _OWN_STATES:
        frappe.throw("Barang ini bagian dari paket: statusnya mengikuti kiriman utama paket.")


def package_items(flow):
    """[{flow, item, quantity, unit, status}] of the package `flow` belongs to
    (main first), or [] for a single-item shipment."""
    if not frappe.db.has_column("RN Distribution Flow", "package_flow"):
        return [], None
    lead = frappe.db.get_value("RN Distribution Flow", flow, "package_flow") or flow
    members = package_members(lead)
    if not members:
        return [], None
    names = [lead] + [m.name for m in members]
    rows = {r.name: r for r in frappe.get_all(
        "RN Distribution Flow", filters={"name": ["in", names]},
        fields=["name", "item_name", "quantity", "unit", "flow_status"], limit_page_length=101)}
    return [{"flow": n, "item": rows[n].item_name, "quantity": flt(rows[n].quantity),
             "unit": rows[n].unit, "status": rows[n].flow_status} for n in names if n in rows], lead


def _parse_items(items):
    if isinstance(items, str):
        try:
            items = json.loads(items)
        except ValueError:
            frappe.throw("Daftar barang paket tidak valid.")
    out = []
    for it in items or []:
        text = str((it or {}).get("item_text") or "").strip()
        if not text:
            continue
        qty = flt((it or {}).get("quantity"))
        if qty <= 0:
            frappe.throw("Isi jumlah untuk %s." % text)
        out.append({"item_text": text, "quantity": qty, "unit": str((it or {}).get("unit") or "").strip()})
    if not out:
        frappe.throw("Isi minimal satu barang.")
    if len(out) > 30:
        frappe.throw("Satu paket maksimal 30 barang.")
    seen = set()
    for it in out:
        key = (it["item_text"].lower(), it["unit"].lower())
        if key in seen:
            frappe.throw("Barang %s tercantum dua kali — gabungkan jumlahnya." % it["item_text"])
        seen.add(key)
    return out


@frappe.whitelist()
def create_package(destination_posko, items, source_posko=None, disaster_event=None, transport_space=None,
                   window_from=None, window_to=None, weight_kg=None, volume_m3=None, first_mile=None,
                   first_mile_space=None, terms_ack=None, eta_final=None):
    """Kirim paket: several items from one posko to one destination on one
    armada. Each item is checked against stock (create_flow); the first one
    carries the booking for the whole weight. One request = one transaction,
    so a refused item leaves nothing half-created."""
    from rescue_net.logistics.flows import _assert_in_stock, create_flow
    from rescue_net.reference_resolver import resolve_posko

    rows = _parse_items(items)
    # every item is checked before anything is created
    src = resolve_posko(source_posko)
    if src:
        for r in rows:
            _assert_in_stock(src, r["item_text"], r["quantity"], r["unit"])
    common = dict(destination_posko=destination_posko, source_posko=source_posko,
                  disaster_event=disaster_event, quantity_mode="exact", eta_final=eta_final)
    lead_row = rows[0]
    lead = create_flow(item_text=lead_row["item_text"], quantity=lead_row["quantity"], unit=lead_row["unit"],
                       transport_space=transport_space, window_from=window_from, window_to=window_to,
                       weight_kg=weight_kg, volume_m3=volume_m3, first_mile=first_mile,
                       first_mile_space=first_mile_space, terms_ack=terms_ack, **common)
    flows = [lead["flow"]]
    for r in rows[1:]:
        m = create_flow(item_text=r["item_text"], quantity=r["quantity"], unit=r["unit"], **common)
        frappe.db.set_value("RN Distribution Flow", m["flow"], "package_flow", lead["flow"])
        flows.append(m["flow"])
    sync_package(lead["flow"])

    # the booking(s) describe the whole package, not only its first item
    if len(rows) > 1:
        desc = "Paket: " + ", ".join(("%s %g %s" % (r["item_text"], r["quantity"], r["unit"])).strip() for r in rows)
        for bk in (lead.get("booking"), lead.get("first_mile_booking")):
            if bk:
                frappe.db.set_value("RN Transport Booking", bk, "cargo_desc", desc[:140])

    return dict(lead, package=lead["flow"], flows=flows, items=len(rows))
