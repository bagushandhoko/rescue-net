import frappe
from frappe.utils import now_datetime, add_days

# Seed for Management Donation tender / RAB (RN Procurement Tender +
# RN Tender Bid). Idempotent: skip a tender whose title already exists.
# Simulation content only.

EVENT = "event-sim-001"


def _resolved_event():
    for cand in (EVENT, "disaster_events:" + EVENT):
        if frappe.db.exists("RN Disaster Event", cand):
            return cand
    try:
        from rescue_net.reference_resolver import resolve_disaster_event
        r = resolve_disaster_event(EVENT)
        if r and frappe.db.exists("RN Disaster Event", r):
            return r
    except Exception:
        pass
    return None


TENDERS = [
    {
        "title": "[SIMULASI] Rehabilitasi 2 ruang kelas SD 3 Samatiga",
        "location": "Samatiga, Aceh Barat",
        "scope_description": "Perbaikan atap, kuda-kuda, plafon, lantai, dan pengecatan 2 ruang kelas. Termasuk instalasi listrik dasar.",
        "rab_total": 185000000,
        "rab_document_url": "https://osiun.tail251e1e.ts.net/rescue-net/blueprint/DISASTER%20MANAGEMENT%20SYSTEM.docx.pdf",
        "status": "open", "days_to_close": 14,
        "contact_person": "Panitia Rehab Sekolah", "contact_phone": "0651-700123",
        "bids": [
            {"bidder_name": "CV Bangun Aceh Mandiri", "bidder_org": "CV Bangun Aceh Mandiri",
             "bidder_contact": "0812-3400-1122", "bid_amount": 178500000, "bid_days": 40,
             "proposal_summary": "Rangka atap baja ringan, garansi 6 bulan.", "status": "submitted"},
            {"bidder_name": "PT Karya Meulaboh", "bidder_org": "PT Karya Meulaboh",
             "bidder_contact": "0813-6001-7788", "bid_amount": 183000000, "bid_days": 35,
             "proposal_summary": "Kayu kelas II, selesai lebih cepat.", "status": "submitted"},
        ],
    },
    {
        "title": "[SIMULASI] Pengeboran sumur bor + tandon RW 04 Johan Pahlawan",
        "location": "Johan Pahlawan, Aceh Barat",
        "scope_description": "Sumur bor dalam 60 m, pompa submersible, tandon 5.000 L + rangka, jaringan pipa 200 m ke titik distribusi.",
        "rab_total": 95000000,
        "rab_document_url": "https://osiun.tail251e1e.ts.net/rescue-net/blueprint/DISASTER%20MANAGEMENT%20SYSTEM.docx.pdf",
        "status": "evaluation", "days_to_close": -1,
        "contact_person": "Pokja Air Bersih", "contact_phone": "0651-700456",
        "bids": [
            {"bidder_name": "CV Tirta Nauli", "bidder_org": "CV Tirta Nauli",
             "bidder_contact": "0852-7700-3344", "bid_amount": 92500000, "bid_days": 21,
             "proposal_summary": "Pengalaman 12 sumur bor pasca-bencana.", "status": "shortlisted"},
            {"bidder_name": "UD Sumber Jaya", "bidder_org": "UD Sumber Jaya",
             "bidder_contact": "0821-6600-9911", "bid_amount": 94000000, "bid_days": 18,
             "proposal_summary": "Alat bor sendiri, mobilisasi cepat.", "status": "submitted"},
            {"bidder_name": "Kelompok Tukang Gampong", "bidder_org": "Swadaya Gampong",
             "bidder_contact": "0813-1122-3300", "bid_amount": 88000000, "bid_days": 30,
             "proposal_summary": "Tenaga lokal, sewa alat bor.", "status": "submitted"},
        ],
    },
]


def _mk_tender(cfg):
    if frappe.db.exists("RN Procurement Tender", {"title": cfg["title"]}):
        return "skip"
    ev = _resolved_event()
    doc = frappe.new_doc("RN Procurement Tender")
    if ev:
        doc.disaster_event = ev
    else:
        doc.disaster_event_legacy_id = EVENT
    for k in ("title", "location", "scope_description", "rab_total",
              "rab_document_url", "status", "contact_person", "contact_phone"):
        doc.set(k, cfg.get(k))
    doc.bidding_opens_at = now_datetime()
    doc.bidding_closes_at = add_days(now_datetime(), cfg.get("days_to_close", 14))
    doc.insert(ignore_permissions=True)

    for b in cfg.get("bids", []):
        bid = frappe.new_doc("RN Tender Bid")
        bid.tender = doc.name
        for bk, bv in b.items():
            bid.set(bk, bv)
        bid.submitted_at = now_datetime()
        bid.insert(ignore_permissions=True)
    return doc.name


def install_defaults():
    if not frappe.db.exists("DocType", "RN Procurement Tender"):
        print("[tender_defaults] doctype not migrated yet — skip")
        return {"created": 0, "skipped": 0}
    made = skipped = 0
    for cfg in TENDERS:
        r = _mk_tender(cfg)
        made += 1 if r not in ("skip", None) else 0
        skipped += 1 if r == "skip" else 0
    frappe.db.commit()
    print(f"[tender_defaults] created {made}, skipped {skipped}")
    return {"created": made, "skipped": skipped}
