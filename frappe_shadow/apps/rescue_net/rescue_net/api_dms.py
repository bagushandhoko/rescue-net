"""Menu khusus DMS (Edisi Instansi) - penyimpanan sementara di RN.

Keputusan owner 22 Nov 2026: 36 menu disetujui, data disimpan dulu di RN, nama instansi asli dipakai.
Nanti dipindah ke backend instansi dan ditukar lewat federasi (docs/RANCANGAN-BACKEND-NODE-DAN-FEDERASI.md).

Aturan akses (selalu di server, menu di layar bukan kontrol keamanan):
- Hanya anggota disetujui dari organisasi TERTUTUP; tamu dan organisasi terbuka ditolak.
- Menu harus termasuk template organisasi: instansi == template, atau "bersama", atau template ada di template_tambahan.
- Klasifikasi RAHASIA hanya untuk owner/deputy organisasi (dan System Manager).
- Isian divalidasi terhadap definisi menu (dms/menus.json): field dikenal saja, wajib, angka, tanggal, waktu, pilihan.
"""
import json
import re
from functools import lru_cache
from pathlib import Path

import frappe
from frappe.utils import cint

from rescue_net.services.drill import assert_scope, dms_event_names, scope_hidden_events, showing_dms

from rescue_net.access_policy import approved_member, is_system_manager, rn_actor

DOCTYPE = "RN DMS Record"
SECRET = "RAHASIA"
SECRET_ROLES = ("owner", "deputy")
MAX_TEXT = 2000
MAX_SHORT = 280


@lru_cache(maxsize=1)
def _catalog():
    menus = json.loads(Path(__file__).with_name("dms").joinpath("menus.json").read_text(encoding="utf-8"))
    return {m["id"]: m for m in menus}


def _menu(menu_id):
    menu = _catalog().get((menu_id or "").strip())
    if not menu:
        frappe.throw("Menu DMS tidak dikenal.")
    return menu


def _allowed(menu, template):
    return (menu["instansi"] == "bersama" or menu["instansi"] == template
            or template in (menu.get("template_tambahan") or []))


def _org_context(actor, organization):
    """Organisasi tertutup yang dipakai + template + peran anggota."""
    if not organization:
        from rescue_net.api_org_profile import my_operation_template
        organization = my_operation_template().get("organization")
    if not organization or not frappe.db.exists("RN Organization", organization):
        frappe.throw("Pilih organisasi tertutup Anda.", frappe.PermissionError)
    org = frappe.db.get_value("RN Organization", organization, ["name", "privacy_mode", "operation_template"], as_dict=True)
    manager = is_system_manager()
    if not manager and not approved_member(actor.name, organization):
        frappe.throw("Anda bukan anggota organisasi ini.", frappe.PermissionError)
    if org.privacy_mode != "closed":
        frappe.throw("Menu DMS hanya untuk organisasi tertutup.", frappe.PermissionError)
    role = None
    if not manager:
        role = frappe.db.get_value("RN Organization Membership",
                                   {"user_account": actor.name, "organization": organization, "status": "approved"},
                                   "membership_role")
    return org, (org.operation_template or "umum"), manager, role


def _check_menu(menu, template, manager, role):
    if not _allowed(menu, template):
        frappe.throw("Menu ini di luar template operasi organisasi Anda.", frappe.PermissionError)
    if menu["klasifikasi"] == SECRET and not manager and role not in SECRET_ROLES:
        frappe.throw("Data RAHASIA hanya untuk pemilik/wakil organisasi.", frappe.PermissionError)


_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME = re.compile(r"^\d{2}:\d{2}(:\d{2})?$")


