"""Control Centre — posko detail, Posko Logistik board (stock cards, incoming, dispatch), posko functions and operator writes."""

import frappe
from frappe.rate_limiter import rate_limit

from rescue_net.api_ai import (
    public_context,
    public_active_disasters,
)

from rescue_net.control_centre.common import (  # noqa: F401
    _DRILL_CLOSED_NEED,
    _INTRANSIT_STATES,
    _LOGISTIK_CONVERSIONS,
    _POSKO_OWNER_REASONS,
    _RECEIVED_STATES,
    _norm_item,
    _num,
    _poskos_viewer_context,
    _resolve_posko,
    _sf,
    canonical_event,
    cols,
    event_filters,
)
from rescue_net.control_centre.map_evidence import (  # noqa: F401
    event_evidence,
    map_points,
)


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def event_poskos(disaster_event):
    """Posko list for an event, each tagged with Control Centre sharing
    mode, plus a small `viewer` block so operational-page selectors can
    group "my organisation" vs "national" poskos.

    Returns {"points": [...], "viewer": {...}}. Existing callers already
    unwrap `res.points` when the response is not a bare list."""
    return {
        "points": map_points(canonical_event(disaster_event)),
        "viewer": _poskos_viewer_context(),
    }


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def posko_detail(posko, disaster_event=None):
    """Posko view for the Control Centre drill-down.

    Always returns a safe summary rollup. Adds the per-record `detail`
    bundle only when the organisation's Control Centre sharing (or the
    posko's own override, or the viewer being an operator/member) allows
    full detail. See rescue_net.visibility.effective_posko_share.
    """
    import json

    name = _resolve_posko(posko)

    if not name:
        frappe.throw("Posko tidak ditemukan")

    p = frappe.db.get_value(
        "RN Posko",
        name,
        [
            "name", "legacy_id", "title", "posko_type", "organization",
            "address", "province_name", "city_name", "district_name",
            "latitude", "longitude", "operational_status",
            "verification_status", "trusted_verifier_count", "public_detail",
            "public_participation", "accept_goods",
            "officer_in_charge_name", "officer_in_charge_phone",
            "officer_in_charge_role", "disaster_event",
        ],
        as_dict=True,
    ) or {}

    org_name = p.get("organization")
    org = frappe.db.get_value(
        "RN Organization",
        org_name,
        ["name", "title", "organization_type",
         "control_centre_share", "verification_status"],
        as_dict=True,
    ) or {} if org_name else {}

    try:
        from rescue_net.visibility import effective_posko_share
        from rescue_net.access_policy import rn_actor

        try:
            actor = rn_actor(required=False)
        except Exception:
            actor = None

        share = effective_posko_share(name, actor)
    except Exception:
        share = {"mode": "summary", "reason": "visibility_unavailable"}
        actor = None

    full = share.get("mode") == "full"

    # Three access levels, not two:
    #   guest / logged-out         -> view only (can_manage=can_coordinate=False)
    #   operator / member of posko -> full management (can_manage=True)
    #   any logged-in user + posko.public_participation
    #                              -> coordinate only: book / send aid to it,
    #                                 never edit its internal needs / stock
    logged_in = bool(actor)
    can_manage = share.get("reason") in _POSKO_OWNER_REASONS
    # coordinate = send goods to another org's posko that opened itself up.
    # Mirrors api_logistics.create_aid_offer's public_ok EXACTLY
    # (public_posko_allowed + public_participation + accept_goods) so the
    # "Tambah Bantuan" form is only offered when a submit would succeed.
    can_coordinate = bool(
        logged_in
        and not can_manage
        and p.get("public_participation")
        and p.get("accept_goods")
    )
    if can_coordinate:
        try:
            from rescue_net.access_policy import public_posko_allowed
            can_coordinate = bool(public_posko_allowed(name))
        except Exception:
            can_coordinate = False

    # ---- needs ----------------------------------------------------------
    need_rows = frappe.get_all(
        "RN Logistic Need",
        filters={"posko": name},
        fields=_sf("RN Logistic Need", ["name", "item_name", "quantity", "unit",
                "urgency", "need_status", "legacy_payload", "modified"]),
        order_by="modified desc",
        limit_page_length=200,
    )

    urgent = {"critical", "urgent", "high", "tinggi", "darurat"}
    req_total = real_total = 0.0
    open_needs = crit_needs = 0
    detail_needs = []

    for n in need_rows:
        payload = n.get("legacy_payload")
        if isinstance(payload, str) and payload.strip():
            try:
                payload = json.loads(payload)
            except (ValueError, TypeError):
                payload = {}
        if not isinstance(payload, dict):
            payload = {}

        required = _num(payload.get("required_quantity") or n.get("quantity"))
        realized = _num(payload.get("realized_quantity"))
        if realized > required > 0:
            realized = required
        gap = max(0.0, required - realized)

        status = str(n.get("need_status") or "open").lower()
        if status not in {"fulfilled", "closed", "cancelled", "met"}:
            open_needs += 1
            req_total += required
            real_total += realized
            if str(n.get("urgency") or "").lower() in urgent:
                crit_needs += 1

        if full:
            detail_needs.append({
                "item_name": n.get("item_name"),
                "quantity_required": required,
                "realized_quantity": realized,
                "gap": gap,
                "realization_percent": (
                    round(realized / required * 100, 1) if required else 0.0
                ),
                "unit": n.get("unit"),
                "priority": n.get("urgency"),
                "status": status,
            })

    # ---- stock / flows / offers / medical / volunteers / shelter ------
    stock_count = frappe.db.count("RN Stock Observation", {"posko": name})
    medical_count = frappe.db.count("RN Medical Case", {"posko": name})
    volunteer_count = frappe.db.count("RN Volunteer Assignment", {"posko": name})
    shelter_count = frappe.db.count("RN Shelter Occupancy", {"posko": name})

    flow_rows = frappe.get_all(
        "RN Distribution Flow",
        filters={"destination_posko": name},
        fields=_sf("RN Distribution Flow", ["name", "item_name", "quantity",
                "unit", "flow_status", "source_posko"]),
        order_by="modified desc",
        limit_page_length=100,
    )
    out_flow_rows = frappe.get_all(
        "RN Distribution Flow",
        filters={"source_posko": name},
        fields=_sf("RN Distribution Flow", ["name", "item_name", "quantity",
                "unit", "flow_status", "destination_posko"]),
        order_by="modified desc",
        limit_page_length=100,
    )

    offer_cols = cols("RN Aid Offer")
    offer_filter = None

    if "target_posko" in offer_cols:
        offer_filter = {"target_posko": name}
    elif "organization" in offer_cols and org_name:
        offer_filter = {"organization": org_name}
    elif "disaster_event" in offer_cols and p.get("disaster_event"):
        offer_filter = {"disaster_event": p.get("disaster_event")}

    offer_rows = frappe.get_all(
        "RN Aid Offer",
        filters=offer_filter,
        fields=_sf("RN Aid Offer", ["name", "item_name", "quantity", "unit",
                "offer_status", "status"]),
        limit_page_length=100,
    ) if offer_filter else []

    summary = {
        "open_need_count": open_needs,
        "critical_need_count": crit_needs,
        "need_required_total": round(req_total, 1),
        "need_realized_total": round(real_total, 1),
        "need_realization_percent": (
            round(real_total / req_total * 100, 1) if req_total else 0.0
        ),
        "stock_item_count": stock_count,
        "incoming_flow_count": len(flow_rows),
        "outgoing_flow_count": len(out_flow_rows),
        "aid_offer_count": len(offer_rows),
        "medical_case_count": medical_count,
        "volunteer_assignment_count": volunteer_count,
        "shelter_occupancy_count": shelter_count,
    }

    result = {
        "posko": {
            "id": p.get("legacy_id") or name,
            "name": name,
            "title": p.get("title") or name,
            "posko_type": p.get("posko_type"),
            "address": p.get("address"),
            "province_name": p.get("province_name"),
            "city_name": p.get("city_name"),
            "district_name": p.get("district_name"),
            "latitude": p.get("latitude"),
            "longitude": p.get("longitude"),
            "operational_status": p.get("operational_status"),
            "verification_status": p.get("verification_status"),
            "disaster_event": p.get("disaster_event"),
            **_posko_functions(name),
        },
        "organization": {
            "id": org.get("name"),
            "title": org.get("title"),
            "type": org.get("organization_type"),
            "control_centre_share": org.get("control_centre_share") or "aggregate",
            "verification_status": org.get("verification_status"),
        },
        "share_mode": share.get("mode", "summary"),
        "detail_allowed": full,
        "share_reason": share.get("reason"),
        "logged_in": logged_in,
        "can_manage": can_manage,
        "can_coordinate": can_coordinate,
        "public_participation": bool(p.get("public_participation")),
        "summary": summary,
    }

    if full:
        result["detail"] = {
            "needs": detail_needs,
            "stocks": frappe.get_all(
                "RN Stock Observation",
                filters={"posko": name},
                fields=_sf("RN Stock Observation", ["name", "item_name",
                        "quantity", "unit", "stock_state", "observed_at"]),
                order_by="observed_at desc",
                limit_page_length=100,
            ),
            "incoming_flows": flow_rows,
            "outgoing_flows": out_flow_rows,
            "aid_offers": offer_rows,
            "officer": {
                "name": p.get("officer_in_charge_name"),
                "phone": p.get("officer_in_charge_phone"),
                "role": p.get("officer_in_charge_role"),
            },
        }

    return result


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def logistik_board(posko, disaster_event=None):
    """Posko Logistik dashboard (matches the DMS mock-up).

    Reuses posko_detail() for the visibility-gated summary + detail, then
    reshapes into KPI tiles, an urgent-needs table, in/out movements, a
    nearest-shipment trace and the unit-conversion reference.
    """
    base = posko_detail(posko, disaster_event)
    name = base["posko"]["name"]
    summary = base["summary"]
    detail = base.get("detail") or {}
    full = base["detail_allowed"]

    # Jiwa dilayani: manual field first, else shelter occupancy.
    bene = _posko_beneficiary(name)
    jiwa = bene["count"]
    if not jiwa:
        try:
            for row in frappe.get_all(
                "RN Shelter Occupancy",
                filters={"posko": name},
                fields=["current_occupancy"],
                limit_page_length=200,
            ):
                jiwa += int(_num(row.get("current_occupancy")))
        except Exception:
            jiwa = 0

    cards = _stock_cards(name)

    # Stok menipis: kartu stok yang habis dalam < 3 hari.
    stok_menipis = sum(
        1 for c in cards
        if c.get("estimasi_habis_hari") is not None
        and c["estimasi_habis_hari"] < 3
    )

    urgent_terms = {"critical", "urgent", "high", "tinggi", "darurat"}

    # Urgent needs table.
    need_src = detail.get("needs") or []
    needs_full = frappe.get_all(
        "RN Logistic Need",
        filters={"posko": name},
        fields=_sf("RN Logistic Need", ["name", "item_name", "quantity", "unit",
                "urgency", "need_status", "needed_before", "legacy_payload"]),
        order_by="modified desc",
        limit_page_length=200,
    )

    import json

    urgent_rows = []
    for n in needs_full:
        status = str(n.get("need_status") or "open").lower()
        if status in {"fulfilled", "closed", "cancelled", "met"}:
            continue

        payload = n.get("legacy_payload")
        if isinstance(payload, str) and payload.strip():
            try:
                payload = json.loads(payload)
            except (ValueError, TypeError):
                payload = {}
        if not isinstance(payload, dict):
            payload = {}

        required = _num(payload.get("required_quantity") or n.get("quantity"))
        realized = _num(payload.get("realized_quantity"))
        if realized > required > 0:
            realized = required

        urgent_rows.append({
            "item_name": n.get("item_name"),
            "unit": n.get("unit"),
            "stok_tersedia": realized,
            "gap": max(0.0, required - realized),
            "estimasi_habis": payload.get("estimasi_habis") or "-",
            "waktu_harus_tiba": n.get("needed_before") or "-",
            "priority": n.get("urgency") or "normal",
        })

    urgent_rows.sort(key=lambda r: (
        0 if str(r["priority"]).lower() in urgent_terms else 1,
        -_num(r["gap"]),
    ))

    urgent_total = len(urgent_rows)
    urgent_show = urgent_rows[: (8 if full else 3)]

    # In / out movements.
    def _mv(rows, who_key, who_label):
        out = []
        for f in rows or []:
            out.append({
                who_label: f.get(who_key),
                "item_name": f.get("item_name"),
                "quantity": f.get("quantity"),
                "unit": f.get("unit"),
                "status": f.get("flow_status"),
            })
        return out

    movements_in = _mv(detail.get("incoming_flows"), "source_posko", "dari")
    movements_out = _mv(detail.get("outgoing_flows"), "destination_posko", "tujuan")

    # Nearest shipment trace = newest incoming flow.
    trace = None
    inc = detail.get("incoming_flows") or []
    if inc:
        f = inc[0]
        st = str(f.get("flow_status") or "").lower()
        step = 1
        if st in {"dispatched", "in_transit", "on_the_way"}:
            step = 2
        elif st in {"arrived_at_posko", "partially_received"}:
            step = 3
        elif st in {"received", "completed", "closed"}:
            step = 4
        trace = {
            "dari": f.get("source_posko"),
            "item_name": f.get("item_name"),
            "quantity": f.get("quantity"),
            "unit": f.get("unit"),
            "status": f.get("flow_status"),
            "resi": "RN-" + str(f.get("name") or "")[-10:].upper(),
            "step": step,
        }

    posko_out = dict(base["posko"])
    posko_out["beneficiary_count"] = bene["count"]
    posko_out["beneficiary_note"] = bene["note"]
    posko_out["beneficiary_updated_at"] = bene["updated_at"]

    is_collector = bool(posko_out.get("is_collector"))

    # Field evidence tied to this posko — same unified feed the Control Centre
    # "Bukti Lapangan" panel uses, narrowed to records that name this posko
    # (posko link, linked object, or the posko title inside location_text).
    bukti = []
    bukti_last_at = None
    try:
        ev_event = (
            frappe.db.get_value("RN Posko", name, "disaster_event")
            or disaster_event
        )
        ptitle = str(posko_out.get("title") or "").lower().strip()
        for row in event_evidence(ev_event, limit=80):
            loc = str(row.get("location_text") or "").lower()
            hit = (
                row.get("posko") == name
                or row.get("linked_object_id") == name
                or (ptitle and len(ptitle) > 4 and ptitle in loc)
            )
            if hit:
                bukti.append(row)
        bukti.sort(
            key=lambda r: str(r.get("created_at") or r.get("creation") or ""),
            reverse=True,
        )
        bukti = bukti[:8]
        if bukti:
            bukti_last_at = bukti[0].get("created_at") or bukti[0].get("creation")
    except Exception:
        bukti = []

    return {
        "posko": posko_out,
        "organization": base["organization"],
        "share_mode": base["share_mode"],
        "detail_allowed": full,
        "logged_in": base.get("logged_in", False),
        "can_manage": base.get("can_manage", False),
        "can_coordinate": base.get("can_coordinate", False),
        "public_participation": base.get("public_participation", False),
        "is_collector": is_collector,
        "logistics_role": posko_out.get("logistics_role"),
        "functions": posko_out.get("functions", []),
        "kpi": {
            "jiwa_dilayani": jiwa,
            "stok_menipis": stok_menipis,
            "stok_item": len(cards),
            "kebutuhan_kritis": summary["critical_need_count"],
            "kebutuhan_terbuka": summary["open_need_count"],
            "bantuan_menuju": summary["incoming_flow_count"],
        },
        "stock_cards": cards if full else [],
        "stock_cards_total": len(cards),
        "urgent_needs": urgent_show,
        "urgent_needs_total": urgent_total,
        "movements_in": movements_in,
        "movements_out": movements_out,
        "incoming": _incoming_flows(name) if full else [],
        "public_shipments": _public_shipments(name) if full else [],
        "trace": trace,
        "conversions": _LOGISTIK_CONVERSIONS,
        "bukti": bukti,
        "bukti_total": len(bukti),
        "bukti_last_at": bukti_last_at,
    }


