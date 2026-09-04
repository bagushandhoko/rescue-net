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


_MODULE_KEYWORDS = [
    ("Medis", ("medical", "medis")),
    ("Distribusi", ("distribution", "distribusi", "transport", "road_access")),
    ("Logistik", ("logistic", "logistik", "stock", "aid_offer", "aid offer", "donation", "donasi")),
    ("Search & Found", ("missing_person", "found_person", "search_found", "missing", "found")),
    ("Shelter", ("shelter",)),
    ("Dapur Umum", ("kitchen", "dapur")),
    ("Relawan", ("volunteer", "relawan")),
    ("Program", ("donor", "recovery", "program", "work_tool", "resource_profile")),
]


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


_MIME_EXT = {
    "jpg": "image", "jpeg": "image", "png": "image", "gif": "image", "webp": "image",
    "mp4": "video", "mov": "video", "webm": "video", "avi": "video",
    "pdf": "document", "doc": "document", "docx": "document", "xls": "document", "xlsx": "document",
}


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


_EVIDENCE_MODULE_ORDER = [
    "Logistik", "Medis", "Distribusi", "Program", "Search & Found",
    "Shelter", "Dapur Umum", "Relawan", "Lainnya",
]


@frappe.whitelist(allow_guest=True)
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
            "verification_status", "trusted_verifier_count", "public_detail",
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
        "RN Aid Offer", filters={"target_posko": name},
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


def _norm_item(v):
    import re
    return re.sub(r"[_\s]+", " ", str(v or "").strip().lower())


_RECEIVED_STATES = {
    "received", "received_verified", "arrived", "arrived_at_posko",
    "stock_transferred", "completed", "closed",
}
_INTRANSIT_STATES = {"dispatched", "in_transit", "on_the_way", "assigned_pickup", "pickup_claimed"}


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
def set_posko_functions(posko, functions=None, logistics_role=None):
    """Set which functions a posko serves (logistik / shelter / dapur umum)
    and, for logistik, whether it is a collector or a receiver.
    `functions` may be a JSON array or a comma string."""
    import json
    from rescue_net.access_policy import rn_actor

    rn_actor()
    name = _resolve_posko(posko)
    if not name:
        frappe.throw("Posko tidak ditemukan")

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
    frappe.db.commit()
    return {"posko": name, **_posko_functions(name)}


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


# ============================================================
# KPI drill-down — one feed for every Control Centre figure.
#
# Rescue-Net integrates data from many groups. Clicking a KPI or
# module tile on the Control Centre opens the underlying list of
# items / objects / situations, grouped by the owning organisation.
# Clicking "Lanjut" on a row drills into that posko.
#
# An organisation that shares only "aggregate" (closed coordination)
# contributes counts / totals ONLY — no per-record rows. An open
# organisation ("full_authorized"), or a posko whose own
# public_detail overrides it, contributes the full item list.
# See rescue_net.visibility.effective_posko_share.
# ============================================================

_DRILL_URGENT = {"critical", "urgent", "high", "tinggi", "darurat", "segera"}
_DRILL_CLOSED_NEED = {"fulfilled", "closed", "cancelled", "met", "resolved", "done"}
_DRILL_BLOCKED_FLOW = {
    "blocked", "delayed", "on_hold", "pending", "pending_pickup",
    "need_pickup", "awaiting_pickup", "stuck", "assigned_pickup", "cancelled",
}
_DRILL_DELIVERED_OFFER = {
    "delivered", "distributed", "completed", "closed", "received", "fulfilled",
}

_DRILL_TITLES = {
    "kebutuhan": "Kebutuhan Lapangan Belum Terpenuhi",
    "posko_kritis": "Posko Berstatus Kritis",
    "distribusi": "Alur Distribusi Bantuan",
    "distribusi_terhambat": "Distribusi Terhambat / Menunggu Pickup",
    "medis": "Kasus Medis",
    "donasi": "Tawaran Bantuan Belum Tersalur",
    "stok": "Stok Barang per Posko",
    "relawan": "Penugasan Relawan",
    "program": "Program Khusus & Donasi Terarah",
    "search": "Laporan Orang Hilang & Ditemukan",
}


def _fmt(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v or "")
    return f"{int(round(f)):,}".replace(",", ".")


def _event_posko_names(event):
    return [
        p["name"]
        for p in frappe.get_all(
            "RN Posko",
            filters=event_filters(cols("RN Posko"), event),
            fields=["name"],
            limit_page_length=1000,
        )
    ]


class _OrgResolver:
    """posko name -> organisation row + effective Control Centre share mode,
    with per-call caching so a drill-down touches each posko/org once."""

    def __init__(self, actor):
        self.actor = actor
        self._posko = {}
        self._org = {}
        self._mode = {}
        try:
            from rescue_net.visibility import effective_posko_share
            self._share_fn = effective_posko_share
        except Exception:
            self._share_fn = None

    def posko(self, name):
        if name not in self._posko:
            self._posko[name] = frappe.db.get_value(
                "RN Posko", name,
                ["name", "legacy_id", "title", "organization"],
                as_dict=True,
            ) or {}
        return self._posko[name]

    def org(self, org_name):
        if not org_name:
            return {}
        if org_name not in self._org:
            self._org[org_name] = frappe.db.get_value(
                "RN Organization", org_name,
                ["name", "title", "organization_type",
                 "control_centre_share", "privacy_mode"],
                as_dict=True,
            ) or {}
        return self._org[org_name]

    def share_mode(self, posko_name):
        if not posko_name:
            return "summary"
        if posko_name not in self._mode:
            mode = "summary"
            if self._share_fn:
                try:
                    mode = self._share_fn(
                        posko_name, self.actor
                    ).get("mode", "summary")
                except Exception:
                    mode = "summary"
            self._mode[posko_name] = mode
        return self._mode[posko_name]


def _drill_kebutuhan(event, res, limit):
    import json

    rows = []
    for n in frappe.get_all(
        "RN Logistic Need",
        filters=event_filters(cols("RN Logistic Need"), event),
        fields=_sf("RN Logistic Need", [
            "name", "item_name", "quantity", "unit", "urgency",
            "need_status", "posko", "needed_before", "legacy_payload", "modified",
        ]),
        order_by="modified desc",
        limit_page_length=limit,
    ):
        status = str(n.get("need_status") or "open").lower()
        if status in _DRILL_CLOSED_NEED:
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

        rows.append({
            "id": n.get("name"),
            "title": n.get("item_name") or "Kebutuhan",
            "detail": (
                f"butuh {_fmt(required)} {n.get('unit') or ''}".strip()
                + (f" · realisasi {_fmt(realized)}" if realized else "")
            ),
            "quantity": required,
            "unit": n.get("unit"),
            "gap": max(0.0, required - realized),
            "status": status,
            "priority": n.get("urgency"),
            "when": n.get("needed_before"),
            "_posko": n.get("posko"),
        })

    if frappe.db.exists("DocType", "RN Shelter Need"):
        posko_names = _event_posko_names(event)
        if posko_names:
            for s in frappe.get_all(
                "RN Shelter Need",
                filters={"posko": ["in", posko_names]},
                fields=_sf("RN Shelter Need", [
                    "name", "item_name", "quantity_needed", "unit", "priority",
                    "need_status", "posko", "needed_before",
                ]),
                limit_page_length=limit,
            ):
                status = str(s.get("need_status") or "open").lower()
                if status in _DRILL_CLOSED_NEED:
                    continue
                req = _num(s.get("quantity_needed"))
                rows.append({
                    "id": s.get("name"),
                    "title": (s.get("item_name") or "Kebutuhan shelter") + " (shelter)",
                    "detail": f"butuh {_fmt(req)} {s.get('unit') or ''}".strip(),
                    "quantity": req,
                    "unit": s.get("unit"),
                    "gap": req,
                    "status": status,
                    "priority": s.get("priority"),
                    "when": s.get("needed_before"),
                    "_posko": s.get("posko"),
                })
    return rows


def _drill_posko_kritis(event, res, limit):
    rows = []
    for p in map_points(event):
        if p.get("situation") != "critical":
            continue
        rows.append({
            "id": p.get("posko_id"),
            "title": p.get("name"),
            "detail": " · ".join(x for x in [
                p.get("posko_type"), p.get("address"),
            ] if x),
            "quantity": 0,
            "unit": None,
            "gap": 0,
            "status": p.get("status"),
            "priority": "critical",
            "when": None,
            "_posko": p.get("posko_id"),
        })
    return rows


def _drill_flows(event, res, limit, only_blocked):
    rows = []
    for f in frappe.get_all(
        "RN Distribution Flow",
        filters=event_filters(cols("RN Distribution Flow"), event),
        fields=_sf("RN Distribution Flow", [
            "name", "item_name", "quantity", "unit", "flow_status",
            "source_posko", "destination_posko", "eta_final",
            "transport_provider", "transport_type", "modified",
        ]),
        order_by="modified desc",
        limit_page_length=limit,
    ):
        st = str(f.get("flow_status") or "").lower()
        if only_blocked and st not in _DRILL_BLOCKED_FLOW:
            continue
        transport = f.get("transport_type") or f.get("transport_provider")
        rows.append({
            "id": f.get("name"),
            "title": f.get("item_name") or "Distribusi",
            "detail": (
                (f.get("source_posko") or "?") + " → "
                + (f.get("destination_posko") or "?")
                + (f" · {transport}" if transport else "")
            ),
            "quantity": _num(f.get("quantity")),
            "unit": f.get("unit"),
            "gap": 0,
            "status": f.get("flow_status"),
            "priority": "urgent" if only_blocked else None,
            "when": f.get("eta_final"),
            "_posko": f.get("destination_posko") or f.get("source_posko"),
        })
    return rows


def _drill_distribusi(event, res, limit):
    return _drill_flows(event, res, limit, only_blocked=False)


def _drill_distribusi_terhambat(event, res, limit):
    return _drill_flows(event, res, limit, only_blocked=True)


def _drill_medis(event, res, limit):
    rows = []
    for m in frappe.get_all(
        "RN Medical Case",
        filters=event_filters(cols("RN Medical Case"), event),
        fields=_sf("RN Medical Case", [
            "name", "patient_code", "complaint", "severity", "triage_status",
            "case_status", "age_group", "gender", "posko", "observed_at",
        ]),
        order_by="observed_at desc",
        limit_page_length=limit,
    ):
        rows.append({
            "id": m.get("name"),
            "title": m.get("complaint") or m.get("patient_code") or "Kasus medis",
            "detail": " · ".join(x for x in [
                m.get("patient_code"), m.get("age_group"), m.get("gender"),
                (f"triase {m.get('triage_status')}" if m.get("triage_status") else None),
            ] if x),
            "quantity": 0,
            "unit": None,
            "gap": 0,
            "status": m.get("case_status") or m.get("triage_status"),
            "priority": m.get("severity"),
            "when": m.get("observed_at"),
            "_posko": m.get("posko"),
        })
    return rows


