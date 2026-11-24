"""Management Refugee / Displacement Person — forward planning for pengungsi:
relokasi vs kembali, estimasi dana, dukungan yang diperlukan, plus pendataan
pengungsi non-camp (berserakan). Data operasional shelter tetap di api_shelter;
ini lapisan perencanaan / masukan kebijakan (blueprint: Rehabilitation).
"""

import frappe
from frappe.rate_limiter import rate_limit
from frappe.utils import now_datetime, flt, cint

from rescue_net.access_policy import rn_actor, is_system_manager
from rescue_net.reference_resolver import resolve_disaster_event

_PLAN_LABEL = {"undecided": "Belum diputuskan", "return_home": "Kembali ke asal",
               "relocate": "Relokasi"}
_HEALTH_LABEL = {"healthy": "Sehat", "needs_care": "Perlu perawatan",
                 "orphan": "Yatim piatu", "mixed": "Campuran"}
_STATUS_LABEL = {"draft": "Draft", "proposed": "Diusulkan", "approved": "Disetujui",
                 "in_progress": "Berjalan", "done": "Selesai"}


def _event(disaster_event):
    if not disaster_event:
        return None
    try:
        return resolve_disaster_event(disaster_event)
    except Exception:
        return disaster_event


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def displacement_board(disaster_event=None):
    ev = _event(disaster_event)
    _f = ["name", "title", "household_code", "origin_area", "current_location",
          "in_camp", "posko", "people_count", "vulnerable_count",
          "health_status", "plan_type", "est_return_cost",
          "est_rebuild_support", "support_needed", "supporting_org",
          "status", "notes", "modified", "disaster_event"]
    vals = [x for x in {ev, disaster_event} if x]
    orf = ([["disaster_event", "in", vals], ["disaster_event_legacy_id", "in", vals]]
           if vals else None)

    rows = frappe.get_all(
        "RN Displacement Plan", or_filters=orf, fields=_f,
        order_by="modified desc", limit_page_length=1000,
    )
    from rescue_net.services import drill
    rows = drill.drop_hidden_rows(rows)  # tampilan riil: tanpa rencana pengungsi simulasi
    if drill.simulation_hidden():  # data riil selalu milik suatu bencana; data contoh tanpa bencana disembunyikan
        rows = [r for r in rows if r.get("disaster_event")]

    def _p(r):
        r = dict(r)
        r["plan_label"] = _PLAN_LABEL.get(r.get("plan_type"), r.get("plan_type"))
        r["health_label"] = _HEALTH_LABEL.get(r.get("health_status"), r.get("health_status"))
        r["status_label"] = _STATUS_LABEL.get(r.get("status"), r.get("status"))
        r["est_total"] = flt(r.get("est_return_cost")) + flt(r.get("est_rebuild_support"))
        return r

    plans = [_p(r) for r in rows]
    # owner 24 Nov 2026: di bencana RIIL tamu & non-pengelola hanya melihat ANGKA; daftar per KK (kode KK, lokasi
    # sekarang, yatim piatu, catatan) hanya untuk pengelola posko yang melayani bencana itu. Simulasi tetap terbuka.
    seen, shown = {}, []
    for p in plans:
        key = p.get("disaster_event")
        if key not in seen:
            seen[key] = _may_see_detail(key)
        if seen[key]:
            shown.append(p)
    hidden = len(plans) - len(shown)

    by_plan = {"undecided": 0, "return_home": 0, "relocate": 0}
    people_by_plan = {"undecided": 0, "return_home": 0, "relocate": 0}
    for p in plans:
        k = p.get("plan_type") or "undecided"
        by_plan[k] = by_plan.get(k, 0) + 1
        people_by_plan[k] = people_by_plan.get(k, 0) + cint(p.get("people_count"))

    return {
        "disaster_event": ev,
        "generated_at": now_datetime(),
        "plans": shown,
        "detail_hidden": hidden,
        "totals": {
            "household_count": len(plans),
            "people_total": sum(cint(p.get("people_count")) for p in plans),
            "vulnerable_total": sum(cint(p.get("vulnerable_count")) for p in plans),
            "non_camp": sum(1 for p in plans if not p.get("in_camp")),
            "orphan_households": sum(1 for p in plans if p.get("health_status") == "orphan"),
            "needs_care_households": sum(1 for p in plans if p.get("health_status") == "needs_care"),
            "est_dana_total": sum(p["est_total"] for p in plans),
            "undecided": by_plan["undecided"],
            "return_home": by_plan["return_home"],
            "relocate": by_plan["relocate"],
            "people_by_plan": people_by_plan,
        },
    }


def _may_see_detail(disaster_event):
    from rescue_net.services.drill import is_simulation_event
    # tanpa bencana = data contoh lama; hanya ikut di tampilan simulasi (tampilan riil sudah membuangnya di atas)
    if not disaster_event or is_simulation_event(disaster_event):
        return True
    return _writer_ok(rn_actor(required=False), disaster_event)


