"""Kelola Posko (owner 2026-11-01, tahap 1): one page for posko managers / owners, separate from the
public / Control Centre posko pages. Lists the poskos the user manages, what needs action at each one,
the posko's settings at a glance and links to every management tool for its type.

Read-only hub: every change still goes through the existing, permission-checked endpoints
(api_community_cluster.update_posko, set_posko_served_events, api_comms.set_posko_comms_support,
api_volunteer_booking.decide_booking, ...)."""

import frappe

from rescue_net.access_policy import can_manage_posko, rn_actor
from rescue_net.reference_resolver import resolve_posko

TYPE_LABEL = {
    "logistics": "Posko Logistik", "collection_hub": "Gudang Pengumpul", "transport": "Posko Distribusi / Transport",
    "medical": "Posko Medis", "shelter": "Shelter", "kitchen": "Dapur Umum", "field_assessment": "Assessment Lapangan",
    "communication": "Posko Komunikasi", "command": "Komando",
}
WORKSPACE = {
    "logistics": "posko-logistik.html", "collection_hub": "posko-logistik.html", "transport": "posko-distribusi.html",
    "medical": "posko-medis-detail.html", "shelter": "shelter-detail.html", "kitchen": "dapur-umum.html",
}
CONTACT_FIELDS = ("officer_in_charge_phone", "officer_in_charge_whatsapp", "emergency_contact")


def _managed(actor):
    from rescue_net.api_offline import _my_poskos
    return [p for p in _my_poskos(actor) if can_manage_posko(actor, p)]


def _pending(posko):
    out = {
        "relawan": frappe.db.count("RN Volunteer Booking", {"posko": posko, "status": "requested"}),
        "operator": frappe.db.count("RN Posko Assignment", {"posko": posko, "status": "pending"}),
        "kedaluwarsa": 0,
        # bookings waiting for this posko's armada (owner 2026-11-02)
        "pesanan_armada": frappe.db.count("RN Transport Booking", {"status": "requested", "transport_space": ["in",
            frappe.get_all("RN Transport Space", filters={"coordination_posko": posko}, pluck="name") or ["-"]]}),
    }
    # S14 (2026-11-02): stock already expired or expiring soon
    if frappe.db.exists("RN Stock Batch", {"posko": posko}):
        from rescue_net.services.expiry import expiring_report
        rep = expiring_report(posko)
        out["kedaluwarsa"] = rep["expired"] + rep["soon"]
    return out


def _tools(p, ev):
    q = "?id=" + p.name + ("&event=" + ev if ev else "")
    t = (p.posko_type or "").lower()
    tools = [
        {"key": "workspace", "label": "Ruang kerja posko", "desc": "Halaman kerja harian sesuai jenis posko",
         "href": WORKSPACE.get(t, "posko-detail.html") + q},
        {"key": "settings", "label": "Pengaturan & kontak", "desc": "Nama, lokasi, PIC, nomor HP, WhatsApp notifikasi",
         "href": WORKSPACE.get(t, "posko-detail.html") + q + "&settings=1"},
        {"key": "relawan", "label": "Permintaan relawan", "desc": "Relawan yang menawarkan diri, jemputan & shelter",
         "href": "management-relawan.html?posko=" + p.name},
        {"key": "armada", "label": "Alat transport / armada",
         "desc": "Daftarkan armada, jadwal, kapasitas; terima / tolak pesanan ruang muat",
         "href": "posko-distribusi.html" + q},
        {"key": "komunikasi", "label": "Alat komunikasi", "desc": "Radio, frekuensi, jangkauan, energi, dukungan",
         "href": "alat-komunikasi.html?posko=" + p.name + ("&event=" + ev if ev else "")},
        {"key": "notifikasi", "label": "Notifikasi", "desc": "Atur pemberitahuan untuk akun Anda",
         "href": "notifikasi-settings.html"},
    ]
    if t in ("logistics", "collection_hub", "transport") or p.get("rn_fn_logistics"):
        tools.insert(1, {"key": "distribusi", "label": "Manajemen distribusi", "desc": "Kiriman masuk / keluar",
                         "href": "management-distribusi.html" + q})
    return tools