def _drill_donasi(event, res, limit):
    rows = []
    for o in frappe.get_all(
        "RN Aid Offer",
        filters=event_filters(cols("RN Aid Offer"), event),
        fields=_sf("RN Aid Offer", [
            "name", "donor_name", "item_name", "quantity", "unit",
            "offer_status", "target_posko", "ready_at", "pickup_location", "modified",
        ]),
        order_by="modified desc",
        limit_page_length=limit,
    ):
        st = str(o.get("offer_status") or "").lower()
        if st in _DRILL_DELIVERED_OFFER:
            continue
        rows.append({
            "id": o.get("name"),
            "title": o.get("item_name") or "Bantuan",
            "detail": " · ".join(x for x in [
                (f"dari {o.get('donor_name')}" if o.get("donor_name") else None),
                o.get("pickup_location"),
            ] if x),
            "quantity": _num(o.get("quantity")),
            "unit": o.get("unit"),
            "gap": 0,
            "status": o.get("offer_status"),
            "priority": None,
            "when": o.get("ready_at"),
            "_posko": o.get("target_posko"),
        })
    return rows


def _drill_stok(event, res, limit):
    rows = []
    seen = set()
    for o in frappe.get_all(
        "RN Stock Observation",
        filters=event_filters(cols("RN Stock Observation"), event),
        fields=_sf("RN Stock Observation", [
            "name", "item_name", "canonical_item", "quantity", "unit",
            "stock_state", "posko", "observed_at",
        ]),
        order_by="observed_at desc",
        limit_page_length=limit * 3,
    ):
        key = (o.get("posko"), _norm_item(o.get("canonical_item") or o.get("item_name")))
        if key in seen:
            continue
        seen.add(key)
        low = str(o.get("stock_state") or "").lower() in {
            "critical", "low", "menipis", "habis", "empty",
        }
        rows.append({
            "id": o.get("name"),
            "title": o.get("item_name") or "Barang",
            "detail": (o.get("stock_state") or "stok tercatat"),
            "quantity": _num(o.get("quantity")),
            "unit": o.get("unit"),
            "gap": 0,
            "status": o.get("stock_state"),
            "priority": "urgent" if low else None,
            "when": o.get("observed_at"),
            "_posko": o.get("posko"),
        })
    return rows


def _drill_relawan(event, res, limit):
    rows = []
    vcache = {}

    def vol_name(v):
        if not v:
            return None
        if v not in vcache:
            try:
                vcache[v] = frappe.db.get_value(
                    "RN Volunteer Profile", v, "volunteer_name"
                ) or v
            except Exception:
                vcache[v] = v
        return vcache[v]

    for a in frappe.get_all(
        "RN Volunteer Assignment",
        filters=event_filters(cols("RN Volunteer Assignment"), event),
        fields=_sf("RN Volunteer Assignment", [
            "name", "volunteer", "task_title", "assignment_type",
            "assignment_status", "required_skill", "priority", "posko", "shift_start",
        ]),
        order_by="modified desc",
        limit_page_length=limit,
    ):
        rows.append({
            "id": a.get("name"),
            "title": a.get("task_title") or a.get("assignment_type") or "Penugasan relawan",
            "detail": " · ".join(x for x in [
                vol_name(a.get("volunteer")), a.get("required_skill"),
                a.get("assignment_type"),
            ] if x),
            "quantity": 0,
            "unit": None,
            "gap": 0,
            "status": a.get("assignment_status"),
            "priority": a.get("priority"),
            "when": a.get("shift_start"),
            "_posko": a.get("posko"),
        })
    return rows


def _drill_program(event, res, limit):
    rows = []
    for d in frappe.get_all(
        "RN Donor Program",
        filters=event_filters(cols("RN Donor Program"), event),
        fields=_sf("RN Donor Program", [
            "name", "program_name", "program_type", "owner_type", "owner_id",
            "status", "target_amount", "target_unit", "current_amount",
            "location", "priority", "modified",
        ]),
        order_by="modified desc",
        limit_page_length=limit,
    ):
        tgt = _num(d.get("target_amount"))
        cur = _num(d.get("current_amount"))
        owner_is_org = str(d.get("owner_type") or "").lower() in {
            "organization", "org", "rn organization", "kelompok",
        }
        rows.append({
            "id": d.get("name"),
            "title": d.get("program_name") or "Program",
            "detail": " · ".join(x for x in [
                d.get("program_type"),
                (f"target {_fmt(tgt)} {d.get('target_unit') or ''}".strip() if tgt else None),
                (f"terkumpul {_fmt(cur)}" if cur else None),
                d.get("location"),
            ] if x),
            "quantity": tgt,
            "unit": d.get("target_unit"),
            "gap": max(0.0, tgt - cur),
            "status": d.get("status"),
            "priority": d.get("priority"),
            "when": None,
            "_posko": None,
            "_org_direct": d.get("owner_id") if owner_is_org else None,
            "_force_mode": None if owner_is_org else "full",
        })
    return rows


def _drill_search(event, res, limit):
    rows = []
    for dt, kind, loc_field, time_field in [
        ("RN Missing Person Report", "Hilang", "last_seen_location", "last_seen_time"),
        ("RN Found Person Report", "Ditemukan", "found_location", "found_time"),
    ]:
        if not frappe.db.exists("DocType", dt):
            continue
        for m in frappe.get_all(
            dt,
            filters=event_filters(cols(dt), event),
            fields=_sf(dt, [
                "name", "person_code", "person_name", loc_field, time_field,
                "report_status", "posko", "description",
            ]),
            order_by="modified desc",
            limit_page_length=limit,
        ):
            rows.append({
                "id": m.get("name"),
                "title": (m.get("person_name") or m.get("person_code") or "Orang")
                + f" ({kind})",
                "detail": " · ".join(x for x in [
                    m.get(loc_field), m.get("description"),
                ] if x),
                "quantity": 0,
                "unit": None,
                "gap": 0,
                "status": m.get("report_status"),
                "priority": "urgent" if kind == "Hilang" else None,
                "when": m.get(time_field),
                "_posko": m.get("posko"),
            })
    return rows


_DRILL_BUILDERS = {
    "kebutuhan": _drill_kebutuhan,
    "posko_kritis": _drill_posko_kritis,
    "distribusi": _drill_distribusi,
    "distribusi_terhambat": _drill_distribusi_terhambat,
    "medis": _drill_medis,
    "donasi": _drill_donasi,
    "stok": _drill_stok,
    "relawan": _drill_relawan,
    "program": _drill_program,
    "search": _drill_search,
}


def _group_by_org(rows, dimension, res):
    groups = {}
    order = []

    for r in rows:
        posko_name = r.pop("_posko", None)
        org_direct = r.pop("_org_direct", None)
        force_mode = r.pop("_force_mode", None)

        if posko_name:
            p = res.posko(posko_name)
            org_row = res.org(p.get("organization")) if p.get("organization") else {}
            key = p.get("organization") or "__none__"
            mode = force_mode or res.share_mode(posko_name)
        else:
            p = {}
            org_row = res.org(org_direct) if org_direct else {}
            key = org_row.get("name") or "__none__"
            if force_mode:
                mode = force_mode
            else:
                share = (org_row.get("control_centre_share") or "aggregate").lower()
                mode = "full" if share == "full_authorized" else "summary"

        if key not in groups:
            order.append(key)
            groups[key] = {
                "organization": org_row.get("name"),
                "organization_title": (
                    org_row.get("title")
                    or ("Tanpa organisasi" if key == "__none__" else key)
                ),
                "organization_type": org_row.get("organization_type"),
                "control_centre_share": (
                    org_row.get("control_centre_share") or "aggregate"
                ),
                "privacy_mode": org_row.get("privacy_mode"),
                "count": 0,
                "shown_count": 0,
                "hidden_count": 0,
                "critical_count": 0,
                "total_quantity": 0.0,
                "total_gap": 0.0,
                "_poskos": set(),
                "_any_full": False,
                "items": [],
            }

        g = groups[key]
        g["count"] += 1
        if posko_name:
            g["_poskos"].add(posko_name)
        g["total_quantity"] += _num(r.get("quantity"))
        g["total_gap"] += _num(r.get("gap"))
        if (
            str(r.get("priority") or "").lower() in _DRILL_URGENT
            or str(r.get("status") or "").lower() in {"critical", "overload", "emergency"}
        ):
            g["critical_count"] += 1

        r["posko"] = posko_name
        r["posko_title"] = p.get("title")
        r["organization_title"] = g["organization_title"]

        if mode == "full":
            g["_any_full"] = True
            g["shown_count"] += 1
            g["items"].append(r)
        else:
            g["hidden_count"] += 1

    out = []
    for key in order:
        g = groups[key]
        g["posko_count"] = len(g.pop("_poskos"))
        g["share_mode"] = "full" if g.pop("_any_full") else "summary"
        g["total_quantity"] = round(g["total_quantity"], 1)
        g["total_gap"] = round(g["total_gap"], 1)
        out.append(g)

    out.sort(key=lambda x: (0 if x["share_mode"] == "full" else 1, -x["count"]))

    return {
        "dimension": dimension,
        "title": _DRILL_TITLES.get(dimension, dimension),
        "total": sum(g["count"] for g in out),
        "shown_total": sum(g["shown_count"] for g in out),
        "hidden_total": sum(g["hidden_count"] for g in out),
        "org_count": len(out),
        "groups": out,
    }


@frappe.whitelist(allow_guest=True)
def kpi_drilldown(disaster_event, dimension, limit=500):
    """Underlying records for one Control Centre KPI / module tile,
    grouped by the owning organisation and gated by that organisation's
    Control Centre sharing mode (open -> item rows; closed -> summary)."""
    event = canonical_event(disaster_event)
    dimension = str(dimension or "").strip().lower()

    builder = _DRILL_BUILDERS.get(dimension)
    if not builder:
        frappe.throw(f"Dimensi drill-down tidak dikenal: {dimension}")

    try:
        from rescue_net.access_policy import rn_actor
        try:
            actor = rn_actor(required=False)
        except Exception:
            actor = None
    except Exception:
        actor = None

    res = _OrgResolver(actor)
    rows = builder(event, res, int(limit))
    return _group_by_org(rows, dimension, res)


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


# ---------------------------------------------------------------------------
# Bencana Aktif dashboard (pages/bencana-aktif.html)
# ---------------------------------------------------------------------------

_SIT_RANK = {"safe": 0, "warning": 1, "critical": 2}
_SIT_STATUS = {"safe": "Waspada", "warning": "Siaga", "critical": "Kritis"}
_SEV_STATUS = {
    "critical": "Kritis", "urgent": "Siaga", "high": "Siaga",
    "warning": "Siaga", "normal": "Waspada", "low": "Waspada", "": "Waspada",
}
_OPS_CRITICAL = {"critical", "overload", "emergency", "danger"}
_OPS_WARNING = {"urgent", "warning", "affected", "disrupted"}
_CRIT_URGENCY = {"critical", "urgent", "high"}
_CLOSED_NEED = {"fulfilled", "closed", "cancelled", "met", "done"}


def _ba_region_key(posko):
    return (
        (posko.get("city_name") or "").strip()
        or (posko.get("province_name") or "").strip()
        or "Wilayah lain"
    )


