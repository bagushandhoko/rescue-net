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
