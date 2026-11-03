"""Management Donation — tender / RAB. Sebuah program donasi yang membangun
sesuatu bisa menampilkan B&Q / RAB untuk ditenderkan (dokumen bisa diunduh),
dan pihak lain bisa mengajukan penawaran dengan batas waktu.
"""

import frappe
from frappe.rate_limiter import rate_limit
from frappe.utils import now_datetime, flt, cint, get_datetime, getdate

from rescue_net.access_policy import rn_actor, is_system_manager, can_manage_organization
from rescue_net.reference_resolver import resolve_disaster_event

_TENDER_STATUS = {"draft": "Draft", "open": "Terbuka", "evaluation": "Evaluasi",
                  "awarded": "Ditetapkan", "cancelled": "Dibatalkan"}
_CATEGORY = {"construction": "Pekerjaan Konstruksi", "goods": "Pengadaan Barang",
             "services": "Jasa Lainnya", "consultancy": "Jasa Konsultansi"}
_EVALUATION = {"lowest_price": "Harga terendah (memenuhi syarat)",
               "quality_price": "Kualitas dan harga", "quality": "Kualitas teknis"}
# Owner 2026-11-03: information a tender normally publishes (besides RAB / scope / deadline).
INFO_FIELDS = ("tender_category", "funding_source", "explanation_schedule", "work_start_date",
               "target_completion_date", "work_duration_days", "maintenance_days", "bidder_requirements",
               "required_documents", "bid_submission_email", "evaluation_method", "bid_validity_days",
               "payment_terms")
# Fields the organiser may change after creating the tender (not the status / winner).
EDITABLE_FIELDS = ("title", "location", "scope_description", "rab_total", "rab_document_url",
                   "design_image_url", "bidding_opens_at", "bidding_closes_at", "contact_person",
                   "contact_phone", "notes") + INFO_FIELDS
_TEXT_MAX = 4000
MAX_DRAWINGS = 20
MAX_RAB_PAGES = 20
_BID_STATUS = {"submitted": "Masuk", "shortlisted": "Shortlist",
               "rejected": "Ditolak", "awarded": "Pemenang"}


def _event(v):
    if not v:
        return None
    try:
        return resolve_disaster_event(v)
    except Exception:
        return v


def _event_or_filters(disaster_event, ev):
    vals = [x for x in {ev, disaster_event} if x]
    if not vals:
        return None
    return [["disaster_event", "in", vals], ["disaster_event_legacy_id", "in", vals]]