def _ba_situation(value):
    v = str(value or "").lower()
    if v in _OPS_CRITICAL:
        return "critical"
    if v in _OPS_WARNING:
        return "warning"
    return "safe"


def _ba_max_dt(a, b):
    if b is None:
        return a
    if a is None:
        return b
    try:
        return a if a >= b else b
    except TypeError:
        return a


def _ba_iso(v):
    if not v:
        return None
    try:
        return frappe.utils.get_datetime(v).isoformat()
    except Exception:
        return str(v)


def _ba_dominant_area(poskos):
    from collections import Counter

    counter = Counter(
        (p.get("city_name") or p.get("province_name") or "").strip()
        for p in poskos
        if (p.get("city_name") or p.get("province_name"))
    )
    return counter.most_common(1)[0][0] if counter else None


@frappe.whitelist(allow_guest=True)
def active_disasters_board(limit=60):
    """Public 'Bencana Aktif' dashboard feed: every active RN Disaster Event
    with a per-region (kabupaten/kota) breakdown, rolled-up KPI totals, and a
    short 'isu kritis teratas' list per event. Read-only, guest-safe."""
    events = frappe.get_all(
        "RN Disaster Event",
        filters={"event_status": "active"},
        fields=_sf("RN Disaster Event", [
            "name", "legacy_id", "title", "severity", "event_status",
            "started_at", "location_summary", "modified",
        ]),
        order_by="started_at desc",
        limit_page_length=int(limit),
    )

    posko_cols = cols("RN Posko")
    need_cols = cols("RN Logistic Need")
    flow_cols = cols("RN Distribution Flow")

    out_events = []
    tot_jiwa = tot_krit = tot_hambat = tot_pkritis = 0

    for ev in events:
        event_id = ev["name"]

        poskos = frappe.get_all(
            "RN Posko",
            filters=event_filters(posko_cols, event_id),
            fields=_sf("RN Posko", [
                "name", "title", "city_name", "province_name", "address",
                "posko_type", "operational_status", "organization",
                "rn_beneficiary_count", "rn_fn_shelter", "modified",
            ]),
            limit_page_length=500,
        )
        needs = frappe.get_all(
            "RN Logistic Need",
            filters=event_filters(need_cols, event_id),
            fields=_sf("RN Logistic Need", [
                "name", "item_name", "urgency", "need_status", "posko", "modified",
            ]),
            limit_page_length=500,
        )
        flows = frappe.get_all(
            "RN Distribution Flow",
            filters=event_filters(flow_cols, event_id),
            fields=_sf("RN Distribution Flow", [
                "name", "item_name", "flow_status", "destination_posko", "modified",
            ]),
            limit_page_length=500,
        )

        posko_region = {p["name"]: _ba_region_key(p) for p in poskos}
        posko_title = {p["name"]: (p.get("title") or p["name"]) for p in poskos}

        crit_needs = [
            n for n in needs
            if str(n.get("urgency") or "").lower() in _CRIT_URGENCY
            and str(n.get("need_status") or "open").lower() not in _CLOSED_NEED
        ]
        blocked_flows = [
            f for f in flows
            if str(f.get("flow_status") or "").lower() in _DRILL_BLOCKED_FLOW
        ]

        short_ev = str(ev["name"]).replace("disaster_events:", "")

        kebutuhan_items = [
            {
                "item": n.get("item_name") or "Kebutuhan logistik",
                "urgency": str(n.get("urgency") or "").lower(),
                "posko": n.get("posko"),
                "posko_title": posko_title.get(n.get("posko")) or n.get("posko") or "-",
                "region": posko_region.get(n.get("posko")) or "Lintas wilayah",
                "href": (
                    "posko-logistik.html?id="
                    + str(n.get("posko") or "").replace("posko_nodes:", "")
                    + "&event=" + short_ev
                    + "&penuhi=" + (n.get("item_name") or "")
                ) if n.get("posko") else ("war-room.html?event=" + short_ev),
            }
            for n in sorted(
                crit_needs,
                key=lambda n: 0
                if str(n.get("urgency") or "").lower() == "critical" else 1,
            )
        ]
        distribusi_items = [
            {
                "item": f.get("item_name") or "Distribusi",
                "status": str(f.get("flow_status") or "").lower(),
                "posko": f.get("destination_posko"),
                "posko_title": posko_title.get(f.get("destination_posko"))
                or f.get("destination_posko") or "-",
                "region": posko_region.get(f.get("destination_posko")) or "Lintas wilayah",
                "href": "management-distribusi.html?event=" + short_ev,
            }
            for f in blocked_flows
        ]
        posko_kritis_items = [
            {
                "posko": p["name"],
                "posko_title": p.get("title") or p["name"],
                "region": posko_region[p["name"]],
                "type": p.get("posko_type"),
                "href": (
                    "posko-detail.html?id="
                    + str(p["name"]).replace("posko_nodes:", "")
                    + "&event=" + short_ev
                ),
            }
            for p in poskos
            if _ba_situation(p.get("operational_status")) == "critical"
        ]

        jiwa = sum(int(_num(p.get("rn_beneficiary_count"))) for p in poskos)
        pengungsi = sum(
            int(_num(p.get("rn_beneficiary_count")))
            for p in poskos
            if p.get("rn_fn_shelter")
            or str(p.get("posko_type") or "").lower() == "shelter"
        )

        regions = {}
        for p in poskos:
            key = posko_region[p["name"]]
            row = regions.setdefault(key, {
                "name": key, "jiwa_berisiko": 0, "kebutuhan_kritis": 0,
                "distribusi": 0, "situation": "safe", "posko_count": 0,
                "last_updated": None,
            })
            row["posko_count"] += 1
            row["jiwa_berisiko"] += int(_num(p.get("rn_beneficiary_count")))
            sit = _ba_situation(p.get("operational_status"))
            if _SIT_RANK[sit] > _SIT_RANK[row["situation"]]:
                row["situation"] = sit
            row["last_updated"] = _ba_max_dt(row["last_updated"], p.get("modified"))

        for n in crit_needs:
            key = posko_region.get(n.get("posko"))
            if key in regions:
                regions[key]["kebutuhan_kritis"] += 1
                regions[key]["last_updated"] = _ba_max_dt(
                    regions[key]["last_updated"], n.get("modified"))
        for f in flows:
            key = posko_region.get(f.get("destination_posko"))
            if key in regions:
                regions[key]["distribusi"] += 1

        region_rows = sorted(
            regions.values(),
            key=lambda r: (-_SIT_RANK[r["situation"]], -r["jiwa_berisiko"]),
        )
        for row in region_rows:
            row["status_label"] = _SIT_STATUS[row["situation"]]
            row["last_updated"] = _ba_iso(row["last_updated"])

        isu = []
        for it in kebutuhan_items[:6]:
            isu.append({
                "kind": "kebutuhan",
                "title": it["item"],
                "detail": it["region"],
                "level": "Sangat Tinggi" if it["urgency"] == "critical" else "Tinggi",
                "href": it["href"],
            })
        for it in posko_kritis_items:
            isu.append({
                "kind": "posko",
                "title": it["posko_title"] + " berstatus kritis",
                "detail": it["region"],
                "level": "Sangat Tinggi",
                "href": it["href"],
            })
        isu = isu[:6]

        last_updated = ev.get("modified")
        for coll in (poskos, needs, flows):
            for row in coll:
                last_updated = _ba_max_dt(last_updated, row.get("modified"))

        sev = str(ev.get("severity") or "normal").lower()
        out_events.append({
            "id": ev.get("legacy_id") or ev["name"],
            "event_id": ev["name"],
            "name": ev.get("title") or ev["name"],
            "location": ev.get("location_summary")
            or _ba_dominant_area(poskos) or "Indonesia",
            "severity": sev,
            "status_label": _SEV_STATUS.get(sev, "Waspada"),
            "started_at": _ba_iso(ev.get("started_at")),
            "last_updated": _ba_iso(last_updated),
            "jiwa_berisiko": jiwa,
            "pengungsi": pengungsi,
            "kebutuhan_kritis": len(crit_needs),
            "distribusi_terhambat": len(blocked_flows),
            "distribusi_total": len(flows),
            "posko_count": len(poskos),
            "posko_kritis": len(posko_kritis_items),
            "regions": region_rows,
            "isu_kritis": isu,
            "kebutuhan_items": kebutuhan_items,
            "distribusi_items": distribusi_items,
            "posko_kritis_items": posko_kritis_items,
        })

        tot_jiwa += jiwa
        tot_krit += len(crit_needs)
        tot_hambat += len(blocked_flows)
        tot_pkritis += len(posko_kritis_items)

    return {
        "generated_at": _ba_iso(frappe.utils.now_datetime()),
        "totals": {
            "bencana_aktif": len(out_events),
            "jiwa_berisiko": tot_jiwa,
            "kebutuhan_kritis": tot_krit,
            "distribusi_terhambat": tot_hambat,
            "posko_kritis": tot_pkritis,
        },
        "events": out_events,
    }


# ============================================================
# Manajemen Distribusi — pages/management-distribusi.html
# ============================================================

_DISTRIBUSI_STATUS_LABEL = {
    "planned": "Direncanakan",
    "pickup_claimed": "Akan Dijemput",
    "assigned_pickup": "Menunggu Pickup",
    "dispatched": "Dalam Perjalanan",
    "in_transit": "Dalam Perjalanan",
    "arrived": "Tiba di Tujuan",
    "received": "Diterima",
    "received_verified": "Diterima (Terverifikasi)",
    "stock_transferred": "Stok Ditransfer",
    "cancelled": "Dibatalkan",
}


def _distribusi_posko_titles(names):
    names = {n for n in names if n}
    if not names:
        return {}
    return {
        r.name: r.title
        for r in frappe.get_all(
            "RN Posko", filters={"name": ["in", list(names)]},
            fields=["name", "title"], limit_page_length=len(names),
        )
    }


def _distribusi_trace(name):
    return "RN-" + str(name or "")[-8:].upper()


def _qty_fmt(value):
    v = _num(value)
    if v == int(v):
        return f"{int(v):,}".replace(",", ".")
    return f"{v:,.1f}".replace(",", ".")


