"""Private optional attachments for a guest aid batch (never a public upload API)."""

import base64
import binascii
import io
import json
import os
import warnings

import frappe
from rescue_net.access_policy import can_manage_organization, can_manage_posko, is_system_manager, rn_actor

MAX_FILES = 3
MAX_BYTES = 2 * 1024 * 1024
_IMAGE_TYPES = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".webp": "WEBP"}


def validate_attachments(value):
    if value in (None, "", "[]"):
        return []
    # Bound the JSON before parsing/decoding, including base64 overhead.
    if isinstance(value, str) and len(value) > MAX_FILES * ((MAX_BYTES + 2) // 3 * 4 + 1024):
        frappe.throw("Lampiran terlalu besar. Maksimal 3 berkas, masing-masing 2 MB.")
    try:
        rows = json.loads(value) if isinstance(value, str) else value
    except (ValueError, TypeError):
        frappe.throw("Daftar lampiran tidak valid.")
    if not isinstance(rows, list) or len(rows) > MAX_FILES:
        frappe.throw("Maksimal 3 lampiran per pengiriman bantuan.")
    out = []
    for row in rows:
        if not isinstance(row, dict):
            frappe.throw("Data lampiran tidak valid.")
        name = str(row.get("filename") or "").strip()
        # Reject paths rather than silently letting an upload choose a directory.
        if not name or len(name) > 140 or "/" in name or "\\" in name or any(ord(c) < 32 for c in name):
            frappe.throw("Nama lampiran tidak valid.")
        ext = os.path.splitext(name)[1].lower()
        if ext not in (*_IMAGE_TYPES, ".pdf"):
            frappe.throw("Lampiran hanya boleh JPG, PNG, WebP, atau PDF.")
        encoded = row.get("content_base64")
        if not isinstance(encoded, str) or len(encoded) > (MAX_BYTES + 2) // 3 * 4:
            frappe.throw("Ukuran setiap lampiran maksimal 2 MB.")
        try:
            content = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error):
            frappe.throw("Isi lampiran tidak valid.")
        if not content or len(content) > MAX_BYTES:
            frappe.throw("Lampiran kosong atau melebihi 2 MB.")
        if ext == ".pdf":
            if not content.startswith(b"%PDF-"):
                frappe.throw("Isi lampiran tidak cocok dengan berkas PDF.")
            try:
                from pypdf import PdfReader
                from pypdf.generic import IndirectObject
                reader = PdfReader(io.BytesIO(content), strict=False)
                if reader.is_encrypted:
                    raise ValueError("encrypted PDF")
                seen, count = set(), [0]
                def passive(obj, depth=0):
                    if depth > 100 or count[0] > 5000:
                        raise ValueError("PDF object limit")
                    if isinstance(obj, IndirectObject):
                        key = (obj.idnum, obj.generation)
                        if key in seen:
                            return True
                        seen.add(key)
                        return passive(obj.get_object(), depth + 1)
                    count[0] += 1
                    if isinstance(obj, dict):
                        if any(str(k) in {"/JS", "/JavaScript", "/Launch", "/EmbeddedFiles", "/RichMedia"} for k in obj):
                            return False
                        return all(passive(v, depth + 1) for v in obj.values())
                    if isinstance(obj, (list, tuple)):
                        return all(passive(v, depth + 1) for v in obj)
                    return True
                safe_pdf = passive(reader.trailer)
            except Exception:
                frappe.throw("PDF tidak bisa dibaca. Pilih PDF yang valid dan tidak dikunci sandi.")
            if not safe_pdf:
                frappe.throw("PDF dengan skrip atau lampiran aktif tidak dapat dilampirkan.")
        else:
            from PIL import Image
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("error", Image.DecompressionBombWarning)
                    with Image.open(io.BytesIO(content)) as image:
                        if image.format != _IMAGE_TYPES[ext] or image.width * image.height > 25_000_000:
                            raise ValueError("image type/size")
                        image.verify()
                    # Do not retain camera EXIF/GPS or other uploaded image metadata.
                    with Image.open(io.BytesIO(content)) as image:
                        image = image.convert("RGBA" if image.mode in ("RGBA", "LA", "P") and _IMAGE_TYPES[ext] != "JPEG" else "RGB")
                        clean = Image.new(image.mode, image.size)
                        clean.paste(image)
                        buf = io.BytesIO()
                        clean.save(buf, format=_IMAGE_TYPES[ext])
                        content = buf.getvalue()
                        if len(content) > MAX_BYTES:
                            raise ValueError("image size")
            except Exception:
                frappe.throw("Gambar rusak, terlalu besar, atau tidak cocok dengan jenis berkasnya.")
        out.append((name, ext, content))
    return out