def _public_shipments(name):
    """Aid offers coming straight from the public / another collector toward
    this posko - "kiriman masyarakat", no stock card, one-off or repeated."""
    import json
    fields = _sf("RN Aid Offer", [
        "name", "donor_name", "item_name", "quantity", "unit",
        "offer_status", "handling_mode", "ready_at", "pickup_location",
        "legacy_payload", "creation", "modified",
    ])
    out = []
    for o in frappe.get_all(
        "RN Aid Offer",
        filters={
            "target_posko": name,
            "offer_status": ["not in", ["received", "received_verified", "cancelled"]],
        },
        fields=fields, order_by="creation desc", limit_page_length=100,
    ):
        wave = None
        p = o.get("legacy_payload")
        if isinstance(p, str) and p.strip():
            try:
                wave = (json.loads(p) or {}).get("wave")
            except Exception:
                wave = None
        out.append({
            "id": o["name"],
            "donor_name": o.get("donor_name"),
            "item_name": o.get("item_name"),
            "quantity": o.get("quantity"),
            "unit": o.get("unit"),
            "status": o.get("offer_status"),
            "ready_at": o.get("ready_at"),
            "pickup_location": o.get("pickup_location"),
            "wave": wave,
        })
    return out


# ============================================================
# Logistik stock-card + beneficiary + open-needs helpers
# ============================================================
def _posko_beneficiary(name):
    row = frappe.db.get_value(
        "RN Posko", name,
        ["rn_beneficiary_count", "rn_beneficiary_note",
         "rn_beneficiary_updated_at"],
        as_dict=True,
    ) or {}
    return {
        "count": int(_num(row.get("rn_beneficiary_count"))),
        "note": row.get("rn_beneficiary_note"),
        "updated_at": row.get("rn_beneficiary_updated_at"),
    }


