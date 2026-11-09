"""Estafet (relay) antar-posko distribusi — owner 2026-11-09:
"mutasi pergerakan … baik yang langsung ke posko logistik atau yang berpindah antar posko distribusi (estafet)".

Satu kiriman (RN Distribution Flow) bisa punya beberapa kaki:
  first_mile  kurir ke titik serah armada utama (sudah ada)
  main        armada utama (sudah ada; mengisi flow.transport_space)
  relay       kaki lanjutan berurutan (leg_seq 1, 2, …) — mis. kapal TNI → truk Rotary → motor pelajar.

Kaki relay adalah RN Transport Booking biasa (kapasitas, PIN/kebijakan booking, konfirmasi oleh posko armada) yang
diberi distribution_flow + booking_leg="relay" + leg_seq. Kaki relay tidak mengganti armada utama kiriman.

Posko "pembawa" (pemilik armada pada kaki mana pun yang terkonfirmasi) boleh mencatat serah-terima / perjalanan
(api_custody.record_scan) dan memesan kaki berikutnya — tetapi tidak mencatat penerimaan akhir.
"""

import frappe
from frappe.utils import cint

from rescue_net.access_policy import rn_actor
from rescue_net.logistics.common import _can_operate

LEG_LABEL = {"first_mile": "Jemput ke titik serah", "main": "Armada utama", "relay": "Estafet"}
_LIVE = ("requested", "confirmed", "completed")


def _flow_bookings(flow):
    if not frappe.db.has_column("RN Transport Booking", "distribution_flow"):
        return []
    fields = ["name", "transport_space", "booking_leg", "status", "pickup_location", "dropoff_location",
              "qty_weight_kg", "qty_volume_m3", "requested_window", "window_from", "creation"]
    if frappe.db.has_column("RN Transport Booking", "leg_seq"):
        fields.append("leg_seq")
    return frappe.get_all("RN Transport Booking", filters={"distribution_flow": flow, "status": ["in", list(_LIVE)]},
                          fields=fields, order_by="creation asc", limit_page_length=50)


def carrier_poskos(flow):
    """Posko pemilik armada yang (terkonfirmasi) membawa kiriman ini pada kaki mana pun."""
    f = frappe.db.get_value("RN Distribution Flow", flow, ["transport_space", "first_mile_space"], as_dict=True) or {}
    spaces = {s for s in (f.get("transport_space"), f.get("first_mile_space")) if s}
    spaces |= {b.transport_space for b in _flow_bookings(flow) if b.status in ("confirmed", "completed") and b.transport_space}
    if not spaces:
        return set()
    return set(frappe.get_all("RN Transport Space", filters={"name": ["in", list(spaces)]},
                              pluck="coordination_posko", limit_page_length=0)) - {None, ""}


def is_carrier(actor, flow):
    return any(_can_operate(actor, p) for p in carrier_poskos(flow))


def flow_legs(flow):
    """Urutan kaki kiriman, aman untuk publik (tanpa kontak / PIN): jemput → utama → estafet 1..n."""
    f = frappe.db.get_value("RN Distribution Flow", flow, ["transport_space", "first_mile_space"], as_dict=True) or {}
    rows = _flow_bookings(flow)
    by_space = {}
    for b in rows:
        by_space.setdefault((b.transport_space, b.booking_leg or "main"), b)
    legs = []
    # legacy / directly assigned armada without a booking row still count as a leg
    if f.get("first_mile_space") and (f["first_mile_space"], "first_mile") not in by_space:
        rows.append(frappe._dict(transport_space=f["first_mile_space"], booking_leg="first_mile", status="confirmed"))
    if f.get("transport_space") and not any(b.transport_space == f["transport_space"] and (b.booking_leg or "main") == "main"
                                             for b in rows):
        rows.append(frappe._dict(transport_space=f["transport_space"], booking_leg="main", status="confirmed"))
    spaces = {b.transport_space for b in rows if b.transport_space}
    sp = {s.name: s for s in frappe.get_all("RN Transport Space", filters={"name": ["in", list(spaces) or ["-"]]},
          fields=["name", "provider_name", "transport_type", "coordination_posko", "route_origin", "route_destination",
                  "departure_at", "eta_at", "transport_status", "handover_location"], limit_page_length=0)}
    pk = {p.name: p.title for p in frappe.get_all("RN Posko", filters={"name": ["in", [s.coordination_posko for s in sp.values()
          if s.coordination_posko] or ["-"]]}, fields=["name", "title"], limit_page_length=0)}
    order = {"first_mile": 0, "main": 1, "relay": 2}
    rows.sort(key=lambda b: (order.get(b.booking_leg or "main", 1), cint(b.get("leg_seq")), str(b.get("creation") or "")))
    for i, b in enumerate(rows, 1):
        s = sp.get(b.transport_space)
        if not s:
            continue
        leg = b.booking_leg or "main"
        legs.append({
            "no": i, "leg": leg,
            "leg_label": LEG_LABEL.get(leg, leg) + (" %d" % cint(b.get("leg_seq")) if leg == "relay" and b.get("leg_seq") else ""),
            "armada": s.provider_name or "-", "transport_type": s.transport_type or "",
            "posko": pk.get(s.coordination_posko) or "-",
            "from": b.get("pickup_location") or s.route_origin or "-",
            "to": b.get("dropoff_location") or s.route_destination or "-",
            "berangkat": str(s.departure_at or "")[:16], "tiba": str(s.eta_at or "")[:16],
            "booking_status": b.status, "armada_status": s.transport_status or "",
        })
    return legs