@frappe.whitelist(allow_guest=True)
def distribusi_board(disaster_event=None):
    """Manajemen Distribusi dashboard (matches the DMS mock-up), guest
    read-only. One payload: KPI totals + drill items, the 4-column matching
    board (read-only overview — deep-links to the module that owns each
    record, not a drag/drop redesign), Ruang Transportasi (real per
    transport_type, since RN Transport Space.transport_type already has
    darat/laut/udara/lainnya), Alur Distribusi (live RN Distribution Flow),
    Peringatan & Hambatan, and the static Pedoman Kemasan reference (reuses
    `_LOGISTIK_CONVERSIONS`, same source as Posko Logistik's "Konversi").
    Write action `auto_match_distribution` (login required) actually creates
    RN Distribution Flow records — not a UI-only button.
    """
    event = canonical_event(disaster_event) if disaster_event else None

    flow_filter = event_filters(cols("RN Distribution Flow"), event) if event else {}
    flows = frappe.get_all(
        "RN Distribution Flow", filters=flow_filter,
        fields=_sf("RN Distribution Flow", [
            "name", "item_name", "quantity", "unit", "flow_status",
            "source_posko", "destination_posko", "eta_final",
            "transport_provider", "transport_type", "transport_space",
            "logistic_need", "aid_offer", "dispatched_at", "in_transit_at",
            "arrived_at", "received_at", "modified",
        ]),
        order_by="modified desc", limit_page_length=500,
    )

    transport_filter = event_filters(cols("RN Transport Space"), event) if event else {}
    transports = frappe.get_all(
        "RN Transport Space", filters=transport_filter,
        fields=_sf("RN Transport Space", [
            "name", "provider_name", "transport_type", "transport_status",
            "capacity_weight_kg", "capacity_volume_m3", "route_origin",
            "route_destination", "observed_at", "coordination_posko",
            "departure_time", "eta", "current_location", "handover_location",
            "handover_contact_person", "handover_contact_phone",
            "coordination_notes", "departure_at", "eta_at", "service_mode",
            "booking_policy", "capacity_committed_kg", "capacity_committed_m3",
            "pickup_volunteer", "pickup_volunteer_name",
        ]),
        limit_page_length=200,
    )

    # confirmed/requested bookings that block armada capacity
    _tspace_names = [t.get("name") for t in transports]
    _bookings_by_space = {}
    if _tspace_names and frappe.db.exists("DocType", "RN Transport Booking"):
        for bk in frappe.get_all(
            "RN Transport Booking",
            filters={"transport_space": ["in", _tspace_names]},
            fields=_sf("RN Transport Booking", [
                "name", "transport_space", "cargo_desc", "qty_weight_kg",
                "qty_volume_m3", "status", "booker_name", "booked_by_type",
                "pickup_location", "dropoff_location", "contact_person",
                "contact_phone", "verification_pin", "requested_at",
                "delivery_method", "requested_window",
            ]),
            order_by="creation desc", limit_page_length=1000,
        ):
            _bookings_by_space.setdefault(bk.transport_space, []).append(bk)

    need_filter = event_filters(cols("RN Logistic Need"), event) if event else {}
    needs = frappe.get_all(
        "RN Logistic Need", filters=need_filter,
        fields=["name", "item_name", "quantity", "unit", "urgency",
                "need_status", "posko"],
        limit_page_length=500,
    )

    offer_filter = event_filters(cols("RN Aid Offer"), event) if event else {}
    offers = frappe.get_all(
        "RN Aid Offer", filters=offer_filter,
        fields=["name", "item_name", "quantity", "unit", "offer_status",
                "handling_mode", "target_posko", "observed_at"],
        limit_page_length=500,
    )

    posko_names = (
        {f.source_posko for f in flows} | {f.destination_posko for f in flows}
        | {n.posko for n in needs} | {o.target_posko for o in offers}
        | {t.get("coordination_posko") for t in transports}
    )
    posko_titles = _distribusi_posko_titles(posko_names)

    matched_need_ids = {f.logistic_need for f in flows if f.logistic_need}
    matched_offer_ids = {f.aid_offer for f in flows if f.aid_offer}

    # ---- capacity utilisation (overall + per transport_type) ----
    UTILISED_STATES = {"reserved", "assigned", "in_transit", "arrived", "completed"}

    def _blocked_m3_for(t):
        """Booked (confirmed + requested) volume on this armada that is not yet
        reflected in transport_status — the mock-up's donut "Blocked" segment."""
        bks = _bookings_by_space.get(t.get("name"), [])
        return sum(_num(b.qty_volume_m3) for b in bks
                   if b.status in ("confirmed", "requested"))

    def _cap_bucket(rows):
        total_kg = sum(_num(t.capacity_weight_kg) for t in rows)
        used_kg = sum(_num(t.capacity_weight_kg) for t in rows if t.transport_status in UTILISED_STATES)
        pct = round(100.0 * used_kg / total_kg, 1) if total_kg else 0
        blocked_m3 = round(sum(_blocked_m3_for(t) for t in rows), 1)
        terpakai_m3 = round(sum(_num(t.capacity_volume_m3) for t in rows
                                if t.transport_status in UTILISED_STATES), 1)
        total_m3 = round(sum(_num(t.capacity_volume_m3) for t in rows), 1)
        return {
            "tersedia_m3": round(max(0.0, sum(_num(t.capacity_volume_m3) for t in rows
                                      if t.transport_status == "available") - blocked_m3), 1),
            "terpakai_m3": terpakai_m3,
            "blocked_m3": blocked_m3,
            "total_m3": total_m3,
            "pct": pct,
            "units": [
                {
                    "provider": t.provider_name,
                    "capacity_m3": _num(t.capacity_volume_m3),
                    "route": (t.route_origin or "-") + " → " + (t.route_destination or "-"),
                    "status": t.transport_status,
                    "berangkat": t.get("departure_time") or "-",
                    "eta": t.get("eta") or "-",
                    "lokasi_serah_terima": t.get("handover_location") or "-",
                    "narahubung": t.get("handover_contact_person") or "-",
                    "kontak": t.get("handover_contact_phone") or "-",
                    "pct": round(100.0 * _num(t.capacity_weight_kg) /
                                  (_num(t.capacity_weight_kg) or 1), 0) if t.transport_status in UTILISED_STATES else 0,
                }
                for t in rows
            ],
        }

    overall_cap = _cap_bucket(transports)
    by_type = {
        ttype: _cap_bucket([t for t in transports if t.transport_type == ttype])
        for ttype in ("darat", "laut", "udara")
    }

    # ---- KPI totals ----
    urgent_terms = {"critical", "urgent", "high", "tinggi", "darurat"}
    open_needs = [n for n in needs if str(n.need_status or "open").lower() == "open"]
    unmatched_needs = [n for n in open_needs if n.name not in matched_need_ids]

    blocked_flows = [f for f in flows if str(f.flow_status or "").lower() in _DRILL_BLOCKED_FLOW]

    totals = {
        "transport_space_pct": overall_cap["pct"],
        "kapasitas_darat_pct": by_type["darat"]["pct"],
        "kapasitas_laut_pct": by_type["laut"]["pct"],
        "kapasitas_udara_pct": by_type["udara"]["pct"],
        "kebutuhan_belum_match": len(unmatched_needs),
        "distribusi_terhambat": len(blocked_flows),
    }

    def _drill(title, sub, href=None):
        return {"title": title, "sub": sub, "href": href}

    kpi_items = {
        "kebutuhan_items": [
            _drill(n.item_name, (posko_titles.get(n.posko) or "-") + f" · {_qty_fmt(n.quantity)} {n.unit or ''}".rstrip(),
                   "posko-logistik.html?id=" + (n.posko or "") + "&event=" + (event or ""))
            for n in sorted(unmatched_needs, key=lambda r: 0 if str(r.urgency).lower() in urgent_terms else 1)[:30]
        ],
        "terhambat_items": [
            _drill(f.item_name or f.name, _DISTRIBUSI_STATUS_LABEL.get(f.flow_status, f.flow_status),
                   "posko-detail.html?id=" + (f.destination_posko or f.source_posko or "") + "&event=" + (event or ""))
            for f in blocked_flows[:30]
        ],
    }

    # ---- matching board (read-only 4 columns) ----
    unmatched_offers = [o for o in offers
                         if o.name not in matched_offer_ids
                         and str(o.offer_status or "").lower() not in _DRILL_DELIVERED_OFFER]

    pickup_volunteers = frappe.get_all(
        "RN Volunteer Assignment",
        filters={"assignment_type": "distribution"} if not event else
                 {"assignment_type": "distribution", "disaster_event": event},
        fields=["name", "volunteer", "posko", "task_title", "assignment_status"],
        limit_page_length=100,
    )
    vol_names = {v.volunteer for v in pickup_volunteers if v.volunteer}
    vol_titles = {}
    if vol_names:
        vol_titles = {
            r.name: r.volunteer_name
            for r in frappe.get_all("RN Volunteer Profile", filters={"name": ["in", list(vol_names)]},
                                     fields=["name", "volunteer_name"], limit_page_length=len(vol_names))
        }

    matching_board = {
        "kebutuhan": {
            "total": len(unmatched_needs),
            "items": [
                {"title": n.item_name, "sub": (posko_titles.get(n.posko) or "-") + f" · {_qty_fmt(n.quantity)} {n.unit or ''}".rstrip(),
                 "urgency": n.urgency,
                 "href": "posko-logistik.html?id=" + (n.posko or "") + "&event=" + (event or "")}
                for n in unmatched_needs[:6]
            ],
        },
        "bantuan": {
            "total": len(unmatched_offers),
            "items": [
                {"title": o.item_name, "sub": f"{_qty_fmt(o.quantity)} {o.unit or ''} · " + (posko_titles.get(o.target_posko) or "-"),
                 "status": o.offer_status,
                 "href": "posko-logistik.html?id=" + (o.target_posko or "") + "&event=" + (event or "")}
                for o in unmatched_offers[:6]
            ],
        },
        "relawan_pickup": {
            "total": len(pickup_volunteers),
            "items": [
                {"title": vol_titles.get(v.volunteer, v.volunteer), "sub": v.task_title,
                 "href": None}
                for v in pickup_volunteers[:6]
            ],
        },
        "transportasi": {
            "total": sum(1 for t in transports if t.transport_status == "available"),
            "items": [
                {"title": t.get("provider_name"),
                 "sub": (t.get("transport_type") or "-") + " · "
                        + (t.get("current_location") or t.get("route_origin") or "-")
                        + (" · ☎ " + t.get("handover_contact_phone") if t.get("handover_contact_phone") else ""),
                 "href": ("posko-detail.html?id=" + t.get("coordination_posko") + "&event=" + (event or ""))
                         if t.get("coordination_posko") else None}
                for t in transports if t.get("transport_status") == "available"
            ][:6],
        },
    }

    today = frappe.utils.getdate()
    matched_today = sum(
        1 for f in flows
        if f.dispatched_at and frappe.utils.getdate(f.dispatched_at) == today
    )

    # ---- Alur Distribusi (live shipment table) ----
    alur_distribusi = []
    for f in flows[:40]:
        alur_distribusi.append({
            "id": f.name,
            "kebutuhan": (posko_titles.get(f.destination_posko) or "-") + f" · {_qty_fmt(f.quantity)} {f.unit or ''}".rstrip(),
            "bantuan": f.item_name or "-",
            "pickup_oleh": f.transport_provider or posko_titles.get(f.source_posko) or "-",
            "transportasi": (f.transport_type or "-"),
            "rute": (posko_titles.get(f.source_posko) or "-") + " → " + (posko_titles.get(f.destination_posko) or "-"),
            "eta": f.eta_final or "-",
            "status": f.flow_status,
            "status_label": _DISTRIBUSI_STATUS_LABEL.get(f.flow_status, f.flow_status or "-"),
            "trace": _distribusi_trace(f.name),
            "href": "posko-detail.html?id=" + (f.destination_posko or f.source_posko or "") + "&event=" + (event or ""),
        })

    # ---- Peringatan & Hambatan ----
    peringatan = []
    for f in blocked_flows[:10]:
        peringatan.append({
            "title": "Distribusi Terhambat — " + (f.item_name or f.name),
            "sub": _DISTRIBUSI_STATUS_LABEL.get(f.flow_status, f.flow_status) + " · " +
                   (posko_titles.get(f.source_posko) or "-") + " → " + (posko_titles.get(f.destination_posko) or "-"),
            "level": "critical",
            "href": "posko-detail.html?id=" + (f.destination_posko or f.source_posko or "") + "&event=" + (event or ""),
        })
    now = frappe.utils.now_datetime()
    for o in unmatched_offers:
        if o.observed_at and (now - o.observed_at).total_seconds() / 86400.0 >= 3:
            peringatan.append({
                "title": "Penumpukan Donasi — " + (o.item_name or o.name),
                "sub": f"Belum dijemput ≥3 hari di {posko_titles.get(o.target_posko) or '-'}",
                "level": "warning",
                "href": "posko-logistik.html?id=" + (o.target_posko or "") + "&event=" + (event or ""),
            })
    for ttype, label in (("darat", "Darat"), ("laut", "Laut"), ("udara", "Udara")):
        if by_type[ttype]["pct"] >= 90:
            peringatan.append({
                "title": f"Kapasitas {label} Hampir Penuh",
                "sub": f"{by_type[ttype]['pct']}% terpakai — pertimbangkan opsi tambahan.",
                "level": "warning",
                "href": None,
            })

    # ---- Armada Distribusi Posko — koordinasi penyerahan + booking ----
    _ARMADA_STATUS_LABEL = {
        "available": "Tersedia", "reserved": "Dipesan", "assigned": "Ditugaskan",
        "in_transit": "Dalam Perjalanan", "arrived": "Tiba",
        "completed": "Selesai", "cancelled": "Dibatalkan",
    }
    _SERVICE_MODE_LABEL = {
        "space_only": "Penyedia Space", "courier_pickup": "Kurir Jemput-Antar",
        "both": "Space + Kurir",
    }
    _BOOKING_STATUS_LABEL = {
        "requested": "Menunggu Konfirmasi", "confirmed": "Terkonfirmasi",
        "rejected": "Ditolak", "cancelled": "Dibatalkan", "completed": "Selesai",
    }
    _DELIVERY_LABEL = {
        "use_transporter": "Pakai transporter posko",
        "self_deliver": "Antar sendiri ke titik jemput",
    }

    def _fmt_dt(v):
        if not v:
            return ""
        s = str(v)
        return s[:16].replace("T", " ") if len(s) >= 16 else s

    armada_posko = []
    pickup_matches = []
    for t in sorted(
        transports,
        key=lambda r: str(r.get("departure_at") or r.get("observed_at") or ""),
        reverse=True,
    ):
        cap_kg = _num(t.get("capacity_weight_kg"))
        cap_m3 = _num(t.get("capacity_volume_m3"))
        bks = _bookings_by_space.get(t.get("name"), [])
        used_kg = sum(_num(b.qty_weight_kg) for b in bks if b.status == "confirmed")
        used_m3 = sum(_num(b.qty_volume_m3) for b in bks if b.status == "confirmed")
        held_kg = sum(_num(b.qty_weight_kg) for b in bks if b.status == "requested")
        held_m3 = sum(_num(b.qty_volume_m3) for b in bks if b.status == "requested")
        avail_kg = max(0.0, cap_kg - used_kg - held_kg)
        avail_m3 = max(0.0, cap_m3 - used_m3 - held_m3)
        pct_kg = round(100.0 * (used_kg + held_kg) / cap_kg) if cap_kg else 0

        cap_bits = []
        if cap_kg:
            cap_bits.append(f"{_qty_fmt(cap_kg)} kg")
        if cap_m3:
            cap_bits.append(f"{_qty_fmt(cap_m3)} m³")

        smode = t.get("service_mode") or "both"
        berangkat = _fmt_dt(t.get("departure_at")) or (t.get("departure_time") or "-")
        eta_v = _fmt_dt(t.get("eta_at")) or (t.get("eta") or "-")

        armada_posko.append({
            "id": t.get("name"),
            "provider": t.get("provider_name") or "-",
            "posko": posko_titles.get(t.get("coordination_posko")) or "-",
            "posko_id": t.get("coordination_posko") or "",
            "jenis": t.get("transport_type") or "-",
            "service_mode": smode,
            "service_mode_label": _SERVICE_MODE_LABEL.get(smode, smode),
            "booking_policy": t.get("booking_policy") or "pin_verify",
            "kapasitas": " · ".join(cap_bits) or "-",
            "kapasitas_total_kg": cap_kg,
            "kapasitas_total_m3": cap_m3,
            "kapasitas_terpakai_kg": round(used_kg + held_kg, 1),
            "kapasitas_tersedia_kg": round(avail_kg, 1),
            "kapasitas_tersedia_m3": round(avail_m3, 1),
            "kapasitas_pct": pct_kg,
            "lokasi_saat_ini": t.get("current_location") or "-",
            "rute": (t.get("route_origin") or "-") + " → " + (t.get("route_destination") or "-"),
            "berangkat": berangkat,
            "eta": eta_v,
            "lokasi_serah_terima": t.get("handover_location") or "-",
            "narahubung": t.get("handover_contact_person") or "-",
            "kontak": t.get("handover_contact_phone") or "-",
            "catatan": t.get("coordination_notes") or "",
            "status": t.get("transport_status") or "-",
            "status_label": _ARMADA_STATUS_LABEL.get(t.get("transport_status"), t.get("transport_status") or "-"),
            "pickup_volunteer": t.get("pickup_volunteer") or "",
            "pickup_volunteer_name": t.get("pickup_volunteer_name") or "",
            # transporter-side follow-up contact (for the coordinating posko)
            "transporter_contact_person": t.get("handover_contact_person") or "",
            "transporter_contact_phone": t.get("handover_contact_phone") or "",
            "bookings_count": sum(1 for b in bks if b.status in ("requested", "confirmed")),
            "bookings": [
                {
                    "id": b.name,
                    "cargo": b.cargo_desc or "-",
                    "qty": (f"{_qty_fmt(b.qty_weight_kg)} kg" if _num(b.qty_weight_kg) else "")
                           + ((" · " if _num(b.qty_weight_kg) and _num(b.qty_volume_m3) else "")
                              + (f"{_qty_fmt(b.qty_volume_m3)} m³" if _num(b.qty_volume_m3) else "")),
                    "status": b.status,
                    "status_label": _BOOKING_STATUS_LABEL.get(b.status, b.status),
                    "booker": b.booker_name or b.booked_by_type or "-",
                    "pickup": b.pickup_location or "",
                    "dropoff": b.dropoff_location or "",
                    "delivery_method": b.get("delivery_method") or "use_transporter",
                    "delivery_label": _DELIVERY_LABEL.get(b.get("delivery_method"), "Pakai transporter posko"),
                    "requested_window": b.get("requested_window") or "",
                    # supplier-side follow-up contact (for the coordinating posko)
                    "supplier_contact_person": b.contact_person or "",
                    "supplier_contact_phone": b.contact_phone or "",
                }
                for b in bks if b.status in ("requested", "confirmed")
            ],
            "href": "posko-detail.html?id=" + (t.get("coordination_posko") or "") + "&event=" + (event or ""),
        })

        # relawan-pickup matching: courier-capable armada with no volunteer yet
        if smode in ("courier_pickup", "both") and not t.get("pickup_volunteer"):
            cands = [
                {"name": vol_titles.get(v.volunteer, v.volunteer), "task": v.task_title or "Distribusi"}
                for v in pickup_volunteers
                if (not v.posko) or v.posko == t.get("coordination_posko")
            ][:5]
            open_need_here = sum(
                1 for n in unmatched_needs if n.posko == t.get("coordination_posko")
            )
            pickup_matches.append({
                "armada_id": t.get("name"),
                "armada": t.get("provider_name") or "-",
                "posko": posko_titles.get(t.get("coordination_posko")) or "-",
                "candidates": cands,
                "open_need_count": open_need_here,
                "href": "management-relawan.html?event=" + (event or ""),
            })

    return {
        "disaster_event": event,
        "generated_at": now,
        "totals": totals,
        "kpi_items": kpi_items,
        "matching_board": matching_board,
        "matched_today": matched_today,
        "ruang_transportasi": {"overall": overall_cap, "by_type": by_type},
        "armada_posko": armada_posko,
        "pickup_matches": pickup_matches,
        "alur_distribusi": alur_distribusi,
        "peringatan": peringatan,
        "conversions": _LOGISTIK_CONVERSIONS,
    }


