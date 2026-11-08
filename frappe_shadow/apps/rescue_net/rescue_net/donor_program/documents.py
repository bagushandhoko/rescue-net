"""Program Khusus (owner 2026-11-01): RAB as PDF + work drawings uploads, the initiator's bank account,
and the initiator's verification status shown to the public.

- Only the program's manager (owner org/posko/person) or Control Centre uploads / edits.
- RAB: several files (owner 2026-11-02: "anggaran bisa beberapa halaman") — PDF or a photo/scan per page, up to
  MAX_RAB_PAGES, kept in order. Stored in the same JSON field as the drawings (entries with kind "rab"), so no
  schema change; rab_file_url keeps pointing at the first RAB file for older readers (tender board, exports).
- Gambar kerja / gambar rencana: up to MAX_DRAWINGS images or PDFs.
- Files are public (transparency) but only listed while the program itself is visible.
- QRIS (owner 2026-11-08): one payment QR image per program (kind "qris"), shown with the bank account and under
  the same rule — public only while the initiator is verified.
- Rekening koran (kind "koran", owner 2026-11-08): bank statements per period, PDF or photo, public for
  transparency; the uploader must confirm that donors' personal data (names / account numbers) is masked.
- The bank account is shown to the public only while the initiator is VERIFIED — an unverified
  initiator's account number is never published (fraud guard); donors see the badge either way.
"""

import base64
import json
import re

import frappe
from frappe.utils.file_manager import save_file

from rescue_net.api_kitchen import rn_actor, _is_control
from rescue_net.donor_program.common import _actor_verified_person, _allowed_owner, _owner_verified, _program, _program_manager

MAX_BYTES = 10 * 1024 * 1024
MAX_DRAWINGS = 12
MAX_RAB_PAGES = 20
MAX_STATEMENTS = 24
_OTHER_KINDS = ("rab", "qris", "koran")     # not drawings
_IMAGE_EXT = {"png": b"\x89PNG", "jpg": b"\xff\xd8\xff", "jpeg": b"\xff\xd8\xff", "webp": b"RIFF"}
_PDF_MAGIC = b"%PDF"


def _assert_manage(actor, row):
    if not (_is_control(actor) or _program_manager(actor, row)):
        frappe.throw("Hanya pemrakarsa program atau Control Centre yang boleh mengubah ini.", frappe.PermissionError)


def _org_creator_trusted(row):
    """Owner 2026-11-08: an approved MEMBER may start a program for the organisation (e.g. LAZISMU), but its
    bank account / QRIS goes public only when the organisation vouches for that member (HQ attestation
    member_verified, or the member is owner/deputy/staff, or runs a posko of the org). Programs created via the
    old route (posko/control, no membership row) are unchanged."""
    acct = row.get("created_by_user")
    if not acct or not row.get("owner_id"):
        return True
    m = frappe.db.get_value("RN Organization Membership",
                            {"user_account": acct, "organization": row.owner_id, "status": "approved"},
                            ["membership_role", "member_verified"], as_dict=True)
    if not m:
        return True
    if (m.membership_role or "") in ("owner", "deputy", "staff") or m.member_verified:
        return True
    poskos = frappe.get_all("RN Posko Assignment", filters={"user_account": acct, "status": "approved"}, pluck="posko")
    return bool(poskos and frappe.db.exists("RN Posko", {"name": ["in", poskos], "organization": row.owner_id}))


def initiator_verified(row):
    """Is the program's initiator verified right now (org / posko status, or the creating person)?"""
    if row.owner_type == "organization":
        return bool(_owner_verified(row.owner_type, row.owner_id)) and _org_creator_trusted(row)
    if row.owner_type == "posko":
        return bool(_owner_verified(row.owner_type, row.owner_id))
    acct = row.get("created_by_user") or row.get("owner_id")
    return bool(acct and _actor_verified_person(frappe._dict(name=acct)))


def _entries(raw):
    try:
        val = json.loads(raw or "[]")
        return [d for d in val if isinstance(d, dict) and d.get("url")]
    except (ValueError, TypeError):
        return []


def _drawings(raw):
    return [d for d in _entries(raw) if d.get("kind") not in _OTHER_KINDS]