def _posko_functions(name):
    """Which posko functions are enabled + the logistics role.

    A posko can serve several functions at once (logistik + shelter + dapur
    umum). rn_logistics_role: 'collector' (daerah aman, tak melayani korban)
    or 'receiver' (daerah bencana, melayani korban)."""
    cols_p = cols("RN Posko")
    fields = [f for f in (
        "posko_type", "rn_fn_logistics", "rn_fn_shelter", "rn_fn_kitchen",
        "rn_logistics_role", "rn_beneficiary_count",
    ) if f in cols_p]
    r = frappe.db.get_value("RN Posko", name, fields, as_dict=True) or {}

    fns = []
    if r.get("rn_fn_logistics"):
        fns.append("logistics")
    if r.get("rn_fn_shelter"):
        fns.append("shelter")
    if r.get("rn_fn_kitchen"):
        fns.append("kitchen")
    if not fns:
        # fall back to posko_type
        t = (r.get("posko_type") or "").lower()
        if t in {"logistics", "collection_hub"}:
            fns = ["logistics"]
        elif t == "shelter":
            fns = ["shelter"]
        elif t == "kitchen":
            fns = ["kitchen"]
        else:
            fns = [t] if t else []

    role = r.get("rn_logistics_role")
    if not role and "logistics" in fns:
        role = "collector" if not int(_num(r.get("rn_beneficiary_count"))) else "receiver"

    return {
        "functions": fns,
        "logistics_role": role,
        "is_collector": role == "collector",
        "is_merged": len([f for f in fns if f in
                          {"logistics", "shelter", "kitchen"}]) > 1,
    }


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def posko_functions(posko):
    """Tiny guest lookup for the sidebar function-switcher group.

    Returns {posko, title, functions[], logistics_role, is_collector,
    is_merged}. Used by rn-navigation-v2.js to render the top sidebar group
    for a posko that merges logistik / shelter / dapur umum in one node."""
    name = _resolve_posko(posko)
    if not name:
        return {"posko": None, "title": None, "functions": [],
                "logistics_role": None, "is_collector": False,
                "is_merged": False}
    out = _posko_functions(name)
    out["posko"] = name
    out["title"] = frappe.db.get_value("RN Posko", name, "title") or name
    return out


