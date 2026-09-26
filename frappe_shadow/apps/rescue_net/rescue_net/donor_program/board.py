"""Donor programs — program board, cash donations, program detail, publish recheck."""

from collections import defaultdict

import frappe
from frappe.rate_limiter import rate_limit
from rescue_net.reference_resolver import resolve_disaster_event
from rescue_net.access_policy import is_system_manager

from frappe.utils import flt, now_datetime, nowdate

from rescue_net.api_kitchen import (
    rn_actor,
    _actor_name,
    _allowed_poskos,
    _is_control,
    _assert_operate,
)

from rescue_net.donor_program.common import (  # noqa: F401
    SPECIAL_PROGRAM_FIELDS,
    UPDATE_FIELDS,
    _PRIORITY_CRITICAL,
    _PROGRAM_TYPE_LABELS,
    _allowed_owner,
    _assert_owner,
    _campaign_owner_verified,
    _program,
)


def _program_type_label(value):
    if not value:
        return "Lainnya"
    return _PROGRAM_TYPE_LABELS.get(value, value.replace("_", " ").title())


def _pk_drill(title, sub, href=""):
    return {"title": title, "sub": sub, "href": href}


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def program_board(disaster_event=None):
    """Program Khusus dashboard (matches the DMS mock-up), guest read-only.

    Shows every public RN Donor Program for the event regardless of
    program_type (program_type is just a category label, e.g.
    energy_support/water_sanitation/health — "special_program" was only
    ever the create-form's default value, not a real scoping filter).
    """
    event = resolve_disaster_event(disaster_event)

    filters = {"public_visibility": "summary_public"}
    if event:
        filters["disaster_event"] = event

    rows = frappe.get_all(
        "RN Donor Program",
        filters=filters,
        fields=SPECIAL_PROGRAM_FIELDS,
        order_by="creation desc",
        limit_page_length=1000,
        ignore_permissions=True,
    )

    # Also surface the caller's OWN not-yet-public programs (kept off the
    # public list until their org/posko/account is verified — see
    # _campaign_owner_verified) so they can find & manage/publish them.
    own_hidden_names = set()
    try:
        actor = rn_actor(required=False)
    except Exception:
        actor = None
    if actor:
        hidden_filters = {"public_visibility": ["!=", "summary_public"]}
        if event:
            hidden_filters["disaster_event"] = event
        for hr in frappe.get_all(
            "RN Donor Program", filters=hidden_filters,
            fields=SPECIAL_PROGRAM_FIELDS, limit_page_length=1000,
        ):
            if _allowed_owner(actor, hr.owner_type, hr.owner_id):
                rows.append(hr)
                own_hidden_names.add(hr.name)

    names = [r.name for r in rows]
    updates = frappe.get_all(
        "RN Donor Program Update",
        filters={"program": ["in", names], "public_visibility": "summary_public"},
        fields=["program", "progress_percent", "update_type", "observed_at", "creation"],
        order_by="creation desc",
        limit_page_length=3000,
    ) if names else []

    updates_by_program = defaultdict(list)
    for u in updates:
        updates_by_program[u.program].append(u)

    # "Project base" vs "cash base": a program that funds a real
    # RN Procurement Tender (design/RAB/pelaksana, already built for
    # Pengadaan & Tender) is project-based; everything else is a plain
    # cash campaign. One donation list (program_donations) works for both.
    tender_by_program = {}
    if names:
        for t in frappe.get_all(
            "RN Procurement Tender", filters={"donor_program": ["in", names]},
            fields=["name", "donor_program", "status", "title"],
            order_by="creation asc", limit_page_length=2000,
        ):
            tender_by_program.setdefault(t.donor_program, t)

    today = nowdate()
    programs = []
    for r in rows:
        prog_updates = updates_by_program.get(r.name, [])
        if prog_updates:
            progress = flt(prog_updates[0].progress_percent)
        elif flt(r.target_amount) > 0:
            progress = round(min(100.0, 100.0 * flt(r.current_amount) / flt(r.target_amount)), 1)
        else:
            progress = 0.0

        location = r.target_location or r.location or "-"
        is_late = bool(
            r.status == "active"
            and r.end_date
            and str(r.end_date) < str(today)
        )

        tender = tender_by_program.get(r.name)
        programs.append({
            "name": r.name,
            "program_name": r.program_name,
            "category": _program_type_label(r.program_type),
            "location": location,
            "status": r.status,
            "priority": r.priority,
            "progress_percent": progress,
            "target_description": r.target_description,
            "target_beneficiaries": r.target_beneficiaries,
            "budget_target": flt(r.budget_target),
            "budget_received": flt(r.budget_received),
            "budget_spent": flt(r.budget_spent),
            "start_date": r.start_date,
            "end_date": r.end_date,
            "update_count": len(prog_updates),
            "is_late": is_late,
            "program_kind": "project" if tender else "cash",
            "tender": tender.name if tender else None,
            "tender_status": tender.status if tender else None,
            "is_own_hidden": r.name in own_hidden_names,
        })

    active = [p for p in programs if p["status"] == "active"]
    critical = [
        p for p in programs
        if (p["priority"] or "").lower() in _PRIORITY_CRITICAL and p["status"] != "completed"
    ]
    completed = [p for p in programs if p["status"] == "completed"]
    late = [p for p in programs if p["is_late"]]
    underserved_locations = {
        p["location"] for p in active
        if p["update_count"] == 0 and p["location"] != "-"
    }
    needs_support = [
        p for p in active
        if (p["priority"] or "").lower() in _PRIORITY_CRITICAL and p["progress_percent"] < 50
    ]

    totals = {
        "program_aktif": len(active),
        "program_critical": len(critical),
        "program_selesai": len(completed),
        "milestone_terlambat": len(late),
        "lokasi_belum_terlayani": len(underserved_locations),
        "butuh_support": len(needs_support),
    }

    kpi_items = {
        "program_aktif_items": [
            _pk_drill(p["program_name"], p["category"] + " · " + p["location"]) for p in active
        ],
        "program_critical_items": [
            _pk_drill(p["program_name"], p["location"] + " · prioritas " + (p["priority"] or "-"))
            for p in critical
        ],
        "program_selesai_items": [
            _pk_drill(p["program_name"], p["location"]) for p in completed
        ],
        "milestone_terlambat_items": [
            _pk_drill(p["program_name"], "Target selesai " + str(p["end_date"])) for p in late
        ],
        "lokasi_belum_terlayani_items": [
            _pk_drill(loc, "Belum ada update program") for loc in underserved_locations
        ],
        "butuh_support_items": [
            _pk_drill(p["program_name"], f"Progress {p['progress_percent']}% · prioritas {p['priority'] or '-'}")
            for p in needs_support
        ],
    }

    return {
        "disaster_event": event,
        "generated_at": now_datetime(),
        "totals": totals,
        "kpi_items": kpi_items,
        "programs": programs,
    }


