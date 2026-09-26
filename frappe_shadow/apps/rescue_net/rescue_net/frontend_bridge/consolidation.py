"""Frontend bridge — Sync Data Konsolidasi (summary, consolidated needs, duplicates, overrides)."""

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
    DUPLICATE_RADIUS_KM,
    _actor,
    _canonical_event,
    _meta_fields,
    _require_event_edit,
    _safe_fields,
)
from rescue_net.frontend_bridge.reports import (  # noqa: F401
    community_reports,
)


def _count_for_event(
    doctype,
    event,
):
    fields = _meta_fields(doctype)

    if "disaster_event" not in fields:
        return frappe.db.count(doctype)

    return frappe.db.count(
        doctype,
        {
            "disaster_event": event
        },
    )


@frappe.whitelist(allow_guest=True)
def consolidation_edit_scope(disaster_event=None):
    """Tells Sync Data Konsolidasi's frontend what to enable, instead of
    it inferring permission from a failed write. Guest → everything
    disabled. Logged in → enabled only for events their organisation
    actually operates in (or every event, for a System Manager)."""
    actor = rn_actor(required=False)
    event = _canonical_event(disaster_event) if disaster_event else None

    editable = editable_disaster_events(actor) if actor else set()

    return {
        "logged_in": bool(actor),
        "is_system_manager": bool(actor) and is_system_manager(),
        "editable_events": (
            None if editable is None else sorted(editable)
        ),
        "can_edit_current": (
            bool(event) and bool(actor) and can_edit_event(actor, event)
        ),
    }


@frappe.whitelist(allow_guest=True)
def consolidation_summary(
    disaster_event,
):
    rn_actor(required=False)

    event = _canonical_event(
        disaster_event
    )

    doctypes = {
        "community_report_count":
            "RN Community Report",

        "community_need_count":
            "RN Community Need",

        "logistic_need_count":
            "RN Logistic Need",

        "aid_offer_count":
            "RN Aid Offer",

        "distribution_flow_count":
            "RN Distribution Flow",

        "posko_count":
            "RN Posko",

        "stock_observation_count":
            "RN Stock Observation",

        "medical_case_count":
            "RN Medical Case",

        "shelter_occupancy_count":
            "RN Shelter Occupancy",

        "missing_person_count":
            "RN Missing Person Report",

        "found_person_count":
            "RN Found Person Report",
    }

    result = {}

    for key, doctype in doctypes.items():
        if frappe.db.exists(
            "DocType",
            doctype,
        ):
            result[key] = (
                _count_for_event(
                    doctype,
                    event,
                )
            )
        else:
            result[key] = 0

    return result


@frappe.whitelist(allow_guest=True)
def consolidation_raw_reports(
    disaster_event,
):
    return community_reports(
        disaster_event=disaster_event
    )


@frappe.whitelist(allow_guest=True)
def consolidated_needs(
    disaster_event,
):
    rn_actor(required=False)

    event = _canonical_event(
        disaster_event
    )

    result = []

    for doctype in (
        "RN Community Need",
        "RN Logistic Need",
    ):
        if not frappe.db.exists(
            "DocType",
            doctype,
        ):
            continue

        fields = _safe_fields(
            doctype,
            [
                "name",
                "title",
                "disaster_event",
                "description",
                "item_name",
                "quantity",
                "unit",
                "urgency",
                "status",
                "need_status",
                "verification_status",
                "canonical_category",
                "canonical_group",
                "canonical_item",
                "posko",
                "source_report",
                "creation",
            ],
        )

        rows = frappe.get_all(
            doctype,
            filters={
                "disaster_event":
                    event
            },
            fields=fields,
            order_by="creation desc",
            limit_page_length=3000,
        )

        for row in rows:
            item = dict(row)

            item["id"] = item["name"]

            item["source_type"] = (
                "community"
                if doctype
                == "RN Community Need"
                else "logistic"
            )

            item["status"] = (
                item.get("status")
                or item.get(
                    "need_status"
                )
            )

            result.append(item)

    return result


def _haversine_km(lat1, lng1, lat2, lng2):
    if None in (lat1, lng1, lat2, lng2):
        return None

    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    )

    return 2 * r * math.asin(math.sqrt(a))


