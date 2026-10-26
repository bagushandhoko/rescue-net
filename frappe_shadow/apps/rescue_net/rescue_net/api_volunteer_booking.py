"""Relawan menawarkan diri untuk beberapa bencana dan memesan kursi armada
(posko distribusi) atau tempat menginap (posko shelter) — owner 2026-10-26.

A volunteer account has one RN Volunteer Profile per disaster (same account,
`user_account` set); offering a disaster creates/reopens that profile,
withdrawing sets it unavailable (never while assigned). A booking is
`requested` until the providing posko confirms; seats/beds are checked on
request and again on confirm."""

import json

import frappe
from frappe.utils import cint, now_datetime

from rescue_net.access_policy import can_manage_posko, is_system_manager, rn_actor

ACTIVE = ("requested", "confirmed")
_PROFILE_COPY = ("volunteer_name", "contact", "main_skill", "skill_category", "skill_tags", "duration_available",
                 "current_location", "preferences", "equipment_owned", "needs_transport", "needs_pickup",
                 "transport_vehicle", "service_areas", "availability_schedule")


def _me():
    actor = rn_actor(required=False)
    if not actor or not actor.name:
        frappe.throw("Masuk dulu sebagai relawan.", frappe.PermissionError)
    return actor


def _events():
    from rescue_net.api_ai import public_active_disasters
    out = []
    for e in public_active_disasters() or []:
        name = e.get("name") or e.get("id")
        if name and not frappe.db.exists("RN Disaster Event", name):
            name = frappe.db.get_value("RN Disaster Event", {"legacy_id": name}, "name") or name
        out.append({"id": name, "title": e.get("title") or name})
    return out


def _profiles(actor):
    return frappe.get_all("RN Volunteer Profile", filters={"user_account": actor.name},
                          fields=["name", "disaster_event", "availability_status", "assigned_posko", "volunteer_name",
                                  "main_skill", "skill_category", "modified"],
                          order_by="modified desc", limit_page_length=50)


def _title(dt, name, field="title"):
    return (frappe.db.get_value(dt, name, field) or name) if name else None


@frappe.whitelist()
def my_volunteer():
    actor = _me()
    profiles = _profiles(actor)
    bookings = frappe.get_all("RN Volunteer Booking", filters={"user_account": actor.name},
                              fields=["name", "booking_kind", "status", "disaster_event", "posko", "transport_space",
                                      "accommodation", "date_from", "date_to", "decision_note", "creation"],
                              order_by="creation desc", limit_page_length=50)
    for b in bookings:
        b["posko_title"] = _title("RN Posko", b.posko)
        b["target_title"] = (_title("RN Transport Space", b.transport_space, "provider_name") if b.transport_space
                             else _title("RN Volunteer Accommodation", b.accommodation, "location_name"))
    return {
        "account": {"name": frappe.db.get_value("User", frappe.session.user, "full_name") or frappe.session.user},
        "events": _events(),
        "offered": [p.disaster_event for p in profiles if p.availability_status != "unavailable"],
        "profiles": profiles,
        "bookings": bookings,
    }


@frappe.whitelist()
def offer_events(events, main_skill=None, skill_category=None, contact=None, current_location=None, duration_available=None):
    """Tick the disasters this volunteer offers to help. Creates a profile per
    new disaster (copied from the latest profile), reopens withdrawn ones and
    withdraws unticked ones that are not assigned."""
    actor = _me()
    if isinstance(events, str):
        events = json.loads(events or "[]")
    wanted = {e for e in (events or []) if e}
    valid = {e["id"] for e in _events()}
    unknown = wanted - valid
    if unknown:
        frappe.throw("Bencana tidak dikenal atau tidak aktif: %s" % ", ".join(sorted(unknown)))
    profiles = _profiles(actor)
    by_event = {p.disaster_event: p for p in profiles}
    base = frappe.get_doc("RN Volunteer Profile", profiles[0].name) if profiles else None
    name = (base.volunteer_name if base else None) or frappe.db.get_value("User", frappe.session.user, "full_name")
    phone = contact or (base.contact if base else None) or frappe.db.get_value("User", frappe.session.user, "mobile_no")
    if not phone and wanted - set(by_event):
        frappe.throw("Isi nomor HP / WhatsApp agar posko bisa menghubungi Anda.")
    skill = main_skill or skill_category or (base.main_skill if base else None)
    if not skill and wanted - set(by_event):
        frappe.throw("Isi keahlian utama Anda.")
    for ev in wanted:
        p = by_event.get(ev)
        if p:
            if p.availability_status == "unavailable":
                frappe.db.set_value("RN Volunteer Profile", p.name, "availability_status", "available")
            continue
        doc = frappe.new_doc("RN Volunteer Profile")
        if base:
            for f in _PROFILE_COPY:
                if doc.meta.has_field(f):
                    doc.set(f, base.get(f))
        doc.user_account = actor.name
        doc.disaster_event = ev
        doc.volunteer_name = name
        doc.contact = phone
        doc.main_skill = main_skill or doc.main_skill or skill
        if skill_category:
            doc.skill_category = skill_category
        if current_location:
            doc.current_location = current_location
        if duration_available:
            doc.duration_available = duration_available
        doc.availability_status = "available"
        doc.verification_status = "self_reported"
        doc.observed_at = doc.source_updated_at = now_datetime()
        doc.insert(ignore_permissions=True)
    for ev, p in by_event.items():
        if ev not in wanted and p.availability_status in ("available", "limited"):
            frappe.db.set_value("RN Volunteer Profile", p.name, "availability_status", "unavailable")
    return my_volunteer()


