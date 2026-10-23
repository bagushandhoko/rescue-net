"""Logistics — distribution flows, flow status, evidence, public/Control Centre logistics views."""

from collections import defaultdict

import frappe
from frappe.rate_limiter import rate_limit
from rescue_net.reference_resolver import resolve_disaster_event, resolve_posko
from frappe.utils import cint, flt, now_datetime

from rescue_net.access_policy import (
    approved_member,
    can_manage_organization,
    can_manage_posko,
    is_system_manager,
    public_posko_allowed,
    rn_actor,
)
from rescue_net.intelligence.freshness import freshness
from rescue_net.rn_logistics.doctype.rn_distribution_flow.rn_distribution_flow import TRANSITIONS
from rescue_net.intelligence.normalization import normalize_unit

from rescue_net.logistics.common import (  # noqa: F401
    ALLOWED_EVIDENCE_DOCTYPES,
    OPERATOR_ROLES,
    _can_contribute,
    _can_operate,
)


@frappe.whitelist()
def create_flow(
    destination_posko,
    item_text,
    quantity=None,
    unit=None,
    quantity_mode="unknown",
    source_posko=None,
    logistic_need=None,
    aid_offer=None,
    transport_reference=None,
    transport_provider=None,
    transport_space=None,
    eta_final=None,
    disaster_event=None,
    window_from=None,
    window_to=None,
    weight_kg=None,
    volume_m3=None,
    first_mile=None,
    first_mile_space=None,
):
    # RN_CANONICAL_REF destination_posko = resolve_posko(destination_posko)
    destination_posko = resolve_posko(destination_posko)
    # RN_CANONICAL_REF source_posko = resolve_posko(source_posko)
    source_posko = resolve_posko(source_posko)
    actor = rn_actor()

    if not _can_operate(actor, destination_posko):
        if not source_posko or not _can_operate(actor, source_posko):
            frappe.throw(
                "Anda tidak dapat membuat flow untuk Posko ini",
                frappe.PermissionError,
            )

    if source_posko and not aid_offer:
        _assert_in_stock(source_posko, item_text, quantity, unit)

    transport_doc = None
    book_space = None       # another posko's armada -> booking (see _book_for_flow)

    # owner 2026-10-20: after the main armada, how the cargo reaches its
    # handover point (or the destination without one): self_deliver / queue
    # (a posko distribusi picks it up) / transporter (a booked courier)
    first_mile = (first_mile or "").strip() or None
    if first_mile not in (None, "self_deliver", "queue", "transporter"):
        frappe.throw("Pilihan cara kirim tidak valid.")
    if first_mile == "transporter":
        if not first_mile_space:
            frappe.throw("Pilih posko distribusi transporter.")
        if not (flt(weight_kg) > 0 or flt(volume_m3) > 0):
            frappe.throw("Isi perkiraan berat (kg) atau volume (m3) muatan untuk booking transporter.")
        if not transport_space:
            # no main armada: the courier carries it all the way = the main leg
            transport_space, first_mile_space = first_mile_space, None
    else:
        first_mile_space = None

    if transport_space:
        locked = frappe.db.sql(
            """
            SELECT name, transport_status
            FROM `tabRN Transport Space`
            WHERE name=%s
            FOR UPDATE
            """,
            (transport_space,),
            as_dict=True,
        )

        if not locked:
            frappe.throw("Transport tidak ditemukan")

        space_posko = frappe.db.get_value("RN Transport Space", transport_space, "coordination_posko")
        if _can_contribute(actor, space_posko):
            # the armada's own posko puts the shipment on it directly
            if locked[0].transport_status != "available":
                frappe.throw(
                    "Transport sudah dipakai atau tidak tersedia"
                )
            transport_doc = frappe.get_doc("RN Transport Space", transport_space)
        else:
            # owner 2026-10-19: another posko's armada is BOOKED — same
            # organisation approved at once, else that posko confirms
            if locked[0].transport_status in ("completed", "cancelled"):
                frappe.throw("Armada ini sudah selesai / dibatalkan.")
            if not (flt(weight_kg) > 0 or flt(volume_m3) > 0):
                frappe.throw("Isi perkiraan berat (kg) atau volume (m3) muatan untuk booking armada.")
            book_space = transport_space

    aid_doc = None

    if aid_offer:
        locked_aid = frappe.db.sql(
            """
            SELECT name, offer_status
            FROM `tabRN Aid Offer`
            WHERE name=%s
            FOR UPDATE
            """,
            (aid_offer,),
            as_dict=True,
        )

        if not locked_aid:
            frappe.throw("Aid Offer tidak ditemukan")

        if locked_aid[0].offer_status not in (
            "available",
            "need_pickup",
        ):
            frappe.throw(
                "Aid Offer sudah dialokasikan atau tidak tersedia"
            )

        aid_doc = frappe.get_doc(
            "RN Aid Offer",
            aid_offer,
        )

        if (
            aid_doc.target_posko
            and aid_doc.target_posko != destination_posko
        ):
            frappe.throw(
                "Aid Offer ditujukan ke Posko yang berbeda"
            )

    need_doc = None

    if logistic_need:
        need_doc = frappe.get_doc(
            "RN Logistic Need",
            logistic_need,
        )

        if (
            need_doc.posko
            and need_doc.posko != destination_posko
        ):
            frappe.throw(
                "Kebutuhan berasal dari Posko yang berbeda"
            )

        # L-20: no new flow for a need that is already closed
        from rescue_net.api_control_centre import _DRILL_CLOSED_NEED
        if str(need_doc.need_status or "open").lower() in _DRILL_CLOSED_NEED:
            frappe.throw(
                f"Kebutuhan ini sudah ditutup ({need_doc.need_status})."
            )

    doc = frappe.new_doc("RN Distribution Flow")
    doc.title = item_text
    doc.destination_posko = destination_posko
    doc.source_posko = source_posko
    # event-scope the flow so it shows on the event dashboards / pickup queue
    doc.disaster_event = (
        _flow_event(disaster_event, source_posko, destination_posko)
        or frappe.db.get_value("RN Posko", source_posko, "disaster_event")
        or frappe.db.get_value("RN Posko", destination_posko, "disaster_event")
    )
    doc.item_name = item_text
    doc.raw_item_text = item_text

    if quantity not in (None, ""):
        doc.quantity = flt(quantity)

    doc.unit = unit
    doc.quantity_mode = quantity_mode or "unknown"
    doc.logistic_need = logistic_need
    doc.aid_offer = aid_offer
    doc.transport_reference = transport_reference
    doc.transport_provider = transport_provider
    doc.transport_space = transport_doc.name if transport_doc else None   # booking: set on confirm
    if doc.meta.has_field("first_mile"):
        doc.first_mile = first_mile
    doc.eta_final = eta_final
    doc.flow_status = "planned"
    doc.insert(ignore_permissions=True)

    if transport_doc:
        frappe.db.set_value(
            "RN Transport Space",
            transport_doc.name,
            {
                "transport_status":"reserved",
                "source_updated_at":now_datetime(),
            },
            update_modified=False,
        )

    main_drop = None
    if transport_space and first_mile:
        main_drop = frappe.db.get_value("RN Transport Space", transport_space, "handover_location") or None
    booking = (_book_for_flow(actor, doc, book_space, window_from, window_to, weight_kg, volume_m3,
                              brought_in=bool(first_mile))
               if book_space else None)
    first_booking = None
    if first_mile_space:
        # courier to the main armada's handover point
        first_booking = _book_for_flow(actor, doc, first_mile_space, window_from, window_to, weight_kg,
                                       volume_m3, leg="first_mile", dropoff=main_drop)

    if aid_doc:
        frappe.db.set_value(
            "RN Aid Offer",
            aid_doc.name,
            {
                "offer_status":"reserved",
                "source_updated_at":now_datetime(),
            },
            update_modified=False,
        )

    if (
        need_doc
        and (need_doc.need_status or "open") == "open"
    ):
        frappe.db.set_value(
            "RN Logistic Need",
            need_doc.name,
            "need_status",
            "in_progress",
            update_modified=False,
        )

    from rescue_net.services.access_status import access_warnings

    return {
        "flow":doc.name,
        "flow_status":doc.flow_status,
        "canonical_group":doc.canonical_group,
        "access_warnings": access_warnings(destination_posko),  # nasihat saja (10e)
        "booking": booking.name if booking else None,
        "booking_status": booking.status if booking else None,
        "verification_pin": booking.verification_pin if booking else None,
        "first_mile": first_mile,
        "first_mile_booking": first_booking.name if first_booking else None,
        "first_mile_status": first_booking.status if first_booking else None,
    }