def _stock_cards(name):
    import json as _json
    from frappe.utils import get_datetime, now_datetime

    now = now_datetime()

    def _age_days(dt):
        try:
            return max(0.0, (now - get_datetime(dt)).total_seconds() / 86400.0)
        except Exception:
            return 999.0

    # latest stock observation per item
    obs_fields = _sf("RN Stock Observation", [
        "name", "item_name", "canonical_item", "quantity", "unit",
        "stock_state", "observed_at", "rn_daily_consumption",
        "rn_consumption_source",
    ])
    latest = {}
    for o in frappe.get_all(
        "RN Stock Observation", filters={"posko": name},
        fields=obs_fields, order_by="observed_at desc", limit_page_length=500,
    ):
        key = _norm_item(o.get("canonical_item") or o.get("item_name"))
        if key and key not in latest:
            latest[key] = o

    # flows touching this posko
    flow_fields = _sf("RN Distribution Flow", [
        "name", "item_name", "quantity", "unit", "flow_status",
        "rn_movement_type", "source_posko", "destination_posko",
        "received_quantity", "dispatched_at", "received_at",
        "in_transit_at", "modified",
    ])
    flows_in = frappe.get_all(
        "RN Distribution Flow", filters={"destination_posko": name},
        fields=flow_fields, limit_page_length=500,
    )
    flows_out = frappe.get_all(
        "RN Distribution Flow", filters={"source_posko": name},
        fields=flow_fields, limit_page_length=500,
    )

    # open needs per item
    need_qty = {}
    for n in frappe.get_all(
        "RN Logistic Need", filters={"posko": name},
        fields=_sf("RN Logistic Need", ["name", "item_name", "quantity",
                "unit", "need_status", "legacy_payload"]),
        limit_page_length=300,
    ):
        if str(n.get("need_status") or "open").lower() in {
            "fulfilled", "closed", "cancelled", "met",
        }:
            continue
        payload = n.get("legacy_payload")
        if isinstance(payload, str) and payload.strip():
            try:
                payload = _json.loads(payload)
            except (ValueError, TypeError):
                payload = {}
        req = _num((payload or {}).get("required_quantity") or n.get("quantity"))
        k = _norm_item(n.get("item_name"))
        need_qty[k] = need_qty.get(k, 0.0) + req

    keys = set(latest) | set(need_qty)
    for f in flows_in + flows_out:
        keys.add(_norm_item(f.get("item_name")))

    cards = []
    for k in sorted(keys):
        if not k:
            continue
        o = latest.get(k) or {}
        label = (o.get("item_name")
                 or next((f.get("item_name") for f in flows_in + flows_out
                          if _norm_item(f.get("item_name")) == k), k))
        unit = o.get("unit") or next(
            (f.get("unit") for f in flows_in + flows_out
             if _norm_item(f.get("item_name")) == k), "")

        stok_ada = _num(o.get("quantity"))

        masuk_7h = sum(
            _num(f.get("received_quantity") or f.get("quantity"))
            for f in flows_in
            if _norm_item(f.get("item_name")) == k
            and str(f.get("flow_status") or "").lower() in _RECEIVED_STATES
            and _age_days(f.get("received_at") or f.get("modified")) <= 7
        )
        keluar_7h = sum(
            _num(f.get("quantity")) for f in flows_out
            if _norm_item(f.get("item_name")) == k
            and _age_days(f.get("dispatched_at") or f.get("modified")) <= 7
        )
        otw = sum(
            _num(f.get("quantity")) for f in flows_in
            if _norm_item(f.get("item_name")) == k
            and str(f.get("flow_status") or "").lower() in _INTRANSIT_STATES
        )
        otw_count = sum(
            1 for f in flows_in
            if _norm_item(f.get("item_name")) == k
            and str(f.get("flow_status") or "").lower() in _INTRANSIT_STATES
        )

        kebutuhan = need_qty.get(k, 0.0)
        gap = max(0.0, kebutuhan - stok_ada - otw)

        manual_rate = _num(o.get("rn_daily_consumption"))
        if manual_rate > 0:
            laju, laju_src = manual_rate, "manual"
        elif keluar_7h > 0:
            laju, laju_src = round(keluar_7h / 7.0, 2), "computed"
        else:
            laju, laju_src = 0.0, "none"

        habis = round(stok_ada / laju, 1) if laju > 0 else None
        habis_otw = round((stok_ada + otw) / laju, 1) if laju > 0 else None

        cards.append({
            "item": label,
            "unit": unit,
            "stok_ada": stok_ada,
            "masuk_7h": masuk_7h,
            "keluar_7h": keluar_7h,
            "otw": otw,
            "otw_count": otw_count,
            "kebutuhan": kebutuhan,
            "gap": gap,
            "laju_harian": laju,
            "laju_sumber": laju_src,
            "estimasi_habis_hari": habis,
            "estimasi_habis_dengan_otw_hari": habis_otw,
            "observed_at": o.get("observed_at"),
        })

    cards.sort(key=lambda c: (
        c["estimasi_habis_hari"] if c["estimasi_habis_hari"] is not None else 1e9,
        -c["gap"],
    ))
    return cards


