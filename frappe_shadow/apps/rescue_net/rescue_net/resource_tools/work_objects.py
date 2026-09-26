"""Resource tools — field conditions (work objects) -> tool estimates -> tool requests."""

import math
from collections import defaultdict

import frappe
from frappe.rate_limiter import rate_limit
from rescue_net.reference_resolver import resolve_disaster_event, resolve_posko
from rescue_net.intelligence.normalization import normalize_unit
# classify_text via the registry so the live "Kelompok Alat" fallback honours
# the editable RN Normalization Rule records, same as the record-insert hooks.
from rescue_net.intelligence.normalization_registry import classify_text
from frappe.utils import (
    cint,
    flt,
    get_datetime,
    now_datetime,
    nowdate,
    time_diff_in_hours,
)

from rescue_net.services import tool_needs
from rescue_net.access_policy import (
    can_manage_organization,
    can_manage_posko,
    is_system_manager,
    rn_actor,
)

from rescue_net.resource_tools.common import (  # noqa: F401
    _OBJECT_TYPE_LABELS,
    _OPEN_REQUEST,
    _actor_name,
    _assert_reference_access,
    _is_manager,
)


def _predict_equipment(object_type, size_value, ready_by_category, work_days=None, requested_by_category=None):
    """Field condition -> tools (services/tool_needs.py), with what is ready
    and what is already requested next to each estimate."""
    requested_by_category = requested_by_category or {}
    out = []
    for e in tool_needs.estimate(object_type, size_value, work_days):
        ready = ready_by_category.get(e["category"], 0)
        requested = requested_by_category.get(e["category"], 0)
        out.append({
            **e,
            "ready_available": ready,
            "gap": max(0, e["predicted_qty"] - ready),
            "requested": requested,
            "to_request": max(0, e["predicted_qty"] - requested),
        })
    return out


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def work_objects_board(disaster_event=None):
    """Object Kerja & Prediksi Kebutuhan Alat — real reported incident/damage
    objects (longsoran/jembatan putus/puing berat/...) with a heuristic
    equipment-need prediction per object, cross-referenced against real
    ready-available counts per category (same categories as tools_board's
    Inventari Alat per Kategori) so a gap is visible immediately.
    """
    event = resolve_disaster_event(disaster_event)
    filters = {"disaster_event": event} if event else {}

    objects = frappe.get_all(
        "RN Work Object",
        filters=filters,
        fields=[
            "name", "title", "object_type", "location", "size_value",
            "size_unit", "status", "reported_by", "notes", "observed_at",
            "work_days_target", "posko",
        ],
        order_by="creation desc",
        limit_page_length=200,
    )

    resources = frappe.get_all(
        "RN Resource Profile",
        filters=filters,
        fields=["category", "availability_status", "quantity"],
        limit_page_length=2000,
    )
    ready_by_category = defaultdict(float)
    for r in resources:
        if r.availability_status == "available":
            # a profile may hold several units (3 ekskavator, 300 kantong)
            ready_by_category[r.category] += flt(r.quantity) or 1

    requested = defaultdict(lambda: defaultdict(float))
    if objects:
        for q in frappe.get_all(
            "RN Work Tool Request",
            filters={"work_object": ["in", [o.name for o in objects]], "request_status": ["in", _OPEN_REQUEST]},
            fields=["work_object", "tool_type", "quantity"],
            limit_page_length=5000,
        ):
            requested[q.work_object][q.tool_type] += flt(q.quantity)

    rows = []
    for o in objects:
        predictions = _predict_equipment(o.object_type, o.size_value, ready_by_category,
                                         o.work_days_target, requested.get(o.name))
        rows.append({
            "name": o.name,
            "title": o.title,
            "object_type": o.object_type,
            "object_type_label": _OBJECT_TYPE_LABELS.get(o.object_type, o.object_type),
            "location": o.location,
            "size_value": o.size_value,
            "size_unit": o.size_unit,
            "status": o.status,
            "reported_by": o.reported_by,
            "notes": o.notes,
            "observed_at": o.observed_at,
            "work_days_target": o.work_days_target,
            "posko": o.posko,
            "predictions": predictions,
            "total_gap": sum(p["gap"] for p in predictions),
            "to_request": sum(p["to_request"] for p in predictions),
        })

    return {
        "disaster_event": event,
        "generated_at": now_datetime(),
        "objects": rows,
        "open_count": sum(1 for r in rows if r["status"] == "open"),
        "conditions": tool_needs.condition_catalog(),
        "method_note": (
            "Perkiraan alat dihitung dari kondisi fisik lapangan dan target hari "
            "kerja dengan aturan lapangan yang ditampilkan di setiap angka (bukan "
            "perhitungan teknik/rekayasa resmi) — titik awal perencanaan, bukan "
            "keputusan akhir."
        ),
    }


