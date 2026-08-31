import frappe

from rescue_net.api_ai import (
    public_context,
    public_active_disasters,
)


def cols(doctype):
    return set(
        frappe.get_meta(
            doctype
        ).get_valid_columns()
    )


def canonical_event(value):
    value = str(
        value or ""
    ).strip()

    if value.startswith(
        "disaster_events:"
    ):
        return value

    return (
        "disaster_events:"
        + value
    )


def first(row, *names):
    for name in names:
        value = row.get(name)

        if value not in (
            None,
            "",
        ):
            return value

    return None


def event_filters(columns, event):
    if "disaster_event" in columns:
        return {
            "disaster_event":
                event
        }

    if (
        "disaster_event_id"
        in columns
    ):
        return {
            "disaster_event_id":
                event
        }

    return {}


def map_points(event):
    doctype = "RN Posko"

    columns = cols(
        doctype
    )

    wanted = [
        "name",
        "legacy_id",
        "title",
        "posko_type",
        "address",
        "status",
        "operational_status",
        "severity",
        "latitude",
        "longitude",
        "lat",
        "lng",
        "organization",
        "public_detail",
        "disaster_event",
        "disaster_event_id",
    ]

    fields = [
        f
        for f in wanted
        if (
            f == "name"
            or f in columns
        )
    ]

    rows = frappe.get_all(
        doctype,
        filters=event_filters(
            columns,
            event,
        ),
        fields=fields,
        limit_page_length=500,
    )

    result = []

    for raw in rows:
        row = dict(raw)

        lat = first(
            row,
            "latitude",
            "lat",
        )

        lng = first(
            row,
            "longitude",
            "lng",
        )

        try:
            lat = float(lat)
            lng = float(lng)

        except (
            TypeError,
            ValueError,
        ):
            continue

        status = str(
            first(
                row,
                "operational_status",
                "severity",
                "status",
            )
            or "normal"
        ).lower()

        if status in {
            "critical",
            "overload",
            "emergency",
            "danger",
        }:
            situation = "critical"

        elif status in {
            "urgent",
            "warning",
            "affected",
            "disrupted",
        }:
            situation = "warning"

        else:
            situation = "safe"

        result.append({
            "id":
                first(
                    row,
                    "legacy_id",
                    "name",
                ),

            "posko_id":
                row.get("name"),

            "name":
                first(
                    row,
                    "title",
                    "name",
                ),

            "posko_type":
                row.get(
                    "posko_type"
                ),

            "address":
                row.get(
                    "address"
                ),

            "latitude":
                lat,

            "longitude":
                lng,

            "status":
                status,

            "situation":
                situation,

            "organization":
                row.get("organization"),

            "google_maps_url":
                (
                    "https://www.google.com/"
                    "maps/search/?api=1&query="
                    f"{lat},{lng}"
                ),
        })

    _annotate_share_mode(result)

    return result


def _annotate_share_mode(points):
    """Tag each map point with the org's Control Centre sharing mode.

    full  -> the drill-down may show full posko detail
    summary -> only the aggregated rollup for that org is exposed
    """
    try:
        from rescue_net.visibility import effective_posko_share
        from rescue_net.access_policy import rn_actor
    except Exception:
        for point in points:
            point["share_mode"] = "summary"
            point["detail_allowed"] = False
        return

    try:
        actor = rn_actor(required=False)
    except Exception:
        actor = None

    for point in points:
        posko_name = point.get("posko_id")

        try:
            info = effective_posko_share(posko_name, actor)
        except Exception:
            info = {"mode": "summary"}

        point["share_mode"] = info.get("mode", "summary")
        point["detail_allowed"] = point["share_mode"] == "full"