_SERVICE_MODE_LABEL = {
    "space_only": "Penyedia Space", "courier_pickup": "Kurir Jemput-Antar",
    "both": "Space + Kurir",
}
_ARMADA_STATUS_LABEL = {
    "available": "Tersedia", "reserved": "Dipesan", "assigned": "Ditugaskan",
    "in_transit": "Dalam Perjalanan", "arrived": "Tiba",
    "completed": "Selesai", "cancelled": "Dibatalkan",
}
_BOOKING_STATUS_LABEL = {
    "requested": "Menunggu Konfirmasi", "confirmed": "Terkonfirmasi",
    "rejected": "Ditolak", "cancelled": "Dibatalkan", "completed": "Selesai",
}
_DELIVERY_LABEL = {
    "use_transporter": "Pakai transporter posko",
    "self_deliver": "Antar sendiri ke titik jemput",
}


@frappe.whitelist(allow_guest=True)
def posko_distribusi_board(posko=None, disaster_event=None):
    """Workspace for a Posko Distribusi (posko_type='transport') — the party
    that provides transport equipment + space: bisa Garuda, kapal TNI AL,
    motor pick-up, atau rombongan Land Rover club yang berangkat ke lokasi
    bencana. Lists the armada it registered (RN Transport Space), the booking
    inbox on those armada, capacity rollup, and relawan-pickup candidates.

    Separate from `distribusi_board` (that one stays the coordination
    dashboard matching the Manajemen Distribusi mock-up).
    """
    event = canonical_event(disaster_event) if disaster_event else None
    posko = _resolve_posko(posko) if posko else None

    posko_row = None
    if posko:
        posko_row = frappe.db.get_value(
            "RN Posko", posko,
            ["name", "title", "posko_type", "organization", "operational_status",
             "officer_in_charge_name", "emergency_contact", "city_name"],
            as_dict=True,
        )

    tfilter = {}
    if posko:
        tfilter["coordination_posko"] = posko
    elif event:
        tfilter = event_filters(cols("RN Transport Space"), event)

    transports = frappe.get_all(
        "RN Transport Space", filters=tfilter,
        fields=_sf("RN Transport Space", [
            "name", "provider_name", "transport_type", "transport_status",
            "capacity_weight_kg", "capacity_volume_m3", "route_origin",
            "route_destination", "coordination_posko", "disaster_event",
            "departure_time", "eta", "departure_at", "eta_at", "service_mode",
            "booking_policy", "current_location", "handover_location",
            "handover_contact_person", "handover_contact_phone",
            "coordination_notes", "pickup_volunteer", "pickup_volunteer_name",
        ]),
        order_by="modified desc", limit_page_length=200,
    )
    tnames = [t.name for t in transports]

    bookings = []
    if tnames and frappe.db.exists("DocType", "RN Transport Booking"):
        bookings = frappe.get_all(
            "RN Transport Booking",
            filters={"transport_space": ["in", tnames]},
            fields=_sf("RN Transport Booking", [
                "name", "transport_space", "cargo_desc", "qty_weight_kg",
                "qty_volume_m3", "status", "booker_name", "booked_by_type",
                "pickup_location", "dropoff_location", "contact_person",
                "contact_phone", "verification_pin", "requested_at",
                "confirmed_at", "delivery_method", "requested_window",
                "logistic_need", "aid_offer",
            ]),
            order_by="creation desc", limit_page_length=1000,
        )
    bk_by_space = {}
    for b in bookings:
        bk_by_space.setdefault(b.transport_space, []).append(b)

    def _dt(v):
        s = str(v or "")
        return s[:16].replace("T", " ") if len(s) >= 16 else s

    armada = []
    tot_kg = tot_m3 = used_kg = used_m3 = 0.0
    for t in transports:
        cap_kg = _num(t.capacity_weight_kg)
        cap_m3 = _num(t.capacity_volume_m3)
        mine = bk_by_space.get(t.name, [])
        c_kg = sum(_num(b.qty_weight_kg) for b in mine if b.status == "confirmed")
        c_m3 = sum(_num(b.qty_volume_m3) for b in mine if b.status == "confirmed")
        h_kg = sum(_num(b.qty_weight_kg) for b in mine if b.status == "requested")
        h_m3 = sum(_num(b.qty_volume_m3) for b in mine if b.status == "requested")
        tot_kg += cap_kg
        tot_m3 += cap_m3
        used_kg += c_kg + h_kg
        used_m3 += c_m3 + h_m3
        smode = t.service_mode or "both"
        armada.append({
            "id": t.name,
            "provider": t.provider_name or "-",
            "jenis": t.transport_type or "-",
            "service_mode": smode,
            "service_mode_label": _SERVICE_MODE_LABEL.get(smode, smode),
            "booking_policy": t.booking_policy or "pin_verify",
            "status": t.transport_status or "-",
            "status_label": _ARMADA_STATUS_LABEL.get(t.transport_status, t.transport_status or "-"),
            "kapasitas_total_kg": cap_kg, "kapasitas_total_m3": cap_m3,
            "kapasitas_terpakai_kg": round(c_kg + h_kg, 1),
            "kapasitas_tersedia_kg": round(max(0.0, cap_kg - c_kg - h_kg), 1),
            "kapasitas_tersedia_m3": round(max(0.0, cap_m3 - c_m3 - h_m3), 1),
            "kapasitas_pct": round(100.0 * (c_kg + h_kg) / cap_kg) if cap_kg else 0,
            "berangkat": _dt(t.departure_at) or (t.departure_time or "-"),
            "eta": _dt(t.eta_at) or (t.eta or "-"),
            "current_location": t.current_location or "-",
            "rute": (t.route_origin or "-") + " → " + (t.route_destination or "-"),
            "handover_location": t.handover_location or "-",
            "handover_contact_person": t.handover_contact_person or "-",
            "handover_contact_phone": t.handover_contact_phone or "-",
            "coordination_notes": t.coordination_notes or "",
            "pickup_volunteer": t.pickup_volunteer or "",
            "pickup_volunteer_name": t.pickup_volunteer_name or "",
            "bookings_count": sum(1 for b in mine if b.status in ("requested", "confirmed")),
        })

    inbox = []
    for b in bookings:
        t = next((x for x in transports if x.name == b.transport_space), None)
        inbox.append({
            "id": b.name,
            "armada": (t.provider_name if t else b.transport_space),
            "armada_id": b.transport_space,
            "cargo": b.cargo_desc or "-",
            "qty_kg": _num(b.qty_weight_kg), "qty_m3": _num(b.qty_volume_m3),
            "status": b.status,
            "status_label": _BOOKING_STATUS_LABEL.get(b.status, b.status),
            "delivery_method": b.get("delivery_method") or "use_transporter",
            "delivery_label": _DELIVERY_LABEL.get(b.get("delivery_method"), "Pakai transporter posko"),
            "requested_window": b.get("requested_window") or "",
            "booker": b.booker_name or b.booked_by_type or "-",
            "supplier_contact_person": b.contact_person or "",
            "supplier_contact_phone": b.contact_phone or "",
            "pickup": b.pickup_location or "",
            "dropoff": b.dropoff_location or "",
            "verification_pin": b.verification_pin or "",
            "requested_at": _dt(b.requested_at),
        })

    # relawan pickup candidates (distribution assignments at this posko / event)
    va_filter = {"assignment_type": "distribution"}
    if event:
        va_filter["disaster_event"] = event
    vas = frappe.get_all(
        "RN Volunteer Assignment", filters=va_filter,
        fields=["name", "volunteer", "posko", "task_title", "assignment_status"],
        limit_page_length=200,
    )
    if posko:
        vas = [v for v in vas if (not v.posko) or v.posko == posko]
    vnames = {v.volunteer for v in vas if v.volunteer}
    vtitle = {}
    if vnames:
        vtitle = {r.name: r.volunteer_name for r in frappe.get_all(
            "RN Volunteer Profile", filters={"name": ["in", list(vnames)]},
            fields=["name", "volunteer_name"], limit_page_length=len(vnames))}
    relawan_candidates = [
        {"id": v.volunteer, "name": vtitle.get(v.volunteer, v.volunteer),
         "task": v.task_title or "Distribusi", "status": v.assignment_status}
        for v in vas if v.volunteer
    ]

    # other transporter poskos for the switcher
    tp_filter = {"posko_type": "transport"}
    if event:
        tp_rows = frappe.get_all(
            "RN Posko",
            or_filters={"disaster_event": event, "disaster_event_legacy_id": event},
            filters=tp_filter, fields=["name", "title", "city_name"],
            limit_page_length=200,
        )
    else:
        tp_rows = frappe.get_all("RN Posko", filters=tp_filter,
                                 fields=["name", "title", "city_name"], limit_page_length=200)

    # ---- aktif pickup vs pasif (hanya sediakan space) ----
    is_active_pickup = any(
        (t.service_mode or "both") in ("courier_pickup", "both") for t in transports
    )
    pickup_mode_label = "Pickup Aktif" if is_active_pickup else "Pasif — Hanya Sediakan Space"

    # ---- pickup queue: open aid offers needing pickup, not yet claimed ----
    pickup_queue = []
    dest_options = []
    if event:
        off_filter = event_filters(cols("RN Aid Offer"), event)
        offers_all = frappe.get_all(
            "RN Aid Offer", filters=off_filter,
            fields=_sf("RN Aid Offer", [
                "name", "item_name", "raw_item_text", "quantity", "unit",
                "offer_status", "handling_mode", "donor_name", "donor_contact",
                "pickup_location", "ready_at", "target_posko",
            ]),
            order_by="creation desc", limit_page_length=500,
        )
        flow_off_ids = set(frappe.get_all(
            "RN Distribution Flow",
            filters={"aid_offer": ["!=", ""], "flow_status": ["not in", ["cancelled", "rejected"]]},
            pluck="aid_offer",
        ))
        _OPEN_OFFER = {"", "available", "need_pickup", "pending", "self_reported"}
        for o in offers_all:
            st = str(o.offer_status or "").lower()
            if o.name in flow_off_ids:
                continue
            if st not in _OPEN_OFFER:
                continue
            if (o.handling_mode or "").lower() not in ("need_pickup", "", "active_booking") \
               and st != "need_pickup":
                continue
            pickup_queue.append({
                "aid_offer": o.name,
                "item": o.item_name or o.raw_item_text or "-",
                "quantity": o.quantity,
                "unit": o.unit or "",
                "donor": o.donor_name or "-",
                "donor_contact": o.donor_contact or "",
                "pickup_location": o.pickup_location or "-",
                "ready_at": o.ready_at or "-",
                "suggested_destination": o.target_posko or "",
            })

        dest_rows = frappe.get_all(
            "RN Posko",
            or_filters={"disaster_event": event, "disaster_event_legacy_id": event},
            fields=["name", "title", "posko_type", "city_name"],
            limit_page_length=300,
        )
        dest_options = [
            {"id": r.name, "title": r.title or r.name,
             "type": r.posko_type or "", "city": r.get("city_name") or ""}
            for r in dest_rows
            if (r.posko_type or "").lower() != "transport"
        ]

    return {
        "disaster_event": event,
        "generated_at": frappe.utils.now_datetime(),
        "posko": posko,
        "posko_info": posko_row,
        "is_transport_posko": bool(posko_row and (posko_row.get("posko_type") or "").lower() == "transport"),
        "is_active_pickup": is_active_pickup,
        "pickup_mode_label": pickup_mode_label,
        "totals": {
            "armada_count": len(armada),
            "kapasitas_total_kg": round(tot_kg, 1),
            "kapasitas_total_m3": round(tot_m3, 1),
            "kapasitas_terpakai_kg": round(used_kg, 1),
            "kapasitas_terpakai_m3": round(used_m3, 1),
            "kapasitas_tersedia_kg": round(max(0.0, tot_kg - used_kg), 1),
            "booking_menunggu": sum(1 for b in bookings if b.status == "requested"),
            "booking_terkonfirmasi": sum(1 for b in bookings if b.status == "confirmed"),
            "pickup_queue": len(pickup_queue),
        },
        "armada": armada,
        "booking_inbox": inbox,
        "pickup_queue": pickup_queue,
        "destination_options": dest_options,
        "relawan_candidates": relawan_candidates,
        "transporter_poskos": [
            {"id": r.name, "title": r.title, "city": r.get("city_name") or ""}
            for r in tp_rows
        ],
    }