def _incoming_flows(name):
    fields = _sf("RN Distribution Flow", [
        "name", "item_name", "quantity", "unit", "flow_status",
        "source_posko", "eta_final", "transport_provider", "transport_type",
        "dispatched_at", "in_transit_at", "arrived_at", "received_at",
        "received_quantity", "logistic_need", "transport_space", "modified",
    ])
    out = []
    for f in frappe.get_all(
        "RN Distribution Flow", filters={"destination_posko": name},
        fields=fields, order_by="modified desc", limit_page_length=100,
    ):
        f["id"] = f.pop("name", None)
        f["distribusi_url"] = (
            "management-distribusi.html?flow=" + str(f["id"] or "")
        )
        out.append(f)
    return out


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def logistik_stock_cards(posko, disaster_event=None):
    name = _resolve_posko(posko)
    if not name:
        frappe.throw("Posko tidak ditemukan")
    return {"posko": name, "cards": _stock_cards(name)}


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def logistik_incoming(posko, disaster_event=None):
    name = _resolve_posko(posko)
    if not name:
        frappe.throw("Posko tidak ditemukan")
    return {"posko": name, "incoming": _incoming_flows(name)}


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def logistik_stock_sources(posko, item=None):
    """"Asal item" — where the stock at this posko for `item` came from:
    received aid offers (donations / community shipments) + arrived
    distribution flows from other poskos."""
    name = _resolve_posko(posko)
    if not name:
        frappe.throw("Posko tidak ditemukan")
    want = _norm_item(item) if item else None

    out = []
    for o in frappe.get_all(
        "RN Aid Offer",
        filters={"target_posko": name},
        fields=_sf("RN Aid Offer", [
            "name", "item_name", "raw_item_text", "canonical_item", "quantity",
            "unit", "donor_name", "offer_status", "creation", "modified",
        ]),
        order_by="modified desc", limit_page_length=300,
    ):
        it = o.get("item_name") or o.get("raw_item_text")
        if want and _norm_item(o.get("canonical_item") or it) != want:
            continue
        st = str(o.get("offer_status") or "").lower()
        out.append({
            "kind": "donasi",
            "item": it,
            "from": o.get("donor_name") or "Donatur",
            "quantity": _num(o.get("quantity")),
            "unit": o.get("unit") or "",
            "status": st,
            "received": st in ("received", "received_verified"),
            "at": str(o.get("modified") or o.get("creation") or "")[:16],
        })

    for f in frappe.get_all(
        "RN Distribution Flow",
        filters={"destination_posko": name},
        fields=_sf("RN Distribution Flow", [
            "name", "item_name", "raw_item_text", "canonical_item", "quantity",
            "received_quantity", "unit", "source_posko", "flow_status",
            "received_at", "modified",
        ]),
        order_by="modified desc", limit_page_length=300,
    ):
        it = f.get("item_name") or f.get("raw_item_text")
        if want and _norm_item(f.get("canonical_item") or it) != want:
            continue
        src = f.get("source_posko")
        src_title = (
            frappe.db.get_value("RN Posko", src, "title") or src
        ) if src else "-"
        st = str(f.get("flow_status") or "").lower()
        out.append({
            "kind": "kiriman posko",
            "item": it,
            "from": src_title,
            "quantity": _num(f.get("received_quantity") or f.get("quantity")),
            "unit": f.get("unit") or "",
            "status": st,
            "received": st in ("received", "arrived_at_posko", "arrived"),
            "at": str(f.get("received_at") or f.get("modified") or "")[:16],
        })

    out.sort(key=lambda r: r.get("at") or "", reverse=True)
    return {"posko": name, "item": item, "sources": out}


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def logistik_dispatch_options(disaster_event, source_posko=None):
    """Choices for the "Kirim stok" form on Posko Logistik:
      destinations = receiver poskos of this event (not transport, not self)
      armada       = available RN Transport Space (route the shipment through
                     a kapal TNI AL / Land Rover club / … instead of direct)."""
    event = canonical_event(disaster_event) if disaster_event else None
    src = _resolve_posko(source_posko) if source_posko else None

    prow = frappe.get_all(
        "RN Posko",
        or_filters={"disaster_event": event, "disaster_event_legacy_id": event}
        if event else None,
        fields=["name", "title", "posko_type", "city_name", "rn_logistics_role",
                "rn_beneficiary_count"],
        limit_page_length=500,
    )
    destinations = [
        {
            "id": p.name,
            "title": (p.title or "").replace("[SIMULASI] ", "").strip() or p.name,
            "city": p.get("city_name") or "",
            "role": p.get("rn_logistics_role") or "",
            "jiwa": _num(p.get("rn_beneficiary_count")),
        }
        for p in prow
        if p.name != src and (p.posko_type or "").lower() != "transport"
    ]
    destinations.sort(key=lambda d: (d["role"] != "receiver", -d["jiwa"], d["title"]))

    trow = frappe.get_all(
        "RN Transport Space",
        filters=event_filters(cols("RN Transport Space"), event) if event else {},
        fields=_sf("RN Transport Space", [
            "name", "provider_name", "transport_type", "transport_status",
            "capacity_weight_kg", "capacity_volume_m3", "coordination_posko",
            "departure_at", "eta_at", "departure_time", "eta", "service_mode",
        ]),
        order_by="modified desc", limit_page_length=200,
    )
    armada = []
    for t in trow:
        if (t.transport_status or "") in ("completed", "cancelled"):
            continue
        posko_title = (
            frappe.db.get_value("RN Posko", t.coordination_posko, "title")
            or t.coordination_posko or "-"
        )
        armada.append({
            "id": t.name,
            "provider": t.provider_name or "-",
            "jenis": t.transport_type or "-",
            "posko_title": (posko_title or "").replace("[SIMULASI] ", "").strip(),
            "kapasitas_kg": _num(t.capacity_weight_kg),
            "berangkat": (str(t.departure_at or "")[:16] or t.departure_time or "-"),
            "eta": (str(t.eta_at or "")[:16] or t.eta or "-"),
        })

    return {"destinations": destinations, "armada": armada}


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def logistik_open_needs(disaster_event, limit=200):
    """Public 'papan kebutuhan' - open logistic needs across every posko of
    an event, each with the serving posko's beneficiary count and fulfilment
    so an outside collector / the public can pick one to fulfil."""
    import json as _json

    event = canonical_event(disaster_event)
    need_cols = cols("RN Logistic Need")
    rows = frappe.get_all(
        "RN Logistic Need",
        filters=event_filters(need_cols, event),
        fields=_sf("RN Logistic Need", [
            "name", "legacy_id", "item_name", "quantity", "unit", "urgency",
            "need_status", "needed_before", "posko", "legacy_payload",
        ]),
        order_by="modified desc",
        limit_page_length=int(limit),
    )

    posko_cache = {}

    def _posko_info(pn):
        if pn not in posko_cache:
            r = frappe.db.get_value(
                "RN Posko", pn,
                ["title", "city_name", "province_name", "organization",
                 "rn_beneficiary_count", "latitude", "longitude"],
                as_dict=True,
            ) or {}
            posko_cache[pn] = r
        return posko_cache[pn]

    out = []
    for n in rows:
        if str(n.get("need_status") or "open").lower() in {
            "fulfilled", "closed", "cancelled", "met",
        }:
            continue
        payload = n.get("legacy_payload")
        if isinstance(payload, str) and payload.strip():
            try:
                payload = _json.loads(payload)
            except (ValueError, TypeError):
                payload = {}
        payload = payload or {}
        req = _num(payload.get("required_quantity") or n.get("quantity"))
        real = _num(payload.get("realized_quantity"))
        pi = _posko_info(n.get("posko")) if n.get("posko") else {}
        out.append({
            "id": n.get("legacy_id") or n["name"],
            "name": n["name"],
            "item": n.get("item_name"),
            "unit": n.get("unit"),
            "required": req,
            "realized": real,
            "gap": max(0.0, req - real),
            "percent": round(real / req * 100, 1) if req else 0.0,
            "priority": n.get("urgency"),
            "needed_before": n.get("needed_before"),
            "posko": n.get("posko"),
            "posko_title": pi.get("title"),
            "posko_area": " / ".join(
                x for x in [pi.get("city_name"), pi.get("province_name")] if x
            ),
            "beneficiary_count": int(_num(pi.get("rn_beneficiary_count"))),
        })

    out.sort(key=lambda x: (
        0 if str(x["priority"] or "").lower() in {"critical", "urgent", "high"}
        else 1,
        -x["gap"],
    ))
    return {"disaster_event": event, "needs": out}


