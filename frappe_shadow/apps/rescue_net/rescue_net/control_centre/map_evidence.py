"""Control Centre — map points, community reports on the map, evidence feed and board."""

import frappe
from frappe.rate_limiter import rate_limit

from rescue_net.api_ai import (
    public_context,
    public_active_disasters,
)

from rescue_net.control_centre.common import (  # noqa: F401
    _EVIDENCE_MODULE_ORDER,
    _MIME_EXT,
    _MODULE_KEYWORDS,
    _num,
    canonical_event,
    cols,
    event_filters,
    first,
)
from rescue_net.control_centre.critical import (  # noqa: F401
    _derived_critical_reasons,
)


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
        "public_participation",
        "rn_fn_logistics",
        "rn_fn_shelter",
        "rn_fn_kitchen",
        "rn_logistics_role",
        "rn_beneficiary_count",
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

    def _row_fns(r):
        fns = []
        if r.get("rn_fn_logistics"):
            fns.append("logistics")
        if r.get("rn_fn_shelter"):
            fns.append("shelter")
        if r.get("rn_fn_kitchen"):
            fns.append("kitchen")
        if not fns:
            t = (r.get("posko_type") or "").lower()
            if t in {"logistics", "collection_hub"}:
                fns = ["logistics"]
            elif t in {"shelter", "kitchen"}:
                fns = [t]
        role = r.get("rn_logistics_role")
        if not role and "logistics" in fns:
            role = ("collector"
                    if not int(_num(r.get("rn_beneficiary_count")))
                    else "receiver")
        return {"functions": fns, "logistics_role": role}

    _fn = {r.get("name"): _row_fns(r) for r in rows}

    derived = _derived_critical_reasons([r.get("name") for r in rows])

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

        if row.get("name") in derived:
            situation = "critical"

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

            "critical_reasons":
                derived.get(row.get("name"), []),

            "organization":
                row.get("organization"),

            "public_participation":
                bool(row.get("public_participation")),

            "functions":
                _fn.get(
                    row.get("name"), {}
                ).get("functions", []),

            "logistics_role":
                _fn.get(
                    row.get("name"), {}
                ).get("logistics_role"),

            "google_maps_url":
                (
                    "https://www.google.com/"
                    "maps/search/?api=1&query="
                    f"{lat},{lng}"
                ),
        })

    _annotate_share_mode(result)

    return result


def _hide_reasons(point):
    """Why a posko is critical is posko-level detail: like the rest of its
    detail it is only shown to a viewer allowed the "full" share mode. The pin
    itself (situation) stays visible — it is summary-level — so flag that the
    reasons exist but are withheld."""
    if point.get("critical_reasons"):
        point["critical_reasons_hidden"] = True
    point["critical_reasons"] = []


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
            _hide_reasons(point)
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
        if not point["detail_allowed"]:
            _hide_reasons(point)


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


def _evidence_module(linked_object_type, report_type=None):
    # report_type (from RN Community Report) is the real classifying signal
    # for community-submitted evidence — linked_object_type is uniformly
    # "RN Community Report" for that whole source, so it can't distinguish
    # modules on its own.
    for text in (report_type, linked_object_type):
        text = str(text or "").lower()
        if not text:
            continue
        for label, keywords in _MODULE_KEYWORDS:
            if any(k in text for k in keywords):
                return label
    return "Lainnya"