def reports(event):
    doctype = (
        "RN Community Report"
    )

    if not frappe.db.exists(
        "DocType",
        doctype,
    ):
        return []

    columns = cols(
        doctype
    )

    wanted = [
        "name",
        "legacy_id",
        "title",
        "description",
        "report_type",
        "priority",
        "status",
        "location_text",
        "latitude",
        "longitude",
        "evidence_url",
        "file_url",
        "legacy_payload",
        "reporter_name",
        "creation",
        "modified",
        "disaster_event",
        "disaster_event_id",
    ]

    fields = [
        f
        for f in wanted
        if (
            f == "name"
            or f in columns
        )
    ]

    rows = frappe.get_all(
        doctype,
        filters=event_filters(
            columns,
            event,
        ),
        fields=fields,
        order_by=(
            "modified desc"
            if "modified" in fields
            else "creation desc"
        ),
        limit_page_length=12,
    )

    enrich_report_evidence(rows)

    return rows


def enrich_report_evidence(rows):
    """Populate evidence_url / caption / reporter for the Control Centre feed.

    RN Community Report has no evidence_url column; the demo/simulation seeds
    stash the photo under legacy_payload.evidence.image and also attach a File.
    Fall back to the newest public File attached to the report.
    """
    import json

    for row in rows:
        if row.get("evidence_url"):
            continue

        payload = row.get("legacy_payload")

        if isinstance(payload, str) and payload.strip():
            try:
                payload = json.loads(payload)
            except (ValueError, TypeError):
                payload = None

        if isinstance(payload, dict):
            evidence = payload.get("evidence") or {}

            row["evidence_url"] = (
                evidence.get("image")
                or evidence.get("url")
                or evidence.get("file_url")
            )
            row["evidence_caption"] = (
                evidence.get("caption")
                or row.get("title")
            )
            row["evidence_details"] = (
                evidence.get("details")
                or row.get("description")
            )
            row["reporter_name"] = (
                row.get("reporter_name")
                or payload.get("source")
            )

        if not row.get("evidence_url") and row.get("name"):
            attached = frappe.get_all(
                "File",
                filters={
                    "attached_to_doctype": "RN Community Report",
                    "attached_to_name": row["name"],
                    "is_private": 0,
                },
                fields=["file_url"],
                order_by="creation desc",
                limit_page_length=1,
            )

            if attached:
                row["evidence_url"] = attached[0]["file_url"]


def _user_label(user_name):
    """RN User Account -> {'label': display name, 'role': ...}."""
    if not user_name:
        return {}

    row = frappe.db.get_value(
        "RN User Account",
        user_name,
        ["title", "username", "role"],
        as_dict=True,
    ) or {}

    return {
        "label": row.get("title") or row.get("username") or user_name,
        "role": row.get("role"),
    }


def _ev_norm(**kw):
    """Normalise one evidence record to the shape both the Control Centre
    'Bukti Lapangan' panel and the Evidence page expect."""
    url = kw.get("evidence_url") or kw.get("file_url")

    return {
        "id": kw.get("id"),
        "source": kw.get("source"),
        "evidence_url": url,
        "file_url": url,
        "caption": kw.get("caption"),
        "evidence_caption": kw.get("caption") or kw.get("title"),
        "evidence_type": kw.get("evidence_type") or "photo",
        "description": kw.get("description"),
        "evidence_details": kw.get("description"),
        "title": kw.get("title") or kw.get("caption"),
        "report_type": kw.get("report_type"),
        "priority": kw.get("priority"),
        "status": kw.get("status"),
        "location_text": kw.get("location_text"),
        "latitude": kw.get("latitude"),
        "longitude": kw.get("longitude"),
        "reporter_name": kw.get("reporter_name"),
        "uploader": kw.get("uploader"),
        "uploader_role": kw.get("uploader_role"),
        "posko": kw.get("posko"),
        "linked_object_type": kw.get("linked_object_type"),
        "linked_object_id": kw.get("linked_object_id"),
        "disaster_event_id": kw.get("disaster_event_id"),
        "observed_at": kw.get("observed_at"),
        "created_at": kw.get("created_at") or kw.get("creation"),
        "creation": kw.get("creation"),
        "modified": kw.get("modified"),
    }


