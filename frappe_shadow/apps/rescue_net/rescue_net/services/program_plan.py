"""Program Khusus implementation plan: milestones, locations, needs, support, output verification.

Everything here is derived from rows the owner keeps (RN Program Milestone /
Location / Need + the output fields on RN Donor Program) — no estimates.
"""

from collections import defaultdict

import frappe
from frappe.utils import flt, nowdate

SUPPORT_KINDS = ("logistik", "distribusi", "relawan", "alat_kerja")
SUPPORT_LABEL = {"logistik": "Support Logistik", "distribusi": "Support Distribusi",
                 "relawan": "Support Relawan", "alat_kerja": "Support Alat Kerja"}
MS_FIELDS = ["name", "program", "title", "sort_order", "due_date", "milestone_status", "progress_percent", "completed_at"]
LOC_FIELDS = ["name", "program", "title", "latitude", "longitude", "location_status", "served_at"]
NEED_FIELDS = ["name", "program", "item", "kind", "qty_needed", "qty_available", "unit", "needed_by"]


def _rows(doctype, fields, programs):
    if not programs:
        return []
    return frappe.get_all(doctype, filters={"program": ["in", list(programs)]}, fields=fields,
                          order_by="sort_order asc, creation asc" if doctype == "RN Program Milestone" else "creation asc",
                          limit_page_length=5000, ignore_permissions=True)


def is_late(ms, today=None):
    today = today or nowdate()
    return bool(ms.get("due_date") and ms.get("milestone_status") != "selesai" and str(ms["due_date"]) < str(today))


def shortfall(need):
    return max(0.0, flt(need.get("qty_needed")) - flt(need.get("qty_available")))


def support_cards(needs):
    """Four support cards from needs of that kind: status + biggest gaps."""
    cards = {}
    for kind in SUPPORT_KINDS:
        mine = [n for n in needs if n.get("kind") == kind]
        gaps = sorted((n for n in mine if shortfall(n) > 0), key=shortfall, reverse=True)
        cards[kind] = {
            "label": SUPPORT_LABEL[kind],
            "status": "butuh_support" if gaps else ("terpenuhi" if mine else "tidak_ada"),
            "items": [{"item": n["item"], "qty": shortfall(n), "unit": n.get("unit")} for n in gaps[:3]],
        }
    return cards


def plan_for(program, row=None):
    """Full plan of one program (detail view)."""
    ms = _rows("RN Program Milestone", MS_FIELDS, [program])
    locs = _rows("RN Program Location", LOC_FIELDS, [program])
    needs = _rows("RN Program Need", NEED_FIELDS, [program])
    served = [l for l in locs if l["location_status"] == "terlayani"]
    out = {
        "milestones": [{**m, "is_late": is_late(m)} for m in ms],
        "locations": locs,
        "location_totals": {"total": len(locs), "served": len(served), "unserved": len(locs) - len(served)},
        "needs": [{**n, "shortfall": shortfall(n)} for n in needs if n["kind"] == "material"],
        "all_needs": [{**n, "shortfall": shortfall(n)} for n in needs],
        "support": support_cards(needs),
    }
    if row:
        out["verification"] = {
            "status": row.get("output_verification_status") or None,
            "output_target": row.get("output_target"),
            "output_verified": row.get("output_verified"),
            "verifier": row.get("output_verifier"),
            "estimated_done": row.get("output_estimated_done"),
        }
    return out


def board_stats(programs):
    """Per-program counts for the board: {program: {late, unserved, gap, ms, loc}}."""
    names = [p for p in programs]
    ms, locs, needs = (_rows("RN Program Milestone", MS_FIELDS, names), _rows("RN Program Location", LOC_FIELDS, names),
                       _rows("RN Program Need", NEED_FIELDS, names))
    st = defaultdict(lambda: {"milestones": 0, "late_milestones": 0, "locations": 0, "unserved_locations": [], "support_gap": False})
    for m in ms:
        s = st[m["program"]]
        s["milestones"] += 1
        s["late_milestones"] += 1 if is_late(m) else 0
    for l in locs:
        s = st[l["program"]]
        s["locations"] += 1
        if l["location_status"] != "terlayani":
            s["unserved_locations"].append(l["title"])
    for n in needs:
        if n["kind"] in SUPPORT_KINDS and shortfall(n) > 0:
            st[n["program"]]["support_gap"] = True
    return st
