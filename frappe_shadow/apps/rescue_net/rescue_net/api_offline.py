"""Offline outbox replay (owner 2026-10-19: field forms must work without signal).

A field form saved without a connection is kept on the phone by
assets/js/rn-offline-outbox.js with a client id, and sent here when the
signal returns. `replay` runs the SAME whitelisted method the form would
have called, as the logged-in user (all permission checks stay in that
method), exactly once per client id: the id is the unique `event_id` of an
RN Sync Log row written in the same transaction, so a second send of the
same item (flaky signal, two tabs) returns the stored result instead of
recording it twice. Only the field-form methods below may be replayed.
"""

import json
import re

import frappe
from frappe.utils import now_datetime

# dotted path the page calls -> short label for the sync log / outbox list
OFFLINE_METHODS = {
    "rescue_net.api_logistics.create_need": "Kebutuhan posko",
    "rescue_net.api_logistics.create_stock_observation": "Catat stok",
    "rescue_net.api_logistics.receive_aid_offer_and_update_stock": "Terima kiriman",
    "rescue_net.api_logistics.confirm_reported_need": "Konfirmasi kebutuhan",
    "rescue_net.api_control_centre.set_posko_beneficiary": "Jiwa dilayani",
    "rescue_net.api_medical.create_case": "Pasien baru",
    "rescue_net.api_medical.update_case_status": "Status pasien",
    "rescue_net.api_medical.record_supply_use": "Pemakaian obat/alat",
    "rescue_net.api_shelter.create_occupancy": "Okupansi shelter",
    "rescue_net.api_shelter.create_need": "Kebutuhan shelter",
    "rescue_net.api_kitchen.create_production": "Produksi dapur",
    "rescue_net.api_resource_tools.create_work_object": "Kondisi lapangan",
    "rescue_net.api_recovery.create_update": "Progres recovery",
}

_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{8,120}$")


def _json(value):
    try:
        return json.dumps(value, default=str, ensure_ascii=False)
    except Exception:
        return json.dumps(str(value))


@frappe.whitelist(methods=["POST"])
def replay(method, args=None, client_event_id=None, device_id=None, created_local_at=None):
    user = frappe.session.user
    if not user or user == "Guest":
        frappe.throw("Login diperlukan untuk mengirim data offline.", frappe.PermissionError)
    if method not in OFFLINE_METHODS:
        frappe.throw("Formulir ini tidak bisa dikirim lewat antrean offline.", frappe.PermissionError)
    eid = str(client_event_id or "").strip()
    if not _ID_RE.match(eid):
        frappe.throw("ID antrean offline tidak valid.")
    eid = "offline:" + eid

    done = frappe.db.get_value("RN Sync Log", {"event_id": eid},
                               ["source_user_id", "apply_result_json"], as_dict=True)
    if done:
        if done.source_user_id != user:
            frappe.throw("ID antrean offline milik pengguna lain.", frappe.PermissionError)
        try:
            result = json.loads(done.apply_result_json or "null")
        except ValueError:
            result = None
        return {"duplicate": True, "result": result}

    if isinstance(args, str):
        args = json.loads(args or "{}")
    if not isinstance(args, dict):
        frappe.throw("Isi antrean offline tidak valid.")
    args = {k: v for k, v in args.items() if k not in ("cmd", "csrf_token")}

    # claim the id first: the unique event_id makes a concurrent second send
    # fail here, and an error in the method rolls the claim back with it
    log = frappe.get_doc({
        "doctype": "RN Sync Log",
        "event_id": eid,
        "object_type": "offline_call",
        "operation": method,
        "source_user_id": user,
        "source_device_id": str(device_id or "")[:140] or None,
        "payload_json": _json(args),
        "apply_status": "accepted",
        "received_at": now_datetime(),
    })
    log.insert(ignore_permissions=True)

    fn = frappe.get_attr(method)
    frappe.is_whitelisted(fn)
    frappe.local.form_dict = frappe._dict(args)
    result = frappe.call(fn, **args)

    log.db_set({"apply_status": "applied", "apply_result_json": _json(result),
                "applied_at": now_datetime()}, update_modified=False)
    return {"duplicate": False, "result": result}



# ---------------------------------------------------------------------------
# Offline pack: after login the app downloads the current data of the user's
# own posko(s) and organisation(s), so it keeps working offline with the same
# screens. Each entry is the answer of the SAME read method the page calls,
# computed here as the logged-in user -> exactly the same permission checks;
# nothing the user could not open online ends up on the phone.
# ---------------------------------------------------------------------------

MAX_POSKO = 20

