"""Control Centre — distribution board, flow trace (QR), posko distribusi board, auto-matching."""

import frappe
from frappe.rate_limiter import rate_limit

from rescue_net.api_ai import (
    public_context,
    public_active_disasters,
)

from rescue_net.control_centre.common import (  # noqa: F401
    _ARMADA_STATUS_LABEL,
    _BOOKING_STATUS_LABEL,
    _DELIVERY_LABEL,
    _DISTRIBUSI_STATUS_LABEL,
    _DRILL_BLOCKED_FLOW,
    _DRILL_DELIVERED_OFFER,
    _FLOW_STATUS_TO_STEP,
    _FLOW_TRACE_STEPS,
    _LOGISTIK_CONVERSIONS,
    _SERVICE_MODE_LABEL,
    _num,
    _posko_actor_flags,
    _poskos_viewer_context,
    _resolve_posko,
    _sf,
    canonical_event,
    cols,
    event_filters,
)
from rescue_net.control_centre.critical import (  # noqa: F401
    _event_posko_names,
)


def _distribusi_posko_titles(names):
    names = {n for n in names if n}
    if not names:
        return {}
    return {
        r.name: r.title
        for r in frappe.get_all(
            "RN Posko", filters={"name": ["in", list(names)]},
            fields=["name", "title"], limit_page_length=len(names),
        )
    }


def _distribusi_trace(name):
    return "RN-" + str(name or "")[-8:].upper()


def _resolve_flow_by_trace(code):
    """`RN-XXXXXXXX` (or the bare 8 chars) -> RN Distribution Flow name."""
    code = str(code or "").strip().upper()
    if code.startswith("RN-"):
        code = code[3:]
    code = code.strip()
    if not code:
        return None
    for r in frappe.get_all(
        "RN Distribution Flow", fields=["name"],
        order_by="modified desc", limit_page_length=5000,
    ):
        if str(r.name)[-8:].upper() == code:
            return r.name
    return None


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def flow_trace(flow=None, trace=None):
    """Public shipment tracking for ONE RN Distribution Flow, keyed by record
    name (`flow`) or by its `RN-XXXXXXXX` trace code (`trace`). Guest-safe
    subset only — item, quantity, the two posko titles, transport label,
    status and the lifecycle timeline. No user names, no cost, no legacy
    payload. Backs pages/lacak-logistik.html (opened from a printed QR)."""
    name = str(flow or "").strip()
    if not name and trace:
        name = _resolve_flow_by_trace(trace) or ""

    if not name or not frappe.db.exists("RN Distribution Flow", name):
        frappe.throw("Kiriman tidak ditemukan.", frappe.DoesNotExistError)

    f = frappe.db.get_value(
        "RN Distribution Flow", name,
        _sf("RN Distribution Flow", [
            "name", "item_name", "raw_item_text", "canonical_item",
            "quantity", "unit", "quantity_mode", "quantity_min", "quantity_max",
            "estimate_text", "flow_status", "source_posko", "destination_posko",
            "eta_final", "transport_provider", "transport_type",
            "received_quantity", "received_unit", "receipt_note",
            "creation", "assigned_pickup_at", "dispatched_at", "in_transit_at",
            "arrived_at", "received_at", "cancelled_at", "modified",
        ]),
        as_dict=True,
    ) or {}

    titles = _distribusi_posko_titles([f.get("source_posko"), f.get("destination_posko")])
    status = f.get("flow_status") or "planned"
    cancelled = status == "cancelled"

    step_index = {key: i for i, (key, _, _) in enumerate(_FLOW_TRACE_STEPS)}
    reached_key = _FLOW_STATUS_TO_STEP.get(status, "planned")
    reached = step_index.get(reached_key, 0)

    steps = []
    for i, (key, label, field) in enumerate(_FLOW_TRACE_STEPS):
        at = f.get(field)
        done = (not cancelled) and i <= reached
        steps.append({
            "key": key,
            "label": label,
            "at": str(at) if at else None,
            "done": done,
            "current": (not cancelled) and i == reached,
        })

    if f.get("quantity_mode") == "range" and (f.get("quantity_min") or f.get("quantity_max")):
        qty_text = f"{_qty_fmt(f.get('quantity_min'))}–{_qty_fmt(f.get('quantity_max'))}"
    elif f.get("quantity"):
        qty_text = _qty_fmt(f.get("quantity"))
    else:
        qty_text = (f.get("estimate_text") or "").strip()

    return {
        "trace": _distribusi_trace(f.get("name")),
        "flow": f.get("name"),
        "item": (f.get("canonical_item") or f.get("item_name")
                 or f.get("raw_item_text") or "-"),
        "quantity_text": (qty_text + " " + (f.get("unit") or "")).strip() or "-",
        "status": status,
        "status_label": _DISTRIBUSI_STATUS_LABEL.get(status, status),
        "cancelled": cancelled,
        "cancelled_at": str(f.get("cancelled_at")) if f.get("cancelled_at") else None,
        "source_posko": titles.get(f.get("source_posko")) or "-",
        "destination_posko": titles.get(f.get("destination_posko")) or "-",
        "route": ((titles.get(f.get("source_posko")) or "-") + " → "
                  + (titles.get(f.get("destination_posko")) or "-")),
        "transport": " · ".join(x for x in [
            f.get("transport_provider"), f.get("transport_type")] if x) or "-",
        "eta_final": (f.get("eta_final") or "").strip() or None,
        "received_text": (
            (f"{_qty_fmt(f.get('received_quantity'))} {f.get('received_unit') or ''}".strip())
            if f.get("received_quantity") else None
        ),
        "receipt_note": (f.get("receipt_note") or "").strip() or None,
        "steps": steps,
        "updated_at": str(f.get("modified")) if f.get("modified") else None,
    }