def event_evidence(event, limit=60):
    """Single source of truth for field evidence of a disaster event.

    Unions RN Community Report (+ its legacy_payload photo / child evidence),
    RN Community Report Evidence, RN Evidence File and RN Operational Evidence
    so the Control Centre and the Evidence page always show the same records.
    """
    import json

    out = []
    seen = set()

    def push(row):
        url = row.get("evidence_url")
        if url and url not in seen:
            seen.add(url)
            out.append(row)

    # --- Collect this event's community reports (context for the evidence) ---
    report_names = set()
    rep_rows = []

    if frappe.db.exists("DocType", "RN Community Report"):
        rep_cols = cols("RN Community Report")
        rep_rows = frappe.get_all(
            "RN Community Report",
            filters=event_filters(rep_cols, event),
            fields=[
                f for f in (
                    "name", "title", "description", "report_type",
                    "priority", "status", "location_text", "latitude",
                    "longitude", "legacy_payload", "reporter_name",
                    "reporter_user", "creation", "modified",
                ) if f == "name" or f in rep_cols
            ],
            order_by="modified desc" if "modified" in rep_cols else "creation desc",
            limit_page_length=limit,
        )
        report_names = {r["name"] for r in rep_rows}

    rep_by_name = {r["name"]: r for r in rep_rows}

    # --- 1. RN Community Report Evidence (structured, user-attributed) ---
    if frappe.db.exists("DocType", "RN Community Report Evidence") and report_names:
        cre_cols = cols("RN Community Report Evidence")
        cre_fields = [f for f in (
            "name", "report", "file_url", "caption", "evidence_type",
            "verification_status", "uploader_user", "observed_at", "creation",
        ) if f == "name" or f in cre_cols]

        for e in frappe.get_all(
            "RN Community Report Evidence",
            filters={"report": ["in", list(report_names)]},
            fields=cre_fields,
            limit_page_length=limit,
        ):
            up = _user_label(e.get("uploader_user"))
            r = rep_by_name.get(e.get("report"), {})
            push(_ev_norm(
                id=e["name"], source="community_report_evidence",
                file_url=e.get("file_url"), caption=e.get("caption"),
                evidence_type=e.get("evidence_type"), status=e.get("verification_status"),
                title=e.get("caption") or r.get("title"),
                description=r.get("description"),
                report_type=r.get("report_type"), priority=r.get("priority"),
                location_text=r.get("location_text"),
                latitude=r.get("latitude"), longitude=r.get("longitude"),
                uploader=up.get("label"), uploader_role=up.get("role"),
                reporter_name=up.get("label") or r.get("reporter_name"),
                linked_object_type="RN Community Report", linked_object_id=e.get("report"),
                disaster_event_id=event,
                observed_at=e.get("observed_at"), creation=e.get("creation"),
            ))

    # --- 2. Community-report legacy_payload photo (fallback, unattributed) ---
    for r in rep_rows:
        payload = r.get("legacy_payload")
        if isinstance(payload, str) and payload.strip():
            try:
                payload = json.loads(payload)
            except (ValueError, TypeError):
                payload = None
        ev = payload.get("evidence") if isinstance(payload, dict) else None
        src = payload.get("source") if isinstance(payload, dict) else None
        if not isinstance(ev, dict):
            continue
        url = ev.get("image") or ev.get("url") or ev.get("file_url")
        if not url:
            continue
        up = _user_label(r.get("reporter_user"))
        push(_ev_norm(
            id=r["name"], source="community_report",
            evidence_url=url,
            caption=ev.get("caption"), evidence_type=ev.get("evidence_type") or "photo",
            description=ev.get("details") or r.get("description"),
            title=r.get("title"), report_type=r.get("report_type"),
            priority=r.get("priority"), status=r.get("status"),
            location_text=r.get("location_text"),
            latitude=r.get("latitude"), longitude=r.get("longitude"),
            uploader=up.get("label"), uploader_role=up.get("role"),
            reporter_name=up.get("label") or r.get("reporter_name") or src,
            linked_object_type="RN Community Report", linked_object_id=r["name"],
            disaster_event_id=event,
            creation=r.get("creation"), modified=r.get("modified"),
        ))

    # --- 3. RN Evidence File (native uploads) ---
    if frappe.db.exists("DocType", "RN Evidence File"):
        ef_cols = cols("RN Evidence File")
        for e in frappe.get_all(
            "RN Evidence File",
            filters=event_filters(ef_cols, event),
            fields=[
                f for f in (
                    "name", "posko", "file_url", "caption", "evidence_type",
                    "linked_doctype", "linked_name", "reference_doctype",
                    "reference_name", "object_type", "object_id",
                    "uploaded_by", "created_by_user",
                    "verification_status", "observed_at", "creation",
                ) if f == "name" or f in ef_cols
            ],
            order_by="creation desc",
            limit_page_length=limit,
        ):
            up = _user_label(e.get("uploaded_by") or e.get("created_by_user"))
            push(_ev_norm(
                id=e["name"], source="evidence_file",
                file_url=e.get("file_url"), caption=e.get("caption"),
                evidence_type=e.get("evidence_type"), status=e.get("verification_status"),
                title=e.get("caption"), posko=e.get("posko"),
                uploader=up.get("label"), uploader_role=up.get("role"),
                reporter_name=up.get("label"),
                linked_object_type=e.get("linked_doctype") or e.get("reference_doctype") or e.get("object_type"),
                linked_object_id=e.get("linked_name") or e.get("reference_name") or e.get("object_id"),
                disaster_event_id=event,
                observed_at=e.get("observed_at"), creation=e.get("creation"),
            ))

    # --- 4. RN Operational Evidence (attached to operational records) ---
    if frappe.db.exists("DocType", "RN Operational Evidence"):
        posko_names = [
            p.name for p in frappe.get_all(
                "RN Posko",
                filters=event_filters(cols("RN Posko"), event),
                fields=["name"], limit_page_length=500,
            )
        ]

        if posko_names:
            for e in frappe.get_all(
                "RN Operational Evidence",
                filters={"posko": ["in", posko_names]},
                fields=["name", "posko", "file_url", "caption", "evidence_type",
                        "linked_doctype", "linked_name", "uploader_user",
                        "verification_status", "observed_at", "creation"],
                order_by="creation desc",
                limit_page_length=limit,
            ):
                up = _user_label(e.get("uploader_user"))
                push(_ev_norm(
                    id=e["name"], source="operational_evidence",
                    file_url=e.get("file_url"), caption=e.get("caption"),
                    evidence_type=e.get("evidence_type"), status=e.get("verification_status"),
                    title=e.get("caption"), posko=e.get("posko"),
                    uploader=up.get("label"), uploader_role=up.get("role"),
                    reporter_name=up.get("label"),
                    linked_object_type=e.get("linked_doctype"),
                    linked_object_id=e.get("linked_name"),
                    disaster_event_id=event,
                    observed_at=e.get("observed_at"), creation=e.get("creation"),
                ))

    return out[:limit]


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _resolve_posko(value):
    value = str(value or "").strip()

    if not value:
        return None

    if frappe.db.exists("RN Posko", value):
        return value

    return frappe.db.get_value(
        "RN Posko", {"legacy_id": value}, "name"
    ) or frappe.db.get_value(
        "RN Posko", {"legacy_id": "posko_nodes:" + value}, "name"
    )