@frappe.whitelist(allow_guest=True)
def duplicate_candidates(
    disaster_event,
):
    """Real first-pass duplicate detector — not fabricated, but computed
    live every call (no persisted "resolved" state yet; the Needs Review /
    Not Duplicate / Confirm Duplicate buttons in the UI don't have
    anywhere real to save to until a canonical duplicate model exists —
    same caveat as before, just no longer hidden behind an always-empty
    stub).

    Compares open `RN Logistic Need` rows for the same disaster event,
    grouped by canonical item/group so unrelated items are never compared,
    and flags a pair as a candidate when either:
    - both sides' posko have coordinates and are within
      `DUPLICATE_RADIUS_KM` of each other ("berdekatan"), or
    - neither has coordinates but their posko share the same village name
      ("daerah yang sama") — a coarser fallback for posko without GPS set.
    Two needs logged by the SAME posko are not a "duplicate" of each
    other (that's just the same source reporting twice), so those pairs
    are skipped.
    """
    rn_actor(required=False)
    event = _canonical_event(disaster_event)

    need_fields = _safe_fields(
        "RN Logistic Need",
        [
            "name", "disaster_event", "posko", "item_name",
            "canonical_group", "canonical_item", "need_status",
        ],
    )
    needs = frappe.get_all(
        "RN Logistic Need",
        filters={
            "disaster_event": event,
            "need_status": ["in", ["open", "needs_review"]],
        },
        fields=need_fields,
        limit_page_length=2000,
    )

    posko_ids = list({n.get("posko") for n in needs if n.get("posko")})
    posko_geo = {}
    if posko_ids:
        for p in frappe.get_all(
            "RN Posko",
            filters={"name": ["in", posko_ids]},
            fields=["name", "latitude", "longitude", "village_name", "district_name"],
        ):
            posko_geo[p.name] = p

    enriched = []
    for n in needs:
        p = posko_geo.get(n.get("posko")) or {}
        item_key = (
            n.get("canonical_item")
            or n.get("canonical_group")
            or n.get("item_name")
            or ""
        ).strip().lower()

        if not item_key or not n.get("posko"):
            continue

        enriched.append({
            "name": n.get("name"),
            "posko": n.get("posko"),
            "item_key": item_key,
            "lat": p.get("latitude"),
            "lng": p.get("longitude"),
            "area": p.get("village_name") or p.get("district_name"),
        })

    by_item = defaultdict(list)
    for row in enriched:
        by_item[row["item_key"]].append(row)

    candidates = []
    for rows in by_item.values():
        for i in range(len(rows)):
            for j in range(i + 1, len(rows)):
                a, b = rows[i], rows[j]

                if a["posko"] == b["posko"]:
                    continue

                dist = _haversine_km(a["lat"], a["lng"], b["lat"], b["lng"])
                reason = None
                score = 0

                if dist is not None and dist <= DUPLICATE_RADIUS_KM:
                    reason = "Lokasi berdekatan (~%.1f km), item sama" % dist
                    score = max(30, round(100 - (dist / DUPLICATE_RADIUS_KM) * 40))
                elif dist is None and a["area"] and a["area"] == b["area"]:
                    reason = "Area sama (%s), item sama, posko tanpa koordinat" % a["area"]
                    score = 55

                if reason:
                    candidates.append({
                        "id": "%s::%s" % (a["name"], b["name"]),
                        "object_type": "RN Logistic Need",
                        "object_id_a": a["name"],
                        "object_id_b": b["name"],
                        "posko_a": a["posko"],
                        "posko_b": b["posko"],
                        "match_reason": reason,
                        "match_score": score,
                        "status": "pending_review",
                    })

    candidates.sort(key=lambda c: c["match_score"], reverse=True)
    candidates = candidates[:100]

    # Overlay any persisted operator decision (RN Duplicate Candidate
    # Resolution) — this used to always read back as "pending_review"
    # because resolve_duplicate_candidate() didn't exist yet.
    if candidates:
        resolutions = frappe.get_all(
            "RN Duplicate Candidate Resolution",
            filters={"pair_id": ["in", [c["id"] for c in candidates]]},
            fields=["pair_id", "status", "reviewed_by", "ai_verdict", "notes"],
        )
        resolution_by_pair = {r.pair_id: r for r in resolutions}

        for c in candidates:
            r = resolution_by_pair.get(c["id"])
            if r:
                c["status"] = r.status
                c["reviewed_by"] = r.reviewed_by
                c["ai_verdict"] = r.ai_verdict
                c["notes"] = r.notes

    return candidates