def _of_kind(raw, kind):
    return [d for d in _entries(raw) if d.get("kind") == kind]


def _rab_pages(raw, legacy_url=None):
    pages = [d for d in _entries(raw) if d.get("kind") == "rab"]
    if legacy_url and legacy_url not in [d["url"] for d in pages]:
        pages.insert(0, {"url": legacy_url, "name": legacy_url.rsplit("/", 1)[-1], "label": "", "pdf": True, "kind": "rab"})
    return pages


def _check_file(kind, filename, content):
    ext = (filename.rsplit(".", 1)[-1] if "." in filename else "").lower()
    if len(content) > MAX_BYTES:
        frappe.throw("File terlalu besar (maks. 10 MB).")
    if ext == "pdf" and content.startswith(_PDF_MAGIC):
        if kind == "qris":
            frappe.throw("QRIS harus berupa gambar (PNG / JPG / WEBP).")
        return
    magic = _IMAGE_EXT.get(ext)
    if not magic or not content.startswith(magic) or (ext == "webp" and content[8:12] != b"WEBP"):
        frappe.throw({"rab": "Dokumen RAB", "qris": "QRIS", "koran": "Rekening koran"}.get(kind, "Gambar rencana") +
                     " harus berupa PDF atau gambar (PNG / JPG / WEBP).")


def documents_for(row_name):
    v = frappe.db.get_value("RN Donor Program", row_name, ["rab_file_url", "work_drawings"], as_dict=True) or {}
    pages = _rab_pages(v.get("work_drawings"), v.get("rab_file_url"))
    return {"rab": pages[0]["url"] if pages else "", "rab_pages": pages, "drawings": _drawings(v.get("work_drawings")),
            "statements": _of_kind(v.get("work_drawings"), "koran")}


def bank_for(row, can_manage):
    """Bank account block for program_detail: managers always see what they entered; the public only
    while the initiator is verified."""
    v = frappe.db.get_value("RN Donor Program", row.name, ["bank_name", "bank_account_number", "bank_account_holder",
                                                           "work_drawings"], as_dict=True) or {}
    qris = (_of_kind(v.get("work_drawings"), "qris") or [None])[-1]
    has = bool(v.get("bank_account_number")) or bool(qris)
    verified = initiator_verified(row)
    show = has and (can_manage or verified)
    return {
        "available": has,
        "shown_publicly": has and verified,
        "qris_url": (qris or {}).get("url", "") if show else "",
        "qris_available": bool(qris),
        "bank_name": (v.get("bank_name") or "") if show else "",
        "account_number": (v.get("bank_account_number") or "") if show else "",
        "account_holder": (v.get("bank_account_holder") or "") if show else "",
    }