def _summary(name, actor):
    p = frappe.get_doc("RN Posko", name)
    from rescue_net.control_centre.common import posko_served_events
    events = posko_served_events(name) or ([p.disaster_event] if p.disaster_event else [])
    ev_titles = [{"id": e, "title": frappe.db.get_value("RN Disaster Event", e, "title") or e} for e in events]
    has_contact = any((p.get(f) or "").strip() for f in CONTACT_FIELDS)
    warnings = []
    if not has_contact:
        warnings.append("Nomor kontak posko belum diisi — publik tidak bisa menghubungi posko.")
    if not (p.latitude and p.longitude):
        warnings.append("Koordinat posko belum diisi — posko tidak muncul di peta.")
    if (p.verification_status or "self_reported") in ("self_reported", "needs_correction"):
        warnings.append("Posko belum diajukan / perlu koreksi untuk verifikasi.")
    pending = _pending(name)
    return {
        "posko": name,
        "title": p.title or name,
        "type": p.posko_type or "",
        "type_label": TYPE_LABEL.get((p.posko_type or "").lower(), p.posko_type or "Posko"),
        "status": p.operational_status or "",
        "verification": p.verification_status or "self_reported",
        "organization": frappe.db.get_value("RN Organization", p.organization, "title") if p.organization else "",
        "events": ev_titles,
        "contact": {"name": p.officer_in_charge_name or "", "phone": p.officer_in_charge_phone or "",
                    "whatsapp": p.officer_in_charge_whatsapp or "", "emergency": p.emergency_contact or ""},
        "comms": {"offered": p.get("comms_support_offered") or "", "needed": p.get("comms_support_needed") or ""},
        "pending": pending,
        "pending_total": sum(pending.values()),
        "warnings": warnings,
        "public_href": "posko-detail.html?id=" + name + ("&event=" + events[0] if events else ""),
        "tools": _tools(p, events[0] if events else ""),
    }


@frappe.whitelist()
def my_managed_poskos():
    """Poskos the logged-in user manages, each with its action count (Kelola Posko list)."""
    actor = rn_actor()
    out = []
    for name in _managed(actor):
        row = frappe.db.get_value("RN Posko", name, ["title", "posko_type", "operational_status"], as_dict=True)
        pending = _pending(name)
        out.append({"posko": name, "title": row.title or name,
                    "type_label": TYPE_LABEL.get((row.posko_type or "").lower(), row.posko_type or "Posko"),
                    "status": row.operational_status or "", "pending_total": sum(pending.values())})
    return {"poskos": out}


@frappe.whitelist()
def manage_hub(posko):
    """Everything a manager needs for one posko. 403 for anyone who does not manage it."""
    actor = rn_actor()
    name = resolve_posko(posko)
    if not name or not frappe.db.exists("RN Posko", name):
        frappe.throw("Posko tidak ditemukan")
    if not can_manage_posko(actor, name):
        frappe.throw("Halaman ini hanya untuk pengelola posko ini.", frappe.PermissionError)
    return _summary(name, actor)


@frappe.whitelist(allow_guest=True)
def can_manage(posko):
    """Guest-safe gate for the "🔧 Kelola Posko" button on public posko pages."""
    actor = rn_actor(required=False)
    name = resolve_posko(posko)
    return {"can_manage": bool(actor and name and can_manage_posko(actor, name))}


# --- Alat transport posko (owner 2026-11-02: "halaman untuk mengatur alat transport dia") ----------------------

ARMADA_STATUS_LABEL = {"available": "Tersedia", "reserved": "Dipesan", "assigned": "Ditugaskan", "in_transit": "Dalam perjalanan",
                       "arrived": "Tiba", "completed": "Selesai", "cancelled": "Batal"}