@frappe.whitelist()
def update_flow_status(
    flow,
    new_status,
    received_quantity=None,
    received_unit=None,
    receipt_note=None,
):
    actor = rn_actor()
    doc = frappe.get_doc("RN Distribution Flow", flow)

    allowed_actor = (
        (doc.source_posko and _can_operate(actor, doc.source_posko))
        or
        (doc.destination_posko and _can_operate(actor, doc.destination_posko))
    )

    if not allowed_actor:
        frappe.throw(
            "Anda tidak dapat memperbarui flow ini",
            frappe.PermissionError,
        )

    current = doc.flow_status or "planned"

    if new_status not in TRANSITIONS.get(current, set()):
        frappe.throw(
            f"Transisi {current} → {new_status} tidak diperbolehkan"
        )

    now = now_datetime()

    doc.flow_status = new_status
    doc.source_updated_at = now
    doc.last_updated_by_user = actor.name

    field_map = {
        "assigned_pickup":"assigned_pickup_at",
        "dispatched":"dispatched_at",
        "in_transit":"in_transit_at",
        "arrived_at_posko":"arrived_at",
        "received":"received_at",
        "cancelled":"cancelled_at",
    }

    if new_status in field_map:
        setattr(doc, field_map[new_status], now)

    if received_quantity not in (None, ""):
        doc.received_quantity = flt(received_quantity)

    if received_unit:
        doc.received_unit = received_unit

    if receipt_note:
        doc.receipt_note = receipt_note

    doc.save(ignore_permissions=True)

    # armada + aid offer follow in RNDistributionFlow.on_update (L-11)

    return {
        "flow":doc.name,
        "previous_status":current,
        "flow_status":doc.flow_status,
        "received_quantity":doc.received_quantity,
        "received_unit":doc.received_unit,
        "stock_created":False,
        "note":"Penerimaan tidak otomatis menjadi stok; stok harus diperbarui melalui Stock Observation.",
    }


