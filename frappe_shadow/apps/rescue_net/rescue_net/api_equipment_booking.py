"""Booking angkutan alat kerja / alat berat: mobilisasi (mob) dan demobilisasi (demob) (owner 2026-11-14).

Owner: "mob demob ikutin alat distribusi ... alat distribusi bisa ditambahkan bisa angkut orang, dan alat berat".
Pola sama dengan kursi relawan di armada (api_volunteer_booking):
- pemilik alat (perorangan / organisasi yang dikelola / posko yang dikelola) memesan armada posko distribusi yang
  ditandai carries_heavy_equipment, untuk mob (ke lokasi kerja) atau demob (pulang);
- pengelola posko armada (coordination_posko) menyetujui / menolak; status tampil di kedua sisi;
- sistem menolak arah yang tidak dilayani armada dan berat yang melebihi sisa muatan (heavy_max_ton) per arah.
"""

import frappe
from frappe.rate_limiter import rate_limit
from frappe.utils import flt, now_datetime

from rescue_net.access_policy import can_manage_organization, can_manage_posko, is_system_manager, rn_actor

DT = "RN Equipment Transport Booking"
TS = "RN Transport Space"
RP = "RN Resource Profile"
ACTIVE = ("requested", "confirmed")
TRIP_LABEL = {"mob": "Mob (ke lokasi kerja)", "demob": "Demob (pulang)"}
DECK_LABEL = {"lowbed": "Lowbed", "selfloader": "Selfloader", "flatbed": "Flatbed", "tongkang": "Tongkang", "lainnya": "Lainnya"}


def _owns_tool(actor, rp):
    if is_system_manager():
        return True
    if not actor:
        return False
    if rp.owner_type == "individual":
        return rp.owner_id == actor.name
    if rp.owner_type == "organization":
        return bool(rp.owner_id) and can_manage_organization(actor, rp.owner_id)
    if rp.owner_type == "posko":
        return bool(rp.owner_id) and can_manage_posko(actor, rp.owner_id)
    return False


def _serves(space, trip):
    t = (space.get("heavy_trip") or "mob_demob").strip()
    return t == "mob_demob" or t == trip


def _used_ton(space, trip, exclude=None):
    rows = frappe.get_all(DT, filters={"transport_space": space, "trip": trip, "status": "confirmed"},
                          fields=["name", "weight_ton"], limit_page_length=0)
    return sum(flt(r.weight_ton) for r in rows if r.name != exclude)


def _space_row(s):
    left = {t: max(flt(s.heavy_max_ton) - _used_ton(s.name, t), 0) for t in ("mob", "demob")}
    return {
        "id": s.name, "title": s.title or s.provider_name or s.name, "type": s.transport_type,
        "posko": s.coordination_posko,
        "posko_title": frappe.db.get_value("RN Posko", s.coordination_posko, "title") if s.coordination_posko else None,
        "route": " → ".join(x for x in (s.route_origin, s.route_destination) if x),
        "departure_at": str(s.departure_at) if s.departure_at else None,
        "demob_at": str(s.heavy_demob_at) if s.heavy_demob_at else None,
        "max_ton": flt(s.heavy_max_ton), "left_ton": left,
        "deck": DECK_LABEL.get(s.heavy_deck_type or "", s.heavy_deck_type or ""),
        "trip": s.heavy_trip or "mob_demob",
    }


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def heavy_armada(disaster_event=None, trip=None):
    """Armada yang bisa mengangkut alat berat (publik: tanpa kontak)."""
    from rescue_net.services import drill
    filters = {"carries_heavy_equipment": 1}
    if disaster_event:
        from rescue_net.reference_resolver import resolve_disaster_event
        filters["disaster_event"] = resolve_disaster_event(disaster_event) or disaster_event
    rows = frappe.get_all(TS, filters=filters, fields=[
        "name", "title", "provider_name", "transport_type", "coordination_posko", "route_origin", "route_destination",
        "departure_at", "heavy_demob_at", "heavy_max_ton", "heavy_deck_type", "heavy_trip", "disaster_event",
        "transport_status"], limit_page_length=500)
    rows = drill.drop_hidden_rows(rows, posko_keys=("coordination_posko",))
    out = [_space_row(r) for r in rows if (r.transport_status or "") not in ("unavailable", "cancelled")]
    if trip in ("mob", "demob"):
        out = [r for r in out if r["trip"] in ("mob_demob", trip)]
    return {"armada": out}


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=30, seconds=60)
def book(resource_profile, transport_space, trip, trip_date=None, weight_ton=None, pickup_location=None,
         destination=None, note=None):
    actor = rn_actor()
    rp = frappe.get_doc(RP, resource_profile)
    if not _owns_tool(actor, rp):
        frappe.throw("Hanya pemilik / pengelola alat ini yang bisa memesan angkutan.", frappe.PermissionError)
    if trip not in ("mob", "demob"):
        frappe.throw("Pilih arah: mob (ke lokasi) atau demob (pulang).")
    s = frappe.get_doc(TS, transport_space)
    if not s.get("carries_heavy_equipment"):
        frappe.throw("Armada ini tidak ditandai bisa mengangkut alat berat.")
    if not _serves(s, trip):
        frappe.throw("Armada ini tidak melayani arah " + TRIP_LABEL[trip] + ".")
    w = flt(weight_ton)
    if w <= 0:
        frappe.throw("Isi berat alat (ton).")
    left = flt(s.heavy_max_ton) - _used_ton(s.name, trip)
    if w > left:
        frappe.throw("Melebihi sisa muatan armada untuk arah ini (sisa %.1f ton)." % max(left, 0))
    dup = frappe.db.exists(DT, {"resource_profile": rp.name, "trip": trip, "status": ["in", list(ACTIVE)]})
    if dup:
        frappe.throw("Alat ini sudah punya booking " + TRIP_LABEL[trip] + " yang aktif.")
    doc = frappe.get_doc({"doctype": DT, "trip": trip, "status": "requested", "resource_profile": rp.name,
                          "transport_space": s.name, "disaster_event": s.disaster_event or rp.get("disaster_event"),
                          "requested_by": actor.name if actor else None, "trip_date": trip_date or None,
                          "weight_ton": w, "pickup_location": (pickup_location or "")[:140] or None,
                          "destination": (destination or "")[:140] or None, "note": (note or "")[:500] or None})
    doc.insert(ignore_permissions=True)
    return {"booking": doc.name, "status": doc.status}