def _served_spaces(event):
    names = set(frappe.get_all("RN Transport Space", filters={"disaster_event": event}, pluck="name"))
    if frappe.db.table_exists("RN Transport Space Event"):
        names |= set(frappe.get_all("RN Transport Space Event", filters={"disaster_event": event}, pluck="parent"))
    return names


def _used(kind, target):
    field = "transport_space" if kind == "transport" else "accommodation"
    return frappe.db.count("RN Volunteer Booking", {field: target, "status": "confirmed"})


def _capacity(kind, target):
    if kind == "transport":
        return cint(frappe.db.get_value("RN Transport Space", target, "volunteer_capacity_seats"))
    row = frappe.db.get_value("RN Volunteer Accommodation", target, ["capacity_beds", "occupants_count"], as_dict=True) or {}
    return max(0, cint(row.get("capacity_beds")) - cint(row.get("occupants_count")))


@frappe.whitelist()
def booking_options(disaster_event):
    _me()
    from rescue_net.control_centre.common import canonical_event
    event = canonical_event(disaster_event) or disaster_event
    armada = []
    spaces = list(_served_spaces(event))
    for s in frappe.get_all("RN Transport Space", filters={"name": ["in", spaces or [""]],
                                                         "transport_status": ["not in", ["completed", "cancelled"]]},
                            fields=["name", "provider_name", "transport_type", "coordination_posko", "departure_at",
                                    "volunteer_capacity_seats", "volunteer_needs_pickup", "volunteer_pickup_location",
                                    "handover_location"], limit_page_length=200):
        seats = cint(s.get("volunteer_capacity_seats"))
        if seats <= 0:
            continue
        armada.append({"id": s.name, "title": s.provider_name, "type": s.transport_type, "posko": s.coordination_posko,
                       "posko_title": _title("RN Posko", s.coordination_posko), "departure_at": str(s.departure_at or "")[:16],
                       "seats_left": max(0, seats - _used("transport", s.name)), "seats": seats,
                       "pickup": s.get("volunteer_pickup_location") or s.get("handover_location")})
    akomodasi = []
    for a in frappe.get_all("RN Volunteer Accommodation", filters={"disaster_event": event},
                            fields=["name", "location_name", "accommodation_type", "posko", "capacity_beds", "safety_status"],
                            limit_page_length=200):
        cap = _capacity("akomodasi", a.name)
        if cint(a.capacity_beds) <= 0:
            continue
        akomodasi.append({"id": a.name, "title": a.location_name, "type": a.accommodation_type, "posko": a.posko,
                          "posko_title": _title("RN Posko", a.posko), "safety": a.safety_status,
                          "beds_left": max(0, cap - _used("akomodasi", a.name)), "beds": cint(a.capacity_beds)})
    return {"disaster_event": event, "armada": armada, "akomodasi": akomodasi}