@frappe.whitelist()
def add_evidence(
    linked_doctype,
    linked_name,
    file_url,
    evidence_type="photo",
    caption=None,
    observed_at=None,
):
    actor = rn_actor()

    if linked_doctype not in ALLOWED_EVIDENCE_DOCTYPES:
        frappe.throw("Jenis objek evidence tidak didukung")

    if not frappe.db.exists(linked_doctype, linked_name):
        frappe.throw("Objek evidence tidak ditemukan")

    posko = None

    if linked_doctype == "RN Logistic Need":
        posko = frappe.db.get_value(linked_doctype, linked_name, "posko")
    elif linked_doctype == "RN Aid Offer":
        posko = frappe.db.get_value(linked_doctype, linked_name, "target_posko")
    elif linked_doctype == "RN Distribution Flow":
        posko = frappe.db.get_value(linked_doctype, linked_name, "destination_posko")
    elif linked_doctype == "RN Stock Observation":
        posko = frappe.db.get_value(linked_doctype, linked_name, "posko")
    elif linked_doctype == "RN Transport Space":
        posko = frappe.db.get_value(
            linked_doctype,
            linked_name,
            "coordination_posko",
        )

    if posko and not _can_contribute(actor, posko):
        frappe.throw(
            "Anda tidak dapat menambahkan evidence ke data ini",
            frappe.PermissionError,
        )

    doc = frappe.new_doc("RN Operational Evidence")
    doc.linked_doctype = linked_doctype
    doc.linked_name = linked_name
    doc.posko = posko
    doc.file_url = file_url
    doc.evidence_type = evidence_type
    doc.caption = caption
    doc.observed_at = observed_at or now_datetime()
    doc.uploaded_at = now_datetime()
    doc.uploader_user = actor.name
    doc.verification_status = "pending"
    doc.insert(ignore_permissions=True)

    return {
        "evidence":doc.name,
        "verification_status":doc.verification_status,
    }


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def public_dashboard(posko):
    if not public_posko_allowed(posko):
        frappe.throw(
            "Detail Posko tidak dibuka untuk publik",
            frappe.PermissionError,
        )

    posko_row = frappe.db.get_value(
        "RN Posko",
        posko,
        [
            "name","title","posko_type",
            "public_participation","accept_goods",
            "accept_volunteers","accept_donations",
            "accept_partners","public_service_access",
        ],
        as_dict=True,
    )

    latest_stock = frappe.get_all(
        "RN Stock Observation",
        filters={
            "posko":posko,
            "stock_state":"available",
        },
        fields=[
            "canonical_group","canonical_item",
            "quantity","unit","quantity_mode",
            "quantity_min","quantity_max",
            "observed_at","source_updated_at",
            "freshness_policy_minutes","modified",
        ],
        order_by="observed_at desc",
        limit_page_length=100,
    )

    for row in latest_stock:
        row["freshness"] = freshness(
            row.source_updated_at,
            row.observed_at,
            None,
            row.freshness_policy_minutes,
            "stock",
        )

    return {
        "posko":posko_row,
        "stock_observations":latest_stock,
    }