@frappe.whitelist()
def set_posko_functions(posko, functions=None, logistics_role=None):
    """Set which functions a posko serves (logistik / shelter / dapur umum)
    and, for logistik, whether it is a collector or a receiver.
    `functions` may be a JSON array or a comma string."""
    from rescue_net.access_policy import rn_actor

    actor = rn_actor()
    name = _resolve_posko(posko)
    if not name:
        frappe.throw("Posko tidak ditemukan")

    # Komando terpusat: which functions a posko serves is structural. Under a
    # command organisation only the pusat applies it directly; a member of that
    # organisation files a request; anyone else is refused (this endpoint had no
    # permission check at all before). `mandiri` poskos: unchanged.
    from rescue_net import command
    posko_org = command.posko_org(name)
    if posko_org and not command.is_bypassed() and command.needs_approval(actor, posko_org):
        if not command.is_account_member(actor, posko_org):
            frappe.throw("Anda tidak dapat mengubah posko ini", frappe.PermissionError)
        return command.file_request(
            actor, posko_org, "set_posko_functions",
            {"posko": name, "functions": functions, "logistics_role": logistics_role},
            "Ubah fungsi posko %s" % (frappe.db.get_value("RN Posko", name, "title") or name),
            target_posko=name,
        )

    # Everyone else (mandiri poskos, or the pusat itself applying an approved
    # request): System Manager, whoever manages the posko (approved assignment
    # / org coordinator / pusat authority) or the owner of the posko's
    # organisation. The creator's first choice is applied by create_posko
    # itself — a pending creator has no rights on the posko yet (O-9).
    from rescue_net.access_policy import can_manage_organization, can_manage_posko, is_system_manager
    if not (
        is_system_manager()
        or can_manage_posko(actor, name)
        or (posko_org and can_manage_organization(actor, posko_org))
    ):
        frappe.throw("Anda tidak dapat mengubah fungsi posko ini", frappe.PermissionError)

    return {"posko": name, **apply_posko_functions(name, functions, logistics_role)}


