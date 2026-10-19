"""Control Centre — Back Office Penanganan (owner 2026-10-19).

One disaster, seen from the support side: WHO is helping (4W "who does what
where"), grouped into Pemerintah / Organisasi Masyarakat / Masyarakat Umum /
Program Donasi, WHAT each brings (posko, relawan, sumbangan, peralatan, dana)
and the GAP between what posko need and what the ecosystem has delivered or
has on the way.

Guest-readable on purpose, like org_posko_board: only organisation names and
counts/totals. Never a person's name, phone, e-mail or a donor's identity —
private people are only counted. Drill events are refused for guests by the
global before_request guard (services/drill.py).
"""

import frappe
from frappe.rate_limiter import rate_limit

from rescue_net.control_centre.common import (  # noqa: F401
    _DRILL_CLOSED_NEED,
    _POSKO_INACTIVE_TERMS,
    _num,
    canonical_event,
)

GOV_TYPES = {"government", "pemerintah", "gov", "tni", "polri", "bpbd", "basarnas"}
GROUPS = [
    ("pemerintah", "Pemerintah"),
    ("organisasi", "Organisasi Masyarakat & Lembaga"),
    ("masyarakat", "Masyarakat Umum"),
    ("program", "Program Donasi"),
]
_OFFER_DONE = {"received", "received_verified"}
_OFFER_DEAD = {"cancelled", "rejected", "expired"}
_TOOL_REQ_OPEN = {"requested", "approved", "partially_fulfilled", "open", "pending"}


def _group_of_type(org_type):
    return "pemerintah" if str(org_type or "").strip().lower() in GOV_TYPES else "organisasi"


def _account_orgs(account_names):
    """RN User Account -> organisation (legacy field, else first approved membership)."""
    names = [a for a in set(account_names) if a]
    if not names:
        return {}
    out = {r.name: r.organization for r in frappe.get_all(
        "RN User Account", filters={"name": ["in", names]},
        fields=["name", "organization"], limit_page_length=len(names) + 1) if r.organization}
    missing = [a for a in names if a not in out]
    if missing:
        for m in frappe.get_all(
            "RN Organization Membership",
            filters={"user_account": ["in", missing], "status": "approved"},
            fields=["user_account", "organization"], order_by="creation asc",
            limit_page_length=5000,
        ):
            out.setdefault(m.user_account, m.organization)
    return out


