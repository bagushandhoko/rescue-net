"""Frontend bridge — community reports list, status, conversion, submit."""

import base64
import math
import uuid
from collections import defaultdict

import frappe
from frappe.utils import flt, now_datetime
from frappe.utils.file_manager import save_file

from rescue_net.access_policy import (
    can_edit_event,
    editable_disaster_events,
    is_system_manager,
    rn_actor,
)
from rescue_net.reference_resolver import (
    resolve_disaster_event,
    resolve_posko,
)

from rescue_net.frontend_bridge.common import (  # noqa: F401
    _actor,
    _canonical_event,
    _meta_fields,
    _safe_fields,
)


@frappe.whitelist(allow_guest=True)
def community_reports(
    disaster_event=None,
    status=None,
):
    rn_actor(required=False)

    event = (
        _canonical_event(disaster_event)
        if disaster_event
        else None
    )

    filters = {}

    if event:
        filters["disaster_event"] = event

    meta_fields = _meta_fields(
        "RN Community Report"
    )

    if (
        status
        and "status" in meta_fields
    ):
        filters["status"] = status

    fields = _safe_fields(
        "RN Community Report",
        [
            "name",
            "legacy_id",
            "title",
            "description",
            "report_type",
            "priority",
            "status",
            "verification_status",
            "disaster_event",
            "location_text",
            "latitude",
            "longitude",
            "affected_people_count",
            "urgent_needs",
            "damage_scale_value",
            "damage_scale_unit",
            "province_name",
            "city_name",
            "district_name",
            "village_name",
            "area_level",
            "consolidation_status",
            "trust_score",
            "posko",
            "routing_reason",
            "intake_mode",
            "intake_parser",
            "consent_to_contact",
            "reporter_name",
            "reporter_phone",
            "reporter_email",
            "creation",
            "modified",
        ],
    )

    rows = frappe.get_all(
        "RN Community Report",
        filters=filters,
        fields=fields,
        order_by="creation desc",
        limit_page_length=3000,
    )

    from rescue_net.api_reports import predict_report_needs

    routed = {r.get("posko") for r in rows if r.get("posko")}
    posko_titles = dict(frappe.get_all(
        "RN Posko", filters={"name": ["in", list(routed)]},
        fields=["name", "title"], as_list=True,
    )) if routed else {}

    result = []

    for row in rows:
        item = dict(row)

        item["id"] = (
            item.get("legacy_id")
            or item["name"]
        )

        item["created_at"] = (
            item.get("creation")
        )

        item["updated_at"] = (
            item.get("modified")
        )

        item["predicted_needs"] = predict_report_needs(
            item.get("report_type"),
            item.get("damage_scale_value"),
            item.get("affected_people_count"),
        )

        item["posko_title"] = (
            posko_titles.get(item.get("posko"))
            if item.get("posko") else None
        )

        result.append(item)

    return result


@frappe.whitelist()
def set_community_report_status(
    report,
    status,
):
    _actor()

    if not frappe.db.exists(
        "RN Community Report",
        report,
    ):
        report = frappe.db.get_value(
            "RN Community Report",
            {"legacy_id": report},
            "name",
        )

    if not report:
        frappe.throw(
            "Community Report tidak ditemukan"
        )

    meta_fields = _meta_fields(
        "RN Community Report"
    )

    if "status" not in meta_fields:
        frappe.throw(
            "RN Community Report tidak memiliki field status"
        )

    doc = frappe.get_doc(
        "RN Community Report",
        report,
    )

    doc.status = status
    doc.save(ignore_permissions=True)

    return {
        "id": doc.name,
        "status": doc.status,
    }


@frappe.whitelist()
def convert_community_report(
    report,
):
    _actor()

    if not frappe.db.exists(
        "RN Community Report",
        report,
    ):
        report = frappe.db.get_value(
            "RN Community Report",
            {"legacy_id": report},
            "name",
        )

    if not report:
        frappe.throw(
            "Community Report tidak ditemukan"
        )

    existing = frappe.db.get_value(
        "RN Community Need",
        {"source_report": report},
        "name",
    )

    if existing:
        return {
            "report": report,
            "community_need": existing,
            "created": False,
        }

    source = frappe.get_doc(
        "RN Community Report",
        report,
    )

    need = frappe.new_doc(
        "RN Community Need"
    )

    fields = _meta_fields(
        "RN Community Need"
    )

    def set_if(field, value):
        if (
            field in fields
            and value not in (None, "")
        ):
            need.set(field, value)

    set_if(
        "source_report",
        source.name,
    )

    set_if(
        "disaster_event",
        getattr(
            source,
            "disaster_event",
            None,
        ),
    )

    set_if(
        "title",
        "Kebutuhan - "
        + (
            getattr(
                source,
                "title",
                None,
            )
            or source.name
        ),
    )

    set_if(
        "need_type",
        getattr(
            source,
            "report_type",
            None,
        )
        or "community_report",
    )

    set_if(
        "description",
        getattr(
            source,
            "urgent_needs",
            None,
        )
        or getattr(
            source,
            "description",
            None,
        ),
    )

    set_if(
        "urgency",
        getattr(
            source,
            "priority",
            None,
        )
        or "normal",
    )

    set_if(
        "status",
        "open",
    )

    set_if(
        "verification_status",
        getattr(
            source,
            "verification_status",
            None,
        )
        or "unverified",
    )

    need.insert(
        ignore_permissions=True
    )

    return {
        "report": source.name,
        "community_need": need.name,
        "created": True,
    }


@frappe.whitelist()
def submit_community_report_bridge(
    title=None,
    description=None,
    report_type=None,
    priority=None,
    affected_people_count=0,
    urgent_needs=None,
    location_text=None,
    latitude=None,
    longitude=None,
    province_code=None,
    city_code=None,
    district_code=None,
    village_code=None,
    consent_to_contact=0,
    location_input_method=None,
    create_need=0,
    damage_scale_value=None,
    damage_scale_unit=None,
    disaster_event=None,
    intake_mode="form",
    intake_parser=None,
):
    _actor()

    from rescue_net.api_reports import (
        submit_community_report,
    )

    return submit_community_report(
        title=title,
        description=description,
        report_type=report_type,
        priority=priority,
        affected_people_count=affected_people_count,
        urgent_needs=urgent_needs,
        location_text=location_text,
        latitude=latitude,
        longitude=longitude,
        province_code=province_code,
        city_code=city_code,
        district_code=district_code,
        village_code=village_code,
        consent_to_contact=consent_to_contact,
        location_input_method=location_input_method,
        create_need=create_need,
        damage_scale_value=damage_scale_value,
        damage_scale_unit=damage_scale_unit,
        disaster_event=disaster_event,
        intake_mode=intake_mode,
        intake_parser=intake_parser,
    )