def apply_posko_functions(name, functions=None, logistics_role=None):
    """Write the function flags; callers check the rights."""
    import json

    if isinstance(functions, str):
        functions = functions.strip()
        try:
            functions = json.loads(functions)
        except Exception:
            functions = [x.strip() for x in functions.split(",") if x.strip()]
    functions = set(functions or [])

    upd = {
        "rn_fn_logistics": 1 if "logistics" in functions else 0,
        "rn_fn_shelter": 1 if "shelter" in functions else 0,
        "rn_fn_kitchen": 1 if "kitchen" in functions else 0,
    }
    if logistics_role in ("collector", "receiver"):
        upd["rn_logistics_role"] = logistics_role

    frappe.db.set_value("RN Posko", name, upd)
    return _posko_functions(name)


def _assert_posko_operator(actor, posko):
    """Posko data / stock edits: the posko's own operators and managers only."""
    from rescue_net.api_logistics import _can_operate
    if not _can_operate(actor, posko):
        frappe.throw("Hanya operator/pengelola posko ini yang dapat mengubah data ini.",
                     frappe.PermissionError)


@frappe.whitelist()
def set_posko_beneficiary(posko, count, note=None):
    from rescue_net.access_policy import rn_actor
    from frappe.utils import now_datetime

    actor = rn_actor()
    name = _resolve_posko(posko)
    if not name:
        frappe.throw("Posko tidak ditemukan")
    _assert_posko_operator(actor, name)          # O-7
    if _num(count) < 0:
        frappe.throw("Jumlah penerima manfaat tidak boleh negatif.")

    frappe.db.set_value("RN Posko", name, {
        "rn_beneficiary_count": int(_num(count)),
        "rn_beneficiary_note": note,
        "rn_beneficiary_updated_at": now_datetime(),
    })
    frappe.db.commit()
    return {"posko": name, "beneficiary_count": int(_num(count))}