def _qty_fmt(value):
    v = _num(value)
    if v == int(v):
        return f"{int(v):,}".replace(",", ".")
    return f"{v:,.1f}".replace(",", ".")


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def distribusi_board(disaster_event=None):
    """Manajemen Distribusi dashboard (matches the DMS mock-up), guest
    read-only. One payload: KPI totals + drill items, the 4-column matching
    board (read-only overview — deep-links to the module that owns each
    record, not a drag/drop redesign), Ruang Transportasi (real per
    transport_type, since RN Transport Space.transport_type already has
    darat/laut/udara/lainnya), Alur Distribusi (live RN Distribution Flow),
    Peringatan & Hambatan, and the static Pedoman Kemasan reference (reuses
    `_LOGISTIK_CONVERSIONS`, same source as Posko Logistik's "Konversi").
    Write action `auto_match_distribution` (login required) actually creates
    RN Distribution Flow records — not a UI-only button.
    """
    event = canonical_event(disaster_event) if disaster_event else None

    flow_filter = event_filters(cols("RN Distribution Flow"), event) if event else {}
    flows = frappe.get_all(
        "RN Distribution Flow", filters=flow_filter,
        fields=_sf("RN Distribution Flow", [
            "name", "item_name", "quantity", "unit", "flow_status",
            "source_posko", "destination_posko", "eta_final",
            "transport_provider", "transport_type", "transport_space",
            "logistic_need", "aid_offer", "dispatched_at", "in_transit_at",
            "arrived_at", "received_at", "modified",
        ]),
        order_by="modified desc", limit_page_length=500,
    )

    transport_filter = event_filters(cols("RN Transport Space"), event) if event else {}
    transports = frappe.get_all(
        "RN Transport Space", filters=transport_filter,
        fields=_sf("RN Transport Space", [
            "name", "provider_name", "transport_type", "transport_status",
            "capacity_weight_kg", "capacity_volume_m3", "route_origin",
            "route_destination", "observed_at", "coordination_posko",
            "departure_time", "eta", "current_location", "handover_location",
            "handover_contact_person", "handover_contact_phone",
            "coordination_notes", "departure_at", "eta_at", "service_mode",
            "booking_policy", "capacity_committed_kg", "capacity_committed_m3",
            "pickup_volunteer", "pickup_volunteer_name",
        ]),
        limit_page_length=200,
    )

    # confirmed/requested bookings that block armada capacity
    _tspace_names = [t.get("name") for t in transports]
    _bookings_by_space = {}
    if _tspace_names and frappe.db.exists("DocType", "RN Transport Booking"):
        for bk in frappe.get_all(
            "RN Transport Booking",
            filters={"transport_space": ["in", _tspace_names]},
            fields=_sf("RN Transport Booking", [
                "name", "transport_space", "cargo_desc", "qty_weight_kg",
                "qty_volume_m3", "status", "booker_name", "booked_by_type",
                "pickup_location", "dropoff_location", "contact_person",
                "contact_phone", "verification_pin", "requested_at",
                "delivery_method", "requested_window",
            ]),
            order_by="creation desc", limit_page_length=1000,
        ):
            _bookings_by_space.setdefault(bk.transport_space, []).append(bk)

    need_filter = event_filters(cols("RN Logistic Need"), event) if event else {}
    needs = frappe.get_all(
        "RN Logistic Need", filters=need_filter,
        fields=["name", "item_name", "quantity", "unit", "urgency",
                "need_status", "posko"],
        limit_page_length=500,
    )

    offer_filter = event_filters(cols("RN Aid Offer"), event) if event else {}
    offers = frappe.get_all(
        "RN Aid Offer", filters=offer_filter,
        fields=["name", "item_name", "quantity", "unit", "offer_status",
                "handling_mode", "target_posko", "observed_at"],
        limit_page_length=500,
    )

    posko_names = (
        {f.source_posko for f in flows} | {f.destination_posko for f in flows}
        | {n.posko for n in needs} | {o.target_posko for o in offers}
        | {t.get("coordination_posko") for t in transports}
    )
    posko_titles = _distribusi_posko_titles(posko_names)

    matched_need_ids = {f.logistic_need for f in flows if f.logistic_need}
    matched_offer_ids = {f.aid_offer for f in flows if f.aid_offer}

    # ---- capacity utilisation (overall + per transport_type) ----
    UTILISED_STATES = {"reserved", "assigned", "in_transit", "arrived", "completed"}

    def _blocked_m3_for(t):
        """Booked (confirmed + requested) volume on this armada that is not yet
        reflected in transport_status — the mock-up's donut "Blocked" segment."""
        bks = _bookings_by_space.get(t.get("name"), [])
        return sum(_num(b.qty_volume_m3) for b in bks
                   if b.status in ("confirmed", "requested"))

    def _cap_bucket(rows):
        total_kg = sum(_num(t.capacity_weight_kg) for t in rows)
        used_kg = sum(_num(t.capacity_weight_kg) for t in rows if t.transport_status in UTILISED_STATES)
        pct = round(100.0 * used_kg / total_kg, 1) if total_kg else 0
        blocked_m3 = round(sum(_blocked_m3_for(t) for t in rows), 1)
        terpakai_m3 = round(sum(_num(t.capacity_volume_m3) for t in rows
                                if t.transport_status in UTILISED_STATES), 1)
        total_m3 = round(sum(_num(t.capacity_volume_m3) for t in rows), 1)
        return {
            "tersedia_m3": round(max(0.0, sum(_num(t.capacity_volume_m3) for t in rows
                                      if t.transport_status == "available") - blocked_m3), 1),
            "terpakai_m3": terpakai_m3,
            "blocked_m3": blocked_m3,
            "total_m3": total_m3,
            "pct": pct,
            "units": [
                {
                    "provider": t.provider_name,
                    "capacity_m3": _num(t.capacity_volume_m3),
                    "route": (t.route_origin or "-") + " → " + (t.route_destination or "-"),
                    "status": t.transport_status,
                    "berangkat": t.get("departure_time") or "-",
                    "eta": t.get("eta") or "-",
                    "lokasi_serah_terima": t.get("handover_location") or "-",
                    "narahubung": t.get("handover_contact_person") or "-",
                    "kontak": t.get("handover_contact_phone") or "-",
                    "pct": round(100.0 * _num(t.capacity_weight_kg) /
                                  (_num(t.capacity_weight_kg) or 1), 0) if t.transport_status in UTILISED_STATES else 0,
                }
                for t in rows
            ],
        }

    overall_cap = _cap_bucket(transports)
    by_type = {
        ttype: _cap_bucket([t for t in transports if t.transport_type == ttype])
        for ttype in ("darat", "laut", "udara")
    }

    # ---- KPI totals ----
    urgent_terms = {"critical", "urgent", "high", "tinggi", "darurat"}
    open_needs = [n for n in needs if str(n.need_status or "open").lower() == "open"]
    unmatched_needs = [n for n in open_needs if n.name not in matched_need_ids]

    blocked_flows = [f for f in flows if str(f.flow_status or "").lower() in _DRILL_BLOCKED_FLOW]

    totals = {
        "transport_space_pct": overall_cap["pct"],
        "kapasitas_darat_pct": by_type["darat"]["pct"],
        "kapasitas_laut_pct": by_type["laut"]["pct"],
        "kapasitas_udara_pct": by_type["udara"]["pct"],
        "kebutuhan_belum_match": len(unmatched_needs),
        "distribusi_terhambat": len(blocked_flows),
    }

    def _drill(title, sub, href=None):
        return {"title": title, "sub": sub, "href": href}

    kpi_items = {
        "kebutuhan_items": [
            _drill(n.item_name, (posko_titles.get(n.posko) or "-") + f" · {_qty_fmt(n.quantity)} {n.unit or ''}".rstrip(),
                   "posko-logistik.html?id=" + (n.posko or "") + "&event=" + (event or ""))
            for n in sorted(unmatched_needs, key=lambda r: 0 if str(r.urgency).lower() in urgent_terms else 1)[:30]
        ],
        "terhambat_items": [
            _drill(f.item_name or f.name, _DISTRIBUSI_STATUS_LABEL.get(f.flow_status, f.flow_status),
                   "posko-detail.html?id=" + (f.destination_posko or f.source_posko or "") + "&event=" + (event or ""))
            for f in blocked_flows[:30]
        ],
    }

    # ---- matching board (read-only 4 columns) ----
    unmatched_offers = [o for o in offers
                         if o.name not in matched_offer_ids
                         and str(o.offer_status or "").lower() not in _DRILL_DELIVERED_OFFER]

    pickup_volunteers = frappe.get_all(
        "RN Volunteer Assignment",
        filters={"assignment_type": "distribution"} if not event else
                 {"assignment_type": "distribution", "disaster_event": event},
        fields=["name", "volunteer", "posko", "task_title", "assignment_status"],
        limit_page_length=100,
    )
    vol_names = {v.volunteer for v in pickup_volunteers if v.volunteer}
    vol_titles = {}
    if vol_names:
        vol_titles = {
            r.name: r.volunteer_name
            for r in frappe.get_all("RN Volunteer Profile", filters={"name": ["in", list(vol_names)]},
                                     fields=["name", "volunteer_name"], limit_page_length=len(vol_names))
        }

    matching_board = {
        "kebutuhan": {
            "total": len(unmatched_needs),
            "items": [
                {"title": n.item_name, "sub": (posko_titles.get(n.posko) or "-") + f" · {_qty_fmt(n.quantity)} {n.unit or ''}".rstrip(),
                 "urgency": n.urgency,
                 "href": "posko-logistik.html?id=" + (n.posko or "") + "&event=" + (event or "")}
                for n in unmatched_needs[:6]
            ],
        },
        "bantuan": {
            "total": len(unmatched_offers),
            "items": [
                {"title": o.item_name, "sub": f"{_qty_fmt(o.quantity)} {o.unit or ''} · " + (posko_titles.get(o.target_posko) or "-"),
                 "status": o.offer_status,
                 "href": "posko-logistik.html?id=" + (o.target_posko or "") + "&event=" + (event or "")}
                for o in unmatched_offers[:6]
            ],
        },
        "relawan_pickup": {
            "total": len(pickup_volunteers),
            "items": [
                {"title": vol_titles.get(v.volunteer, v.volunteer), "sub": v.task_title,
                 "href": None}
                for v in pickup_volunteers[:6]
            ],
        },
        "transportasi": {
            "total": sum(1 for t in transports if t.transport_status == "available"),
            "items": [
                {"title": t.get("provider_name"),
                 "sub": (t.get("transport_type") or "-") + " · "
                        + (t.get("current_location") or t.get("route_origin") or "-")
                        + (" · ☎ " + t.get("handover_contact_phone") if t.get("handover_contact_phone") else ""),
                 "href": ("posko-detail.html?id=" + t.get("coordination_posko") + "&event=" + (event or ""))
                         if t.get("coordination_posko") else None}
                for t in transports if t.get("transport_status") == "available"
            ][:6],
        },
    }

    today = frappe.utils.getdate()
    matched_today = sum(
        1 for f in flows
        if f.dispatched_at and frappe.utils.getdate(f.dispatched_at) == today
    )

    # ---- Alur Distribusi (live shipment table) ----
    alur_distribusi = []
    for f in flows[:40]:
        alur_distribusi.append({
            "id": f.name,
            "kebutuhan": (posko_titles.get(f.destination_posko) or "-") + f" · {_qty_fmt(f.quantity)} {f.unit or ''}".rstrip(),
            "bantuan": f.item_name or "-",
            "pickup_oleh": f.transport_provider or posko_titles.get(f.source_posko) or "-",
            "transportasi": (f.transport_type or "-"),
            "rute": (posko_titles.get(f.source_posko) or "-") + " → " + (posko_titles.get(f.destination_posko) or "-"),
            "eta": f.eta_final or "-",
            "status": f.flow_status,
            "status_label": _DISTRIBUSI_STATUS_LABEL.get(f.flow_status, f.flow_status or "-"),
            "trace": _distribusi_trace(f.name),
            "href": "posko-detail.html?id=" + (f.destination_posko or f.source_posko or "") + "&event=" + (event or ""),
        })

    # ---- Peringatan & Hambatan ----
    peringatan = []
    for f in blocked_flows[:10]:
        peringatan.append({
            "title": "Distribusi Terhambat — " + (f.item_name or f.name),
            "sub": _DISTRIBUSI_STATUS_LABEL.get(f.flow_status, f.flow_status) + " · " +
                   (posko_titles.get(f.source_posko) or "-") + " → " + (posko_titles.get(f.destination_posko) or "-"),
            "level": "critical",
            "href": "posko-detail.html?id=" + (f.destination_posko or f.source_posko or "") + "&event=" + (event or ""),
        })
    now = frappe.utils.now_datetime()
    for o in unmatched_offers:
        if o.observed_at and (now - o.observed_at).total_seconds() / 86400.0 >= 3:
            peringatan.append({
                "title": "Penumpukan Donasi — " + (o.item_name or o.name),
                "sub": f"Belum dijemput ≥3 hari di {posko_titles.get(o.target_posko) or '-'}",
                "level": "warning",
                "href": "posko-logistik.html?id=" + (o.target_posko or "") + "&event=" + (event or ""),
            })
    for ttype, label in (("darat", "Darat"), ("laut", "Laut"), ("udara", "Udara")):
        if by_type[ttype]["pct"] >= 90:
            peringatan.append({
                "title": f"Kapasitas {label} Hampir Penuh",
                "sub": f"{by_type[ttype]['pct']}% terpakai — pertimbangkan opsi tambahan.",
                "level": "warning",
                "href": None,
            })

    # ---- Armada Distribusi Posko — koordinasi penyerahan + booking ----
    _ARMADA_STATUS_LABEL = {
        "available": "Tersedia", "reserved": "Dipesan", "assigned": "Ditugaskan",
        "in_transit": "Dalam Perjalanan", "arrived": "Tiba",
        "completed": "Selesai", "cancelled": "Dibatalkan",
    }
    _SERVICE_MODE_LABEL = {
        "space_only": "Penyedia Ruang Muat", "courier_pickup": "Kurir Jemput-Antar",
        "both": "Ruang Muat + Kurir",
    }
    _BOOKING_STATUS_LABEL = {
        "requested": "Menunggu Konfirmasi", "confirmed": "Terkonfirmasi",
        "rejected": "Ditolak", "cancelled": "Dibatalkan", "completed": "Selesai",
    }
    _DELIVERY_LABEL = {
        "use_transporter": "Pakai transporter posko",
        "self_deliver": "Antar sendiri ke titik jemput",
    }

    def _fmt_dt(v):
        if not v:
            return ""
        s = str(v)
        return s[:16].replace("T", " ") if len(s) >= 16 else s

    armada_posko = []
    pickup_matches = []
    for t in sorted(
        transports,
        key=lambda r: str(r.get("departure_at") or r.get("observed_at") or ""),
        reverse=True,
    ):
        cap_kg = _num(t.get("capacity_weight_kg"))
        cap_m3 = _num(t.get("capacity_volume_m3"))
        bks = _bookings_by_space.get(t.get("name"), [])
        used_kg = sum(_num(b.qty_weight_kg) for b in bks if b.status == "confirmed")
        used_m3 = sum(_num(b.qty_volume_m3) for b in bks if b.status == "confirmed")
        held_kg = sum(_num(b.qty_weight_kg) for b in bks if b.status == "requested")
        held_m3 = sum(_num(b.qty_volume_m3) for b in bks if b.status == "requested")
        avail_kg = max(0.0, cap_kg - used_kg - held_kg)
        avail_m3 = max(0.0, cap_m3 - used_m3 - held_m3)
        pct_kg = round(100.0 * (used_kg + held_kg) / cap_kg) if cap_kg else 0

        cap_bits = []
        if cap_kg:
            cap_bits.append(f"{_qty_fmt(cap_kg)} kg")
        if cap_m3:
            cap_bits.append(f"{_qty_fmt(cap_m3)} m³")

        smode = t.get("service_mode") or "both"
        berangkat = _fmt_dt(t.get("departure_at")) or (t.get("departure_time") or "-")
        eta_v = _fmt_dt(t.get("eta_at")) or (t.get("eta") or "-")

        armada_posko.append({
            "id": t.get("name"),
            "provider": t.get("provider_name") or "-",
            "posko": posko_titles.get(t.get("coordination_posko")) or "-",
            "posko_id": t.get("coordination_posko") or "",
            "jenis": t.get("transport_type") or "-",
            "service_mode": smode,
            "service_mode_label": _SERVICE_MODE_LABEL.get(smode, smode),
            "booking_policy": t.get("booking_policy") or "pin_verify",
            "kapasitas": " · ".join(cap_bits) or "-",
            "kapasitas_total_kg": cap_kg,
            "kapasitas_total_m3": cap_m3,
            "kapasitas_terpakai_kg": round(used_kg + held_kg, 1),
            "kapasitas_tersedia_kg": round(avail_kg, 1),
            "kapasitas_tersedia_m3": round(avail_m3, 1),
            "kapasitas_pct": pct_kg,
            "lokasi_saat_ini": t.get("current_location") or "-",
            "rute": (t.get("route_origin") or "-") + " → " + (t.get("route_destination") or "-"),
            "berangkat": berangkat,
            "eta": eta_v,
            "lokasi_serah_terima": t.get("handover_location") or "-",
            "narahubung": t.get("handover_contact_person") or "-",
            "kontak": t.get("handover_contact_phone") or "-",
            "catatan": t.get("coordination_notes") or "",
            "status": t.get("transport_status") or "-",
            "status_label": _ARMADA_STATUS_LABEL.get(t.get("transport_status"), t.get("transport_status") or "-"),
            "pickup_volunteer": t.get("pickup_volunteer") or "",
            "pickup_volunteer_name": t.get("pickup_volunteer_name") or "",
            # transporter-side follow-up contact (for the coordinating posko)
            "transporter_contact_person": t.get("handover_contact_person") or "",
            "transporter_contact_phone": t.get("handover_contact_phone") or "",
            "bookings_count": sum(1 for b in bks if b.status in ("requested", "confirmed")),
            "bookings": [
                {
                    "id": b.name,
                    "cargo": b.cargo_desc or "-",
                    "qty": (f"{_qty_fmt(b.qty_weight_kg)} kg" if _num(b.qty_weight_kg) else "")
                           + ((" · " if _num(b.qty_weight_kg) and _num(b.qty_volume_m3) else "")
                              + (f"{_qty_fmt(b.qty_volume_m3)} m³" if _num(b.qty_volume_m3) else "")),
                    "status": b.status,
                    "status_label": _BOOKING_STATUS_LABEL.get(b.status, b.status),
                    "booker": b.booker_name or b.booked_by_type or "-",
                    "pickup": b.pickup_location or "",
                    "dropoff": b.dropoff_location or "",
                    "delivery_method": b.get("delivery_method") or "use_transporter",
                    "delivery_label": _DELIVERY_LABEL.get(b.get("delivery_method"), "Pakai transporter posko"),
                    "requested_window": b.get("requested_window") or "",
                    # supplier-side follow-up contact (for the coordinating posko)
                    "supplier_contact_person": b.contact_person or "",
                    "supplier_contact_phone": b.contact_phone or "",
                }
                for b in bks if b.status in ("requested", "confirmed")
            ],
            "href": "posko-detail.html?id=" + (t.get("coordination_posko") or "") + "&event=" + (event or ""),
        })

        # relawan-pickup matching: courier-capable armada with no volunteer yet
        if smode in ("courier_pickup", "both") and not t.get("pickup_volunteer"):
            cands = [
                {"name": vol_titles.get(v.volunteer, v.volunteer), "task": v.task_title or "Distribusi"}
                for v in pickup_volunteers
                if (not v.posko) or v.posko == t.get("coordination_posko")
            ][:5]
            open_need_here = sum(
                1 for n in unmatched_needs if n.posko == t.get("coordination_posko")
            )
            pickup_matches.append({
                "armada_id": t.get("name"),
                "armada": t.get("provider_name") or "-",
                "posko": posko_titles.get(t.get("coordination_posko")) or "-",
                "candidates": cands,
                "open_need_count": open_need_here,
                "href": "management-relawan.html?event=" + (event or ""),
            })

    return {
        "disaster_event": event,
        "generated_at": now,
        "totals": totals,
        "kpi_items": kpi_items,
        "matching_board": matching_board,
        "matched_today": matched_today,
        "ruang_transportasi": {"overall": overall_cap, "by_type": by_type},
        "armada_posko": armada_posko,
        "pickup_matches": pickup_matches,
        "alur_distribusi": alur_distribusi,
        "peringatan": peringatan,
        "conversions": _LOGISTIK_CONVERSIONS,
    }


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def posko_distribusi_board(posko=None, disaster_event=None):
    """Workspace for a Posko Distribusi (posko_type='transport') — the party
    that provides transport equipment + space: bisa Garuda, kapal TNI AL,
    motor pick-up, atau rombongan Land Rover club yang berangkat ke lokasi
    bencana. Lists the armada it registered (RN Transport Space), the booking
    inbox on those armada, capacity rollup, and relawan-pickup candidates.

    Separate from `distribusi_board` (that one stays the coordination
    dashboard matching the Manajemen Distribusi mock-up).
    """
    event = canonical_event(disaster_event) if disaster_event else None
    posko = _resolve_posko(posko) if posko else None

    # (logged_in, can_manage, can_coordinate) — drives which controls the page
    # shows: manage = daftarkan/perbarui armada, konfirmasi booking, tugaskan
    # relawan; coordinate = pesan slot pada armada posko lain yang terbuka.
    _di_flags = _posko_actor_flags(posko)
    # Booker / donor contacts and the handover PIN are for the posko's own
    # operators only — Guest and other posko see the booking without them.
    _di_contacts = bool(_di_flags[1])

    # can a warga with no account book space here? (transport posko opened
    # public participation and its org privacy allows public detail)
    public_ok = False
    if posko:
        try:
            from rescue_net.access_policy import public_posko_allowed
            public_ok = bool(
                frappe.db.get_value("RN Posko", posko, "public_participation")
                and public_posko_allowed(posko)
            )
        except Exception:
            public_ok = bool(frappe.db.get_value("RN Posko", posko, "public_participation"))

    posko_row = None
    if posko:
        posko_row = frappe.db.get_value(
            "RN Posko", posko,
            ["name", "title", "posko_type", "organization", "operational_status",
             "officer_in_charge_name", "emergency_contact", "city_name",
             "latitude", "longitude"],
            as_dict=True,
        )

    tfilter = {}
    if posko:
        tfilter["coordination_posko"] = posko
    elif event:
        tfilter = event_filters(cols("RN Transport Space"), event)

    transports = frappe.get_all(
        "RN Transport Space", filters=tfilter,
        fields=_sf("RN Transport Space", [
            "name", "provider_name", "transport_type", "transport_status",
            "capacity_weight_kg", "capacity_volume_m3",
            "own_load_kg", "own_load_m3", "own_cargo_desc", "route_origin",
            "route_destination", "coordination_posko", "disaster_event",
            "departure_time", "eta", "departure_at", "eta_at", "service_mode",
            "booking_policy", "current_location", "handover_location",
            "handover_contact_person", "handover_contact_phone",
            "coordination_notes", "pickup_volunteer", "pickup_volunteer_name",
        ]),
        order_by="modified desc", limit_page_length=200,
    )
    tnames = [t.name for t in transports]

    bookings = []
    if tnames and frappe.db.exists("DocType", "RN Transport Booking"):
        bookings = frappe.get_all(
            "RN Transport Booking",
            filters={"transport_space": ["in", tnames]},
            fields=_sf("RN Transport Booking", [
                "name", "transport_space", "cargo_desc", "qty_weight_kg",
                "qty_volume_m3", "status", "booker_name", "booked_by_type",
                "pickup_location", "dropoff_location", "contact_person",
                "contact_phone", "verification_pin", "requested_at",
                "confirmed_at", "delivery_method", "requested_window",
                "logistic_need", "aid_offer", "submitted_channel",
            ]),
            order_by="creation desc", limit_page_length=1000,
        )
    bk_by_space = {}
    for b in bookings:
        bk_by_space.setdefault(b.transport_space, []).append(b)

    def _dt(v):
        s = str(v or "")
        return s[:16].replace("T", " ") if len(s) >= 16 else s

    armada = []
    tot_kg = tot_m3 = used_kg = used_m3 = 0.0
    for t in transports:
        cap_kg = _num(t.capacity_weight_kg)
        cap_m3 = _num(t.capacity_volume_m3)
        own_kg = _num(t.own_load_kg)
        own_m3 = _num(t.own_load_m3)
        # space put on offer to other parties = total minus the provider's own load
        offered_kg = max(0.0, cap_kg - own_kg)
        offered_m3 = max(0.0, cap_m3 - own_m3)
        mine = bk_by_space.get(t.name, [])
        c_kg = sum(_num(b.qty_weight_kg) for b in mine if b.status == "confirmed")
        c_m3 = sum(_num(b.qty_volume_m3) for b in mine if b.status == "confirmed")
        h_kg = sum(_num(b.qty_weight_kg) for b in mine if b.status == "requested")
        h_m3 = sum(_num(b.qty_volume_m3) for b in mine if b.status == "requested")
        tot_kg += cap_kg
        tot_m3 += cap_m3
        used_kg += own_kg + c_kg + h_kg
        used_m3 += own_m3 + c_m3 + h_m3
        smode = t.service_mode or "both"
        armada.append({
            "id": t.name,
            "provider": t.provider_name or "-",
            "jenis": t.transport_type or "-",
            "service_mode": smode,
            "service_mode_label": _SERVICE_MODE_LABEL.get(smode, smode),
            "booking_policy": t.booking_policy or "pin_verify",
            "status": t.transport_status or "-",
            "status_label": _ARMADA_STATUS_LABEL.get(t.transport_status, t.transport_status or "-"),
            "kapasitas_total_kg": cap_kg, "kapasitas_total_m3": cap_m3,
            "muatan_sendiri_kg": round(own_kg, 1), "muatan_sendiri_m3": round(own_m3, 1),
            "muatan_sendiri_desc": t.own_cargo_desc or "",
            "kapasitas_ditawarkan_kg": round(offered_kg, 1),
            "kapasitas_ditawarkan_m3": round(offered_m3, 1),
            "kapasitas_terpakai_kg": round(c_kg + h_kg, 1),
            "kapasitas_tersedia_kg": round(max(0.0, offered_kg - c_kg - h_kg), 1),
            "kapasitas_tersedia_m3": round(max(0.0, offered_m3 - c_m3 - h_m3), 1),
            "kapasitas_pct": round(100.0 * (own_kg + c_kg + h_kg) / cap_kg) if cap_kg else 0,
            "berangkat": _dt(t.departure_at) or (t.departure_time or "-"),
            "eta": _dt(t.eta_at) or (t.eta or "-"),
            "current_location": t.current_location or "-",
            "rute": (t.route_origin or "-") + " → " + (t.route_destination or "-"),
            "handover_location": t.handover_location or "-",
            "handover_contact_person": t.handover_contact_person or "-",
            "handover_contact_phone": t.handover_contact_phone or "-",
            "coordination_notes": t.coordination_notes or "",
            "pickup_volunteer": t.pickup_volunteer or "",
            "pickup_volunteer_name": t.pickup_volunteer_name or "",
            "bookings_count": sum(1 for b in mine if b.status in ("requested", "confirmed")),
        })

    inbox = []
    for b in bookings:
        t = next((x for x in transports if x.name == b.transport_space), None)
        inbox.append({
            "id": b.name,
            "armada": (t.provider_name if t else b.transport_space),
            "armada_id": b.transport_space,
            "cargo": b.cargo_desc or "-",
            "qty_kg": _num(b.qty_weight_kg), "qty_m3": _num(b.qty_volume_m3),
            "status": b.status,
            "status_label": _BOOKING_STATUS_LABEL.get(b.status, b.status),
            "delivery_method": b.get("delivery_method") or "use_transporter",
            "delivery_label": _DELIVERY_LABEL.get(b.get("delivery_method"), "Pakai transporter posko"),
            "requested_window": b.get("requested_window") or "",
            "is_guest": (b.get("submitted_channel") == "guest"),
            "booker": b.booker_name or b.booked_by_type or "-",
            "supplier_contact_person": (b.contact_person or "") if _di_contacts else "",
            "supplier_contact_phone": (b.contact_phone or "") if _di_contacts else "",
            "pickup": b.pickup_location or "",
            "dropoff": b.dropoff_location or "",
            "verification_pin": (b.verification_pin or "") if _di_contacts else "",
            "requested_at": _dt(b.requested_at),
        })

    # relawan pickup candidates (distribution assignments at this posko / event)
    va_filter = {"assignment_type": "distribution"}
    if event:
        va_filter["disaster_event"] = event
    vas = frappe.get_all(
        "RN Volunteer Assignment", filters=va_filter,
        fields=["name", "volunteer", "posko", "task_title", "assignment_status"],
        limit_page_length=200,
    )
    if posko:
        vas = [v for v in vas if (not v.posko) or v.posko == posko]
    vnames = {v.volunteer for v in vas if v.volunteer}
    vtitle = {}
    if vnames:
        vtitle = {r.name: r.volunteer_name for r in frappe.get_all(
            "RN Volunteer Profile", filters={"name": ["in", list(vnames)]},
            fields=["name", "volunteer_name"], limit_page_length=len(vnames))}
    relawan_candidates = [
        {"id": v.volunteer, "name": vtitle.get(v.volunteer, v.volunteer),
         "task": v.task_title or "Distribusi", "status": v.assignment_status}
        for v in vas if v.volunteer
    ]

    # other transporter poskos for the switcher (shared grouped picker needs
    # organization + public_participation to build "my org" vs "open" groups)
    tp_filter = {"posko_type": "transport"}
    _tp_fields = ["name", "title", "city_name", "organization", "public_participation"]
    if event:
        tp_rows = frappe.get_all(
            "RN Posko",
            or_filters={"disaster_event": event, "disaster_event_legacy_id": event},
            filters=tp_filter, fields=_tp_fields,
            limit_page_length=200,
        )
    else:
        tp_rows = frappe.get_all("RN Posko", filters=tp_filter,
                                 fields=_tp_fields, limit_page_length=200)

    # ---- jemput aktif vs pasif (hanya sediakan ruang muat) ----
    is_active_pickup = any(
        (t.service_mode or "both") in ("courier_pickup", "both") for t in transports
    )
    pickup_mode_label = "Jemput Aktif" if is_active_pickup else "Pasif — hanya menyediakan ruang muat"

    # ---- pickup queue: open aid offers needing pickup, not yet claimed ----
    pickup_queue = []
    dest_options = []
    if event:
        off_filter = event_filters(cols("RN Aid Offer"), event)
        offers_all = frappe.get_all(
            "RN Aid Offer", filters=off_filter,
            fields=_sf("RN Aid Offer", [
                "name", "item_name", "raw_item_text", "quantity", "unit",
                "offer_status", "handling_mode", "donor_name", "donor_contact",
                "pickup_location", "ready_at", "target_posko",
            ]),
            order_by="creation desc", limit_page_length=500,
        )
        flow_off_ids = set(frappe.get_all(
            "RN Distribution Flow",
            filters={"aid_offer": ["!=", ""], "flow_status": ["not in", ["cancelled", "rejected"]]},
            pluck="aid_offer",
        ))
        _OPEN_OFFER = {"", "available", "need_pickup", "pending", "self_reported"}
        for o in offers_all:
            st = str(o.offer_status or "").lower()
            if o.name in flow_off_ids:
                continue
            if st not in _OPEN_OFFER:
                continue
            if (o.handling_mode or "").lower() not in ("need_pickup", "", "active_booking") \
               and st != "need_pickup":
                continue
            pickup_queue.append({
                "kind": "aid_offer",
                "aid_offer": o.name,
                "item": o.item_name or o.raw_item_text or "-",
                "quantity": o.quantity,
                "unit": o.unit or "",
                "donor": o.donor_name or "-",
                "donor_contact": (o.donor_contact or "") if _di_contacts else "",
                "pickup_location": o.pickup_location or "-",
                "ready_at": o.ready_at or "-",
                "suggested_destination": o.target_posko or "",
            })

        # outgoing distribution flows a collector posko dispatched WITHOUT a
        # transporter ("lewat" left empty) — any transport posko can claim one.
        _evp = set(_event_posko_names(event) or [])
        _flow_rows = frappe.get_all(
            "RN Distribution Flow",
            filters={"transport_space": ["in", ["", None]]},
            or_filters=(
                {"disaster_event": event, "disaster_event_legacy_id": event}
                if event else None
            ),
            fields=_sf("RN Distribution Flow", [
                "name", "item_name", "raw_item_text", "quantity", "unit",
                "source_posko", "destination_posko", "flow_status",
                "transport_space", "eta_final", "disaster_event",
            ]),
            order_by="modified desc", limit_page_length=400,
        )
        # + flows whose posko belongs to this event (legacy rows w/o disaster_event)
        if _evp:
            _seen = {r.name for r in _flow_rows}
            for fr in frappe.get_all(
                "RN Distribution Flow",
                filters={"transport_space": ["in", ["", None]]},
                or_filters=[
                    ["source_posko", "in", list(_evp)],
                    ["destination_posko", "in", list(_evp)],
                ],
                fields=_sf("RN Distribution Flow", [
                    "name", "item_name", "raw_item_text", "quantity", "unit",
                    "source_posko", "destination_posko", "flow_status",
                    "transport_space", "eta_final", "disaster_event",
                ]),
                order_by="modified desc", limit_page_length=400,
            ):
                if fr.name not in _seen:
                    _flow_rows.append(fr)
        for fr in _flow_rows:
            if fr.get("transport_space"):
                continue
            if str(fr.get("flow_status") or "").lower() not in (
                "", "created", "pending", "planned", "needs_transport",
                "awaiting_transport", "requested",
            ):
                continue
            src_t = frappe.db.get_value("RN Posko", fr.source_posko, "title") if fr.source_posko else None
            pickup_queue.append({
                "kind": "flow",
                "flow": fr.name,
                "aid_offer": fr.name,  # reused as the row key on the frontend
                "item": fr.item_name or fr.raw_item_text or "-",
                "quantity": fr.quantity,
                "unit": fr.unit or "",
                "donor": (src_t or fr.source_posko or "Posko pengumpul"),
                "donor_contact": "",
                "pickup_location": (src_t or fr.source_posko or "-"),
                "ready_at": fr.get("eta_final") or "-",
                "suggested_destination": fr.destination_posko or "",
            })

        dest_rows = frappe.get_all(
            "RN Posko",
            or_filters={"disaster_event": event, "disaster_event_legacy_id": event},
            fields=["name", "title", "posko_type", "city_name"],
            limit_page_length=300,
        )
        dest_options = [
            {"id": r.name, "title": r.title or r.name,
             "type": r.posko_type or "", "city": r.get("city_name") or ""}
            for r in dest_rows
            if (r.posko_type or "").lower() != "transport"
        ]

    return {
        "disaster_event": event,
        "generated_at": frappe.utils.now_datetime(),
        "posko": posko,
        "posko_info": posko_row,
        "is_transport_posko": bool(posko_row and (posko_row.get("posko_type") or "").lower() == "transport"),
        "is_active_pickup": is_active_pickup,
        "pickup_mode_label": pickup_mode_label,
        "totals": {
            "armada_count": len(armada),
            "kapasitas_total_kg": round(tot_kg, 1),
            "kapasitas_total_m3": round(tot_m3, 1),
            "kapasitas_terpakai_kg": round(used_kg, 1),
            "kapasitas_terpakai_m3": round(used_m3, 1),
            "kapasitas_tersedia_kg": round(max(0.0, tot_kg - used_kg), 1),
            "booking_menunggu": sum(1 for b in bookings if b.status == "requested"),
            "booking_terkonfirmasi": sum(1 for b in bookings if b.status == "confirmed"),
            "pickup_queue": len(pickup_queue),
        },
        "armada": armada,
        "booking_inbox": inbox,
        "pickup_queue": pickup_queue,
        "destination_options": dest_options,
        "relawan_candidates": relawan_candidates,
        "transporter_poskos": [
            {"id": r.name, "title": r.title, "city": r.get("city_name") or "",
             "organization": r.get("organization"),
             "public_participation": bool(r.get("public_participation"))}
            for r in tp_rows
        ],
        "viewer": _poskos_viewer_context(),
        "logged_in": _di_flags[0],
        "can_manage": _di_flags[1],
        "can_coordinate": _di_flags[2],
        "public_ok": public_ok,
    }