def _evidence_mime(file_type, url):
    if file_type:
        ft = str(file_type).lower()
        if "video" in ft:
            return "video"
        if "image" in ft or "photo" in ft:
            return "image"
        return "document"
    ext = str(url or "").rsplit(".", 1)[-1].lower() if url and "." in str(url) else ""
    return _MIME_EXT.get(ext, "image")


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
        "module": _evidence_module(kw.get("linked_object_type"), kw.get("report_type")),
        "visibility": kw.get("visibility_scope") or "restricted",
        "mime": _evidence_mime(kw.get("file_type"), url),
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
            "name", "report", "file_url", "caption", "evidence_type", "file_type",
            "verification_status", "uploader_user", "observed_at", "creation",
            "visibility_scope",
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
                file_type=e.get("file_type"), visibility_scope=e.get("visibility_scope"),
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
                        "verification_status", "observed_at", "creation",
                        "visibility_scope"],
                order_by="creation desc",
                limit_page_length=limit,
            ):
                up = _user_label(e.get("uploader_user"))
                push(_ev_norm(
                    id=e["name"], source="operational_evidence",
                    file_url=e.get("file_url"), caption=e.get("caption"),
                    evidence_type=e.get("evidence_type"), status=e.get("verification_status"),
                    visibility_scope=e.get("visibility_scope"),
                    title=e.get("caption"), posko=e.get("posko"),
                    uploader=up.get("label"), uploader_role=up.get("role"),
                    reporter_name=up.get("label"),
                    linked_object_type=e.get("linked_doctype"),
                    linked_object_id=e.get("linked_name"),
                    disaster_event_id=event,
                    observed_at=e.get("observed_at"), creation=e.get("creation"),
                ))

    return out[:limit]


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def evidence_board(disaster_event=None, limit=300):
    """Evidence Center dashboard (matches the DMS mock-up), guest read-only.

    Wraps the already-unified `event_evidence()` feed with the mock-up's KPI
    totals + Filter Modul chip counts. Rows are returned as-is (already rich
    — thumbnail url, module, GPS, uploader+role, verification status,
    visibility) for the frontend to search/filter/paginate client-side, the
    same pattern as Bencana Aktif / Daftar Relawan / Daftar Shelter.
    "Ekspor" (CSV) is a real client-side export of the currently filtered
    rows, not a stub.
    """
    event = canonical_event(disaster_event) if disaster_event else None
    rows = event_evidence(event, limit=int(limit)) if event else []

    today = frappe.utils.getdate()

    def _is_today(row):
        d = row.get("created_at") or row.get("creation")
        return bool(d and frappe.utils.getdate(d) == today)

    def _is_geotagged(row):
        lat, lng = row.get("latitude"), row.get("longitude")
        return bool(lat and lng and (abs(_num(lat)) > 0.0001 or abs(_num(lng)) > 0.0001))

    evidence_baru = [r for r in rows if _is_today(r)]
    pending = [r for r in rows if str(r.get("status") or "").lower() == "pending"]
    restricted = [r for r in rows if r.get("visibility") == "restricted"]
    geotagged = [r for r in rows if _is_geotagged(r)]
    serah_terima = [r for r in rows if str(r.get("evidence_type") or "").lower() in ("handover", "document")]
    video = [r for r in rows if r.get("mime") == "video"]

    def _drill(row):
        return {
            "title": row.get("title") or row.get("caption") or "Evidence",
            "sub": (row.get("module") or "-") + " · " + (row.get("location_text") or row.get("posko") or "-"),
            "href": row.get("evidence_url"),
        }

    module_counts = {}
    for r in rows:
        key = r.get("module") or "Lainnya"
        module_counts[key] = module_counts.get(key, 0) + 1

    filter_modul = [{"label": "Semua", "count": len(rows)}] + [
        {"label": label, "count": module_counts[label]}
        for label in _EVIDENCE_MODULE_ORDER
        if module_counts.get(label)
    ]

    return {
        "disaster_event": event,
        "generated_at": frappe.utils.now_datetime(),
        "totals": {
            "evidence_baru": len(evidence_baru),
            "pending_verifikasi": len(pending),
            "restricted": len(restricted),
            "geotagged": len(geotagged),
            "dokumen_serah_terima": len(serah_terima),
            "video_evidence": len(video),
        },
        "kpi_items": {
            "evidence_baru_items": [_drill(r) for r in evidence_baru[:30]],
            "pending_items": [_drill(r) for r in pending[:30]],
            "restricted_items": [_drill(r) for r in restricted[:30]],
            "geotagged_items": [_drill(r) for r in geotagged[:30]],
            "serah_terima_items": [_drill(r) for r in serah_terima[:30]],
            "video_items": [_drill(r) for r in video[:30]],
        },
        "filter_modul": filter_modul,
        "rows": rows,
    }