@frappe.whitelist()
def resolve_duplicate_candidate(pair_id, status, reviewed_by=None, review_notes=None,
                                 ai_verdict=None, ai_answer=None):
    """Persist an operator's Needs Review / Not Duplicate / Confirm
    Duplicate decision for one candidate pair from duplicate_candidates()
    — this always failed before (no canonical model existed; the button
    rendered as if it worked). `pair_id` is the same
    "<object_id_a>::<object_id_b>" key duplicate_candidates() returns as
    `id`. Upserts by pair_id so re-resolving the same pair updates it
    instead of creating duplicates of the duplicate-resolution itself."""
    valid_statuses = {"needs_review", "not_duplicate", "confirmed_duplicate"}
    if status not in valid_statuses:
        frappe.throw("Status tidak valid.")

    parts = (pair_id or "").split("::")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        frappe.throw("pair_id tidak valid.")

    pair_event = frappe.db.get_value(
        "RN Logistic Need", parts[0], "disaster_event"
    )
    actor = _require_event_edit(pair_event) if pair_event else _actor()

    object_id_a, object_id_b = parts
    who = reviewed_by or getattr(actor, "name", None) or frappe.session.user

    if frappe.db.exists("RN Duplicate Candidate Resolution", pair_id):
        doc = frappe.get_doc("RN Duplicate Candidate Resolution", pair_id)
        doc.status = status
        doc.reviewed_by = who
        doc.notes = review_notes
        if ai_verdict:
            doc.ai_verdict = ai_verdict
            doc.ai_answer = ai_answer
        doc.flags.ignore_permissions = True
        doc.save(ignore_permissions=True)
    else:
        doc = frappe.get_doc({
            "doctype": "RN Duplicate Candidate Resolution",
            "pair_id": pair_id,
            "object_type": "RN Logistic Need",
            "object_id_a": object_id_a,
            "object_id_b": object_id_b,
            "status": status,
            "reviewed_by": who,
            "notes": review_notes,
            "ai_verdict": ai_verdict,
            "ai_answer": ai_answer,
        })
        doc.flags.ignore_permissions = True
        doc.insert(ignore_permissions=True)

    frappe.db.commit()

    return {"ok": True, "pair_id": pair_id, "status": status}


@frappe.whitelist()
def set_consolidation_override(group_key, disaster_event, override_qty,
                                reason=None):
    """Operator's manual judgment on a Rollup Nasional group — takes
    precedence over the MAX-rule estimate (see
    api_intelligence._overlay_group_overrides). Upserts by group_key,
    same pattern as resolve_duplicate_candidate()."""
    event = _canonical_event(disaster_event)
    actor = _require_event_edit(event)

    who = getattr(actor, "name", None) or frappe.session.user

    try:
        override_qty = float(override_qty)
    except (TypeError, ValueError):
        frappe.throw("Override qty tidak valid.")

    if frappe.db.exists("RN Consolidation Group Override", group_key):
        doc = frappe.get_doc("RN Consolidation Group Override", group_key)
        doc.override_qty = override_qty
        doc.reason = reason
        doc.reviewed_by = who
        doc.status = "active"
        doc.flags.ignore_permissions = True
        doc.save(ignore_permissions=True)
    else:
        doc = frappe.get_doc({
            "doctype": "RN Consolidation Group Override",
            "override_key": group_key,
            "disaster_event": event,
            "group_key": group_key,
            "override_qty": override_qty,
            "reason": reason,
            "reviewed_by": who,
            "status": "active",
        })
        doc.flags.ignore_permissions = True
        doc.insert(ignore_permissions=True)

    frappe.db.commit()

    return {"ok": True, "group_key": group_key, "override_qty": override_qty}