@frappe.whitelist()
def auto_match_distribution(disaster_event=None, limit=5):
    """Real (if simple) auto-matcher for the mock-up's "Otomatis Cocokkan"
    button: pairs an open RN Logistic Need with an available RN Aid Offer of
    the same item (case-insensitive) and an available RN Transport Space,
    then creates an RN Distribution Flow linking all three. Requires login
    (any authenticated actor — this mirrors the other create_* endpoints'
    bar, there being no single posko to gate against here).
    """
    from rescue_net.access_policy import rn_actor
    import re

    rn_actor()  # login required; raises if guest

    event = canonical_event(disaster_event) if disaster_event else None
    limit = min(int(limit or 5), 20)

    need_filter = event_filters(cols("RN Logistic Need"), event) if event else {}
    needs = frappe.get_all(
        "RN Logistic Need", filters=dict(need_filter, need_status="open"),
        fields=["name", "item_name", "quantity", "unit", "urgency", "posko"],
        order_by="modified desc", limit_page_length=200,
    )

    offer_filter = event_filters(cols("RN Aid Offer"), event) if event else {}
    offers = frappe.get_all(
        "RN Aid Offer", filters=offer_filter,
        fields=["name", "item_name", "quantity", "unit", "offer_status", "target_posko"],
        order_by="modified desc", limit_page_length=200,
    )
    open_offers = [o for o in offers if str(o.offer_status or "").lower() in
                   {"available", "ready", "need_pickup"}]

    transport_filter = event_filters(cols("RN Transport Space"), event) if event else {}
    free_transports = frappe.get_all(
        "RN Transport Space", filters=dict(transport_filter, transport_status="available"),
        fields=["name", "provider_name", "transport_type"],
        limit_page_length=50,
    )

    already_matched_needs = {f.logistic_need for f in frappe.get_all(
        "RN Distribution Flow", filters={"logistic_need": ["is", "set"]},
        fields=["logistic_need"], limit_page_length=2000) if f.logistic_need}
    already_matched_offers = {f.aid_offer for f in frappe.get_all(
        "RN Distribution Flow", filters={"aid_offer": ["is", "set"]},
        fields=["aid_offer"], limit_page_length=2000) if f.aid_offer}

    def _norm(text):
        return re.sub(r"[^a-z0-9]+", "", str(text or "").lower())

    used_offers, used_transports = set(), set()
    created = []

    for n in needs:
        if len(created) >= limit:
            break
        if n.name in already_matched_needs:
            continue
        need_key = _norm(n.item_name)
        offer = next(
            (o for o in open_offers
             if o.name not in already_matched_offers and o.name not in used_offers
             and _norm(o.item_name) == need_key),
            None,
        )
        if not offer:
            continue
        transport = next(
            (t for t in free_transports if t.name not in used_transports), None,
        )
        if not transport:
            break

        flow = frappe.new_doc("RN Distribution Flow")
        flow.disaster_event = event
        flow.title = f"Auto-match: {n.item_name}"
        flow.item_name = n.item_name
        flow.quantity = min(_num(n.quantity), _num(offer.quantity)) or _num(n.quantity)
        flow.unit = n.unit or offer.unit
        flow.flow_status = "planned"
        flow.source_posko = offer.target_posko
        flow.destination_posko = n.posko
        flow.logistic_need = n.name
        flow.aid_offer = offer.name
        flow.transport_space = transport.name
        flow.transport_provider = transport.provider_name
        flow.transport_type = transport.transport_type
        flow.dispatched_at = frappe.utils.now_datetime()
        flow.verification_status = "self_reported"
        flow.insert(ignore_permissions=True)

        used_offers.add(offer.name)
        used_transports.add(transport.name)
        created.append({
            "flow": flow.name, "item_name": n.item_name,
            "need": n.name, "offer": offer.name, "transport": transport.name,
        })

    return {"matched": len(created), "flows": created}