@frappe.whitelist()
def set_item_consumption(posko, item_name, daily_rate):
    from rescue_net.access_policy import rn_actor

    actor = rn_actor()
    name = _resolve_posko(posko)
    if not name:
        frappe.throw("Posko tidak ditemukan")
    _assert_posko_operator(actor, name)          # L-23
    if _num(daily_rate) < 0:
        frappe.throw("Konsumsi harian tidak boleh negatif.")
    obs = frappe.get_all(
        "RN Stock Observation",
        filters={"posko": name, "item_name": item_name},
        fields=["name"], order_by="observed_at desc", limit_page_length=1,
    )
    if not obs:
        frappe.throw("Belum ada observasi stok untuk item ini")
    frappe.db.set_value("RN Stock Observation", obs[0]["name"], {
        "rn_daily_consumption": _num(daily_rate),
        "rn_consumption_source": "manual",
    })
    frappe.db.commit()
    return {"stock_observation": obs[0]["name"], "daily_rate": _num(daily_rate)}


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=20, seconds=3600)
def fulfill_need(need, donor_name, quantity, unit=None,
                 pickup_location=None, contact=None, disaster_event=None):
    """Public: an outside collector / member of the public offers to fill a
    specific open need. Creates an RN Aid Offer targeting the need's posko
    and links it to the need."""
    import json as _json

    n = frappe.db.get_value(
        "RN Logistic Need",
        need if frappe.db.exists("RN Logistic Need", need)
        else {"legacy_id": need},
        ["name", "item_name", "unit", "posko", "disaster_event", "need_status"],
        as_dict=True,
    )
    if not n:
        frappe.throw("Kebutuhan tidak ditemukan")
    # L-20: only an open need can still be filled
    if str(n.get("need_status") or "open").lower() in _DRILL_CLOSED_NEED:
        frappe.throw("Kebutuhan ini sudah ditutup (%s)." % n.get("need_status"))

    if not str(donor_name or "").strip():
        frappe.throw("Nama donatur wajib diisi")

    # Owner rule (2026-09-26): a posko that is not open to the public takes
    # no donations from outside — same gate as every other aid-offer path
    # (public detail + public_participation + accept_goods), unless the
    # caller is part of the posko's own organisation.
    from rescue_net.access_policy import rn_actor
    from rescue_net.api_logistics import _user_aid_posko_allowed
    if n.get("posko") and not _user_aid_posko_allowed(rn_actor(required=False), n.get("posko")):
        frappe.throw("Posko ini tidak membuka penerimaan bantuan publik.", frappe.PermissionError)

    doc = frappe.new_doc("RN Aid Offer")
    doc.legacy_source = "public_fulfil"
    doc.title = f"Donasi {n.get('item_name')} - {donor_name}"
    for f, v in {
        "disaster_event": n.get("disaster_event"),
        "donor_name": str(donor_name).strip(),
        "donor_contact": contact,
        "item_name": n.get("item_name"),
        "quantity": _num(quantity),
        "unit": unit or n.get("unit"),
        "offer_status": "need_pickup",
        "handling_mode": "need_pickup",
        "target_posko": n.get("posko"),
        "pickup_location": pickup_location,
        "verification_status": "self_reported",
        "legacy_payload": _json.dumps({"fulfils_need": n["name"], "public": True}),
    }.items():
        if v is not None and doc.meta.has_field(f):
            setattr(doc, f, v)
    doc.insert(ignore_permissions=True)
    frappe.db.commit()

    return {
        "aid_offer": doc.name,
        "need": n["name"],
        "target_posko": n.get("posko"),
        "message": "Terima kasih. Penawaran bantuan tercatat dan menunggu penjemputan/konfirmasi posko.",
    }