@frappe.whitelist()
def auto_match_distribution(disaster_event=None, limit=5):
    """Real (if simple) auto-matcher for the mock-up's "Otomatis Cocokkan"
    button: pairs an open RN Logistic Need with an available RN Aid Offer of
    the same item (case-insensitive) and an available RN Transport Space,
    then creates an RN Distribution Flow linking all three. Requires login
    (any authenticated actor — this mirrors the other create_* endpoints'
    bar, there being no single posko to gate against here).
    """
    from rescue_net.access_policy import rn_actor
    import re

    rn_actor()  # login required; raises if guest

    event = canonical_event(disaster_event) if disaster_event else None
    limit = min(int(limit or 5), 20)

    need_filter = event_filters(cols("RN Logistic Need"), event) if event else {}
    needs = frappe.get_all(
        "RN Logistic Need", filters=dict(need_filter, need_status="open"),
        fields=["name", "item_name", "quantity", "unit", "urgency", "posko"],
        order_by="modified desc", limit_page_length=200,
    )

    offer_filter = event_filters(cols("RN Aid Offer"), event) if event else {}
    offers = frappe.get_all(
        "RN Aid Offer", filters=offer_filter,
        fields=["name", "item_name", "quantity", "unit", "offer_status", "target_posko"],
        order_by="modified desc", limit_page_length=200,
    )
    open_offers = [o for o in offers if str(o.offer_status or "").lower() in
                   {"available", "ready", "need_pickup"}]

    transport_filter = event_filters(cols("RN Transport Space"), event) if event else {}
    free_transports = frappe.get_all(
        "RN Transport Space", filters=dict(transport_filter, transport_status="available"),
        fields=["name", "provider_name", "transport_type"],
        limit_page_length=50,
    )

    already_matched_needs = {f.logistic_need for f in frappe.get_all(
        "RN Distribution Flow", filters={"logistic_need": ["is", "set"]},
        fields=["logistic_need"], limit_page_length=2000) if f.logistic_need}
    already_matched_offers = {f.aid_offer for f in frappe.get_all(
        "RN Distribution Flow", filters={"aid_offer": ["is", "set"]},
        fields=["aid_offer"], limit_page_length=2000) if f.aid_offer}

    def _norm(text):
        return re.sub(r"[^a-z0-9]+", "", str(text or "").lower())

    used_offers, used_transports = set(), set()
    created = []

    for n in needs:
        if len(created) >= limit:
            break
        if n.name in already_matched_needs:
            continue
        need_key = _norm(n.item_name)
        offer = next(
            (o for o in open_offers
             if o.name not in already_matched_offers and o.name not in used_offers
             and _norm(o.item_name) == need_key),
            None,
        )
        if not offer:
            continue
        transport = next(
            (t for t in free_transports if t.name not in used_transports), None,
        )
        if not transport:
            break

        flow = frappe.new_doc("RN Distribution Flow")
        flow.disaster_event = event
        flow.title = f"Auto-match: {n.item_name}"
        flow.item_name = n.item_name
        flow.quantity = min(_num(n.quantity), _num(offer.quantity)) or _num(n.quantity)
        flow.unit = n.unit or offer.unit
        flow.flow_status = "planned"
        flow.source_posko = offer.target_posko
        flow.destination_posko = n.posko
        flow.logistic_need = n.name
        flow.aid_offer = offer.name
        flow.transport_space = transport.name
        flow.transport_provider = transport.provider_name
        flow.transport_type = transport.transport_type
        flow.dispatched_at = frappe.utils.now_datetime()
        flow.verification_status = "self_reported"
        flow.insert(ignore_permissions=True)

        used_offers.add(offer.name)
        used_transports.add(transport.name)
        created.append({
            "flow": flow.name, "item_name": n.item_name,
            "need": n.name, "offer": offer.name, "transport": transport.name,
        })

    return {"matched": len(created), "flows": created}


