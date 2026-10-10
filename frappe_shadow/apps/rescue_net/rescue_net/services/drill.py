"""Mode latihan (Fase 10g): event dengan ``is_drill=1`` adalah latihan/simulasi.

Satu tempat untuk aturannya (pelajaran BUG-1..6: aturan yang tersebar di tiap endpoint akan terlewat):
publik/agregat nasional tidak pernah memuat event latihan; notifikasi untuk posko/event latihan selalu
disimulasikan; hanya System Manager yang boleh melihat latihan di panel internal (``include_drill``).
Tidak ada yang dihapus di sini — pembersihan latihan ada di ``scripts/rn-drill.py`` (pratinjau dulu).
"""

import frappe


def drill_event_names():
    """Nama semua RN Disaster Event latihan (himpunan; kosong bila field belum dimigrasi)."""
    if not frappe.get_meta("RN Disaster Event").has_field("is_drill"):
        return set()
    return set(frappe.get_all("RN Disaster Event", filters={"is_drill": 1}, pluck="name"))


def is_drill_event(event):
    return bool(event) and event in drill_event_names()


def is_drill_posko(posko):
    if not posko:
        return False
    return is_drill_event(frappe.db.get_value("RN Posko", posko, "disaster_event"))


def can_include_drill(include_drill=None):
    """Hanya System Manager yang boleh meminta data latihan ikut (panel internal)."""
    asked = str(include_drill or "").lower() in ("1", "true", "yes")
    return asked and "System Manager" in frappe.get_roles()


def real_rows(rows, key="disaster_event", include_drill=None):
    """Buang baris yang terkait event latihan (``key`` = nama kolom event; ``name`` untuk event itu sendiri)."""
    if can_include_drill(include_drill):
        return list(rows)
    drills = drill_event_names()
    if not drills:
        return list(rows)
    return [r for r in rows if (r.get(key) if hasattr(r, "get") else getattr(r, key, None)) not in drills]


# ---- akses tamu lewat id eksplisit ------------------------------------------------------------------------------
EVENT_PARAMS = ("disaster_event", "disaster_event_id", "event")
POSKO_PARAMS = ("posko", "source_posko", "destination_posko")


def _drill_event_refs():
    """Semua cara menyebut event latihan: nama, legacy_id, dan 'disaster_events:<legacy>'."""
    refs = set()
    if not frappe.get_meta("RN Disaster Event").has_field("is_drill"):
        return refs
    for r in frappe.get_all("RN Disaster Event", filters={"is_drill": 1}, fields=["name", "legacy_id"]):
        for v in (r.name, r.legacy_id):
            if v:
                refs.update({v, "disaster_events:" + v})
    return refs


def refers_to_drill(params):
    """True bila parameter permintaan menunjuk event latihan, atau posko di event latihan."""
    refs = _drill_event_refs()
    if not refs:
        return False
    for key in EVENT_PARAMS:
        v = str(params.get(key) or "").strip()
        if v and v in refs:
            return True
    for key in POSKO_PARAMS:
        v = str(params.get(key) or "").strip()
        if v and frappe.db.get_value("RN Posko", v, "disaster_event") in refs:
            return True
    return False


def guard_guest_refs(params):
    """Tamu tidak boleh membuka data latihan lewat id eksplisit (diperlakukan 'tidak ditemukan')."""
    if frappe.session.user == "Guest" and refers_to_drill(params):
        frappe.throw("Data tidak ditemukan.", frappe.DoesNotExistError)


def before_request(*args, **kwargs):
    """Hook before_request: berlaku hanya untuk panggilan /api/method/rescue_net.*; kegagalan internal tidak
    boleh mengganggu request lain (hanya penolakan yang disengaja yang diteruskan)."""
    try:
        req = getattr(frappe.local, "request", None)
        if not req or not (req.path or "").startswith("/api/method/rescue_net."):
            return
        params = frappe.local.form_dict
    except Exception:
        return
    guard_guest_refs(params)
