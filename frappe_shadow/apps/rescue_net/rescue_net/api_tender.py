"""Management Donation — tender / RAB. Sebuah program donasi yang membangun
sesuatu bisa menampilkan B&Q / RAB untuk ditenderkan (dokumen bisa diunduh),
dan pihak lain bisa mengajukan penawaran dengan batas waktu.
"""

import frappe
from frappe.utils import now_datetime, flt, cint, get_datetime

from rescue_net.access_policy import rn_actor, is_system_manager, can_manage_organization
from rescue_net.reference_resolver import resolve_disaster_event

_TENDER_STATUS = {"draft": "Draft", "open": "Terbuka", "evaluation": "Evaluasi",
                  "awarded": "Ditetapkan", "cancelled": "Dibatalkan"}
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
def tender_board(disaster_event=None, limit=200):
    ev = _event(disaster_event)
    rows = frappe.get_all(
        "RN Procurement Tender",
        or_filters=_event_or_filters(disaster_event, ev),
        fields=["name", "title", "location", "donor_program", "organization",
                "rab_total", "rab_document_url", "bidding_opens_at",
                "bidding_closes_at", "status", "awarded_bid", "scope_description",
                "modified"],
        order_by="bidding_closes_at asc, modified desc",
        limit_page_length=cint(limit) or 200,
    )
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
        d = dict(r)
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
def tender_detail(tender):
    t = frappe.db.get_value(
        "RN Procurement Tender", tender,
        ["name", "title", "location", "scope_description", "donor_program",
         "organization", "rab_total", "rab_document_url", "bidding_opens_at",
         "bidding_closes_at", "status", "awarded_bid", "contact_person",
         "contact_phone", "notes"],
        as_dict=True,
    )
    if not t:
        return {"found": False}

    actor = rn_actor(required=False)
    owner = _owns_tender(actor, t)

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
                  rab_document_url=None, bidding_opens_at=None,
                  bidding_closes_at=None, contact_person=None, contact_phone=None,
                  notes=None):
    actor = rn_actor(required=True)
    if organization and not (is_system_manager() or can_manage_organization(actor, organization)):
        frappe.throw("Anda bukan pengelola organisasi ini.", frappe.PermissionError)

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
    doc.bidding_opens_at = bidding_opens_at
    doc.bidding_closes_at = bidding_closes_at
    doc.contact_person = contact_person
    doc.contact_phone = contact_phone
    doc.notes = notes
    doc.status = "open" if bidding_closes_at else "draft"
    doc.insert(ignore_permissions=True)
    return {"tender": doc.name, "status": doc.status}


@frappe.whitelist(allow_guest=True)
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
    frappe.db.set_value("RN Procurement Tender", tender, "status", status)
    return {"tender": tender, "status": status}
