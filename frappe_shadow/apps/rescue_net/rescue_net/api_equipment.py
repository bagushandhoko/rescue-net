"""Posko Alat Kerja / Support (owner 2026-11-03): "posko alat kerja/support semacam logistik tapi lebih ke data
lebih detail secara speks: dari alat berat, tenda, perahu karet, genset dll".

A posko of type `equipment` keeps an inventory of tools (RN Resource Profile, owner_type=posko) with detailed
specifications per category (services/equipment_specs.py). The workspace shows the inventory grouped by
category group, what is out on deployment, and the open tool requests of the disaster it can serve.

- posko_equipment (guest): posko card, inventory with specs (serial number / plate only for its managers),
  summary per group, deployments of its tools, matching open requests, PIC contact under the posko share rule.
- save_equipment (manager of the posko): add / edit one tool with specs; photos via
  api_recovery_support.upload_tool_photo; withdraw via api_recovery_support.withdraw_tool.
"""

import frappe
from frappe.rate_limiter import rate_limit
from frappe.utils import flt

from rescue_net.access_policy import can_manage_posko, rn_actor
from rescue_net.reference_resolver import resolve_posko
from rescue_net.services import equipment_specs

POSKO_TYPE = "equipment"
_ACTIVE_DEPLOY = {"reserved", "deployed", "in_use"}
_DEPLOY_LABEL = {"reserved": "Dipesan", "deployed": "Dikirim", "in_use": "Dipakai", "completed": "Selesai",
                 "returned": "Kembali", "cancelled": "Batal"}


def _posko(posko):
    name = resolve_posko(posko) if posko else None
    p = frappe.db.get_value("RN Posko", name, ["name", "title", "posko_type", "disaster_event", "organization", "address",
                                               "province_name", "city_name", "latitude", "longitude",
                                               "officer_in_charge_name", "officer_in_charge_role",
                                               "officer_in_charge_phone", "officer_in_charge_whatsapp"],
                            as_dict=True) if name else None
    if not p:
        frappe.throw("Posko tidak ditemukan.")
    return p


def _rows(posko_name):
    from rescue_net.api_recovery_support import _PUBLIC_TOOL
    return frappe.get_all("RN Resource Profile", filters={"owner_type": "posko", "owner_id": posko_name},
                          fields=_PUBLIC_TOOL + ["serial_number"], order_by="category asc, resource_name asc",
                          limit_page_length=2000)


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def posko_equipment(posko):
    from rescue_net.api_recovery_support import _tool_public
    from rescue_net.resource_tools.boards import _posko_contacts
    from rescue_net.visibility import posko_contacts_visible

    p = _posko(posko)
    if p.disaster_event:
        from rescue_net.services.drill import real_rows
        if not real_rows([frappe._dict(disaster_event=p.disaster_event)]):
            frappe.throw("Posko tidak ditemukan.")
    actor = rn_actor(required=False)
    manage = bool(actor) and can_manage_posko(actor, p.name)
    rows = _rows(p.name)
    codes = [r.name for r in rows]
    deploys = frappe.get_all("RN Work Tool Deployment", filters={"resource_profile": ["in", codes]},
                             fields=["name", "resource_profile", "quantity_assigned", "deployment_status",
                                     "destination_location", "operator_name", "deployed_at", "completed_at"],
                             order_by="creation desc", limit_page_length=500) if codes else []
    out_qty = {}
    for d in deploys:
        if d.deployment_status in _ACTIVE_DEPLOY:
            out_qty[d.resource_profile] = out_qty.get(d.resource_profile, 0) + (flt(d.quantity_assigned) or 1)

    tools, groups = [], {}
    for r in rows:
        t = _tool_public(r)
        t["serial_number"] = r.serial_number if manage else None
        t["deployed_qty"] = out_qty.get(r.name, 0)
        t["group"] = equipment_specs.CATALOG.get(r.category, equipment_specs.CATALOG["lainnya"])[1]
        tools.append(t)
        g = groups.setdefault(t["group"], {"group": t["group"], "items": 0, "units": 0.0, "ready": 0.0, "deployed": 0.0,
                                           "repair": 0})
        g["items"] += 1
        g["units"] += flt(r.quantity) or 1
        g["deployed"] += t["deployed_qty"]
        if r.availability_status == "available":
            g["ready"] += max(0.0, (flt(r.quantity) or 1) - t["deployed_qty"])
        if r.availability_status in ("maintenance", "unavailable") or r.tool_condition in ("rusak_ringan", "rusak_berat"):
            g["repair"] += 1
    order = equipment_specs.GROUP_ORDER
    summary = sorted(groups.values(), key=lambda g: order.index(g["group"]) if g["group"] in order else 99)

    names = {r.name: r.resource_name for r in rows}
    dispatch = [{
        "resource": d.resource_profile, "tool_name": names.get(d.resource_profile), "quantity": d.quantity_assigned,
        "status": d.deployment_status, "status_label": _DEPLOY_LABEL.get(d.deployment_status, d.deployment_status),
        "destination": d.destination_location, "operator": d.operator_name, "deployed_at": d.deployed_at,
        "completed_at": d.completed_at,
    } for d in deploys]

    cats = {r.category for r in rows if r.category}
    requests = []
    if p.disaster_event:
        for q in frappe.get_all("RN Work Tool Request",
                                filters={"disaster_event": p.disaster_event, "request_status": "requested"},
                                fields=["name", "tool_name", "tool_type", "quantity", "unit", "location", "priority",
                                        "needed_for"], order_by="creation desc", limit_page_length=200):
            q["can_serve"] = q.tool_type in cats
            requests.append(q)
        requests.sort(key=lambda q: (not q["can_serve"],))

    contacts_ok = manage or posko_contacts_visible(p.name, actor)
    org_title = frappe.db.get_value("RN Organization", p.organization, "title") if p.organization else None
    return {
        "posko": {
            "name": p.name, "title": p.title, "posko_type": p.posko_type, "disaster_event": p.disaster_event,
            "address": p.address, "area": ", ".join(x for x in (p.city_name, p.province_name) if x),
            "latitude": p.latitude, "longitude": p.longitude,
            "organization": p.organization, "organization_title": org_title,
            "is_equipment_posko": (p.posko_type or "") == POSKO_TYPE,
        },
        "contacts": _posko_contacts(p, include_accounts=bool(actor)) if contacts_ok else [],
        "contact_locked": not contacts_ok,
        "can_manage": manage,
        "tools": tools,
        "summary": summary,
        "totals": {"items": len(tools), "units": sum(g["units"] for g in summary),
                   "ready": sum(g["ready"] for g in summary), "deployed": sum(g["deployed"] for g in summary),
                   "repair": sum(g["repair"] for g in summary)},
        "dispatch": dispatch,
        "requests": requests,
    }