def _clean(menu, data):
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except ValueError:
            frappe.throw("Isian harus berupa objek JSON.")
    if not isinstance(data, dict):
        frappe.throw("Isian harus berupa objek JSON.")
    fields = {f["id"]: f for f in menu["isian"]}
    unknown = set(data) - set(fields)
    if unknown:
        frappe.throw("Isian tidak dikenal: " + ", ".join(sorted(unknown)[:5]))
    out = {}
    for fid, f in fields.items():
        value = data.get(fid)
        if isinstance(value, str):
            value = value.strip()
        if value in (None, ""):
            if f.get("wajib"):
                frappe.throw(f"Isian wajib: {f['label']}")
            continue
        kind = f.get("jenis")
        if kind == "angka":
            try:
                value = float(value)
            except (TypeError, ValueError):
                frappe.throw(f"{f['label']} harus angka.")
            if value != value or abs(value) > 1e12:
                frappe.throw(f"{f['label']} di luar batas.")
            value = int(value) if value == int(value) else value
        elif kind == "tanggal":
            if not isinstance(value, str) or not _DATE.match(value):
                frappe.throw(f"{f['label']} harus tanggal (YYYY-MM-DD).")
        elif kind == "waktu":
            if not isinstance(value, str) or not _TIME.match(value):
                frappe.throw(f"{f['label']} harus jam (HH:MM).")
        elif kind == "pilihan":
            if value not in (f.get("pilihan") or []):
                frappe.throw(f"{f['label']}: pilihan tidak valid.")
        elif kind == "ya_tidak":
            if value not in ("Ya", "Tidak"):
                frappe.throw(f"{f['label']}: pilih Ya atau Tidak.")
        else:
            if not isinstance(value, str):
                frappe.throw(f"{f['label']} harus teks.")
            limit = MAX_TEXT if kind == "teks_panjang" else MAX_SHORT
            if len(value) > limit:
                frappe.throw(f"{f['label']} terlalu panjang (maks {limit} huruf).")
        out[fid] = value
    if not out:
        frappe.throw("Isian kosong.")
    return out


def _row(doc):
    return {"name": doc.name, "menu_id": doc.menu_id, "organization": doc.organization,
            "classification": doc.classification, "disaster_event": doc.disaster_event, "status": doc.status,
            "data": json.loads(doc.data or "{}"), "modified": str(doc.modified), "creation": str(doc.creation)}


@frappe.whitelist(methods=["GET"])
def list_records(menu_id, organization=None, disaster_event=None, include_archived=0, limit=100):
    actor = rn_actor()
    menu = _menu(menu_id)
    org, template, manager, role = _org_context(actor, organization)
    _check_menu(menu, template, manager, role)
    filters = {"menu_id": menu["id"], "organization": org.name}
    if disaster_event:
        assert_scope(disaster_event)
        filters["disaster_event"] = disaster_event
    elif showing_dms():
        visible = sorted(dms_event_names())
        if not visible:
            return {"menu_id": menu["id"], "organization": org.name, "template": template, "records": []}
        filters["disaster_event"] = ["in", visible]
    elif hidden := scope_hidden_events():
        filters["disaster_event"] = ["not in", sorted(hidden)]
    if not cint(include_archived):
        filters["status"] = "aktif"
    names = frappe.get_all(DOCTYPE, filters=filters, pluck="name", order_by="modified desc",
                           limit_page_length=max(1, min(cint(limit) or 100, 500)))
    return {"menu_id": menu["id"], "organization": org.name, "template": template,
            "records": [_row(frappe.get_doc(DOCTYPE, n)) for n in names]}


@frappe.whitelist(methods=["POST"])
def save_record(menu_id, data, organization=None, disaster_event=None, name=None):
    actor = rn_actor()
    menu = _menu(menu_id)
    org, template, manager, role = _org_context(actor, organization)
    _check_menu(menu, template, manager, role)
    clean = _clean(menu, data)
    assert_scope(disaster_event)
    if disaster_event and not frappe.db.exists("RN Disaster Event", disaster_event):
        frappe.throw("Bencana tidak ditemukan.")
    if name:
        doc = frappe.get_doc(DOCTYPE, name)
        assert_scope(doc.disaster_event)
        if doc.organization != org.name or doc.menu_id != menu["id"]:
            frappe.throw("Catatan tidak ditemukan.", frappe.PermissionError)
    else:
        doc = frappe.new_doc(DOCTYPE)
        doc.menu_id, doc.organization = menu["id"], org.name
        doc.created_by_account = actor.name
    doc.classification = menu["klasifikasi"]
    doc.disaster_event = disaster_event or doc.disaster_event
    if showing_dms() and not doc.disaster_event:
        frappe.throw("Pilih kejadian simulasi DMS.")
    doc.data = json.dumps(clean, ensure_ascii=False, sort_keys=True)
    doc.updated_by_account = actor.name
    doc.status = "aktif"
    doc.save(ignore_permissions=True)
    return _row(doc)


@frappe.whitelist(methods=["POST"])
def archive_record(name, organization=None):
    actor = rn_actor()
    doc = frappe.get_doc(DOCTYPE, name)
    assert_scope(doc.disaster_event)
    org, template, manager, role = _org_context(actor, organization or doc.organization)
    if doc.organization != org.name:
        frappe.throw("Catatan tidak ditemukan.", frappe.PermissionError)
    _check_menu(_menu(doc.menu_id), template, manager, role)
    doc.status = "arsip"
    doc.updated_by_account = actor.name
    doc.save(ignore_permissions=True)
    return {"name": doc.name, "status": doc.status}