@frappe.whitelist()
def armada_list(posko):
    """The posko's own armada with what needs a decision (requested bookings). Managers only."""
    from rescue_net.control_centre.distribusi import _armada_avail

    actor = rn_actor()
    name = resolve_posko(posko)
    if not name or not can_manage_posko(actor, name):
        frappe.throw("Halaman ini hanya untuk pengelola posko ini.", frappe.PermissionError)
    rows = frappe.get_all("RN Transport Space", filters={"coordination_posko": name}, fields=[
        "name", "title", "provider_name", "transport_type", "transport_status", "departure_at", "eta_at",
        "capacity_weight_kg", "own_load_kg", "capacity_committed_kg", "booking_policy", "position_at",
        "route_origin", "route_destination"], order_by="departure_at desc", limit_page_length=100)
    out = []
    for r in rows:
        bookings = frappe.get_all("RN Transport Booking", filters={"transport_space": r.name, "status": "requested"},
                                  fields=["name", "cargo_desc", "qty_weight_kg", "qty_volume_m3", "booker_name",
                                          "booked_by_type", "contact_person", "contact_phone", "requested_window",
                                          "verification_pin", "creation"], order_by="creation asc", limit_page_length=20)
        cap = float(r.capacity_weight_kg or 0)
        left = max(0.0, cap - float(r.own_load_kg or 0) - float(r.capacity_committed_kg or 0)) if cap else None
        out.append({
            "name": r.name, "title": r.title or r.provider_name, "type": r.transport_type or "",
            "status": r.transport_status or "available",
            "status_label": ARMADA_STATUS_LABEL.get(r.transport_status, r.transport_status or "-"),
            "avail": _armada_avail(r.transport_status, left, r.departure_at),
            "departure": str(r.departure_at or "")[:16], "route": (r.route_origin or "-") + " → " + (r.route_destination or "-"),
            "capacity_kg": cap or None, "left_kg": left, "position_at": str(r.position_at or "")[:16],
            "pin_needed": (r.booking_policy or "pin_verify") == "pin_verify",
            "requested": [dict(b, needs_pin=bool(b.pop("verification_pin"))) for b in bookings],
        })
    return {"posko": name, "armada": out,
            "pending_total": sum(len(a["requested"]) for a in out),
            "statuses": ARMADA_STATUS_LABEL}


# --- Kelola Posko tahap 2 (owner 2026-11-02 "kerjakan semua"): input tools on the owner page ------------------

@frappe.whitelist()
def workbench(posko):
    """Data for the owner's input tools: contact & status, open needs, stock, volunteer requests.
    Writes go through the existing endpoints (update_posko, create_need, create_stock_observation, decide_booking)."""
    actor = rn_actor()
    name = resolve_posko(posko)
    if not name or not can_manage_posko(actor, name):
        frappe.throw("Halaman ini hanya untuk pengelola posko ini.", frappe.PermissionError)
    p = frappe.db.get_value("RN Posko", name, ["officer_in_charge_name", "officer_in_charge_role", "officer_in_charge_phone",
                                              "officer_in_charge_whatsapp", "emergency_contact", "operational_status"],
                            as_dict=True)
    needs = frappe.get_all("RN Logistic Need", filters={"posko": name, "need_status": ["in", ["open", "needs_review", "in_progress"]]},
                           fields=["name", "item_name", "quantity", "unit", "urgency", "need_status", "creation"],
                           order_by="creation desc", limit_page_length=50)
    stock = {}
    for r in frappe.get_all("RN Stock Observation", filters={"posko": name},
                            fields=["item_name", "quantity", "unit", "observed_at"], order_by="observed_at desc",
                            limit_page_length=500):
        stock.setdefault((r.item_name, r.unit), r)          # latest per item+unit
    vol = frappe.get_all("RN Volunteer Booking", filters={"posko": name, "status": "requested"},
                         fields=["name", "booking_kind", "volunteer", "note", "creation"], order_by="creation asc",
                         limit_page_length=50)
    for v in vol:
        pr = frappe.db.get_value("RN Volunteer Profile", v.volunteer, ["volunteer_name", "main_skill", "contact"], as_dict=True) or {}
        v.update({"volunteer_name": pr.get("volunteer_name"), "main_skill": pr.get("main_skill"), "contact": pr.get("contact")})
    return {
        "posko": name,
        "contact": {k: (v or "") for k, v in (p or {}).items()},
        "needs": [dict(n, creation=str(n.creation)[:16]) for n in needs],
        "stock": [{"item": r.item_name, "quantity": r.quantity, "unit": r.unit, "observed_at": str(r.observed_at or "")[:16]}
                  for r in list(stock.values())[:60]],
        "volunteer_requests": [dict(v, creation=str(v.creation)[:16]) for v in vol],
    }