@frappe.whitelist()
def book(kind, target, disaster_event, date_from=None, date_to=None, pickup_location=None, note=None):
    actor = _me()
    from rescue_net.control_centre.common import canonical_event
    event = canonical_event(disaster_event) or disaster_event
    if kind not in ("transport", "akomodasi"):
        frappe.throw("Jenis booking tidak valid.")
    prof = frappe.db.get_value("RN Volunteer Profile", {"user_account": actor.name, "disaster_event": event,
                                                       "availability_status": ["!=", "unavailable"]}, "name")
    if not prof:
        frappe.throw("Tawarkan diri Anda untuk bencana ini dulu (centang di Relawan Saya).")
    if kind == "transport":
        if target not in _served_spaces(event):
            frappe.throw("Armada ini tidak melayani bencana tersebut.")
        if frappe.db.get_value("RN Transport Space", target, "transport_status") in ("completed", "cancelled"):
            frappe.throw("Armada ini sudah selesai atau dibatalkan.")
        posko = frappe.db.get_value("RN Transport Space", target, "coordination_posko")
    else:
        row = frappe.db.get_value("RN Volunteer Accommodation", target, ["disaster_event", "posko"], as_dict=True)
        if not row or row.disaster_event != event:
            frappe.throw("Tempat menginap ini tidak untuk bencana tersebut.")
        posko = row.posko
    field = "transport_space" if kind == "transport" else "accommodation"
    if frappe.db.exists("RN Volunteer Booking", {"volunteer": prof, field: target, "status": ["in", ACTIVE]}):
        frappe.throw("Anda sudah punya booking aktif di sini.")
    if _capacity(kind, target) - _used(kind, target) <= 0:
        frappe.throw("Penuh: tidak ada %s tersisa." % ("kursi" if kind == "transport" else "tempat tidur"))
    doc = frappe.get_doc({"doctype": "RN Volunteer Booking", "booking_kind": kind, "status": "requested",
                          "volunteer": prof, "user_account": actor.name, "disaster_event": event, "posko": posko,
                          field: target, "date_from": date_from or None, "date_to": date_to or None,
                          "pickup_location": (pickup_location or "")[:140] or None, "note": (note or "")[:500] or None})
    doc.insert(ignore_permissions=True)
    return {"booking": doc.name, "status": doc.status, "posko": posko}


@frappe.whitelist()
def cancel_booking(booking):
    actor = _me()
    doc = frappe.get_doc("RN Volunteer Booking", booking)
    if doc.user_account != actor.name:
        frappe.throw("Bukan booking Anda.", frappe.PermissionError)
    if doc.status not in ACTIVE:
        frappe.throw("Booking ini sudah tidak aktif.")
    doc.status = "cancelled"
    doc.save(ignore_permissions=True)
    return {"booking": doc.name, "status": doc.status}


@frappe.whitelist()
def posko_bookings(posko=None, status=None):
    """Volunteer bookings for the poskos this account manages (SM: all)."""
    actor = rn_actor(required=False)
    filters = {}
    if status:
        filters["status"] = status
    if posko:
        if not (is_system_manager() or can_manage_posko(actor, posko)):
            frappe.throw("Anda bukan pengelola posko ini.", frappe.PermissionError)
        filters["posko"] = posko
    rows = frappe.get_all("RN Volunteer Booking", filters=filters,
                          fields=["name", "booking_kind", "status", "volunteer", "posko", "transport_space", "accommodation",
                                  "date_from", "date_to", "pickup_location", "note", "creation"],
                          order_by="creation desc", limit_page_length=200)
    if not posko and not is_system_manager():
        rows = [r for r in rows if r.posko and can_manage_posko(actor, r.posko)]
    for r in rows:
        v = frappe.db.get_value("RN Volunteer Profile", r.volunteer, ["volunteer_name", "main_skill", "contact"], as_dict=True) or {}
        r["volunteer_name"], r["main_skill"], r["contact"] = v.get("volunteer_name"), v.get("main_skill"), v.get("contact")
        r["posko_title"] = _title("RN Posko", r.posko)
        r["target_title"] = (_title("RN Transport Space", r.transport_space, "provider_name") if r.transport_space
                             else _title("RN Volunteer Accommodation", r.accommodation, "location_name"))
    return {"bookings": rows}


@frappe.whitelist()
def decide_booking(booking, action, note=None):
    actor = rn_actor()
    doc = frappe.get_doc("RN Volunteer Booking", booking)
    if not (is_system_manager() or (doc.posko and can_manage_posko(actor, doc.posko))):
        frappe.throw("Hanya posko penyedia yang dapat memutuskan.", frappe.PermissionError)
    if doc.status != "requested":
        frappe.throw("Booking ini sudah diputuskan.")
    if action not in ("confirm", "reject"):
        frappe.throw("Aksi tidak valid.")
    if action == "confirm":
        target = doc.transport_space or doc.accommodation
        if _capacity(doc.booking_kind, target) - _used(doc.booking_kind, target) <= 0:
            frappe.throw("Penuh: kapasitas sudah terpakai.")
    doc.status = "confirmed" if action == "confirm" else "rejected"
    doc.decision_note = (note or "")[:500] or None
    doc.decided_by = actor.name if actor else None
    doc.decided_at = now_datetime()
    doc.save(ignore_permissions=True)
    return {"booking": doc.name, "status": doc.status}