def _row(b, with_contact=False):
    rp = frappe.db.get_value(RP, b.resource_profile, ["resource_name", "category", "owner_type", "owner_id"], as_dict=True) or {}
    s = frappe.db.get_value(TS, b.transport_space, ["title", "provider_name", "coordination_posko"], as_dict=True) or {}
    out = {"name": b.name, "trip": b.trip, "trip_label": TRIP_LABEL.get(b.trip, b.trip), "status": b.status,
           "tool": rp.get("resource_name") or b.resource_profile, "tool_id": b.resource_profile,
           "armada": s.get("title") or s.get("provider_name") or b.transport_space, "armada_id": b.transport_space,
           "posko": s.get("coordination_posko"), "trip_date": str(b.trip_date) if b.trip_date else None,
           "weight_ton": flt(b.weight_ton), "pickup_location": b.pickup_location, "destination": b.destination,
           "note": b.note, "decision_note": b.decision_note}
    if with_contact and b.requested_by:
        out["requested_by"] = frappe.db.get_value("RN User Account", b.requested_by, "title") or b.requested_by
    return out


FIELDS = ["name", "trip", "status", "resource_profile", "transport_space", "trip_date", "weight_ton",
          "pickup_location", "destination", "note", "decision_note", "requested_by"]


@frappe.whitelist()
def my_bookings():
    """Booking angkutan untuk alat-alat milik saya."""
    actor = rn_actor()
    from rescue_net.api_recovery_support import my_tools
    ids = [t.get("name") for t in (my_tools().get("tools") or [])]
    if not ids:
        return {"bookings": []}
    rows = frappe.get_all(DT, filters={"resource_profile": ["in", ids]}, fields=FIELDS, order_by="modified desc",
                          limit_page_length=200)
    return {"bookings": [_row(r) for r in rows]}


@frappe.whitelist()
def incoming(posko=None):
    """Booking alat berat yang masuk ke armada posko yang saya kelola (untuk disetujui/ditolak)."""
    actor = rn_actor()
    sf = {"carries_heavy_equipment": 1}
    if posko:
        sf["coordination_posko"] = posko
    spaces = [s for s in frappe.get_all(TS, filters=sf, fields=["name", "coordination_posko"], limit_page_length=0)
              if is_system_manager() or (s.coordination_posko and can_manage_posko(actor, s.coordination_posko))]
    if not spaces:
        return {"bookings": [], "can_manage": False}
    rows = frappe.get_all(DT, filters={"transport_space": ["in", [s.name for s in spaces]]}, fields=FIELDS,
                          order_by="modified desc", limit_page_length=200)
    return {"bookings": [_row(r, with_contact=True) for r in rows], "can_manage": True}


@frappe.whitelist(methods=["POST"])
def decide(booking, action, note=None):
    actor = rn_actor()
    doc = frappe.get_doc(DT, booking)
    posko = frappe.db.get_value(TS, doc.transport_space, "coordination_posko")
    if not (is_system_manager() or (posko and can_manage_posko(actor, posko))):
        frappe.throw("Hanya pengelola posko armada yang dapat memutuskan.", frappe.PermissionError)
    if action == "done":
        if doc.status != "confirmed":
            frappe.throw("Hanya booking yang disetujui yang bisa ditandai selesai.")
        doc.status = "done"
    else:
        if doc.status != "requested":
            frappe.throw("Booking ini sudah diputuskan.")
        if action not in ("confirm", "reject"):
            frappe.throw("Aksi tidak valid.")
        if action == "confirm":
            s = frappe.get_doc(TS, doc.transport_space)
            if flt(doc.weight_ton) > flt(s.heavy_max_ton) - _used_ton(s.name, doc.trip, exclude=doc.name):
                frappe.throw("Sisa muatan armada tidak cukup untuk booking ini.")
        doc.status = "confirmed" if action == "confirm" else "rejected"
    doc.decision_note = (note or "")[:500] or doc.decision_note
    doc.decided_by = actor.name if actor else None
    doc.decided_at = now_datetime()
    doc.save(ignore_permissions=True)
    return {"booking": doc.name, "status": doc.status}


@frappe.whitelist(methods=["POST"])
def cancel(booking):
    actor = rn_actor()
    doc = frappe.get_doc(DT, booking)
    rp = frappe.get_doc(RP, doc.resource_profile)
    if not _owns_tool(actor, rp):
        frappe.throw("Hanya pemilik alat yang bisa membatalkan.", frappe.PermissionError)
    if doc.status not in ACTIVE:
        frappe.throw("Booking ini tidak aktif.")
    doc.status = "cancelled"
    doc.save(ignore_permissions=True)
    return {"booking": doc.name, "status": doc.status}