def _clean(field, value):
    """Normalise one organiser-entered value; '' / None clears it."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if field in ("work_duration_days", "maintenance_days", "bid_validity_days"):
        n = cint(value)
        if n < 0 or n > 3650:
            frappe.throw("Jumlah hari harus 0–3650.")
        return n or None
    if field == "rab_total":
        n = flt(value)
        if n < 0:
            frappe.throw("Nilai RAB tidak boleh negatif.")
        return n
    if field in ("work_start_date", "target_completion_date"):
        return str(getdate(value))
    if field in ("bidding_opens_at", "bidding_closes_at"):
        return str(get_datetime(str(value).replace("T", " ")))
    if field == "tender_category" and value not in _CATEGORY:
        frappe.throw("Jenis pengadaan tidak dikenal.")
    if field == "evaluation_method" and value not in _EVALUATION:
        frappe.throw("Metode evaluasi tidak dikenal.")
    value = str(value).strip()
    if field == "bid_submission_email":
        from frappe.utils import validate_email_address
        value = value.lower()
        if not validate_email_address(value):
            frappe.throw("Alamat email penawaran tidak valid.")
    return value[:_TEXT_MAX]


def _entries(raw):
    import json
    try:
        val = json.loads(raw or "[]")
        return [d for d in val if isinstance(d, dict) and d.get("url")]
    except (ValueError, TypeError):
        return []


def _documents(raw):
    e = _entries(raw)
    return {"drawings": [d for d in e if d.get("kind") != "rab"], "rab_pages": [d for d in e if d.get("kind") == "rab"]}


def _labels(t):
    t["category_label"] = _CATEGORY.get(t.get("tender_category"), "")
    t["evaluation_label"] = _EVALUATION.get(t.get("evaluation_method"), "")
    return t


def _is_open(t):
    if t.get("status") != "open":
        return False
    c = t.get("bidding_closes_at")
    if c and get_datetime(c) < now_datetime():
        return False
    return True


def _owns_tender(actor, t):
    if is_system_manager():
        return True
    if not actor or not actor.get("name"):
        return False
    org = t.get("organization")
    if org and can_manage_organization(actor, org):
        return True
    return frappe.db.get_value("RN Procurement Tender", t.get("name"), "owner") == frappe.session.user


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def tender_board(disaster_event=None, limit=200):
    from rescue_net.api_donor_program import _owner_verified, _is_control, _allowed_owner

    ev = _event(disaster_event)
    rows = frappe.get_all(
        "RN Procurement Tender",
        or_filters=_event_or_filters(disaster_event, ev),
        fields=["name", "title", "location", "donor_program", "organization",
                "rab_total", "rab_document_url", "design_image_url", "bidding_opens_at",
                "bidding_closes_at", "status", "awarded_bid", "scope_description",
                "tender_category", "work_start_date", "target_completion_date", "work_duration_days",
                "bid_submission_email", "work_drawings", "modified"],
        order_by="bidding_closes_at asc, modified desc",
        limit_page_length=cint(limit) or 200,
    )

    # Same verification gate as api_donor_program (create_special_program):
    # a tender whose organization isn't verified is kept off the public
    # board too, unless the caller IS that organization's owner (so they
    # can still find/manage it — same reasoning as program_board). A
    # tender with no organization on record can't be gated meaningfully
    # (legacy/migrated data), so it stays visible as before.
    try:
        actor = rn_actor(required=False)
    except Exception:
        actor = None

    def _visible(r):
        if not r.organization:
            return True
        if _owner_verified("organization", r.organization):
            return True
        return bool(actor and (_is_control(actor) or _allowed_owner(actor, "organization", r.organization)))

    rows = [r for r in rows if _visible(r)]

    names = [r.name for r in rows]
    bid_count = {}
    low_bid = {}
    if names:
        for b in frappe.get_all(
            "RN Tender Bid", filters={"tender": ["in", names]},
            fields=["tender", "bid_amount", "status"], limit_page_length=5000,
        ):
            bid_count[b.tender] = bid_count.get(b.tender, 0) + 1
            if b.bid_amount and (b.tender not in low_bid or b.bid_amount < low_bid[b.tender]):
                low_bid[b.tender] = b.bid_amount

    out = []
    for r in rows:
        d = _labels(dict(r))
        docs = _documents(d.pop("work_drawings", None))
        d["drawing_count"] = len(docs["drawings"])
        d["rab_page_count"] = len(docs["rab_pages"])
        d["status_label"] = _TENDER_STATUS.get(r.status, r.status)
        d["bid_count"] = bid_count.get(r.name, 0)
        d["lowest_bid"] = low_bid.get(r.name)
        d["is_open"] = _is_open(r)
        out.append(d)

    return {
        "disaster_event": ev,
        "generated_at": now_datetime(),
        "tenders": out,
        "totals": {
            "total": len(out),
            "open": sum(1 for t in out if t["is_open"]),
            "awarded": sum(1 for t in out if t["status"] == "awarded"),
            "rab_value_total": sum(flt(t.get("rab_total")) for t in out),
            "bids_total": sum(t["bid_count"] for t in out),
        },
    }


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def tender_detail(tender):
    t = frappe.db.get_value(
        "RN Procurement Tender", tender,
        ["name", "title", "location", "scope_description", "donor_program",
         "organization", "rab_total", "rab_document_url", "design_image_url",
         "bidding_opens_at", "bidding_closes_at", "status", "awarded_bid",
         "contact_person", "contact_phone", "notes", "work_drawings", *INFO_FIELDS],
        as_dict=True,
    )
    if not t:
        return {"found": False}
    t.update(_documents(t.pop("work_drawings", None)))
    _labels(t)

    actor = rn_actor(required=False)
    owner = _owns_tender(actor, t)

    if t.organization and not owner:
        from rescue_net.api_donor_program import _owner_verified

        if not _owner_verified("organization", t.organization):
            return {"found": False}

    bids = frappe.get_all(
        "RN Tender Bid", filters={"tender": tender},
        fields=["name", "bidder_name", "bidder_org", "bidder_contact",
                "bid_amount", "bid_days", "proposal_summary", "attachment_url",
                "status", "submitted_at"],
        order_by="bid_amount asc, submitted_at asc", limit_page_length=500,
    )
    for b in bids:
        if not owner:
            b["bidder_contact"] = None  # kontak penawar hanya untuk penyelenggara

    t["found"] = True
    t["status_label"] = _TENDER_STATUS.get(t["status"], t["status"])
    t["is_open"] = _is_open(t)
    t["can_manage"] = bool(owner)
    t["bids"] = bids
    return t


@frappe.whitelist()
def create_tender(disaster_event, title, rab_total=0, scope_description=None,
                  location=None, donor_program=None, organization=None,
                  rab_document_url=None, design_image_url=None, bidding_opens_at=None,
                  bidding_closes_at=None, contact_person=None, contact_phone=None,
                  notes=None, **info):
    actor = rn_actor(required=True)
    info = {k: _clean(k, v) for k, v in info.items() if k in INFO_FIELDS}
    if organization and not (is_system_manager() or can_manage_organization(actor, organization)):
        frappe.throw("Anda bukan pengelola organisasi ini.", frappe.PermissionError)

    # Same rule as a cash campaign (api_donor_program.create_special_program):
    # only a verified organization may actually open real bidding. An
    # unverified org can still prepare the tender, it just stays `draft`
    # (never auto-opens) until they clear the same org verification queue
    # every organization already goes through.
    org_for_check = organization or actor.get("organization")
    owner_verified = False
    if org_for_check:
        from rescue_net.api_donor_program import _owner_verified
        owner_verified = _owner_verified("organization", org_for_check)

    ev = _event(disaster_event)
    doc = frappe.new_doc("RN Procurement Tender")
    if ev and frappe.db.exists("RN Disaster Event", ev):
        doc.disaster_event = ev
    else:
        doc.disaster_event_legacy_id = disaster_event
    doc.title = title
    doc.rab_total = flt(rab_total)
    doc.scope_description = scope_description
    doc.location = location
    doc.donor_program = donor_program if donor_program and frappe.db.exists("RN Donor Program", donor_program) else None
    doc.organization = organization if organization and frappe.db.exists("RN Organization", organization) else actor.get("organization")
    doc.rab_document_url = rab_document_url
    doc.design_image_url = design_image_url
    doc.bidding_opens_at = bidding_opens_at
    doc.bidding_closes_at = bidding_closes_at
    doc.contact_person = contact_person
    doc.contact_phone = contact_phone
    doc.notes = notes
    doc.update(info)
    doc.status = "open" if (bidding_closes_at and owner_verified) else "draft"
    doc.insert(ignore_permissions=True)
    return {"tender": doc.name, "status": doc.status, "owner_verified": owner_verified}


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=20, seconds=3600)
def submit_bid(tender, bidder_name, bid_amount, bid_days=None,
               bidder_org=None, bidder_contact=None, proposal_summary=None,
               attachment_url=None):
    t = frappe.db.get_value(
        "RN Procurement Tender", tender,
        ["name", "status", "bidding_closes_at"], as_dict=True,
    )
    if not t:
        frappe.throw("Tender tidak ditemukan.")
    if not _is_open(t):
        frappe.throw("Tender ini sudah ditutup / tidak menerima penawaran.")

    bidder_name = str(bidder_name or "").strip()
    if not bidder_name or flt(bid_amount) <= 0:
        frappe.throw("Nama penawar dan nilai penawaran wajib diisi.")

    actor = rn_actor(required=False)
    doc = frappe.new_doc("RN Tender Bid")
    doc.tender = tender
    doc.bidder_name = bidder_name[:140]
    doc.bidder_org = bidder_org
    doc.bidder_contact = bidder_contact
    doc.bidder_user = actor.get("name") if actor else None
    doc.bid_amount = flt(bid_amount)
    doc.bid_days = cint(bid_days) if bid_days else None
    doc.proposal_summary = proposal_summary
    doc.attachment_url = attachment_url
    doc.status = "submitted"
    doc.submitted_at = now_datetime()
    doc.insert(ignore_permissions=True)
    return {"bid": doc.name, "status": doc.status}


@frappe.whitelist()
def set_bid_status(bid, status):
    actor = rn_actor(required=True)
    b = frappe.get_doc("RN Tender Bid", bid)
    t = frappe.db.get_value("RN Procurement Tender", b.tender,
                            ["name", "organization"], as_dict=True)
    if not _owns_tender(actor, t):
        frappe.throw("Hanya penyelenggara tender yang dapat menilai penawaran.", frappe.PermissionError)
    if status not in _BID_STATUS:
        frappe.throw("Status penawaran tidak valid.")
    b.status = status
    b.save(ignore_permissions=True)

    if status == "awarded":
        td = frappe.get_doc("RN Procurement Tender", b.tender)
        td.awarded_bid = b.name
        td.status = "awarded"
        td.save(ignore_permissions=True)
        for other in frappe.get_all("RN Tender Bid",
                                    filters={"tender": b.tender, "name": ["!=", b.name],
                                             "status": ["!=", "rejected"]},
                                    pluck="name"):
            frappe.db.set_value("RN Tender Bid", other, "status", "rejected")
    return {"bid": b.name, "status": b.status}


@frappe.whitelist()
def update_tender_status(tender, status):
    actor = rn_actor(required=True)
    t = frappe.db.get_value("RN Procurement Tender", tender,
                            ["name", "organization"], as_dict=True)
    if not _owns_tender(actor, t):
        frappe.throw("Anda bukan penyelenggara tender ini.", frappe.PermissionError)
    if status not in _TENDER_STATUS:
        frappe.throw("Status tender tidak valid.")
    # through the controller: status graph + verified-org gate (L-16)
    doc = frappe.get_doc("RN Procurement Tender", tender)
    doc.status = status
    doc.save(ignore_permissions=True)
    return {"tender": tender, "status": status}


def _manage_tender(tender):
    actor = rn_actor(required=True)
    t = frappe.db.get_value("RN Procurement Tender", tender, ["name", "organization", "status"], as_dict=True)
    if not t:
        frappe.throw("Tender tidak ditemukan.")
    if not _owns_tender(actor, t):
        frappe.throw("Hanya penyelenggara tender yang dapat mengubah tender ini.", frappe.PermissionError)
    return t


@frappe.whitelist(methods=["POST"])
def update_tender_info(tender, **fields):
    """Organiser fills in / corrects the tender information (owner 2026-11-03). Status and winner are
    not changed here (update_tender_status / set_bid_status)."""
    t = _manage_tender(tender)
    if t.status in ("awarded", "cancelled"):
        frappe.throw("Tender yang sudah ditetapkan / dibatalkan tidak bisa diubah.")
    values = {k: _clean(k, v) for k, v in fields.items() if k in EDITABLE_FIELDS}
    if "title" in values and not values["title"]:
        frappe.throw("Judul pekerjaan wajib diisi.")
    doc = frappe.get_doc("RN Procurement Tender", tender)
    doc.update(values)
    doc.save(ignore_permissions=True)
    return tender_detail(tender)


@frappe.whitelist(methods=["POST"])
def upload_tender_file(tender, filename, content_base64, kind="gambar", label=None):
    """Gambar kerja (kind=gambar) or a RAB page (kind=rab): PDF / PNG / JPG / WEBP, max 10 MB, public."""
    import base64
    import json
    import re
    from frappe.utils.file_manager import save_file
    from rescue_net.donor_program.documents import _check_file

    t = _manage_tender(tender)
    if t.status in ("awarded", "cancelled"):
        frappe.throw("Tender yang sudah ditetapkan / dibatalkan tidak bisa diubah.")
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

    doc = frappe.get_doc("RN Procurement Tender", tender)
    entries = _entries(doc.work_drawings)
    same = [d for d in entries if (d.get("kind") == "rab") == (kind == "rab")]
    limit = MAX_RAB_PAGES if kind == "rab" else MAX_DRAWINGS
    if len(same) >= limit:
        frappe.throw(f"Maksimal {limit} berkas. Hapus yang lama dulu.")
    try:
        f = save_file(filename, content, "RN Procurement Tender", tender, is_private=0)
    except frappe.ValidationError:
        raise
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Tender upload")
        frappe.throw("File tidak bisa dibaca (rusak?). Coba simpan ulang sebagai PDF / gambar lalu unggah lagi.")
    item = {"url": f.file_url, "name": filename, "label": (label or "").strip()[:120],
            "pdf": filename.lower().endswith(".pdf")}
    if kind == "rab":
        item["kind"] = "rab"
        if not doc.rab_document_url:
            doc.rab_document_url = f.file_url
    entries.append(item)
    doc.work_drawings = json.dumps(entries, ensure_ascii=False)
    doc.save(ignore_permissions=True)
    return _documents(doc.work_drawings)


@frappe.whitelist(methods=["POST"])
def remove_tender_file(tender, file_url):
    import json

    _manage_tender(tender)
    doc = frappe.get_doc("RN Procurement Tender", tender)
    entries = _entries(doc.work_drawings)
    keep = [d for d in entries if d["url"] != file_url]
    if len(keep) == len(entries):
        frappe.throw("Berkas tidak ditemukan di tender ini.")
    if doc.rab_document_url == file_url:
        rab = [d for d in keep if d.get("kind") == "rab"]
        doc.rab_document_url = rab[0]["url"] if rab else None
    doc.work_drawings = json.dumps(keep, ensure_ascii=False)
    doc.save(ignore_permissions=True)
    return _documents(doc.work_drawings)
