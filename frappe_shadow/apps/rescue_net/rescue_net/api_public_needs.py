"""Public needs board for donors (Fase 10f, tahap 1 — derived only).

Per PUBLIC posko, per (item, unit):
    kurang = kebutuhan terbuka − stok tersedia − kiriman dalam perjalanan
kurang > 0  -> "dibutuhkan"; kurang <= 0 -> "sudah cukup / jangan kirim lagi".
Deterministic (same rule on every screen, no AI). Guests see only posko that
pass public_posko_allowed, with titles and regions — never contacts, reporters
or free-text notes.
"""

import re
from collections import defaultdict

import frappe
from frappe.rate_limiter import rate_limit
from frappe.utils import flt

from rescue_net.access_policy import can_manage_organization, can_manage_posko, is_system_manager, public_posko_allowed, rn_actor
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
            fields=["name", "title", "city_name", "province_name", "disaster_event",
                    "public_not_needed", "public_not_accepted_packaging", "public_notes_updated"],
            limit_page_length=500)
        if public_posko_allowed(p.name)
    ]
    names = [p.name for p in poskos]
    if not names:
        return {"event": event, "needs": [], "enough": [], "poskos": 0, "notes": []}

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
    notes = []
    for p in poskos:
        region = ", ".join(x for x in (p.city_name, p.province_name) if x)
        if wilayah and wilayah.strip().lower() not in region.lower():
            continue
        if (p.public_not_needed or "").strip() or (p.public_not_accepted_packaging or "").strip():
            notes.append({"posko": p.name, "posko_title": p.title or p.name, "region": region,
                          "not_needed": (p.public_not_needed or "").strip(),
                          "not_accepted_packaging": (p.public_not_accepted_packaging or "").strip(),
                          "updated_at": str(p.public_notes_updated or "")})
    return {"event": event, "needs": want[:300], "enough": enough[:300],
            "poskos": len(poskos), "notes": notes[:300]}


# ---------- Tahap 2: catatan eksplisit posko (barang / kemasan yang tidak diterima) ----------

_NOTE_MAX = 500
_CONTACT_LIKE = re.compile(r"(@|https?://|www\.|\d[\d\s().-]{7,}\d)")


def _can_edit_notes(actor, posko):
    if is_system_manager():
        return True
    if actor and can_manage_posko(actor, posko):
        return True
    org = frappe.db.get_value("RN Posko", posko, "organization")
    return bool(actor and org and can_manage_organization(actor, org))


def _clean_note(text, label):
    text = " ".join(str(text or "").split())
    if len(text) > _NOTE_MAX:
        frappe.throw("%s terlalu panjang (maks %d karakter)." % (label, _NOTE_MAX))
    if _CONTACT_LIKE.search(text):
        frappe.throw("%s tidak boleh memuat nomor telepon, email, atau tautan (halaman ini publik)." % label)
    return text


@frappe.whitelist()
def my_editable_poskos():
    """Posko yang boleh dikelola pemanggil, beserta catatan publik saat ini (untuk editor di halaman Kebutuhan Publik)."""
    actor = rn_actor()
    if not actor and not is_system_manager():
        frappe.throw("Login diperlukan.", frappe.PermissionError)
    out = []
    for p in frappe.get_all("RN Posko", fields=["name", "title", "public_detail", "public_not_needed",
                                                "public_not_accepted_packaging"],
                            order_by="title asc", limit_page_length=500):
        if _can_edit_notes(actor, p.name):
            out.append({"posko": p.name, "title": p.title or p.name, "public": p.public_detail == "public",
                        "not_needed": p.public_not_needed or "",
                        "not_accepted_packaging": p.public_not_accepted_packaging or ""})
    return out


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=60, seconds=3600)
def set_public_notes(posko, not_needed="", not_accepted_packaging=""):
    """Posko menulis barang/kemasan yang TIDAK dibutuhkan; tampil di papan publik bila posko publik."""
    actor = rn_actor()
    if not posko or not frappe.db.exists("RN Posko", posko):
        frappe.throw("Posko tidak ditemukan.", frappe.DoesNotExistError)
    if not _can_edit_notes(actor, posko):
        frappe.throw("Anda tidak berhak mengubah catatan posko ini.", frappe.PermissionError)
    vals = {
        "public_not_needed": _clean_note(not_needed, "Barang yang tidak dibutuhkan"),
        "public_not_accepted_packaging": _clean_note(not_accepted_packaging, "Kemasan yang tidak diterima"),
        "public_notes_updated": frappe.utils.now_datetime(),
    }
    frappe.db.set_value("RN Posko", posko, vals)
    return {"posko": posko, "public": frappe.db.get_value("RN Posko", posko, "public_detail") == "public", **{
        "not_needed": vals["public_not_needed"], "not_accepted_packaging": vals["public_not_accepted_packaging"]}}