def _sf(doctype, wanted):
    """Keep only fields that actually exist on the doctype."""
    valid = cols(doctype)
    return [f for f in wanted if f == "name" or f in valid]


@frappe.whitelist(allow_guest=True)
def event_poskos(disaster_event):
    """Flat posko list for an event, each tagged with Control Centre
    sharing mode. Used by the Kelompok & Posko list to badge + link
    every posko across all organisations."""
    return map_points(canonical_event(disaster_event))


@frappe.whitelist(allow_guest=True)
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
            "verification_status", "public_detail",
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

    full = share.get("mode") == "full"

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


# Unit conversion reference (static domain data).
_LOGISTIK_CONVERSIONS = [
    {"item": "Beras", "base_unit": "karung", "factor": 50, "target_unit": "kg"},
    {"item": "Air Mineral", "base_unit": "dus", "factor": 24, "target_unit": "botol (600 ml)"},
    {"item": "Minyak Goreng", "base_unit": "dus", "factor": 12, "target_unit": "liter"},
    {"item": "Mie Instan", "base_unit": "dus", "factor": 40, "target_unit": "pcs"},
    {"item": "Selimut", "base_unit": "bal", "factor": 25, "target_unit": "pcs"},
]


@frappe.whitelist(allow_guest=True)
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

    return {
        "posko": posko_out,
        "organization": base["organization"],
        "share_mode": base["share_mode"],
        "detail_allowed": full,
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
        "trace": trace,
        "conversions": _LOGISTIK_CONVERSIONS,
    }


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