def _writer_ok(actor, disaster_event=None, posko=None):
    """Siapa boleh menulis (dan melihat daftar per KK) rencana pengungsian. Temuan 24 Nov 2026: dulu SIAPA PUN yang
    login, juga di bencana riil, bisa membuat/mengubah/menyetujui rencana. Sekarang: System Manager; pengelola posko
    rencana itu; pengelola posko mana pun yang melayani bencananya; atau siapa pun yang login di bencana SIMULASI."""
    from rescue_net.access_policy import can_manage_posko, sim_open_event

    if is_system_manager():
        return True
    if not actor:
        return False
    if sim_open_event(actor, disaster_event):
        return True
    if posko and can_manage_posko(actor, posko):
        return True
    if disaster_event:
        from rescue_net.control_centre.common import serving_posko_names
        return any(can_manage_posko(actor, p) for p in serving_posko_names(disaster_event))
    return False


def _can_write(disaster_event=None, posko=None):
    actor = rn_actor(required=True)
    if not _writer_ok(actor, disaster_event, posko):
        frappe.throw("Hanya pengelola posko yang melayani bencana ini yang boleh mengisi rencana pengungsian.",
                     frappe.PermissionError)
    return actor


@frappe.whitelist()
def create_displacement_plan(disaster_event, origin_area, people_count,
                             household_code=None, current_location=None, in_camp=1,
                             posko=None, vulnerable_count=0, health_status="healthy",
                             plan_type="undecided", est_return_cost=0,
                             est_rebuild_support=0, support_needed=None,
                             supporting_org=None, notes=None):
    ev = _event(disaster_event)
    _can_write(ev, posko if posko and frappe.db.exists("RN Posko", posko) else None)
    doc = frappe.new_doc("RN Displacement Plan")
    doc.disaster_event = ev if ev and frappe.db.exists("RN Disaster Event", ev) else None
    if not doc.disaster_event:
        doc.disaster_event_legacy_id = disaster_event
    doc.household_code = household_code
    doc.origin_area = origin_area
    doc.current_location = current_location
    doc.in_camp = 1 if str(in_camp).lower() in ("1", "true", "yes", "on") else 0
    doc.posko = posko if posko and frappe.db.exists("RN Posko", posko) else None
    doc.people_count = cint(people_count)
    doc.vulnerable_count = cint(vulnerable_count)
    doc.health_status = health_status if health_status in _HEALTH_LABEL else "healthy"
    doc.plan_type = plan_type if plan_type in _PLAN_LABEL else "undecided"
    doc.est_return_cost = flt(est_return_cost)
    doc.est_rebuild_support = flt(est_rebuild_support)
    doc.support_needed = support_needed
    doc.supporting_org = supporting_org if supporting_org and frappe.db.exists("RN Organization", supporting_org) else None
    doc.status = "draft"
    doc.notes = notes
    doc.title = (household_code or origin_area or "KK") + " · " + _PLAN_LABEL.get(doc.plan_type, "")
    doc.insert(ignore_permissions=True)
    return {"plan": doc.name, "status": doc.status}


@frappe.whitelist()
def update_displacement_plan(plan, **kwargs):
    doc = frappe.get_doc("RN Displacement Plan", plan)
    _can_write(doc.disaster_event, doc.posko)
    if kwargs.get("posko") and kwargs["posko"] != doc.posko:   # memindah ke posko lain: harus pengelola posko tujuan juga
        _can_write(doc.disaster_event, kwargs["posko"])
    allowed = {"origin_area", "current_location", "posko", "household_code",
               "current_location", "support_needed", "supporting_org", "notes"}
    num = {"people_count", "vulnerable_count"}
    money = {"est_return_cost", "est_rebuild_support"}
    for k, v in (kwargs or {}).items():
        if v is None:
            continue
        if k in ("plan_type",) and v in _PLAN_LABEL:
            doc.plan_type = v
        elif k in ("health_status",) and v in _HEALTH_LABEL:
            doc.health_status = v
        elif k in ("status",) and v in _STATUS_LABEL:
            doc.status = v
        elif k == "in_camp":
            doc.in_camp = 1 if str(v).lower() in ("1", "true", "yes", "on") else 0
        elif k in num:
            doc.set(k, cint(v))
        elif k in money:
            doc.set(k, flt(v))
        elif k in allowed:
            doc.set(k, v)
    doc.title = (doc.household_code or doc.origin_area or "KK") + " · " + _PLAN_LABEL.get(doc.plan_type, "")
    doc.save(ignore_permissions=True)
    return {"plan": doc.name, "status": doc.status, "plan_type": doc.plan_type}