def _require_control_centre():
    actor = rn_actor()

    if not (
        is_system_manager()
        or actor.role in OPERATOR_ROLES
    ):
        frappe.throw(
            "Akses Control Centre diperlukan",
            frappe.PermissionError,
        )

    return actor


@frappe.whitelist()
def control_centre_logistics():
    _require_control_centre()

    # Latest AVAILABLE stock per distinct Posko + canonical group + unit.
    rows = frappe.get_all(
        "RN Stock Observation",
        filters={"stock_state":"available"},
        fields=[
            "name","posko","canonical_group",
            "canonical_item","quantity","unit",
            "quantity_mode","quantity_min","quantity_max",
            "observed_at","source_updated_at",
            "freshness_policy_minutes","modified",
        ],
        order_by="observed_at desc",
        limit_page_length=5000,
    )

    latest = {}
    for row in rows:
        group = row.canonical_group or row.canonical_item or "Belum Dikelompokkan"
        key = (row.posko, group, normalize_unit(row.unit))
        if key not in latest:
            latest[key] = row

    grouped = defaultdict(list)

    for row in latest.values():
        group = row.canonical_group or row.canonical_item or "Belum Dikelompokkan"
        grouped[(group, normalize_unit(row.unit))].append(row)

    stock_summary = []

    for (group, unit), members in grouped.items():
        known = []
        estimated = []
        fresh_count = 0
        stale_count = 0

        for row in members:
            fr = freshness(
                row.source_updated_at,
                row.observed_at,
                None,
                row.freshness_policy_minutes,
                "stock",
            )

            if fr["status"] == "fresh":
                fresh_count += 1
            elif fr["status"] == "stale":
                stale_count += 1

            if row.quantity_mode == "exact":
                known.append(flt(row.quantity))
            elif row.quantity_mode == "estimated":
                estimated.append(flt(row.quantity))
            elif row.quantity_mode == "range":
                if row.quantity_min or row.quantity_max:
                    estimated.append(
                        flt(row.quantity_max or row.quantity_min)
                    )

        stock_summary.append({
            "canonical_group":group,
            "unit":unit or None,
            "posko_count":len(members),
            "exact_total":sum(known) if known else None,
            "estimated_component":sum(estimated) if estimated else None,
            "fresh_count":fresh_count,
            "stale_count":stale_count,
            "rule":"SUM only across distinct Posko scopes with same canonical group and unit",
        })

    flows = frappe.get_all(
        "RN Distribution Flow",
        filters={
            "flow_status":[
                "in",
                [
                    "assigned_pickup",
                    "dispatched",
                    "in_transit",
                    "arrived_at_posko",
                    "partially_received",
                ],
            ]
        },
        fields=[
            "flow_status","canonical_group",
            "quantity","unit","quantity_mode",
            "received_quantity","received_unit",
        ],
        limit_page_length=5000,
    )

    return {
        "available_stock":stock_summary,
        "pipeline_count":len(flows),
        "pipeline":flows,
        "available_transport_count":frappe.db.count(
            "RN Transport Space",
            {"transport_status":"available"},
        ),
        "important_rule":(
            "Aid Offer, Distribution Flow, Received goods, and Stock Observation "
            "are separate states. Received flow never creates available stock automatically."
        ),
    }


def _flow_event(disaster_event, source_posko, destination_posko):
    """The disaster picked on the send form, if the sending posko serves it."""
    if not disaster_event:
        return None
    from rescue_net.control_centre.common import posko_served_events
    from rescue_net.reference_resolver import resolve_disaster_event

    ev = resolve_disaster_event(disaster_event) or disaster_event
    for p in (source_posko, destination_posko):
        if p and ev in posko_served_events(p):
            return ev
    frappe.throw("Posko ini tidak menangani bencana yang dipilih.")


