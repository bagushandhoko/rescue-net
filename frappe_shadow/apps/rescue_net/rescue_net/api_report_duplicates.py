"""Laporan ganda (simulasi S3, 2026-11-02): several residents report the same incident. A posko manager /
Control Centre links the copies to one main report, so people are not counted twice and one posko handles it.

- report_duplicate_candidates: likely copies of a report (same disaster, close in time and place).
- mark_report_duplicate / unmark_report_duplicate: link / unlink (manager of either report's posko, Control
  Centre or System Manager). The copy gets consolidation_status "duplicate", its reporter gets a follow-up
  saying which report handles it.
- group_people(): the people count of a main report = the largest count in its group (never the sum).
"""

import math

import frappe
from frappe.utils import cint, get_datetime

from rescue_net.access_policy import can_manage_posko, is_system_manager, rn_actor

WINDOW_HOURS = 48
RADIUS_KM = 2.0
_FIELDS = ["name", "title", "report_type", "disaster_event", "latitude", "longitude", "village_name",
           "district_name", "city_name", "location_text", "affected_people_count", "creation", "posko",
           "duplicate_of", "status", "reporter_name"]


def _km(a, b):
    if None in (a.latitude, a.longitude, b.latitude, b.longitude) or not (a.latitude or a.longitude) \
            or not (b.latitude or b.longitude):
        return None
    la1, lo1, la2, lo2 = map(math.radians, (float(a.latitude), float(a.longitude), float(b.latitude), float(b.longitude)))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def _same_place(a, b):
    d = _km(a, b)
    if d is not None:
        return d <= RADIUS_KM, ("%.1f km" % d)
    for f in ("village_name", "district_name"):
        if a.get(f) and b.get(f):
            return a.get(f).strip().lower() == b.get(f).strip().lower(), f.split("_")[0]
    ta, tb = (a.location_text or "").strip().lower(), (b.location_text or "").strip().lower()
    return bool(ta and ta == tb), "lokasi sama"


def _root(name, seen=None):
    """Follow duplicate_of to the main report."""
    seen = seen or set()
    while name and name not in seen:
        seen.add(name)
        nxt = frappe.db.get_value("RN Community Report", name, "duplicate_of")
        if not nxt:
            return name
        name = nxt
    return name


def _may_manage(actor, report_row):
    if is_system_manager() or (actor and actor.get("role") == "command_center"):
        return True
    return bool(report_row.posko and actor and can_manage_posko(actor, report_row.posko))


def _row(name):
    row = frappe.db.get_value("RN Community Report", name, _FIELDS, as_dict=True)
    if not row:
        frappe.throw("Laporan tidak ditemukan.", frappe.DoesNotExistError)
    return row


@frappe.whitelist()
def report_duplicate_candidates(report):
    actor = rn_actor()
    me = _row(report)
    if not _may_manage(actor, me):
        frappe.throw("Hanya pengelola posko laporan ini atau Control Centre.", frappe.PermissionError)
    if not me.disaster_event:
        return {"report": me.name, "candidates": []}
    t0 = get_datetime(me.creation)
    rows = frappe.get_all("RN Community Report", filters={"disaster_event": me.disaster_event, "name": ["!=", me.name],
                                                          "duplicate_of": ["is", "not set"]},
                          fields=_FIELDS, order_by="creation asc", limit_page_length=1000)
    out = []
    for r in rows:
        if abs((get_datetime(r.creation) - t0).total_seconds()) > WINDOW_HOURS * 3600:
            continue
        if me.report_type and r.report_type and me.report_type != r.report_type:
            continue
        same, why = _same_place(me, r)
        if not same:
            continue
        out.append({"name": r.name, "title": r.title, "location": r.village_name or r.district_name or r.location_text or "",
                    "people": cint(r.affected_people_count), "created": str(r.creation)[:16], "why": why,
                    "older": get_datetime(r.creation) < t0})
    out.sort(key=lambda x: (not x["older"], x["created"]))
    return {"report": me.name, "candidates": out}


def _note_to_reporter(report, text):
    try:
        frappe.get_doc({"doctype": "RN Community Report Update", "report": report, "update_type": "info",
                        "body": text[:2000], "author_role": "posko"}).insert(ignore_permissions=True)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "report duplicate note")


@frappe.whitelist(methods=["POST"])
def mark_report_duplicate(report, duplicate_of):
    actor = rn_actor()
    me, main = _row(report), _row(duplicate_of)
    if not (_may_manage(actor, me) or _may_manage(actor, main)):
        frappe.throw("Hanya pengelola posko salah satu laporan atau Control Centre.", frappe.PermissionError)
    if me.disaster_event != main.disaster_event:
        frappe.throw("Laporan dari bencana berbeda tidak bisa digabung.")
    root = _root(main.name)
    if root == me.name:
        frappe.throw("Laporan tidak bisa menjadi duplikat dari dirinya sendiri / duplikatnya.")
    # copies of `me` follow it to the new main report
    for child in frappe.get_all("RN Community Report", filters={"duplicate_of": me.name}, pluck="name"):
        frappe.db.set_value("RN Community Report", child, "duplicate_of", root)
    frappe.db.set_value("RN Community Report", me.name, {"duplicate_of": root, "consolidation_status": "duplicate"})
    root_row = _row(root)
    who = frappe.db.get_value("RN Posko", root_row.posko, "title") if root_row.posko else "Control Centre"
    _note_to_reporter(me.name, "Laporan Anda dicatat sama dengan laporan lain untuk kejadian yang sama (%s) dan ditangani "
                      "oleh %s. Terima kasih — tambahkan tindak lanjut di sini bila ada info baru." % (root_row.title, who))
    return {"report": me.name, "duplicate_of": root, "group_people": group_people(root)}


@frappe.whitelist(methods=["POST"])
def unmark_report_duplicate(report):
    actor = rn_actor()
    me = _row(report)
    main = _row(me.duplicate_of) if me.duplicate_of else None
    if not (_may_manage(actor, me) or (main and _may_manage(actor, main))):
        frappe.throw("Hanya pengelola posko salah satu laporan atau Control Centre.", frappe.PermissionError)
    frappe.db.set_value("RN Community Report", me.name, {"duplicate_of": None, "consolidation_status": None})
    return {"report": me.name, "duplicate_of": None}


def group_people(root):
    counts = [cint(frappe.db.get_value("RN Community Report", root, "affected_people_count"))]
    counts += [cint(c) for c in frappe.get_all("RN Community Report", filters={"duplicate_of": root},
                                               pluck="affected_people_count")]
    return max(counts) if counts else 0