@frappe.whitelist(methods=["POST"])
def book_relay_leg(flow, transport_space, pickup_location=None, dropoff_location=None, qty_weight_kg=None,
                   qty_volume_m3=None, requested_window=None, notes=None, terms_ack=None, contact_person=None,
                   contact_phone=None):
    """Pesan kaki estafet berikutnya untuk kiriman `flow` pada armada `transport_space`.
    Boleh: pengelola posko asal / tujuan, atau posko pembawa kaki sebelumnya (estafet)."""
    from rescue_net.logistics.transport import book_transport_space

    actor = rn_actor()
    f = frappe.db.get_value("RN Distribution Flow", flow, ["name", "source_posko", "destination_posko", "flow_status",
                            "transport_space", "first_mile_space"], as_dict=True)
    if not f:
        frappe.throw("Kiriman tidak ditemukan.", frappe.DoesNotExistError)
    if f.flow_status in ("received", "cancelled", "rejected"):
        frappe.throw("Kiriman sudah %s — tidak bisa ditambah kaki estafet." % f.flow_status)
    mine = [p for p in (f.source_posko, f.destination_posko) if p and _can_operate(actor, p)]
    carriers = [p for p in carrier_poskos(flow) if _can_operate(actor, p)]
    if not (mine or carriers):
        frappe.throw("Hanya posko asal/tujuan atau posko pembawa kiriman ini yang dapat memesan kaki estafet.",
                     frappe.PermissionError)
    if transport_space in {f.transport_space, f.first_mile_space}:
        frappe.throw("Armada ini sudah menjadi kaki kiriman ini.")
    seq = 1 + max([cint(b.get("leg_seq")) for b in _flow_bookings(flow) if (b.booking_leg or "") == "relay"] or [0])
    if not qty_weight_kg:
        qty_weight_kg = frappe.db.get_value("RN Transport Booking", {"distribution_flow": flow, "booking_leg": ["!=", "relay"]},
                                            "qty_weight_kg") or None
    booker = (carriers or mine)[0]
    r = book_transport_space(transport_space=transport_space, booked_by_type="posko", booked_by_id=booker,
                             cargo_desc=_cargo_desc(flow), qty_weight_kg=qty_weight_kg, qty_volume_m3=qty_volume_m3,
                             pickup_location=pickup_location, dropoff_location=dropoff_location,
                             contact_person=contact_person, contact_phone=contact_phone, notes=notes,
                             delivery_method="self_deliver", requested_window=requested_window, terms_ack=terms_ack)
    frappe.db.set_value("RN Transport Booking", r["booking"], {"distribution_flow": flow, "booking_leg": "relay",
                                                               "leg_seq": seq})
    r.update({"leg_seq": seq, "flow": flow})
    return r


def _cargo_desc(flow):
    f = frappe.db.get_value("RN Distribution Flow", flow, ["item_name", "raw_item_text", "quantity", "unit"], as_dict=True) or {}
    from rescue_net.control_centre.distribusi import _distribusi_trace
    return "Estafet %s: %s %s %s" % (_distribusi_trace(flow), f.get("item_name") or f.get("raw_item_text") or "-",
                                    f.get("quantity") or "", f.get("unit") or "")
