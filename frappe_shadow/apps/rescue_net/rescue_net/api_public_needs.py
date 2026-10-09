"""Public needs board for donors (Fase 10f, tahap 1 — derived only).

Per PUBLIC posko, per (item, unit):
    kurang = kebutuhan terbuka − stok tersedia − kiriman dalam perjalanan
kurang > 0  -> "dibutuhkan"; kurang <= 0 -> "sudah cukup / jangan kirim lagi".
Deterministic (same rule on every screen, no AI). Guests see only posko that
pass public_posko_allowed, with titles and regions — never contacts, reporters
or free-text notes.
"""

from collections import defaultdict

import frappe
from frappe.rate_limiter import rate_limit
from frappe.utils import flt

from rescue_net.access_policy import public_posko_allowed
from rescue_net.control_centre.common import _CLOSED_NEED, canonical_event

_FLOW_DONE = {"received", "cancelled"}


def _key(row):
    item = (row.get("canonical_item") or row.get("item_name") or "").strip().lower()
    unit = (row.get("unit") or "").strip().lower()
    return item, unit


def _event_filter(event):
    ev = canonical_event(event) if event else None
    return {"disaster_event": ev} if ev else {}


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=60, seconds=60)
def board(event=None, wilayah=None):
    ef = _event_filter(event)
    pf = {"public_detail": "public", **ef}
    poskos = [
        p for p in frappe.get_all(
            "RN Posko", filters=pf,
            fields=["name", "title", "city_name", "province_name", "disaster_event"],
            limit_page_length=500)
        if public_posko_allowed(p.name)
    ]
    names = [p.name for p in poskos]
    if not names:
        return {"event": event, "needs": [], "enough": [], "poskos": 0}

    needs = defaultdict(float)
    meta = {}
    for n in frappe.get_all(
            "RN Logistic Need", filters={"posko": ["in", names]},
            fields=["posko", "item_name", "canonical_item", "unit", "quantity",
                    "need_status", "urgency", "modified"],
            limit_page_length=5000):
        if str(n.need_status or "open").lower() in _CLOSED_NEED or flt(n.quantity) <= 0:
            continue
        k = (n.posko,) + _key(n)
        needs[k] += flt(n.quantity)
        m = meta.setdefault(k, {"item": n.canonical_item or n.item_name, "unit": n.unit,
                                "urgency": "", "modified": n.modified})
        if str(n.urgency or "").lower() == "critical":
            m["urgency"] = "critical"
        if n.modified and n.modified > m["modified"]:
            m["modified"] = n.modified

    stock = defaultdict(float)
    for s in frappe.get_all(
            "RN Stock Observation",
            filters={"posko": ["in", names], "stock_state": "available"},
            fields=["posko", "item_name", "canonical_item", "unit", "quantity"],
            limit_page_length=5000):
        stock[(s.posko,) + _key(s)] += flt(s.quantity)

    incoming = defaultdict(float)
    for f in frappe.get_all(
            "RN Distribution Flow",
            filters={"destination_posko": ["in", names],
                     "flow_status": ["not in", list(_FLOW_DONE)]},
            fields=["destination_posko", "item_name", "canonical_item", "unit", "quantity"],
            limit_page_length=5000):
        incoming[(f.destination_posko,) + _key(f)] += flt(f.quantity)

    pk = {p.name: p for p in poskos}
    want, enough = [], []
    for k, need_qty in needs.items():
        gap = need_qty - stock.get(k, 0) - incoming.get(k, 0)
        m, p = meta[k], pk[k[0]]
        region = ", ".join(x for x in (p.city_name, p.province_name) if x)
        if wilayah and wilayah.strip().lower() not in region.lower():
            continue
        row = {
            "item": m["item"], "unit": m["unit"], "posko": p.name,
            "posko_title": p.title or p.name, "region": region,
            "critical": m["urgency"] == "critical",
            "updated_at": str(m["modified"]),
            "href": "kirim-bantuan.html?posko=" + p.name,
        }
        if gap > 0:
            row["gap"] = round(gap, 2)
            want.append(row)
        else:
            enough.append(row)
    want.sort(key=lambda r: (not r["critical"], -r["gap"]))
    return {"event": event, "needs": want[:300], "enough": enough[:300],
            "poskos": len(poskos)}