@frappe.whitelist()
def create_cash_donation(donor_program, amount, is_anonymous=0, message=None,
                          donor_name=None, donor_contact=None):
    actor = rn_actor()
    row = _program(donor_program)

    amount = flt(amount)
    if amount <= 0:
        frappe.throw("Nominal donasi harus lebih dari 0.")
    is_anonymous = 1 if str(is_anonymous).lower() in ("1", "true", "yes", "on") else 0

    acct = None
    if actor and actor.name:
        acct = frappe.db.get_value(
            "RN User Account", actor.name, ["title", "phone", "email"], as_dict=True
        )
    name_val = (donor_name or "").strip() or (acct and acct.title) or _actor_name(actor) or "Donatur"
    contact_val = (donor_contact or "").strip() or (acct and (acct.phone or acct.email)) or None

    doc = frappe.new_doc("RN Cash Donation")
    doc.disaster_event = row.disaster_event
    doc.donor_program = donor_program
    doc.donor_user = actor.name if actor and actor.name else None
    doc.donor_name = name_val
    doc.donor_contact = contact_val
    doc.is_anonymous = is_anonymous
    doc.amount = amount
    doc.message = (message or "").strip() or None
    doc.status = "pending"
    doc.insert(ignore_permissions=True)

    return {"donation": doc.name, "status": doc.status, "amount": doc.amount}


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def program_donations(donor_program):
    """Public donation wall (received only, donor masked if anonymous) for
    one program. If the caller manages that program's owner, also returns
    the real pending queue for them to confirm/reject."""
    row = _program(donor_program)

    received = frappe.get_all(
        "RN Cash Donation",
        filters={"donor_program": donor_program, "status": "received"},
        fields=["name", "donor_name", "is_anonymous", "amount", "message", "confirmed_at"],
        order_by="confirmed_at desc", limit_page_length=200,
    )
    public_rows = [{
        "name": r.name,
        "donor_name": "Donatur Anonim" if r.is_anonymous else r.donor_name,
        "amount": flt(r.amount),
        "message": r.message,
        "confirmed_at": r.confirmed_at,
    } for r in received]

    can_manage = False
    pending = []
    try:
        actor = rn_actor(required=False)
    except Exception:
        actor = None
    if actor:
        try:
            can_manage = bool(_is_control(actor) or _allowed_owner(actor, row.owner_type, row.owner_id))
        except Exception:
            can_manage = False
    if can_manage:
        pending = [
            dict(r) for r in frappe.get_all(
                "RN Cash Donation",
                filters={"donor_program": donor_program, "status": "pending"},
                fields=["name", "donor_name", "donor_contact", "is_anonymous", "amount", "message", "creation"],
                order_by="creation desc", limit_page_length=200,
            )
        ]

    return {
        "donor_program": donor_program,
        "public": public_rows,
        "total_received": sum(flt(r.amount) for r in received),
        "donor_count": len(public_rows),
        "can_manage": can_manage,
        "pending": pending,
    }


