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
        key = (row.get("evidence_url"), row.get("id"))
        if row.get("evidence_url") and key not in seen:
            seen.add(key)
            out.append(row)

    # --- 1. Community reports for this event (sim seeds live here) ---
    report_names = set()

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
                    "creation", "modified",
                ) if f == "name" or f in rep_cols
            ],
            order_by="modified desc" if "modified" in rep_cols else "creation desc",
            limit_page_length=limit,
        )

        for r in rep_rows:
            report_names.add(r["name"])
            payload = r.get("legacy_payload")

            if isinstance(payload, str) and payload.strip():
                try:
                    payload = json.loads(payload)
                except (ValueError, TypeError):
                    payload = None

            ev = payload.get("evidence") if isinstance(payload, dict) else None
            src = payload.get("source") if isinstance(payload, dict) else None

            if isinstance(ev, dict) and (ev.get("image") or ev.get("url") or ev.get("file_url")):
                push(_ev_norm(
                    id=r["name"], source="community_report",
                    evidence_url=ev.get("image") or ev.get("url") or ev.get("file_url"),
                    caption=ev.get("caption"), evidence_type=ev.get("evidence_type") or "photo",
                    description=ev.get("details") or r.get("description"),
                    title=r.get("title"), report_type=r.get("report_type"),
                    priority=r.get("priority"), status=r.get("status"),
                    location_text=r.get("location_text"),
                    latitude=r.get("latitude"), longitude=r.get("longitude"),
                    reporter_name=r.get("reporter_name") or src,
                    linked_object_type="RN Community Report", linked_object_id=r["name"],
                    disaster_event_id=event,
                    creation=r.get("creation"), modified=r.get("modified"),
                ))

    # --- 2. RN Community Report Evidence (structured child evidence) ---
    if frappe.db.exists("DocType", "RN Community Report Evidence") and report_names:
        for e in frappe.get_all(
            "RN Community Report Evidence",
            filters={"report": ["in", list(report_names)]},
            fields=["name", "report", "file_url", "caption", "evidence_type",
                    "verification_status", "observed_at", "creation"],
            limit_page_length=limit,
        ):
            push(_ev_norm(
                id=e["name"], source="community_report_evidence",
                file_url=e.get("file_url"), caption=e.get("caption"),
                evidence_type=e.get("evidence_type"), status=e.get("verification_status"),
                title=e.get("caption"),
                linked_object_type="RN Community Report", linked_object_id=e.get("report"),
                disaster_event_id=event,
                observed_at=e.get("observed_at"), creation=e.get("creation"),
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
                    "verification_status", "observed_at", "creation",
                ) if f == "name" or f in ef_cols
            ],
            order_by="creation desc",
            limit_page_length=limit,
        ):
            push(_ev_norm(
                id=e["name"], source="evidence_file",
                file_url=e.get("file_url"), caption=e.get("caption"),
                evidence_type=e.get("evidence_type"), status=e.get("verification_status"),
                title=e.get("caption"), posko=e.get("posko"),
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
                        "linked_doctype", "linked_name", "verification_status",
                        "observed_at", "creation"],
                order_by="creation desc",
                limit_page_length=limit,
            ):
                push(_ev_norm(
                    id=e["name"], source="operational_evidence",
                    file_url=e.get("file_url"), caption=e.get("caption"),
                    evidence_type=e.get("evidence_type"), status=e.get("verification_status"),
                    title=e.get("caption"), posko=e.get("posko"),
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