def save_attachments(validated, aid_offer):
    files = []
    for original, ext, content in validated:
        # Unpredictable names, private storage, attached to the FIRST offer of the batch.
        name = "bantuan-" + frappe.generate_hash(length=24) + ext
        # Supply validated bytes, never an existing file URL. save_file()'s
        # old hash lookup can select another guest's private blob and reject
        # a legitimate duplicate upload before checking the provided bytes.
        file_doc = frappe.get_doc({"doctype": "File", "file_name": name,
                                   "content": content, "is_private": 1,
                                   "owner": "Administrator" if frappe.session.user == "Guest" else frappe.session.user,
                                   "attached_to_doctype": "RN Aid Offer", "attached_to_name": aid_offer})
        file_doc.insert(ignore_permissions=True)
        if (not file_doc.is_private or not str(file_doc.file_url).startswith("/private/files/")
                or file_doc.attached_to_doctype != "RN Aid Offer" or file_doc.attached_to_name != aid_offer):
            frappe.throw("Lampiran tidak dapat disimpan secara privat.")
        file_doc.db_set("file_name", original, update_modified=False)
        # Guest is shared by every anonymous visitor, never an attachment owner.
        if frappe.session.user == "Guest":
            file_doc.db_set("owner", "Administrator", update_modified=False)
        files.append({"name": file_doc.name, "file_name": original})
    return files


def batch_offer_ids(doc):
    if not doc.get("guest_batch"):
        return [doc.name]
    return frappe.get_all("RN Aid Offer", filters={"guest_batch": doc.guest_batch}, pluck="name", limit_page_length=30)


def attachment_rows(doc):
    return frappe.get_all("File", filters={"attached_to_doctype": "RN Aid Offer", "attached_to_name": ["in", batch_offer_ids(doc)], "is_private": 1},
                          fields=["name", "file_name", "file_url", "owner"], order_by="creation asc", limit_page_length=MAX_FILES)


def can_read_attachments(aid_offer):
    if frappe.session.user in (None, "", "Guest"):
        return False
    if is_system_manager():
        return True
    doc = frappe.get_doc("RN Aid Offer", aid_offer)
    if any(row.owner == frappe.session.user for row in attachment_rows(doc)):
        return True
    actor = rn_actor(required=False)
    if not actor:
        return False
    from rescue_net.api_kitchen import _is_control
    if _is_control(actor):
        return True
    ids = batch_offer_ids(doc)
    poskos = set(frappe.get_all("RN Aid Offer", filters={"name": ["in", ids]},
                               pluck="target_posko", limit_page_length=30))
    for row in frappe.get_all("RN Distribution Flow", filters={"aid_offer": ["in", ids], "flow_status": ["not in", ["cancelled", "rejected"]]},
                             fields=["source_posko", "destination_posko"], limit_page_length=100):
        poskos.update([row.source_posko, row.destination_posko])
    for posko in filter(None, poskos):
        if can_manage_posko(actor, posko):
            return True
        org = frappe.db.get_value("RN Posko", posko, "organization")
        if org and can_manage_organization(actor, org):
            return True
    return False