@frappe.whitelist(methods=["POST"])
def upload_program_file(donor_program, kind, filename, content_base64, label=None, redacted=0):
    actor = rn_actor()
    row = _program(donor_program)
    _assert_manage(actor, row)
    if kind not in ("rab", "gambar", "qris", "koran"):
        frappe.throw("Jenis dokumen tidak dikenal (rab / gambar / qris / koran).")
    if kind == "koran" and str(redacted).strip().lower() not in ("1", "true", "yes", "on"):
        frappe.throw("Samarkan dulu data pribadi pengirim (nama / nomor rekening) di rekening koran, lalu centang konfirmasinya.")
    filename = re.sub(r"[^\w.\- ]", "_", str(filename or "").strip())[:120]
    if not filename:
        frappe.throw("Nama file wajib diisi.")
    try:
        content = base64.b64decode(content_base64 or "", validate=False)
    except Exception:
        frappe.throw("Isi file tidak valid.")
    if not content:
        frappe.throw("File kosong.")
    _check_file(kind, filename, content)

    doc = frappe.get_doc("RN Donor Program", donor_program)
    entries = _entries(doc.work_drawings)
    if doc.rab_file_url and doc.rab_file_url not in [d["url"] for d in entries]:      # older single-PDF RAB
        entries.insert(0, {"url": doc.rab_file_url, "name": doc.rab_file_url.rsplit("/", 1)[-1], "label": "",
                           "pdf": True, "kind": "rab"})
    if kind == "gambar" and len(_drawings(json.dumps(entries))) >= MAX_DRAWINGS:
        frappe.throw(f"Maksimal {MAX_DRAWINGS} gambar rencana. Hapus yang lama dulu.")
    if kind == "rab" and len([d for d in entries if d.get("kind") == "rab"]) >= MAX_RAB_PAGES:
        frappe.throw(f"Maksimal {MAX_RAB_PAGES} halaman/berkas RAB. Hapus yang lama dulu.")
    if kind == "koran" and len([d for d in entries if d.get("kind") == "koran"]) >= MAX_STATEMENTS:
        frappe.throw(f"Maksimal {MAX_STATEMENTS} berkas rekening koran. Hapus yang lama dulu.")
    if kind == "qris":
        entries = [d for d in entries if d.get("kind") != "qris"]       # satu QRIS per program: yang baru mengganti
    try:
        f = save_file(filename, content, "RN Donor Program", donor_program, is_private=0)
    except frappe.ValidationError:
        raise
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Program Khusus upload")
        frappe.throw("File tidak bisa dibaca (rusak?). Coba simpan ulang sebagai PDF / gambar lalu unggah lagi.")
    item = {"url": f.file_url, "name": filename, "label": (label or "").strip()[:120],
            "pdf": filename.lower().endswith(".pdf")}
    if kind in _OTHER_KINDS:
        item["kind"] = kind
    entries.append(item)
    doc.work_drawings = json.dumps(entries, ensure_ascii=False)
    rab = [d for d in entries if d.get("kind") == "rab"]
    doc.rab_file_url = rab[0]["url"] if rab else None
    doc.save(ignore_permissions=True)
    return documents_for(donor_program)


@frappe.whitelist(methods=["POST"])
def remove_program_file(donor_program, kind, file_url=None):
    actor = rn_actor()
    row = _program(donor_program)
    _assert_manage(actor, row)
    doc = frappe.get_doc("RN Donor Program", donor_program)
    if kind not in ("rab", "gambar", "qris", "koran"):
        frappe.throw("Jenis dokumen tidak dikenal (rab / gambar / qris / koran).")
    entries = _entries(doc.work_drawings)
    if kind in ("qris", "koran"):
        keep = [d for d in entries if d.get("kind") != kind or (file_url and d["url"] != file_url)]
    elif kind == "rab":
        # no file_url = remove every RAB page (old single-PDF behaviour)
        keep = [d for d in entries if d.get("kind") != "rab" or (file_url and d["url"] != file_url)]
        legacy = doc.rab_file_url if (file_url and doc.rab_file_url != file_url) else None
        if legacy and legacy not in [d["url"] for d in keep]:
            keep.insert(0, {"url": legacy, "name": legacy.rsplit("/", 1)[-1], "label": "", "pdf": True, "kind": "rab"})
    else:
        keep = [d for d in entries if d.get("kind") in _OTHER_KINDS or d["url"] != file_url]
    doc.work_drawings = json.dumps(keep, ensure_ascii=False)
    rab = [d for d in keep if d.get("kind") == "rab"]
    doc.rab_file_url = rab[0]["url"] if rab else None
    doc.save(ignore_permissions=True)
    return documents_for(donor_program)


@frappe.whitelist(methods=["POST"])
def set_program_bank(donor_program, bank_name=None, account_number=None, account_holder=None):
    actor = rn_actor()
    row = _program(donor_program)
    _assert_manage(actor, row)
    number = re.sub(r"[\s.\-]", "", str(account_number or ""))
    if number and not re.fullmatch(r"\d{5,20}", number):
        frappe.throw("Nomor rekening harus 5–20 angka.")
    bank_name = (bank_name or "").strip()[:60]
    holder = (account_holder or "").strip()[:120]
    if number and not (bank_name and holder):
        frappe.throw("Isi nama bank dan atas nama rekening.")
    frappe.db.set_value("RN Donor Program", donor_program, {
        "bank_name": bank_name or None, "bank_account_number": number or None, "bank_account_holder": holder or None})
    return bank_for(frappe._dict(row), True)