@frappe.whitelist()
def create_work_object(
    title,
    object_type,
    size_value,
    size_unit=None,
    location=None,
    notes=None,
    disaster_event=None,
    work_days_target=None,
    posko=None,
):
    disaster_event = resolve_disaster_event(disaster_event)
    actor = rn_actor()
    if object_type not in tool_needs.CONDITIONS:
        frappe.throw("Jenis kondisi lapangan tidak valid")
    if flt(size_value) < 0:
        frappe.throw("Ukuran fisik tidak boleh negatif")
    if posko:
        posko = resolve_posko(posko)
        if not (is_system_manager() or can_manage_posko(actor, posko)):
            frappe.throw("Hanya operator posko itu yang dapat mencatat kondisi atas nama posko.",
                         frappe.PermissionError)
        disaster_event = disaster_event or frappe.db.get_value("RN Posko", posko, "disaster_event")

    doc = frappe.new_doc("RN Work Object")
    doc.disaster_event = disaster_event
    doc.title = title
    doc.object_type = object_type
    doc.size_value = flt(size_value)
    doc.size_unit = size_unit or tool_needs.CONDITIONS[object_type]["unit"]
    doc.work_days_target = cint(work_days_target) or tool_needs.CONDITIONS[object_type]["default_days"]
    doc.posko = posko
    doc.location = location
    doc.status = "open"
    doc.reported_by = _actor_name(actor) or "Guest"
    doc.notes = notes
    doc.verification_status = "self_reported"
    doc.insert(ignore_permissions=True)

    return {
        "work_object": doc.name,
        "predictions": _predict_equipment(doc.object_type, doc.size_value, {}, doc.work_days_target),
    }


@frappe.whitelist(methods=["POST"])
def create_requests_from_work_object(work_object, priority=None):
    """Estimate -> kebutuhan: one RN Work Tool Request per tool the estimate
    still lacks (predicted minus what is already requested for this
    condition), linked back to the work object. Management (matching,
    deployment) then works on those requests."""
    actor = rn_actor()
    doc = frappe.get_doc("RN Work Object", work_object)
    requested_by_type, requested_by_id = ("posko", doc.posko) if doc.posko else ("other", None)
    if not _is_manager(actor) and not (doc.posko and can_manage_posko(actor, doc.posko)):
        frappe.throw("Hak operator diperlukan", frappe.PermissionError)
    _assert_reference_access(actor, requested_by_type, requested_by_id)
    if doc.status == "resolved":
        frappe.throw("Kondisi ini sudah selesai ditangani.")

    already = defaultdict(float)
    for q in frappe.get_all("RN Work Tool Request",
                            filters={"work_object": doc.name, "request_status": ["in", _OPEN_REQUEST]},
                            fields=["tool_type", "quantity"]):
        already[q.tool_type] += flt(q.quantity)

    priority = priority if priority in ("normal", "urgent", "critical") else "urgent"
    created = []
    for e in tool_needs.estimate(doc.object_type, doc.size_value, doc.work_days_target):
        qty = e["predicted_qty"] - already.get(e["category"], 0)
        if qty <= 0:
            continue
        days = f", {e['work_days']} hari kerja" if e["work_days"] else ""
        req = frappe.new_doc("RN Work Tool Request")
        req.disaster_event = doc.disaster_event
        req.requested_by_type = requested_by_type
        req.requested_by_id = requested_by_id
        req.tool_name = e["label"]
        req.tool_type = e["category"]
        req.quantity = qty
        req.unit = e["unit"]
        req.location = doc.location
        req.needed_for = f"{doc.title} — {_OBJECT_TYPE_LABELS.get(doc.object_type)} {flt(doc.size_value):g} " \
                         f"{doc.size_unit or ''}{days}. Dasar: {e['basis']}"
        req.work_object = doc.name
        req.priority = priority
        req.request_status = "requested"
        req.created_by_user = _actor_name(actor)
        req.verification_status = "self_reported"
        req.insert(ignore_permissions=True)
        created.append({"work_tool_request": req.name, "tool_type": e["category"], "quantity": qty,
                        "unit": e["unit"], "work_days": e["work_days"]})
    if created and doc.status == "open":
        frappe.db.set_value("RN Work Object", doc.name, "status", "in_progress")
    return {"work_object": doc.name, "created": created,
            "message": f"{len(created)} kebutuhan alat dibuat." if created
            else "Semua alat dari perkiraan ini sudah diminta."}


@frappe.whitelist()
def update_work_object_status(work_object, status):
    actor = rn_actor()

    if not _is_manager(actor):
        frappe.throw("Hak operator diperlukan", frappe.PermissionError)

    if status not in ("open", "in_progress", "resolved"):
        frappe.throw("Status tidak valid")

    doc = frappe.get_doc("RN Work Object", work_object)
    doc.status = status
    doc.save(ignore_permissions=True)

    return {"work_object": doc.name, "status": doc.status}