# (method, needs) — "posko" entries are called per posko, "event" per disaster event
PACK_POSKO = [
    ("rescue_net.api_control_centre.posko_detail", ("posko", "disaster_event")),
    ("rescue_net.api_control_centre.logistik_board", ("posko", "disaster_event")),
    ("rescue_net.api_control_centre.posko_contact", ("posko",)),
    ("rescue_net.api_control_centre.logistik_stock_sources", ("posko",)),
    ("rescue_net.api_verifier.posko_verification_public", ("posko",)),
    ("rescue_net.api_community_cluster.get_posko_settings", ("posko",)),
    ("rescue_net.api_logistics.dashboard", ("posko",)),
]
PACK_BY_TYPE = {
    "medical": [("rescue_net.api_medical.dashboard", ("posko",))],
    "shelter": [("rescue_net.api_shelter.dashboard", ("posko",))],
    "kitchen": [("rescue_net.api_kitchen.dashboard", ("posko",)),
                ("rescue_net.api_kitchen.kitchen_board", ("posko", "disaster_event"))],
    "transport": [("rescue_net.api_control_centre.posko_distribusi_board", ("posko", "disaster_event"))],
}
PACK_EVENT = [
    ("rescue_net.api_control_centre.event_poskos", ("disaster_event",)),
    ("rescue_net.api_control_centre.logistik_open_needs", ("disaster_event",)),
    ("rescue_net.api_control_centre.ecosystem_board", ("disaster_event",)),
    ("rescue_net.api_shelter.shelter_board", ("disaster_event",)),
    ("rescue_net.api_resource_tools.tools_board", ("disaster_event",)),
    ("rescue_net.api_resource_tools.work_objects_board", ("disaster_event",)),
    ("rescue_net.api_resource_tools.dashboard", ("disaster_event",)),
    ("rescue_net.api_recovery.recovery_board", ("disaster_event",)),
]
PACK_GLOBAL = [
    ("rescue_net.api_auth.session_info", ()),
    ("rescue_net.api_control_centre.active_disasters_board", ()),
]


def _my_poskos(actor):
    """Posko the user works for: approved posko assignments first, then every
    posko of the organisations they are an approved member of."""
    from rescue_net.access_policy import is_system_manager

    names = []
    if actor and actor.get("name"):
        names += frappe.get_all("RN Posko Assignment",
                                filters={"user_account": actor.name, "status": "approved"}, pluck="posko")
        orgs = frappe.get_all("RN Organization Membership",
                              filters={"user_account": actor.name, "status": "approved"}, pluck="organization")
        if actor.get("organization"):
            orgs.append(actor.organization)
        if orgs:
            names += frappe.get_all("RN Posko", filters={"organization": ["in", list(set(orgs))]},
                                    pluck="name", order_by="modified desc", limit_page_length=MAX_POSKO * 2)
        if actor.get("posko"):
            names.insert(0, actor.posko)
    if not names and is_system_manager():
        active = frappe.get_all("RN Disaster Event", filters={"event_status": ["in", ["active", "aktif"]]}, pluck="name")
        if active:
            names = frappe.get_all("RN Posko", filters={"disaster_event": ["in", active]}, pluck="name",
                                   order_by="modified desc", limit_page_length=MAX_POSKO)
    seen, out = set(), []
    for n in names:
        if n and n not in seen and frappe.db.exists("RN Posko", n):
            seen.add(n)
            out.append(n)
    return out[:MAX_POSKO]


def _run(method, args):
    fn = frappe.get_attr(method)
    while hasattr(fn, "__wrapped__"):          # skip @rate_limit: one pack = many reads
        fn = fn.__wrapped__
    frappe.local.form_dict = frappe._dict(args)
    return fn(**args)


@frappe.whitelist()
def pack(offset=0, limit=0):
    """All data of the user's posko/organisation for offline work.
    The app downloads it in parts (offset/limit) to show progress; limit=0
    returns everything at once. `total` = number of entries in the plan."""
    from rescue_net.access_policy import rn_actor
    from rescue_net.services.drill import drill_event_names

    user = frappe.session.user
    if not user or user == "Guest":
        frappe.throw("Login diperlukan untuk mengunduh data offline.", frappe.PermissionError)
    actor = rn_actor(required=False)
    mine = _my_poskos(actor)
    poskos = frappe.get_all("RN Posko", filters={"name": ["in", mine]},
                            fields=["name", "title", "disaster_event", "posko_type", "organization"],
                            limit_page_length=MAX_POSKO) if mine else []
    drills = drill_event_names()
    events = []
    from rescue_net.control_centre.common import posko_served_events

    for p in poskos:
        for ev in posko_served_events(p.name):        # every disaster the posko serves
            if ev and ev not in events and ev not in drills:
                events.append(ev)

    plan = [(method, {}) for method, _ in PACK_GLOBAL]
    for e in events:
        plan += [(method, {"disaster_event": e}) for method, _ in PACK_EVENT]
    for p in poskos:
        extra = PACK_BY_TYPE.get(str(p.posko_type or "").lower(), [])
        for method, needs in PACK_POSKO + extra:
            args = {"posko": p.name}
            if "disaster_event" in needs and p.disaster_event:
                args["disaster_event"] = p.disaster_event
            plan.append((method, args))

    offset, limit = max(0, int(offset or 0)), max(0, int(limit or 0))
    part = plan[offset:offset + limit] if limit else plan[offset:]
    entries, skipped = [], 0
    for method, args in part:
        frappe.db.savepoint("rn_pack")
        try:
            entries.append({"method": method, "args": args, "data": _run(method, args)})
        except Exception:
            frappe.db.rollback(save_point="rn_pack")
            frappe.local.message_log = []
            skipped += 1                       # not allowed / not applicable for this posko

    orgs = sorted({p.organization for p in poskos if p.organization})
    return {
        "user": user,
        "generated_at": now_datetime(),
        "poskos": [{"name": p.name, "title": p.title, "posko_type": p.posko_type,
                    "disaster_event": p.disaster_event} for p in poskos],
        "organizations": [{"name": o, "title": frappe.db.get_value("RN Organization", o, "title")} for o in orgs],
        "events": events,
        "total": len(plan),
        "offset": offset,
        "next_offset": offset + len(part) if offset + len(part) < len(plan) else None,
        "entries": entries,
        "skipped": skipped,
    }
