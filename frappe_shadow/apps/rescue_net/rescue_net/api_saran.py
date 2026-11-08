"""Saran untuk Rescue-Net (owner 2026-11-03: menu 'Saran' di header, tanpa login, berisi masukan
perbaikan / tambahan fitur dari pengguna).

Tanpa DocType baru (tanpa migrate): disimpan di RN Community Feedback, ditandai
`disaster_event_legacy_id` = PLATFORM (+ ":dikerjakan" saat sedang dikerjakan) dan
`legacy_id` = "saran:<kategori>:<hash>". Forum Masukan Masyarakat per bencana tidak menampilkannya.
Kontak pengirim tidak pernah dikirim ke publik; status hanya diubah System Manager.
"""

import frappe
from frappe.rate_limiter import rate_limit
from frappe.utils import cint, now_datetime

from rescue_net.access_policy import is_system_manager, rn_actor

DT = "RN Community Feedback"
PLATFORM = "rescue-net-platform"
WORKING = PLATFORM + ":dikerjakan"
CATEGORIES = {"bug": "Perbaikan bug / error", "fitur": "Fitur baru", "tampilan": "Tampilan", "lainnya": "Lainnya"}
STATUSES = ("baru", "ditinjau", "dikerjakan", "selesai", "disembunyikan")


def is_saran(row):
    return str(row.get("legacy_id") or "").startswith("saran:")


def _category(row):
    parts = str(row.get("legacy_id") or "").split(":")
    return parts[1] if len(parts) > 2 and parts[1] in CATEGORIES else "lainnya"


def _status(row):
    if row.get("status") == "hidden":
        return "disembunyikan"
    if row.get("status") == "resolved":
        return "selesai"
    if row.get("disaster_event_legacy_id") == WORKING:
        return "dikerjakan"
    return "ditinjau" if row.get("status") == "noted" else "baru"


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=5, seconds=600)
def submit_suggestion(body=None, category=None, title=None, page=None, author_name=None, author_contact=None, website=None):
    """`website` = honeypot (kolom tersembunyi). Bila terisi, dianggap bot: jawab sukses tanpa menyimpan."""
    if str(website or "").strip():
        return {"saved": True, "status": "baru"}
    body = str(body or "").strip()
    if len(body) < 10:
        frappe.throw("Tulis saran minimal 10 huruf.")
    if len(body) > 4000:
        frappe.throw("Saran terlalu panjang (maks 4000 karakter).")
    category = category if category in CATEGORIES else "lainnya"
    title = str(title or "").strip() or body.split("\n", 1)[0]
    actor = rn_actor(required=False)
    doc = frappe.new_doc(DT)
    doc.legacy_id = "saran:%s:%s" % (category, frappe.generate_hash(length=10))
    doc.disaster_event_legacy_id = PLATFORM
    doc.topic = title[:140]
    doc.category = "keluhan" if category == "bug" else "usul"
    doc.body = body
    doc.wilayah = str(page or "").strip()[:140] or None
    doc.author_name = (str(author_name or "").strip() or (actor.get("username") if actor else "") or "Anonim")[:120]
    doc.author_contact = str(author_contact or "").strip()[:140] or None
    doc.author_user = actor.get("name") if actor else None
    doc.status = "open"
    doc.insert(ignore_permissions=True)
    return {"saved": True, "suggestion": doc.name, "status": "baru"}


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def list_suggestions(category=None, status=None, limit=200):
    admin = is_system_manager()
    rows = frappe.get_all(DT, filters={"disaster_event_legacy_id": ["like", PLATFORM + "%"], "legacy_id": ["like", "saran:%"]},
                          fields=["name", "legacy_id", "disaster_event_legacy_id", "topic", "body", "wilayah", "author_name",
                                  "author_contact", "upvotes", "status", "official_response", "responded_at", "creation"],
                          order_by="creation desc", limit_page_length=min(cint(limit) or 200, 500))
    out, counts = [], {s: 0 for s in STATUSES}
    for r in rows:
        st = _status(r)
        counts[st] += 1
        if st == "disembunyikan" and not admin:
            continue
        cat = _category(r)
        if category in CATEGORIES and cat != category:
            continue
        if status in STATUSES and st != status:
            continue
        item = {"name": r.name, "title": r.topic, "body": r.body, "page": r.wilayah, "author_name": r.author_name or "Anonim",
                "category": cat, "category_label": CATEGORIES[cat], "status": st, "upvotes": cint(r.upvotes),
                "response": r.official_response, "responded_at": r.responded_at, "created": r.creation}
        if admin:
            item["author_contact"] = r.author_contact
        out.append(item)
    if not admin:
        counts.pop("disembunyikan", None)
    return {"suggestions": out, "counts": counts, "categories": CATEGORIES, "can_moderate": admin}


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=30, seconds=3600)
def support_suggestion(suggestion):
    row = frappe.db.get_value(DT, suggestion, ["legacy_id", "upvotes", "status"], as_dict=True)
    if not row or not is_saran(row) or row.status == "hidden":
        frappe.throw("Saran tidak ditemukan.")
    n = cint(row.upvotes) + 1
    frappe.db.set_value(DT, suggestion, "upvotes", n, update_modified=False)
    return {"suggestion": suggestion, "upvotes": n}


@frappe.whitelist(methods=["POST"])
def set_suggestion_status(suggestion, status, response=None):
    if not is_system_manager():
        frappe.throw("Hanya super admin yang dapat mengubah status saran.", frappe.PermissionError)
    if status not in STATUSES:
        frappe.throw("Status tidak dikenal.")
    doc = frappe.get_doc(DT, suggestion)
    if not is_saran(doc.as_dict()):
        frappe.throw("Saran tidak ditemukan.")
    doc.status = {"baru": "open", "ditinjau": "noted", "dikerjakan": "noted", "selesai": "resolved", "disembunyikan": "hidden"}[status]
    doc.disaster_event_legacy_id = WORKING if status == "dikerjakan" else PLATFORM
    if response is not None and str(response).strip():
        doc.official_response = str(response).strip()[:2000]
        doc.responded_by = frappe.session.user
        doc.responded_at = now_datetime()
    doc.save(ignore_permissions=True)
    return {"suggestion": doc.name, "status": status}
