"""Program Khusus (owner 2026-11-01): RAB as PDF + work drawings uploads, the initiator's bank account,
and the initiator's verification status shown to the public.

- Only the program's manager (owner org/posko/person) or Control Centre uploads / edits.
- RAB: one PDF (replaces the previous one). Gambar kerja: up to MAX_DRAWINGS images or PDFs.
- Files are public (transparency) but only listed while the program itself is visible.
- The bank account is shown to the public only while the initiator is VERIFIED — an unverified
  initiator's account number is never published (fraud guard); donors see the badge either way.
"""

import base64
import json
import re

import frappe
from frappe.utils.file_manager import save_file

from rescue_net.api_kitchen import rn_actor, _is_control
from rescue_net.donor_program.common import _actor_verified_person, _allowed_owner, _owner_verified, _program

MAX_BYTES = 10 * 1024 * 1024
MAX_DRAWINGS = 12
_IMAGE_EXT = {"png": b"\x89PNG", "jpg": b"\xff\xd8\xff", "jpeg": b"\xff\xd8\xff", "webp": b"RIFF"}
_PDF_MAGIC = b"%PDF"


def _assert_manage(actor, row):
    if not (_is_control(actor) or _allowed_owner(actor, row.owner_type, row.owner_id)):
        frappe.throw("Hanya pemrakarsa program atau Control Centre yang boleh mengubah ini.", frappe.PermissionError)


def initiator_verified(row):
    """Is the program's initiator verified right now (org / posko status, or the creating person)?"""
    if row.owner_type in ("organization", "posko"):
        return bool(_owner_verified(row.owner_type, row.owner_id))
    acct = row.get("created_by_user") or row.get("owner_id")
    return bool(acct and _actor_verified_person(frappe._dict(name=acct)))


def _drawings(raw):
    try:
        val = json.loads(raw or "[]")
        return [d for d in val if isinstance(d, dict) and d.get("url")]
    except (ValueError, TypeError):
        return []


def _check_file(kind, filename, content):
    ext = (filename.rsplit(".", 1)[-1] if "." in filename else "").lower()
    if len(content) > MAX_BYTES:
        frappe.throw("File terlalu besar (maks. 10 MB).")
    if kind == "rab":
        if ext != "pdf" or not content.startswith(_PDF_MAGIC):
            frappe.throw("Dokumen RAB harus berupa file PDF.")
        return
    if ext == "pdf" and content.startswith(_PDF_MAGIC):
        return
    magic = _IMAGE_EXT.get(ext)
    if not magic or not content.startswith(magic) or (ext == "webp" and content[8:12] != b"WEBP"):
        frappe.throw("Gambar kerja harus berupa gambar (PNG / JPG / WEBP) atau PDF.")


def documents_for(row_name):
    v = frappe.db.get_value("RN Donor Program", row_name, ["rab_file_url", "work_drawings"], as_dict=True) or {}
    return {"rab": v.get("rab_file_url") or "", "drawings": _drawings(v.get("work_drawings"))}


def bank_for(row, can_manage):
    """Bank account block for program_detail: managers always see what they entered; the public only
    while the initiator is verified."""
    v = frappe.db.get_value("RN Donor Program", row.name, ["bank_name", "bank_account_number", "bank_account_holder"],
                            as_dict=True) or {}
    has = bool(v.get("bank_account_number"))
    verified = initiator_verified(row)
    show = has and (can_manage or verified)
    return {
        "available": has,
        "shown_publicly": has and verified,
        "bank_name": (v.get("bank_name") or "") if show else "",
        "account_number": (v.get("bank_account_number") or "") if show else "",
        "account_holder": (v.get("bank_account_holder") or "") if show else "",
    }


@frappe.whitelist(methods=["POST"])
def upload_program_file(donor_program, kind, filename, content_base64, label=None):
    actor = rn_actor()
    row = _program(donor_program)
    _assert_manage(actor, row)
    if kind not in ("rab", "gambar"):
        frappe.throw("Jenis dokumen tidak dikenal (rab / gambar).")
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
    drawings = _drawings(doc.work_drawings)
    if kind == "gambar" and len(drawings) >= MAX_DRAWINGS:
        frappe.throw(f"Maksimal {MAX_DRAWINGS} gambar kerja. Hapus yang lama dulu.")
    try:
        f = save_file(filename, content, "RN Donor Program", donor_program, is_private=0)
    except frappe.ValidationError:
        raise
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Program Khusus upload")
        frappe.throw("File tidak bisa dibaca (rusak?). Coba simpan ulang sebagai PDF / gambar lalu unggah lagi.")
    if kind == "rab":
        doc.rab_file_url = f.file_url
    else:
        drawings.append({"url": f.file_url, "name": filename, "label": (label or "").strip()[:120],
                         "pdf": filename.lower().endswith(".pdf")})
        doc.work_drawings = json.dumps(drawings, ensure_ascii=False)
    doc.save(ignore_permissions=True)
    return documents_for(donor_program)


@frappe.whitelist(methods=["POST"])
def remove_program_file(donor_program, kind, file_url=None):
    actor = rn_actor()
    row = _program(donor_program)
    _assert_manage(actor, row)
    doc = frappe.get_doc("RN Donor Program", donor_program)
    if kind == "rab":
        doc.rab_file_url = None
    elif kind == "gambar":
        doc.work_drawings = json.dumps([d for d in _drawings(doc.work_drawings) if d["url"] != file_url],
                                       ensure_ascii=False)
    else:
        frappe.throw("Jenis dokumen tidak dikenal (rab / gambar).")
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