@frappe.whitelist()
def equipment_catalog():
    return {"catalog": equipment_specs.catalog(),
            "conditions": [{"value": k, "label": v} for k, v in equipment_specs.CONDITIONS.items()]}


@frappe.whitelist(methods=["POST"])
def save_equipment(posko, resource_profile=None, **fields):
    from rescue_net.api_recovery_support import _tool_values

    actor = rn_actor()
    p = _posko(posko)
    if not can_manage_posko(actor, p.name):
        frappe.throw("Hanya pengelola posko ini yang boleh mengubah inventaris alat.", frappe.PermissionError)
    fields.pop("cmd", None)
    if resource_profile:
        doc = frappe.get_doc("RN Resource Profile", resource_profile)
        if doc.owner_type != "posko" or doc.owner_id != p.name:
            frappe.throw("Alat ini bukan milik posko ini.", frappe.PermissionError)
        doc.update(_tool_values(dict(fields, _category=doc.category), partial=True))
        doc.save(ignore_permissions=True)
    else:
        fields.setdefault("category", "lainnya")
        fields.setdefault("availability_status", "available")
        values = _tool_values(fields, partial=False)
        doc = frappe.new_doc("RN Resource Profile")
        doc.update(values)
        doc.disaster_event = p.disaster_event
        doc.owner_type = "posko"
        doc.owner_id = p.name
        doc.resource_type = values.get("category")
        doc.unit = values.get("unit") or equipment_specs.CATALOG.get(values.get("category"), ("", "", "unit"))[2]
        doc.quantity = values.get("quantity") or 1
        doc.current_location = doc.current_location or p.address or p.title
        doc.offered_by_user = actor.get("name")
        doc.verification_status = "self_reported"
        doc.insert(ignore_permissions=True)
    return {"resource_profile": doc.name}


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def equipment_poskos(disaster_event=None):
    """Poskos to pick on posko-alat.html: every `equipment` posko of the disaster plus any other posko that keeps
    tools of its own; with item / unit counts. The viewer's own manageable poskos come first."""
    from rescue_net.reference_resolver import resolve_disaster_event
    from rescue_net.services.drill import real_rows

    event = resolve_disaster_event(disaster_event) if disaster_event else None
    pf = {"posko_type": POSKO_TYPE}
    if event:
        pf["disaster_event"] = event
    poskos = {p.name: p for p in frappe.get_all("RN Posko", filters=pf,
                                                fields=["name", "title", "posko_type", "disaster_event", "address"],
                                                limit_page_length=500)}
    rf = {"owner_type": "posko"}
    if event:
        rf["disaster_event"] = event
    counts = {}
    for r in frappe.get_all("RN Resource Profile", filters=rf, fields=["owner_id", "quantity"], limit_page_length=5000):
        c = counts.setdefault(r.owner_id, {"items": 0, "units": 0.0})
        c["items"] += 1
        c["units"] += flt(r.quantity) or 1
    missing = [n for n in counts if n and n not in poskos]
    if missing:
        for p in frappe.get_all("RN Posko", filters={"name": ["in", missing]},
                                fields=["name", "title", "posko_type", "disaster_event", "address"]):
            poskos[p.name] = p
    rows = real_rows(list(poskos.values()))
    actor = rn_actor(required=False)
    out = []
    for p in rows:
        c = counts.get(p.name, {"items": 0, "units": 0})
        out.append({"name": p.name, "title": p.title, "posko_type": p.posko_type, "address": p.address,
                    "is_equipment_posko": p.posko_type == POSKO_TYPE, "items": c["items"], "units": c["units"],
                    "can_manage": bool(actor) and can_manage_posko(actor, p.name)})
    out.sort(key=lambda x: (not x["can_manage"], not x["is_equipment_posko"], -x["items"], x["title"] or ""))
    return {"disaster_event": event, "poskos": out}