# ============================================================
# Organisasi & Posko — pages/organisasi-posko.html
# ============================================================

_ORG_PENDING_TERMS = {"pending", "self_reported", "", None}
_POSKO_INACTIVE_TERMS = {"offline", "inactive", "closed", "non_aktif", "nonaktif"}


def _org_member_count(org_name):
    """Real member count: RN Organization Membership (formal, approved)
    union RN User Account.organization (looser but far more populated in
    the current seed data — most sim/community accounts never went through
    a formal Membership record)."""
    membership_users = set(frappe.get_all(
        "RN Organization Membership",
        filters={"organization": org_name, "status": "approved"},
        pluck="user_account",
    ))
    account_users = set(frappe.get_all(
        "RN User Account", filters={"organization": org_name}, pluck="name",
    ))
    return len(membership_users | account_users)


def _org_program_count(org_name):
    return frappe.db.count("RN Donor Program", {"owner_type": "organization", "owner_id": org_name})


@frappe.whitelist(allow_guest=True)
def org_posko_board(disaster_event=None):
    """Organisasi & Posko dashboard (matches the DMS mock-up), guest
    read-only. KPI totals + a tree (event -> organisasi -> posko) + a flat
    orgs list with real trust/member/program counts for the detail rail.
    """
    event = canonical_event(disaster_event) if disaster_event else None

    posko_filter = {"disaster_event": event} if event else {}
    poskos = frappe.get_all(
        "RN Posko", filters=posko_filter,
        fields=["name", "title", "organization", "posko_type", "operational_status", "verification_status"],
        limit_page_length=1000,
    )

    org_names = sorted({p.organization for p in poskos if p.organization})
    if not org_names and not event:
        org_names = frappe.get_all("RN Organization", pluck="name", limit_page_length=200)

    posko_by_org = {}
    for p in poskos:
        posko_by_org.setdefault(p.organization, []).append(p)

    orgs_raw = frappe.get_all(
        "RN Organization", filters={"name": ["in", org_names]} if org_names else {},
        fields=["name", "title", "organization_type", "verification_status",
                "trust_level", "trusted_verifier_count", "status", "modified"],
        limit_page_length=500,
    )

    orgs = []
    posko_aktif_total = 0
    pending_total = 0
    anggota_total = 0

    for o in orgs_raw:
        org_poskos = posko_by_org.get(o.name, [])
        posko_list = [
            {"name": p.name, "title": p.title, "posko_type": p.posko_type,
             "status": p.operational_status, "verification_status": p.verification_status,
             "href": "posko-detail.html?id=" + p.name + "&event=" + (event or "")}
            for p in org_poskos
        ]
        active_poskos = sum(1 for p in org_poskos if str(p.operational_status or "").lower() not in _POSKO_INACTIVE_TERMS)
        posko_aktif_total += active_poskos

        members = _org_member_count(o.name)
        anggota_total += members
        programs = _org_program_count(o.name)

        org_pending = str(o.verification_status or "") in _ORG_PENDING_TERMS
        posko_pending = sum(1 for p in org_poskos if str(p.verification_status or "") in _ORG_PENDING_TERMS)
        pending_total += posko_pending + (1 if org_pending else 0)

        orgs.append({
            "name": o.name, "title": o.title, "organization_type": o.organization_type,
            "verification_status": o.verification_status or "self_reported",
            "trust_level": o.trust_level or "unverified",
            "trusted_verifier_count": o.trusted_verifier_count or 0,
            "status": o.status or "active",
            "modified": o.modified,
            "posko_count": len(org_poskos), "posko_active_count": active_poskos,
            "member_count": members, "program_count": programs,
            "poskos": posko_list,
        })

    orgs.sort(key=lambda r: -r["posko_count"])

    return {
        "disaster_event": event,
        "generated_at": frappe.utils.now_datetime(),
        "totals": {
            "organisasi_aktif": sum(1 for o in orgs if o["status"] == "active" or o["verification_status"] not in _ORG_PENDING_TERMS),
            "posko_aktif": posko_aktif_total,
            "pending_verifikasi": pending_total,
            "anggota_terdaftar": anggota_total,
        },
        "tree": {
            "event": event,
            "orgs": [{"name": o["name"], "title": o["title"], "posko_count": o["posko_count"],
                      "verification_status": o["verification_status"], "poskos": o["poskos"]}
                     for o in orgs],
        },
        "orgs": orgs,
    }


@frappe.whitelist(allow_guest=True)
def org_detail(organization):
    """Detail rail for one organisasi — real fields + poskos + a simple
    member list (best-effort: RN User Account rows with this organization,
    since RN Organization Membership is sparsely populated in the seed
    data) + real RN Donor Program rows."""
    org = frappe.db.get_value(
        "RN Organization", organization,
        ["name", "title", "organization_type", "verification_status", "trust_level",
         "trusted_verifier_count", "identity_verification_status", "contact_person",
         "notes", "modified"],
        as_dict=True,
    )
    if not org:
        frappe.throw("Organisasi tidak ditemukan")

    poskos = frappe.get_all(
        "RN Posko", filters={"organization": organization},
        fields=["name", "title", "posko_type", "operational_status", "verification_status"],
        limit_page_length=200,
    )

    members = frappe.get_all(
        "RN User Account", filters={"organization": organization},
        fields=["name", "title", "role", "status"], limit_page_length=200,
    )

    programs = frappe.get_all(
        "RN Donor Program", filters={"owner_type": "organization", "owner_id": organization},
        fields=["name", "program_name", "status", "target_amount", "current_amount", "target_unit"],
        limit_page_length=200,
    )

    checklist = {
        "identitas_organisasi": bool(org.get("verification_status") not in _ORG_PENDING_TERMS),
        "kontak_person": bool(org.get("contact_person")),
        "trusted_verifier": bool((org.get("trusted_verifier_count") or 0) > 0),
    }

    return {
        "org": org,
        "poskos": poskos,
        "members": members,
        "programs": programs,
        "checklist": checklist,
    }


# ============================================================
# Registrasi & Verifikasi Posko — pages/registrasi-posko.html (NEW)
# ============================================================

@frappe.whitelist(allow_guest=True)
def posko_verification_checklist(posko):
    """Real checklist for the mock-up's "Status Verifikasi Posko" panel —
    every item is a literal field-filled check, not a fabricated status."""
    doc = frappe.db.get_value(
        "RN Posko", posko,
        ["name", "officer_in_charge_email", "officer_in_charge_phone",
         "officer_in_charge_name", "latitude", "longitude",
         "trusted_verifier_count", "verification_status"],
        as_dict=True,
    )
    if not doc:
        frappe.throw("Posko tidak ditemukan")

    items = [
        {"key": "email", "label": "Email", "value": doc.officer_in_charge_email,
         "done": bool(doc.officer_in_charge_email)},
        {"key": "phone", "label": "Nomor HP", "value": doc.officer_in_charge_phone,
         "done": bool(doc.officer_in_charge_phone)},
        {"key": "pic", "label": "Identitas PIC", "value": doc.officer_in_charge_name,
         "done": bool(doc.officer_in_charge_name)},
        {"key": "location", "label": "Lokasi Posko",
         "value": (f"{doc.latitude}, {doc.longitude}" if doc.latitude and doc.longitude else None),
         "done": bool(doc.latitude and doc.longitude)},
        {"key": "trusted_verifier", "label": "Trusted Verifier",
         "value": doc.trusted_verifier_count, "done": bool((doc.trusted_verifier_count or 0) > 0)},
    ]

    return {
        "posko": doc.name,
        "verification_status": doc.verification_status or "self_reported",
        "items": items,
        "ready_to_submit": all(i["done"] for i in items[:4]),  # trusted_verifier comes after submission
    }