def _same_org_armada(actor, source_posko, space):
    """Armada of the sender's own organisation."""
    org_src = frappe.db.get_value("RN Posko", source_posko, "organization") if source_posko else None
    org_arm = frappe.db.get_value("RN Posko", space.coordination_posko, "organization")
    return bool(org_src and org_src == org_arm)


def _book_for_flow(actor, flow, transport_space, window_from=None, window_to=None,
                   weight_kg=None, volume_m3=None, leg="main", dropoff=None, brought_in=False):
    """Booking for a shipment (owner 2026-10-19). Same organisation ->
    confirmed at once and the flow rides the armada; otherwise `requested`
    until the armada's posko confirms (confirm_transport_booking assigns the
    flow then)."""
    space = frappe.get_doc("RN Transport Space", transport_space)
    auto = _same_org_armada(actor, flow.source_posko, space)
    title = lambda p: (frappe.db.get_value("RN Posko", p, "title") or p) if p else None
    window = " – ".join(str(x)[:16] for x in (window_from, window_to) if x) or None
    b = frappe.new_doc("RN Transport Booking")
    b.transport_space = space.name
    b.disaster_event = flow.disaster_event or space.disaster_event
    b.booked_by_type = "posko"
    b.booked_by_id = flow.source_posko
    b.booker_name = title(flow.source_posko) or "Posko"
    b.logistic_need = flow.logistic_need or None
    b.aid_offer = flow.aid_offer or None
    qty = flt(flow.quantity)
    qty = ("%g" % qty) if qty else ""
    b.cargo_desc = " ".join(x for x in (flow.item_name or "", qty, flow.unit or "") if x).strip()
    b.pickup_location = title(flow.source_posko)
    b.dropoff_location = dropoff or title(flow.destination_posko)
    b.qty_weight_kg = flt(weight_kg) if weight_kg not in (None, "") else 0.0
    b.qty_volume_m3 = flt(volume_m3) if volume_m3 not in (None, "") else 0.0
    # main armada with a first-mile choice: cargo is brought to its handover point
    b.delivery_method = ("self_deliver" if brought_in or (space.service_mode or "both") == "space_only"
                         else "use_transporter")
    if b.meta.has_field("booking_leg"):
        b.booking_leg = leg
    b.requested_window = window
    if window_from:
        b.window_from = window_from
    if window_to:
        b.window_to = window_to
    b.distribution_flow = flow.name
    b.created_by_user = actor.name if actor else None
    if auto:
        b.status = "confirmed"
        b.confirmed_at = now_datetime()
        b.notes = "Disetujui otomatis (organisasi yang sama)."
    else:
        # posko-to-posko: both sides are logged-in operators, so the armada's
        # posko confirms in its Booking Masuk list without a PIN
        b.status = "requested"
    b.insert(ignore_permissions=True)
    if auto:
        _assign_flow_to_space(flow.name, space, leg)
        from rescue_net.logistics.transport import _recompute_transport_committed
        _recompute_transport_committed(space.name)
    return b


def _assign_flow_to_space(flow_name, space, leg="main"):
    if leg == "first_mile":
        frappe.db.set_value("RN Distribution Flow", flow_name, "first_mile_space", space.name)
        return
    frappe.db.set_value("RN Distribution Flow", flow_name, {
        "transport_space": space.name,
        "transport_provider": space.provider_name,
    })


def _assert_in_stock(posko, item, quantity, unit):
    """Owner 2026-10-20: a posko never sends more than it holds (stock
    observation minus what already left since; see stock_available). A
    donor's aid offer is not the posko's stock, so it is not checked."""
    from rescue_net.control_centre.common import _norm_item, stock_available

    av = stock_available(posko, item)
    if av is None:
        frappe.throw("Belum ada stok tercatat untuk '%s' di posko asal — catat stok dulu." % item)
    if unit and av["unit"] and _norm_item(unit) != _norm_item(av["unit"]):
        frappe.throw("Satuan harus sama dengan kartu stok: %s." % av["unit"])
    qty = flt(quantity)
    if qty <= 0:
        frappe.throw("Isi jumlah yang dikirim.")
    if qty > av["available"] + 1e-9:
        frappe.throw("Stok tidak cukup: tersedia %g %s untuk dikirim (tercatat %g, sudah dikirim %g sejak pencatatan)."
                     % (av["available"], av["unit"], av["observed"], av["sent_since"]))