@frappe.whitelist()
def clear_consolidation_override(group_key, disaster_event):
    """Removes a manual override so the group goes back to the live
    MAX-rule estimate."""
    event = _canonical_event(disaster_event)
    _require_event_edit(event)

    if frappe.db.exists("RN Consolidation Group Override", group_key):
        doc = frappe.get_doc("RN Consolidation Group Override", group_key)
        doc.status = "cleared"
        doc.flags.ignore_permissions = True
        doc.save(ignore_permissions=True)
        frappe.db.commit()

    return {"ok": True, "group_key": group_key}


@frappe.whitelist()
def duplicates_check(disaster_event, object_type="all"):
    """"Check Duplicate" button on Data Konsolidasi. `duplicate_candidates`
    is computed live on every read (no persisted table to refresh), so this
    just validates the event and reports the current count — kept as a
    real endpoint (not the generic unsupported-operation stub) so the
    button gives honest, specific feedback instead of a canned error."""
    event = _canonical_event(disaster_event)
    _require_event_edit(event)

    count = len(duplicate_candidates(event))

    return {
        "ok": True,
        "disaster_event": event,
        "object_type": object_type,
        "candidate_count": count,
    }


@frappe.whitelist()
def community_report_set_consolidation(
    report,
    consolidation_status=None,
    location_status=None,
    is_aggregate=None,
    reviewer_id=None,
    notes=None,
):
    """"Review Lokasi / Tandai Agregat / Verified Unique" buttons on Data
    Konsolidasi's Raw Reports Queue — the actual human-in-the-loop
    duplicate/aggregate resolution mechanism (distinct from the automated
    proximity detector above, which only flags candidates for a human to
    look at). Was previously unrouted in the frontend's rnFetch() and fell
    through to `unsupported_consolidation_operation`, so these buttons
    always failed silently despite rendering as if they worked."""
    if not frappe.db.exists("RN Community Report", report):
        frappe.throw("RN Community Report tidak ditemukan.")

    report_event = frappe.db.get_value(
        "RN Community Report", report, "disaster_event"
    )
    _require_event_edit(report_event) if report_event else _actor()

    fields = _safe_fields(
        "RN Community Report",
        ["consolidation_status", "location_status", "is_aggregate"],
    )

    updates = {}
    if consolidation_status is not None and "consolidation_status" in fields:
        updates["consolidation_status"] = consolidation_status
    if location_status is not None and "location_status" in fields:
        updates["location_status"] = location_status
    if is_aggregate is not None and "is_aggregate" in fields:
        updates["is_aggregate"] = (
            1 if str(is_aggregate).lower() in ("1", "true", "yes") else 0
        )

    if not updates:
        frappe.throw("Tidak ada field consolidation yang valid untuk diupdate.")

    frappe.db.set_value("RN Community Report", report, updates)
    frappe.db.commit()

    frappe.logger().info(
        "[community_report_set_consolidation] %s -> %s oleh %s (%s)"
        % (report, updates, reviewer_id or frappe.session.user, notes or "")
    )

    return {"ok": True, "report": report, "updated": updates}


@frappe.whitelist(allow_guest=True)
def consolidation_auxiliary(
    disaster_event,
):
    rn_actor(required=False)

    event = _canonical_event(
        disaster_event
    )

    poskos = frappe.get_all(
        "RN Posko",
        filters={
            "disaster_event": event
        },
        fields=[
            "name",
            "title",
            "province_name",
            "city_name",
            "district_name",
            "village_name",
            "area_level",
        ],
        limit_page_length=3000,
    )

    operational_areas = []

    seen = set()

    for posko in poskos:
        key = (
            posko.province_name,
            posko.city_name,
            posko.district_name,
            posko.village_name,
        )

        if key in seen:
            continue

        seen.add(key)

        operational_areas.append({
            "id":
                "|".join(
                    str(x or "")
                    for x in key
                ),
            "province_name":
                posko.province_name,
            "city_name":
                posko.city_name,
            "district_name":
                posko.district_name,
            "village_name":
                posko.village_name,
            "area_level":
                posko.area_level,
        })

    return {
        "operational_areas":
            operational_areas,

        "beneficiary_groups":
            [],

        "evidence_requirements":
            [],
    }