@frappe.whitelist()
def decide_cash_donation(donation, action, note=None):
    """Program owner confirms money actually arrived, or rejects a bogus
    pledge. Confirming is the ONLY thing that moves a donation onto the
    public wall and into the program's real budget_received."""
    actor = rn_actor()
    from rescue_net.services.money import add_to_program, lock
    lock("RN Cash Donation", donation)          # L-17: a double click waits, then sees "decided"
    doc = frappe.get_doc("RN Cash Donation", donation)
    if doc.status != "pending":
        frappe.throw("Donasi ini sudah diputuskan.")

    row = _program(doc.donor_program)
    if not (_is_control(actor) or _allowed_owner(actor, row.owner_type, row.owner_id)):
        frappe.throw("Anda bukan pengelola program/lembaga penerima ini.", frappe.PermissionError)

    action = str(action or "").strip().lower()
    if action not in ("confirm", "reject"):
        frappe.throw("Aksi tidak valid (confirm/reject)")

    doc.status = "received" if action == "confirm" else "rejected"
    doc.confirmed_by = actor.name if actor and getattr(actor, "name", None) else frappe.session.user
    doc.confirmed_at = now_datetime()
    if note is not None:
        doc.confirmation_note = str(note)[:500]
    doc.save(ignore_permissions=True)

    if action == "confirm":
        add_to_program(doc.donor_program, "budget_received", doc.amount)

    return {"donation": doc.name, "status": doc.status}


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def program_detail(program):
    row = frappe.db.get_value(
        "RN Donor Program", program, SPECIAL_PROGRAM_FIELDS, as_dict=True,
    )

    if not row:
        frappe.throw("Program tidak ditemukan", frappe.DoesNotExistError)

    if row.public_visibility != "summary_public":
        # Not public yet — still let the owner see their own program (e.g.
        # to check why it's hidden / recheck verification), everyone else
        # gets the same not-found response as before.
        try:
            actor = rn_actor(required=False)
        except Exception:
            actor = None
        if not (actor and (_is_control(actor) or _allowed_owner(actor, row.owner_type, row.owner_id))):
            frappe.throw("Program tidak ditemukan atau tidak publik", frappe.DoesNotExistError)

    updates = frappe.get_all(
        "RN Donor Program Update",
        filters={"program": program, "public_visibility": "summary_public"},
        fields=UPDATE_FIELDS,
        order_by="creation desc",
        limit_page_length=500,
    )

    if updates:
        progress = flt(updates[0].progress_percent)
    elif flt(row.target_amount) > 0:
        progress = round(min(100.0, 100.0 * flt(row.current_amount) / flt(row.target_amount)), 1)
    else:
        progress = 0.0

    bukti = []
    try:
        from rescue_net.api_control_centre import event_evidence

        title_l = (row.program_name or "").lower()
        loc_l = (row.target_location or row.location or "").lower()

        for ev in event_evidence(row.disaster_event, limit=150):
            loc = str(ev.get("location_text") or "").lower()
            hit = (
                (title_l and len(title_l) > 4 and title_l in loc)
                or (loc_l and len(loc_l) > 3 and loc_l in loc)
            )
            if hit:
                bukti.append(ev)

        bukti.sort(
            key=lambda r: str(r.get("created_at") or r.get("creation") or ""),
            reverse=True,
        )
        bukti = bukti[:8]
    except Exception:
        bukti = []

    try:
        donations = program_donations(program)
    except Exception:
        donations = {"public": [], "total_received": 0, "donor_count": 0, "can_manage": False, "pending": []}

    # Project-based program: the "design/RAB/pelaksana" detail already
    # modeled on Pengadaan & Tender, shown as part of this same donation
    # page per owner request instead of a separate disconnected page.
    project = None
    tender_row = frappe.db.get_value(
        "RN Procurement Tender", {"donor_program": program},
        ["name", "title", "scope_description", "location", "rab_total",
         "rab_document_url", "design_image_url", "bidding_opens_at", "bidding_closes_at",
         "status", "awarded_bid", "contact_person", "contact_phone"],
        as_dict=True, order_by="creation asc",
    )
    if tender_row:
        from rescue_net.api_tender import _TENDER_STATUS

        pelaksana = None
        if tender_row.awarded_bid:
            pelaksana = frappe.db.get_value(
                "RN Tender Bid", tender_row.awarded_bid, ["bidder_name", "bidder_org"], as_dict=True,
            )
        project = {
            **dict(tender_row),
            "status_label": _TENDER_STATUS.get(tender_row.status, tender_row.status),
            "pelaksana": (pelaksana.bidder_org or pelaksana.bidder_name) if pelaksana else None,
        }

    try:
        detail_actor = rn_actor(required=False)
    except Exception:
        detail_actor = None
    can_manage = bool(detail_actor and (_is_control(detail_actor) or _allowed_owner(detail_actor, row.owner_type, row.owner_id)))
    owner_verified = _campaign_owner_verified(detail_actor, row.owner_type, row.owner_id) if can_manage else None

    return {
        "program": {
            **dict(row),
            "category": _program_type_label(row.program_type),
            "progress_percent": progress,
            "program_kind": "project" if project else "cash",
        },
        "updates": [dict(u) for u in updates],
        "bukti": bukti,
        "donations": donations,
        "project": project,
        "can_manage": can_manage,
        "owner_verified": owner_verified,
        "note": (
            "Rencana Kerja/Dokumen tidak dimodelkan sebagai daftar rinci "
            "terpisah — gunakan Anggaran (target/diterima/terpakai) dan "
            "Riwayat Update sebagai sumber kebenaran progres program."
        ),
    }


@frappe.whitelist()
def recheck_and_publish(donor_program):
    """Owner asks to re-check verification and go public now that they've
    (hopefully) cleared api_verification.approval_queue — the create_*
    functions can't do this automatically since verification happens
    after creation. Also opens any linked tender still stuck in `draft`
    for the same reason, if it already has real bidding dates."""
    actor = rn_actor()
    row = _program(donor_program)
    _assert_owner(actor, row.owner_type, row.owner_id)

    if not _campaign_owner_verified(actor, row.owner_type, row.owner_id):
        frappe.throw(
            "Organisasi/posko/akun Anda belum terverifikasi. "
            "Selesaikan verifikasi lewat Verification & Approval dulu, baru coba lagi."
        )

    frappe.db.set_value("RN Donor Program", donor_program, "public_visibility", "summary_public")

    opened = []
    for t in frappe.get_all(
        "RN Procurement Tender", filters={"donor_program": donor_program, "status": "draft"},
        fields=["name", "bidding_closes_at"],
    ):
        if t.bidding_closes_at:
            frappe.db.set_value("RN Procurement Tender", t.name, "status", "open")
            opened.append(t.name)

    return {"donor_program": donor_program, "public_visibility": "summary_public", "tenders_opened": opened}
