"""AI — public (guest) context, active disasters and map context, scrubbed."""

import hashlib
import json

import frappe
from frappe.rate_limiter import rate_limit
from rescue_net.reference_resolver import resolve_disaster_event, resolve_posko
from frappe.utils import now_datetime

from rescue_net.access_policy import (
    can_manage_organization,
    is_system_manager,
    rn_actor,
)
from rescue_net.services import llm

from rescue_net.ai.context import (  # noqa: F401
    _build_context,
    _public_scrub,
)


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def public_context(disaster_event_id):
    ctx = _build_context(
        disaster_event_id,
        public=True,
    )

    result = _public_scrub(ctx)

    # ========================================================
    # Public Disaster identity
    # ========================================================
    # Context lama hanya membawa subset field.
    # Untuk Control Centre publik, enrich menggunakan
    # RN Disaster Event canonical, tetapi hanya field
    # operasional yang aman ditampilkan publik.
    disaster = result.get("disaster") or {}

    disaster_name = (
        disaster.get("name")
        or result.get("disaster_event_id")
    )

    if disaster_name:
        meta = frappe.get_meta(
            "RN Disaster Event"
        )

        candidates = [
            "title",
            "event_type",
            "disaster_type",
            "severity",
            "event_status",
            "status",
            "location_text",
            "location",
            "started_at",
            "start_time",
            "ended_at",
            "end_time",
            "description",
        ]

        fields = [
            field
            for field in candidates
            if meta.has_field(field)
        ]

        if fields:
            row = frappe.db.get_value(
                "RN Disaster Event",
                disaster_name,
                fields,
                as_dict=True,
            )

            if row:
                disaster.update(
                    dict(row)
                )

    # Canonical → compatibility aliases.
    #
    # Renderer Control Centre lama masih membaca
    # disaster_type/status/location.
    disaster["disaster_type"] = (
        disaster.get("disaster_type")
        or disaster.get("event_type")
        or "disaster"
    )

    disaster["status"] = (
        disaster.get("status")
        or disaster.get("event_status")
        or "active"
    )

    disaster["event_status"] = (
        disaster.get("event_status")
        or disaster.get("status")
    )

    disaster["location"] = (
        disaster.get("location")
        or disaster.get("location_text")
        or ""
    )

    disaster["location_text"] = (
        disaster.get("location_text")
        or disaster.get("location")
        or ""
    )

    disaster["title"] = (
        disaster.get("title")
        or disaster.get("name")
        or "Disaster Event"
    )

    result["disaster"] = disaster

    result["viewer_mode"] = "public"
    result["read_only"] = True

    return result


def _loads_json_safe(value):
    if not value:
        return None
    try:
        return json.loads(value)
    except Exception:
        return value


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def public_active_disasters():
    rows = frappe.get_all(
        "RN Disaster Event",
        filters={
            "event_status": "active"
        },
        fields=[
            "name",
            "legacy_id",
            "title",
            "severity",
            "event_status",
            "started_at",
        ],
        order_by="started_at desc",
        limit_page_length=100,
    )

    return [
        {
            "id":
                row.legacy_id
                or row.name,

            "name":
                row.name,

            "legacy_id":
                row.legacy_id,

            "title":
                row.title
                or row.name,

            "severity":
                row.severity,

            "status":
                row.event_status,

            "event_status":
                row.event_status,

            "started_at":
                row.started_at,
        }
        for row in rows
    ]


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def public_map_context(disaster_event_id):
    disaster_event_id = str(
        disaster_event_id or ""
    ).strip()

    if not disaster_event_id:
        frappe.throw(
            "disaster_event_id diperlukan"
        )

    if not disaster_event_id.startswith(
        "disaster_events:"
    ):
        canonical_event = (
            "disaster_events:"
            + disaster_event_id
        )
    else:
        canonical_event = disaster_event_id

    meta = frappe.get_meta(
        "RN Posko"
    )

    columns = set(
        meta.get_valid_columns()
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
        "disaster_event",
        "disaster_event_id",
    ]

    fields = [
        field
        for field in wanted
        if field == "name"
        or field in columns
    ]

    filters = {}

    if "disaster_event" in columns:
        filters["disaster_event"] = canonical_event
    elif "disaster_event_id" in columns:
        filters["disaster_event_id"] = canonical_event

    rows = frappe.get_all(
        "RN Posko",
        filters=filters,
        fields=fields,
        limit_page_length=500,
    )

    points = []

    for row in rows:
        row = dict(row)

        lat = (
            row.get("latitude")
            or row.get("lat")
        )

        lng = (
            row.get("longitude")
            or row.get("lng")
        )

        try:
            lat = float(lat)
            lng = float(lng)
        except (TypeError, ValueError):
            continue

        status = str(
            row.get("operational_status")
            or row.get("severity")
            or row.get("status")
            or "normal"
        ).lower()

        if status in {
            "critical",
            "overload",
            "danger",
            "emergency",
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

        points.append({
            "id":
                row.get("legacy_id")
                or row.get("name"),

            "name":
                row.get("title")
                or row.get("name"),

            "posko_type":
                row.get("posko_type"),

            "address":
                row.get("address"),

            "latitude":
                lat,

            "longitude":
                lng,

            "status":
                status,

            "situation":
                situation,

            "google_maps_url":
                "https://www.google.com/maps/search/"
                "?api=1&query="
                + str(lat)
                + ","
                + str(lng),
        })

    return {
        "disaster_event_id":
            canonical_event,

        "points":
            points,

        "summary": {
            "total":
                len(points),

            "critical":
                sum(
                    1
                    for p in points
                    if p["situation"]
                    == "critical"
                ),

            "warning":
                sum(
                    1
                    for p in points
                    if p["situation"]
                    == "warning"
                ),

            "safe":
                sum(
                    1
                    for p in points
                    if p["situation"]
                    == "safe"
                ),
        },
    }
