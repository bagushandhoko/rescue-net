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
