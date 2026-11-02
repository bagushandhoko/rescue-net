"""Cari Armada — public view on Manajemen Distribusi (owner 2026-11-02).

"halaman publik manajemen distribusi: filter untuk memilih, waktu dan lokasi terdekat; jika mau eksekusi harus
login; menggambarkan ketersediaan dan yang sedang digunakan." Every armada (RN Transport Space) serving the
disaster with: availability (tersedia / penuh / sedang dipakai), remaining capacity, schedule, and distance from
the viewer. Read-only and guest-safe (no handover phone numbers); booking happens on the posko page after login.
"""

import math

import frappe
from frappe.rate_limiter import rate_limit
from frappe.utils import flt, get_datetime, getdate

from rescue_net.reference_resolver import resolve_disaster_event

IN_USE = {"reserved", "assigned", "in_transit"}
DONE = {"arrived", "completed", "cancelled"}
STATUS_LABEL = {"tersedia": "Tersedia", "penuh": "Penuh", "dipakai": "Sedang dipakai"}
TYPE_LABEL = {"darat": "Darat", "laut": "Laut", "udara": "Udara", "lainnya": "Lainnya"}


def _km(a_lat, a_lng, b_lat, b_lng):
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(b_lng - a_lng) / 2) ** 2
    return 12742 * math.asin(math.sqrt(h))


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def armada_finder(disaster_event=None, transport_type=None, date_from=None, date_to=None, lat=None, lng=None,
                  status=None):
    from rescue_net.control_centre.common import serving_transport_names

    event = resolve_disaster_event(disaster_event) if disaster_event else None
    names = serving_transport_names(event) if event else frappe.get_all("RN Transport Space", pluck="name",
                                                                       limit_page_length=1000)
    if not names:
        return {"rows": [], "counts": {}, "logged_in": frappe.session.user != "Guest"}
    rows = frappe.get_all("RN Transport Space", filters={"name": ["in", names]}, fields=[
        "name", "title", "provider_name", "transport_type", "route_origin", "route_destination", "departure_at",
        "eta_at", "departure_time", "capacity_weight_kg", "capacity_volume_m3", "own_load_kg", "own_load_m3",
        "capacity_committed_kg", "capacity_committed_m3", "transport_status", "coordination_posko", "booking_policy",
        "volunteer_capacity_seats", "current_location", "service_mode"], limit_page_length=1000)
    pk = {p.name: p for p in frappe.get_all(
        "RN Posko", filters={"name": ["in", list({r.coordination_posko for r in rows if r.coordination_posko}) or ["-"]]},
        fields=["name", "title", "latitude", "longitude", "city_name"])}
    me_lat, me_lng = _num(lat), _num(lng)
    d_from = getdate(date_from) if date_from else None
    d_to = getdate(date_to) if date_to else None
    out, counts = [], {"tersedia": 0, "penuh": 0, "dipakai": 0}
    for r in rows:
        st = r.transport_status or "available"
        if st in DONE:
            continue
        cap_kg, cap_m3 = flt(r.capacity_weight_kg), flt(r.capacity_volume_m3)
        left_kg = max(0.0, cap_kg - flt(r.own_load_kg) - flt(r.capacity_committed_kg)) if cap_kg else None
        left_m3 = max(0.0, cap_m3 - flt(r.own_load_m3) - flt(r.capacity_committed_m3)) if cap_m3 else None
        if st in IN_USE:
            avail = "dipakai"
        elif (left_kg is not None and left_kg <= 0) and (left_m3 is None or left_m3 <= 0):
            avail = "penuh"
        else:
            avail = "tersedia"
        dep = get_datetime(r.departure_at) if r.departure_at else None
        if (d_from or d_to) and dep:
            if (d_from and dep.date() < d_from) or (d_to and dep.date() > d_to):
                continue
        if transport_type and r.transport_type != transport_type:
            continue
        p = pk.get(r.coordination_posko)
        km = None
        if p and me_lat is not None and me_lng is not None and p.latitude and p.longitude:
            km = round(_km(me_lat, me_lng, float(p.latitude), float(p.longitude)), 1)
        counts[avail] += 1
        if status and avail != status:
            continue
        out.append({
            "name": r.name, "title": r.title or r.provider_name, "provider": r.provider_name,
            "type": r.transport_type, "type_label": TYPE_LABEL.get(r.transport_type, r.transport_type or "-"),
            "route": (r.route_origin or "-") + " → " + (r.route_destination or "-"),
            "departure": str(dep)[:16] if dep else (r.departure_time or ""), "flexible": not dep,
            "eta": str(r.eta_at)[:16] if r.eta_at else "",
            "capacity_kg": cap_kg or None, "capacity_m3": cap_m3 or None, "left_kg": left_kg, "left_m3": left_m3,
            "seats": r.volunteer_capacity_seats or 0, "status": avail, "status_label": STATUS_LABEL[avail],
            "raw_status": st, "open_booking": r.booking_policy == "open",
            "posko": r.coordination_posko, "posko_title": p.title if p else "", "city": p.city_name if p else "",
            "km": km, "location": r.current_location or "",
            "href": "posko-distribusi.html?id=" + (r.coordination_posko or "") + ("&event=" + event if event else ""),
        })
    out.sort(key=lambda x: ({"tersedia": 0, "penuh": 1, "dipakai": 2}[x["status"]],
                            x["km"] if x["km"] is not None else 1e9, x["departure"] or "9999"))
    return {"rows": out, "counts": counts, "logged_in": frappe.session.user != "Guest"}