def _new_org_row(org):
    return {
        "name": org.name, "title": org.title or org.name,
        "organization_type": org.organization_type,
        "verification_status": org.verification_status or "self_reported",
        "posko": 0, "posko_aktif": 0, "relawan": 0, "sumbangan": 0,
        "sumbangan_diterima": 0, "peralatan": 0, "peralatan_unit": 0.0,
        "program": 0, "dana_terkumpul": 0.0,
        "poskos": [],
    }


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=60, seconds=60)
def ecosystem_board(disaster_event):
    event = canonical_event(disaster_event)
    if not event or not frappe.db.exists("RN Disaster Event", event):
        frappe.throw("Bencana tidak ditemukan.", frappe.DoesNotExistError)

    ev = frappe.db.get_value("RN Disaster Event", event, ["title", "event_status"], as_dict=True) or {}

    # ---- posko -> organisation ------------------------------------------
    poskos = frappe.get_all(
        "RN Posko", filters={"disaster_event": event},
        fields=["name", "title", "organization", "posko_type", "operational_status",
                "rn_beneficiary_count"],
        limit_page_length=2000,
    )
    posko_names = [p.name for p in poskos]
    posko_org = {p.name: p.organization for p in poskos}

    org_names = {p.organization for p in poskos if p.organization}
    # organisations that only own resources / programs for this event
    for r in frappe.get_all("RN Resource Profile",
                            filters={"disaster_event": event, "owner_type": "organization"},
                            pluck="owner_id", limit_page_length=2000):
        if r:
            org_names.add(r)
    programs = frappe.get_all(
        "RN Donor Program", filters={"disaster_event": event},
        fields=["name", "program_name", "program_type", "owner_type", "owner_id", "status",
                "budget_target", "budget_received", "budget_spent", "target_beneficiaries"],
        limit_page_length=500,
    )
    for p in programs:
        if p.owner_type == "organization" and p.owner_id:
            org_names.add(p.owner_id)

    orgs = {}
    if org_names:
        for o in frappe.get_all(
            "RN Organization", filters={"name": ["in", list(org_names)]},
            fields=["name", "title", "organization_type", "verification_status"],
            limit_page_length=1000,
        ):
            orgs[o.name] = _new_org_row(o)

    groups = {k: {"key": k, "label": lbl, "orgs": 0, "posko": 0, "relawan": 0, "sumbangan": 0,
                  "sumbangan_diterima": 0, "peralatan": 0, "peralatan_unit": 0.0,
                  "program": 0, "dana_terkumpul": 0.0} for k, lbl in GROUPS}

    def bump(org_name, field, n=1):
        """Add to the org row (when it is a known org) and to its group;
        anything without an organisation counts for Masyarakat Umum."""
        row = orgs.get(org_name) if org_name else None
        if row:
            row[field] += n
            groups[_group_of_type(row["organization_type"])][field] += n
        else:
            groups["masyarakat"][field] += n

    for p in poskos:
        row = orgs.get(p.organization)
        active = str(p.operational_status or "").lower() not in _POSKO_INACTIVE_TERMS
        bump(p.organization, "posko")
        if row:
            row["posko_aktif"] += 1 if active else 0
            row["poskos"].append({"name": p.name, "title": p.title, "posko_type": p.posko_type,
                                  "href": "posko-detail.html?id=" + p.name})

    # ---- relawan ---------------------------------------------------------
    vols = frappe.get_all(
        "RN Volunteer Profile", filters={"disaster_event": event},
        fields=["user_account", "assigned_posko", "availability_status", "skill_category"],
        limit_page_length=5000,
    )
    acc_org = _account_orgs([v.user_account for v in vols])
    skills = {}
    vol_available = 0
    for v in vols:
        org = acc_org.get(v.user_account) or posko_org.get(v.assigned_posko)
        bump(org, "relawan")
        skills[v.skill_category or "Lainnya"] = skills.get(v.skill_category or "Lainnya", 0) + 1
        if str(v.availability_status or "") == "available":
            vol_available += 1

    # ---- sumbangan barang (aid offers) to this event's poskos -------------
    offer_filters = {"target_posko": ["in", posko_names]} if posko_names else {"disaster_event": event}
    offers = frappe.get_all(
        "RN Aid Offer", filters=offer_filters,
        fields=["donor_user", "item_name", "canonical_item", "quantity", "unit", "offer_status"],
        limit_page_length=5000,
    )
    off_org = _account_orgs([o.donor_user for o in offers])
    incoming = {}
    for o in offers:
        st = str(o.offer_status or "").lower()
        if st in _OFFER_DEAD:
            continue
        org = off_org.get(o.donor_user)
        bump(org, "sumbangan")
        if st in _OFFER_DONE:
            bump(org, "sumbangan_diterima")
        else:
            key = (str(o.canonical_item or o.item_name or "").strip().lower(), str(o.unit or "").strip().lower())
            incoming[key] = incoming.get(key, 0.0) + _num(o.quantity)

    # ---- peralatan (resource profiles) ------------------------------------
    tools_by_cat = {}
    for r in frappe.get_all(
        "RN Resource Profile", filters={"disaster_event": event},
        fields=["owner_type", "owner_id", "category", "quantity", "availability_status"],
        limit_page_length=5000,
    ):
        org = r.owner_id if r.owner_type == "organization" else None
        bump(org, "peralatan")
        bump(org, "peralatan_unit", _num(r.quantity) or 1.0)
        cat = str(r.category or "lainnya").lower()
        t = tools_by_cat.setdefault(cat, {"category": cat, "tersedia": 0.0, "diminta": 0.0, "dikerahkan": 0.0})
        t["tersedia"] += _num(r.quantity) or 1.0

    # tools asked for vs deployed (Kebutuhan Alat Kerja)
    reqs = frappe.get_all(
        "RN Work Tool Request", filters={"disaster_event": event},
        fields=["name", "tool_type", "tool_name", "quantity", "request_status"],
        limit_page_length=2000,
    )
    deployed = {}
    if reqs:
        for d in frappe.get_all(
            "RN Work Tool Deployment",
            filters={"work_tool_request": ["in", [r.name for r in reqs]],
                     "deployment_status": ["not in", ["cancelled", "returned_cancelled"]]},
            fields=["work_tool_request", "quantity_assigned"], limit_page_length=5000,
        ):
            deployed[d.work_tool_request] = deployed.get(d.work_tool_request, 0.0) + _num(d.quantity_assigned)
    for r in reqs:
        if str(r.request_status or "").lower() in {"cancelled", "rejected"}:
            continue
        cat = str(r.tool_type or r.tool_name or "lainnya").lower()
        t = tools_by_cat.setdefault(cat, {"category": cat, "tersedia": 0.0, "diminta": 0.0, "dikerahkan": 0.0})
        t["diminta"] += _num(r.quantity) or 1.0
        t["dikerahkan"] += deployed.get(r.name, 0.0)

    # ---- program donasi ---------------------------------------------------
    prog_rows = []
    for p in programs:
        groups["program"]["program"] += 1
        groups["program"]["dana_terkumpul"] += _num(p.budget_received)
        owner = orgs.get(p.owner_id) if p.owner_type == "organization" else None
        if owner:
            owner["program"] += 1
            owner["dana_terkumpul"] += _num(p.budget_received)
        target = _num(p.budget_target)
        received = _num(p.budget_received)
        prog_rows.append({
            "name": p.name, "title": p.program_name, "type": p.program_type, "status": p.status,
            "owner": owner["title"] if owner else ("Komunitas / posko" if p.owner_type else "-"),
            "target": target, "received": received, "spent": _num(p.budget_spent),
            "gap": max(0.0, target - received),
            "percent": round(received / target * 100, 1) if target else None,
            "href": "donor-program.html?id=" + p.name,
        })
    prog_rows.sort(key=lambda r: -r["gap"])
    for k in groups:
        if k != "program":
            groups[k]["orgs"] = sum(1 for o in orgs.values() if _group_of_type(o["organization_type"]) == k)

    # ---- gap kebutuhan barang ---------------------------------------------
    need_gap = {}
    if posko_names:
        for n in frappe.get_all(
            "RN Logistic Need", filters={"posko": ["in", posko_names]},
            fields=["item_name", "canonical_item", "quantity", "unit", "need_status", "urgency", "legacy_payload"],
            limit_page_length=5000,
        ):
            if str(n.need_status or "open").lower() in _DRILL_CLOSED_NEED:
                continue
            realized = 0.0
            p = n.legacy_payload
            if isinstance(p, str) and p.strip():
                try:
                    p = frappe.parse_json(p) or {}
                    realized = _num(p.get("realized_quantity"))
                    req = _num(p.get("required_quantity") or n.quantity)
                except Exception:
                    req = _num(n.quantity)
            else:
                req = _num(n.quantity)
            label = n.item_name or n.canonical_item or "-"
            key = (str(n.canonical_item or n.item_name or "").strip().lower(), str(n.unit or "").strip().lower())
            g = need_gap.setdefault(key, {"item": label, "unit": n.unit, "dibutuhkan": 0.0, "terpenuhi": 0.0,
                                         "menuju": 0.0, "kritis": False, "posko": 0})
            g["dibutuhkan"] += req
            g["terpenuhi"] += realized
            g["posko"] += 1
            if str(n.urgency or "").lower() in {"critical", "urgent", "high"}:
                g["kritis"] = True
    for key, g in need_gap.items():
        g["menuju"] = incoming.get(key, 0.0)
        g["gap"] = max(0.0, g["dibutuhkan"] - g["terpenuhi"] - g["menuju"])
        g["percent"] = round(min(100.0, (g["terpenuhi"] + g["menuju"]) / g["dibutuhkan"] * 100), 1) if g["dibutuhkan"] else None
    needs = sorted(need_gap.values(), key=lambda g: (0 if g["kritis"] else 1, -g["gap"]))

    tools = []
    for t in tools_by_cat.values():
        t["gap"] = max(0.0, t["diminta"] - t["dikerahkan"])
        tools.append(t)
    tools.sort(key=lambda t: (-t["gap"], -t["tersedia"]))

    org_list = sorted(orgs.values(), key=lambda o: (_group_of_type(o["organization_type"]) != "pemerintah",
                                                    -(o["posko"] + o["relawan"] + o["peralatan"])))
    for o in org_list:
        o["group"] = _group_of_type(o["organization_type"])
        o["href"] = "organisasi-posko.html?org=" + o["name"]

    return {
        "disaster_event": event,
        "event_title": ev.get("title"),
        "event_status": ev.get("event_status"),
        "generated_at": frappe.utils.now_datetime(),
        "totals": {
            "pihak": len(orgs),
            "posko": len(poskos),
            "jiwa_dilayani": int(sum(_num(p.rn_beneficiary_count) for p in poskos)),
            "relawan": len(vols),
            "relawan_siaga": vol_available,
            "sumbangan": sum(g["sumbangan"] for g in groups.values()),
            "peralatan": sum(g["peralatan"] for g in groups.values()),
            "program": len(programs),
            "dana_terkumpul": groups["program"]["dana_terkumpul"],
            "kebutuhan_terbuka": len(needs),
            "kebutuhan_gap": sum(1 for g in needs if g["gap"] > 0),
        },
        "groups": [groups[k] for k, _ in GROUPS],
        "orgs": org_list,
        "relawan_keahlian": sorted(({"skill": k, "count": v} for k, v in skills.items()), key=lambda r: -r["count"]),
        "needs": needs[:60],
        "tools": tools[:40],
        "programs": prog_rows[:40],
    }