def _norm_item(v):
    import re
    return re.sub(r"[_\s]+", " ", str(v or "").strip().lower())


_RECEIVED_STATES = {
    "received", "received_verified", "arrived", "arrived_at_posko",
    "stock_transferred", "completed", "closed",
}
_INTRANSIT_STATES = {"dispatched", "in_transit", "on_the_way", "assigned_pickup"}


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
def logistik_stock_cards(posko, disaster_event=None):
    name = _resolve_posko(posko)
    if not name:
        frappe.throw("Posko tidak ditemukan")
    return {"posko": name, "cards": _stock_cards(name)}


@frappe.whitelist(allow_guest=True)
def logistik_incoming(posko, disaster_event=None):
    name = _resolve_posko(posko)
    if not name:
        frappe.throw("Posko tidak ditemukan")
    return {"posko": name, "incoming": _incoming_flows(name)}


@frappe.whitelist(allow_guest=True)
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
def set_posko_beneficiary(posko, count, note=None):
    from rescue_net.access_policy import rn_actor
    from frappe.utils import now_datetime

    actor = rn_actor()
    name = _resolve_posko(posko)
    if not name:
        frappe.throw("Posko tidak ditemukan")

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

    rn_actor()
    name = _resolve_posko(posko)
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
        ["name", "item_name", "unit", "posko", "disaster_event"],
        as_dict=True,
    )
    if not n:
        frappe.throw("Kebutuhan tidak ditemukan")

    if not str(donor_name or "").strip():
        frappe.throw("Nama donatur wajib diisi")

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


@frappe.whitelist(
    allow_guest=True
)
def public_dashboard(
    disaster_event_id
):
    event = canonical_event(
        disaster_event_id
    )

    context = public_context(
        disaster_event_id
    )

    active = (
        public_active_disasters()
        or []
    )

    points = map_points(
        event
    )

    report_rows = reports(
        event
    )

    evidence_rows = event_evidence(
        event
    )

    return {
        "viewer_mode":
            "public",

        "read_only":
            True,

        "disaster_event_id":
            event,

        "active_disasters":
            active,

        "context":
            context,

        "map": {
            "points":
                points,

            "summary": {
                "total":
                    len(points),

                "critical":
                    sum(
                        p["situation"]
                        == "critical"
                        for p in points
                    ),

                "warning":
                    sum(
                        p["situation"]
                        == "warning"
                        for p in points
                    ),

                "safe":
                    sum(
                        p["situation"]
                        == "safe"
                        for p in points
                    ),
            },
        },

        "community_reports":
            report_rows,

        "evidence":
            evidence_rows,

        "demo_mode":
            event
            == (
                "disaster_events:"
                "event-sim-001"
            ),

        "demo_source":
            (
                "Komunitas Landrover"
                if event
                == (
                    "disaster_events:"
                    "event-sim-001"
                )
                else None
            ),
    }