@frappe.whitelist(allow_guest=True)
def posko_registry_board(disaster_event=None, limit=200):
    """KPI totals + Daftar Posko table for the mock-up, guest read-only."""
    event = canonical_event(disaster_event) if disaster_event else None
    filters = {"disaster_event": event} if event else {}

    rows = frappe.get_all(
        "RN Posko", filters=filters,
        fields=["name", "title", "posko_type", "address", "city_name",
                "officer_in_charge_name", "rn_beneficiary_count",
                "verification_status", "trusted_verifier_count",
                "operational_status", "modified"],
        order_by="modified desc", limit_page_length=int(limit),
    )

    def _cap(r):
        try:
            return int(r.get("rn_beneficiary_count") or 0)
        except (TypeError, ValueError):
            return 0

    posko_list = [{
        "name": r.name, "title": r.title, "jenis": r.posko_type,
        "lokasi": r.city_name or r.address or "-",
        "pic": r.officer_in_charge_name or "-",
        "kapasitas": _cap(r),
        "status_verifikasi": r.verification_status or "self_reported",
        "trusted_verifier_count": r.trusted_verifier_count or 0,
        "terakhir_diperbarui": r.modified,
        "href": "registrasi-posko.html?id=" + r.name + "&event=" + (event or ""),
    } for r in rows]

    verif_counts = {"pending": 0, "official_verified": 0, "community_verified": 0}
    for r in rows:
        v = str(r.verification_status or "self_reported").lower()
        if v in ("pending", "self_reported", "", "needs_correction"):
            verif_counts["pending"] += 1
        elif v == "community_verified":
            verif_counts["community_verified"] += 1
        elif v in ("official_verified", "verified"):
            verif_counts["official_verified"] += 1

    return {
        "disaster_event": event,
        "generated_at": frappe.utils.now_datetime(),
        "totals": {
            "posko_aktif": sum(1 for r in rows if str(r.operational_status or "").lower() not in _POSKO_INACTIVE_TERMS),
            "pending_verification": verif_counts["pending"],
            "official_verified": verif_counts["official_verified"],
            "community_verified": verif_counts["community_verified"],
        },
        "poskos": posko_list,
    }


# ---------------------------------------------------------------------------
# Koordinasi Internal Organisasi
#
# A logged-in organisation member (e.g. someone in "Komunitas Landrover")
# is a contributor to his OWN posko and a viewer of everyone else's. This
# board gives him exactly that scope:
#   - my_posko            : his assigned posko, editable
#   - my_org_poskos       : the rest of his organisation's poskos, read-only
#   - open_external_poskos : other orgs' poskos that share full detail, read-only
# The complete cross-organisation picture stays on the Control Centre page.
# ---------------------------------------------------------------------------

_ORG_BRAND_ACCENT = {
    "SIM-LR-ORG": "#2f6f3e",              # Komunitas Landrover — green
    "organizations:org-landrover": "#2f6f3e",
}


def _org_brand(org):
    """Light per-organisation skin for the internal-coordination view.

    Prefers the org's own `brand_color` / `brand_logo` (editable in Desk);
    falls back to a small known-accent map, then to a deterministic hue
    derived from the org name — stable per org, never random.
    """
    if not org:
        return {"title": "Organisasi", "accent": "#3355aa", "initial": "?", "logo": None}

    name = org.get("name") or ""
    accent = (org.get("brand_color") or "").strip() or _ORG_BRAND_ACCENT.get(name)
    if not accent:
        h = 0
        for ch in name:
            h = (h * 31 + ord(ch)) & 0xFFFFFFFF
        accent = "hsl(%d, 45%%, 38%%)" % (h % 360)

    title = (org.get("title") or name or "Organisasi").replace("[SIMULASI] ", "").strip()
    return {
        "title": title,
        "accent": accent,
        "logo": (org.get("brand_logo") or "").strip() or None,
        "organization_type": org.get("organization_type") or "",
        "initial": (title[:1] or "?").upper(),
    }


_ORG_BRAND_FIELDS = [
    "name", "title", "organization_type", "control_centre_share",
    "privacy_mode", "allow_posko_public_choice", "brand_color", "brand_logo",
]


def _org_brand_row(org_name):
    if not org_name:
        return None
    try:
        return frappe.db.get_value(
            "RN Organization", org_name, _ORG_BRAND_FIELDS, as_dict=True
        )
    except Exception:
        # brand_* columns may not exist yet (pre-migrate) — degrade gracefully
        return frappe.db.get_value(
            "RN Organization", org_name,
            [f for f in _ORG_BRAND_FIELDS if not f.startswith("brand_")],
            as_dict=True,
        )


def _my_posko_names(actor):
    """Poskos the actor may manage: direct RN User Account.posko + approved
    RN Posko Assignment rows."""
    names = set()
    if actor.get("posko"):
        names.add(actor["posko"])
    try:
        for a in frappe.get_all(
            "RN Posko Assignment",
            filters={"user_account": actor.get("name"), "status": "approved"},
            fields=["posko"], limit_page_length=0,
        ):
            if a.get("posko"):
                names.add(a["posko"])
    except Exception:
        pass
    return names


@frappe.whitelist(allow_guest=True)
def posko_edit_scope(posko=None, disaster_event=None):
    """Tell a posko operational page how to scope itself for the viewer.

    Guests / non-members / System Managers / operators of the shown posko are
    left unrestricted (`can_edit_current: true`). A logged-in org member who
    does NOT manage the shown posko gets `can_edit_current: false` so the page
    hides its create/record forms and shows a read-only banner; `my_poskos` /
    `primary_posko` drive the "default to my own posko" redirect.
    """
    from rescue_net.access_policy import rn_actor, can_manage_posko, is_system_manager

    event = canonical_event(disaster_event) if disaster_event else None
    posko = _resolve_posko(posko) if posko else None

    out = {
        "logged_in": False,
        "is_org_member": False,
        "is_system_manager": False,
        "current_posko": posko,
        "can_edit_current": True,
        "my_poskos": [],
        "primary_posko": None,
        "brand": None,
        "coordination_href": "koordinasi-organisasi.html?event=" + (event or ""),
        "control_centre_href": "war-room.html?event=" + (event or ""),
    }

    actor = rn_actor(required=False)
    if not actor:
        return out
    out["logged_in"] = True

    if actor.get("role") == "system_manager" or is_system_manager():
        out["is_system_manager"] = True
        return out

    org_name = actor.get("organization")
    out["is_org_member"] = bool(org_name)
    if not org_name:
        return out  # logged-in donor / volunteer etc. — not scoped here

    out["brand"] = _org_brand(_org_brand_row(org_name))

    names = _my_posko_names(actor)
    if names:
        rows = frappe.get_all(
            "RN Posko", filters={"name": ["in", list(names)]},
            fields=["name", "title", "posko_type", "disaster_event"],
            limit_page_length=50,
        )
        out["my_poskos"] = [{
            "name": r.name,
            "title": (r.title or "").replace("[SIMULASI] ", "").strip(),
            "posko_type": r.posko_type,
            "operate_href": _operate_href(r, event),
        } for r in rows]
    out["primary_posko"] = actor.get("posko") or (
        out["my_poskos"][0]["name"] if out["my_poskos"] else None
    )

    if posko:
        out["can_edit_current"] = bool(can_manage_posko(actor, posko))

    return out


def _operate_href(posko_row, event):
    """Route a posko to its operational workspace by type."""
    pid = posko_row.get("name")
    ev = event or posko_row.get("disaster_event") or ""
    ptype = str(posko_row.get("posko_type") or "").lower()
    page = {
        "logistics": "posko-logistik.html",
        "collection_hub": "posko-logistik.html",
        "transport": "posko-distribusi.html",
        "medical": "posko-medis-detail.html",
        "shelter": "shelter-detail.html",
        "kitchen": "dapur-umum.html",
    }.get(ptype, "posko-detail.html")
    return page + "?id=" + pid + "&event=" + ev


@frappe.whitelist(allow_guest=True)
def my_org_coordination(disaster_event=None):
    """Internal-organisation coordination board for a logged-in org member."""
    from urllib.parse import quote as _urlquote

    from rescue_net.access_policy import rn_actor, can_manage_posko
    from rescue_net.visibility import effective_posko_share

    event = canonical_event(disaster_event) if disaster_event else None
    cc_href = "war-room.html?event=" + (event or "")

    actor = rn_actor(required=False)
    if not actor or not actor.get("name"):
        return {
            "logged_in": bool(actor),
            "is_org_member": False,
            "disaster_event": event,
            "control_centre_href": cc_href,
            "login_href": "auth.html?next=" + _urlquote(
                "koordinasi-organisasi.html" + (("?event=" + event) if event else "")
            ),
        }

    org_name = actor.get("organization")
    my_posko_name = actor.get("posko")

    org = _org_brand_row(org_name) if org_name else None

    posko_fields = ["name", "title", "organization", "posko_type",
                    "operational_status", "city_name", "disaster_event",
                    "public_detail", "verification_status", "trusted_verifier_count"]

    def _card(p, can_edit):
        share = effective_posko_share(p.get("name"), actor)
        return {
            "name": p.get("name"),
            "title": (p.get("title") or "").replace("[SIMULASI] ", "").strip(),
            "posko_type": p.get("posko_type"),
            "operational_status": p.get("operational_status") or "normal",
            "organization": p.get("organization"),
            "city_name": p.get("city_name") or "-",
            "disaster_event": p.get("disaster_event"),
            "verification_status": p.get("verification_status") or "self_reported",
            "trusted_verifier_count": p.get("trusted_verifier_count") or 0,
            "share_mode": share["mode"],
            "share_reason": share["reason"],
            "can_edit": bool(can_edit),
            "detail_href": "posko-detail.html?id=" + p.get("name")
                           + "&event=" + (event or p.get("disaster_event") or ""),
            "operate_href": _operate_href(p, event),
        }

    # --- my organisation's poskos -----------------------------------------
    my_posko = None
    my_org_poskos = []
    if org_name:
        of = {"organization": org_name}
        if event:
            of["disaster_event"] = event
        rows = frappe.get_all("RN Posko", filters=of, fields=posko_fields,
                              order_by="title asc", limit_page_length=300)
        for p in rows:
            card = _card(p, can_manage_posko(actor, p.get("name")))
            if my_posko_name and p.get("name") == my_posko_name:
                my_posko = card
            else:
                my_org_poskos.append(card)

    # assigned posko might sit under another event / not match the filter
    if my_posko is None and my_posko_name:
        p = frappe.db.get_value("RN Posko", my_posko_name,
                                posko_fields, as_dict=True)
        if p:
            my_posko = _card(p, can_manage_posko(actor, my_posko_name))

    # --- other orgs' poskos that share full detail -----------------------
    ef = {"disaster_event": event} if event else {}
    ext_rows = frappe.get_all("RN Posko", filters=ef, fields=posko_fields,
                              limit_page_length=800)
    open_external = []
    for p in ext_rows:
        if org_name and p.get("organization") == org_name:
            continue
        if p.get("name") == my_posko_name:
            continue
        if effective_posko_share(p.get("name"), actor)["mode"] != "full":
            continue
        open_external.append(_card(p, False))
    open_external.sort(key=lambda c: (c["organization"] or "", c["title"] or ""))

    org_count = len(my_org_poskos) + (1 if my_posko else 0)
    return {
        "logged_in": True,
        "is_org_member": bool(org_name),
        "disaster_event": event,
        "generated_at": frappe.utils.now_datetime(),
        "actor": {
            "user_account": actor.get("name"),
            "role": actor.get("role"),
            "organization": org_name,
            "posko": my_posko_name,
        },
        "organization": org,
        "brand": _org_brand(org),
        "my_posko": my_posko,
        "my_org_poskos": my_org_poskos,
        "open_external_poskos": open_external,
        "totals": {
            "org_posko_count": org_count,
            "open_external_count": len(open_external),
            "editable_count": (1 if (my_posko and my_posko["can_edit"]) else 0)
                              + sum(1 for c in my_org_poskos if c["can_edit"]),
        },
        "control_centre_href": cc_href,
    }
