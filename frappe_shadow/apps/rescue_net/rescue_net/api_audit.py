"""Jejak Audit (2026-10-26, rencana pembenahan tahap 2): who changed which
sensitive record, when, and what. Reads Frappe `Version` rows, which exist
for DocTypes with track_changes (posko, organisasi, keanggotaan, kasus medis,
orang hilang, kiriman, stok, kebutuhan, donasi, relawan, armada, laporan…).
Writes done with frappe.db.set_value bypass Version, so this covers edits
made through documents (forms, API saves), not every internal counter.

System Manager and Control Centre (command_center) only."""

import json

import frappe
from frappe.utils import add_days, cint, now_datetime

from rescue_net.access_policy import is_system_manager, rn_actor

AUDIT_ROLES = {"command_center"}

# DocTypes shown in the filter (label for people, not the DocType name)
AUDITED = {
    "RN Posko": "Posko",
    "RN Organization": "Organisasi",
    "RN Organization Membership": "Keanggotaan organisasi",
    "RN Posko Assignment": "Penugasan posko",
    "RN User Account": "Akun pengguna",
    "RN Medical Case": "Kasus medis",
    "RN Missing Person Report": "Orang hilang",
    "RN Community Report": "Laporan masyarakat",
    "RN Distribution Flow": "Kiriman logistik",
    "RN Stock Observation": "Stok",
    "RN Logistic Need": "Kebutuhan",
    "RN Aid Offer": "Tawaran bantuan",
    "RN Cash Donation": "Donasi tunai",
    "RN Donor Program": "Program donasi",
    "RN Volunteer Profile": "Relawan",
    "RN Volunteer Assignment": "Penugasan relawan",
    "RN Transport Space": "Armada",
    "RN Transport Booking": "Booking armada",
    "RN Shelter Occupancy": "Okupansi shelter",
    "RN Kitchen Production": "Produksi dapur",
}

# values never echoed back, even to auditors (the change is listed, the value masked)
_SECRET_FIELDS = {"verification_pin", "pin", "password", "api_key", "secret", "token", "edit_code"}


def _require_auditor():
    if is_system_manager():
        return
    actor = rn_actor(required=False)
    if not actor or getattr(actor, "role", None) not in AUDIT_ROLES:
        frappe.throw("Jejak Audit hanya untuk System Manager dan Control Centre.", frappe.PermissionError)


def _short(v):
    if v is None or v == "":
        return "—"
    s = str(v)
    return s if len(s) <= 120 else s[:117] + "…"


def _changes(data):
    try:
        d = json.loads(data or "{}")
    except ValueError:
        return [], "ubah"
    out = []
    for row in d.get("changed") or []:
        if len(row) < 3:
            continue
        field, old, new = row[0], row[1], row[2]
        masked = any(k in str(field).lower() for k in _SECRET_FIELDS)
        out.append({"field": field, "old": "•••" if masked else _short(old), "new": "•••" if masked else _short(new)})
    for key, label in (("added", "baris ditambah"), ("removed", "baris dihapus")):
        for row in d.get(key) or []:
            out.append({"field": (row[0] if row else "") + " (" + label + ")", "old": "", "new": ""})
    kind = "buat" if d.get("creation") else "ubah"
    return out, kind


@frappe.whitelist()
def audit_trail(doctype=None, user=None, docname=None, days=7, limit=200):
    """Newest first. Filters: DocType, user (email), record name, last N days."""
    _require_auditor()
    days = max(1, min(cint(days) or 7, 90))
    limit = max(1, min(cint(limit) or 200, 500))
    filters = {"ref_doctype": ["in", list(AUDITED)], "creation": [">=", add_days(now_datetime(), -days)]}
    if doctype:
        if doctype not in AUDITED:
            frappe.throw("Jenis data tidak dikenal.")
        filters["ref_doctype"] = doctype
    if user:
        filters["owner"] = str(user).strip()
    if docname:
        filters["docname"] = str(docname).strip()
    rows = frappe.get_all("Version", filters=filters,
                          fields=["name", "ref_doctype", "docname", "owner", "creation", "data"],
                          order_by="creation desc", limit_page_length=limit, ignore_permissions=True)
    names = {r.owner for r in rows}
    full = dict(frappe.get_all("User", filters={"name": ["in", list(names) or [""]]},
                               fields=["name", "full_name"], as_list=True, ignore_permissions=True))
    out = []
    for r in rows:
        changes, kind = _changes(r.data)
        title = None
        try:
            meta = frappe.get_meta(r.ref_doctype)
            tf = meta.title_field or ("title" if meta.has_field("title") else None)
            if tf:
                title = frappe.db.get_value(r.ref_doctype, r.docname, tf)
        except Exception:
            title = None
        out.append({
            "at": str(r.creation)[:19],
            "user": r.owner,
            "user_name": full.get(r.owner) or r.owner,
            "doctype": r.ref_doctype,
            "doctype_label": AUDITED.get(r.ref_doctype, r.ref_doctype),
            "docname": r.docname,
            "title": title or r.docname,
            "kind": kind,
            "changes": changes,
        })
    return {"rows": out, "days": days, "doctypes": [{"id": k, "label": v} for k, v in AUDITED.items()]}
