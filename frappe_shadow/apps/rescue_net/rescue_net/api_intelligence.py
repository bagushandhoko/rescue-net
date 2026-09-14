import json
from collections import defaultdict

import frappe

from rescue_net.access_policy import (
    is_system_manager,
    rn_actor,
)
from rescue_net.reference_resolver import resolve_disaster_event
from rescue_net.intelligence.freshness import freshness
# Registry = built-in keyword rules + editable RN Normalization Rule records
# (Frappe Desk). Import from here, never straight from `.normalization`, so the
# field-configurable aliases/priorities are always consulted.
from rescue_net.intelligence.normalization_registry import classify_text


def _can_edit_need(actor, need):
    if is_system_manager():
        return True

    if need.requester_user == actor.name:
        return True

    if actor.role in (
        "posko_operator",
        "medical_operator",
        "shelter_operator",
    ):
        return True

    return False


@frappe.whitelist()
def suggest_need(community_need):
    rn_actor()

    doc = frappe.get_doc(
        "RN Community Need",
        community_need,
    )

    raw = (
        doc.raw_need_text
        or doc.description
        or doc.title
        or ""
    )

    return classify_text(raw)


@frappe.whitelist()
def accept_suggestion(
    community_need,
    item_kind=None,
    canonical_category=None,
    canonical_group=None,
    canonical_item=None,
    normalization_source="manual",
    normalization_confidence=None,
):
    actor = rn_actor()
    doc = frappe.get_doc(
        "RN Community Need",
        community_need,
    )

    if not _can_edit_need(actor, doc):
        frappe.throw(
            "Anda tidak dapat mengubah klasifikasi kebutuhan ini",
            frappe.PermissionError,
        )

    if item_kind:
        doc.item_kind = item_kind

    if canonical_category:
        doc.canonical_category = canonical_category

    if canonical_group:
        doc.canonical_group = canonical_group

    if canonical_item:
        doc.canonical_item = canonical_item

    if normalization_source in (
        "manual",
        "rule",
        "ai",
    ):
        doc.normalization_source = normalization_source

    if normalization_confidence not in (
        None,
        "",
    ):
        doc.normalization_confidence = int(
            normalization_confidence
        )

    doc.normalization_status = "accepted"
    doc.save(ignore_permissions=True)

    return {
        "community_need": doc.name,
        "canonical_category": doc.canonical_category,
        "canonical_group": doc.canonical_group,
        "canonical_item": doc.canonical_item,
        "normalization_source": doc.normalization_source,
        "normalization_status": doc.normalization_status,
    }


_AREA_FIELDS = [
    "admin_area_id",
    "village_name",
    "district_name",
    "city_name",
    "province_name",
]


def _source_area(report=None, posko=None):
    # RN Community Need rows carry a source_report; RN Logistic Need rows
    # (no such field) carry a posko instead — either one resolves an area.
    if report:
        row = frappe.db.get_value(
            "RN Community Report", report, _AREA_FIELDS, as_dict=True,
        )
    elif posko:
        row = frappe.db.get_value(
            "RN Posko", posko, _AREA_FIELDS, as_dict=True,
        )
    else:
        row = None

    if not row:
        return {
            "area": "Unknown",
            "admin_area_id": None,
        }

    area = (
        row.village_name
        or row.district_name
        or row.city_name
        or row.province_name
        or "Unknown"
    )

    return {
        "area": area,
        "admin_area_id": row.admin_area_id,
    }


def _group_rows(rows):
    from rescue_net.intelligence.packaging import bucket_quantity

    grouped = defaultdict(list)

    for row in rows:
        area = _source_area(row.source_report, row.posko)

        group_name = (
            row.canonical_group
            or row.canonical_category
            or row.need_type
            or "Belum Dikelompokkan"
        )

        # base unit is computed on the fly — RN Community Need does not persist
        # the conversion_* fields, so pass stored=None.
        bkt = bucket_quantity(
            row.canonical_item, row.canonical_group,
            row.quantity, row.unit, row.quantity_mode,
            row.quantity_min, row.quantity_max,
            row.raw_need_text or "", stored=None,
        )

        key = (
            row.disaster_event or "no-event",
            area["admin_area_id"] or area["area"],
            group_name,
            bkt["base_unit"] or "unit",
        )

        grouped[key].append(
            (row, area, bkt)
        )

    output = []

    for key, members in grouped.items():
        source_ids = set()
        organizations = set()
        units = set()
        qmins = []
        qmaxs = []
        freshness_rows = []
        verified_count = 0
        norm_scores = []
        qty_measurable = 0.0
        qty_estimated = 0.0
        unmeasurable_count = 0
        sources = []

        for row, area, bkt in members:
            source_identity = (
                row.community_owner
                or row.requester_user
                or row.name
            )
            source_ids.add(source_identity)

            # Raw records behind this group's number — an operator needs to
            # see these to judge whether MAX/the AI estimate is actually
            # right, not just trust the rollup.
            sources.append({
                "name": row.name,
                "doctype": row._doctype,
                "item_text": (
                    row.raw_need_text
                    or row.canonical_item
                    or key[2]
                ),
                "quantity": row.quantity,
                "quantity_min": row.quantity_min,
                "quantity_max": row.quantity_max,
                "unit": row.unit,
                "area": area["area"],
                "posko": row.posko,
                "source_report": row.source_report,
                "disaster_event": row.disaster_event,
                "observed_at": row.observed_at or row.source_updated_at,
                "verification_status": row.verification_status,
            })

            if row.community_owner:
                organizations.add(
                    row.community_owner
                )

            qty_measurable += bkt["measurable"]
            qty_estimated += bkt["estimated"]
            unmeasurable_count += bkt["unmeasurable"]

            if row.unit:
                units.add(row.unit)

            if row.quantity_mode == "range":
                if row.quantity_min is not None:
                    qmins.append(row.quantity_min)
                if row.quantity_max is not None:
                    qmaxs.append(row.quantity_max)

            elif row.quantity:
                qmins.append(row.quantity)
                qmaxs.append(row.quantity)

            fr = freshness(
                row.source_updated_at,
                row.observed_at,
                row.modified,
                row.freshness_policy_minutes,
                "need",
            )
            freshness_rows.append(fr)

            if row.verification_status == "verified":
                verified_count += 1

            if row.normalization_confidence:
                norm_scores.append(
                    row.normalization_confidence
                )

        # MAX = safe first pass when scopes may overlap.
        estimate_min = max(qmins) if qmins else None
        estimate_max = max(qmaxs) if qmaxs else None

        fresh_count = sum(
            1 for f in freshness_rows
            if f["status"] == "fresh"
        )
        stale_count = sum(
            1 for f in freshness_rows
            if f["status"] == "stale"
        )

        total = len(members)

        verification_ratio = (
            verified_count / total
            if total else 0
        )
        fresh_ratio = (
            fresh_count / total
            if total else 0
        )
        norm_avg = (
            sum(norm_scores) / len(norm_scores)
            if norm_scores else 35
        )

        confidence = round(
            min(
                100,
                20
                + min(20, len(source_ids) * 5)
                + verification_ratio * 25
                + fresh_ratio * 20
                + (norm_avg / 100) * 15
            )
        )

        if confidence >= 75:
            confidence_label = "high"
        elif confidence >= 50:
            confidence_label = "medium"
        else:
            confidence_label = "low"

        newest = None
        oldest = None
        times = [
            f["timestamp"]
            for f in freshness_rows
            if f["timestamp"]
        ]

        if times:
            newest = max(times)
            oldest = min(times)

        row0, area0, _bkt0 = members[0]

        output.append({
            "group_key": "|".join(str(x) for x in key),
            "disaster_event": row0.disaster_event,
            "area": area0["area"],
            "admin_area_id": area0["admin_area_id"],
            "canonical_category": row0.canonical_category,
            "canonical_group": (
                row0.canonical_group
                or row0.canonical_category
                or row0.need_type
                or "Belum Dikelompokkan"
            ),
            "canonical_item": row0.canonical_item,
            "base_unit": key[3],
            "source_count": total,
            "independent_source_count": len(source_ids),
            "organization_count": len(organizations),
            "units": sorted(units),
            "estimate_method": "MAX_OVERLAP_SAFE",
            "estimate_min": estimate_min,
            "estimate_max": estimate_max,
            # consolidated in ONE base unit, honest 3-way split
            "qty_measurable": round(qty_measurable, 2),
            "qty_estimated": round(qty_estimated, 2),
            "qty_total": round(qty_measurable + qty_estimated, 2),
            "unmeasurable_count": unmeasurable_count,
            "fresh_count": fresh_count,
            "stale_count": stale_count,
            "newest_update": newest,
            "oldest_source_used": oldest,
            "confidence": confidence,
            "confidence_label": confidence_label,
            "note": (
                "Derived estimate. Raw reports remain source of truth; "
                "MAX is used when overlap cannot be excluded."
            ),
            "sources": sources[:50],
        })

    output.sort(
        key=lambda x: (
            x["area"] or "",
            x["canonical_group"] or "",
        )
    )

    return output


_COMMUNITY_NEED_FIELDS = [
    "name", "disaster_event",
    "source_report", "requester_user",
    "community_owner", "need_type",
    "raw_need_text", "canonical_category",
    "canonical_group", "canonical_item",
    "quantity", "unit", "quantity_mode",
    "quantity_min", "quantity_max",
    "verification_status",
    "normalization_confidence",
    "observed_at", "source_updated_at",
    "freshness_policy_minutes", "modified",
]

_LOGISTIC_NEED_FIELDS = [
    "name", "disaster_event", "posko",
    "created_by_user", "item_name", "raw_item_text",
    "canonical_category", "canonical_group", "canonical_item",
    "quantity", "unit", "quantity_mode",
    "quantity_min", "quantity_max",
    "verification_status",
    "normalization_confidence",
    "observed_at", "source_updated_at",
    "freshness_policy_minutes", "modified",
]


def _fetch_need_rows(disaster_event=None, names=None):
    """Shared fetch+alias for RN Community Need + RN Logistic Need feeding
    _group_rows()/_source_area(). RN Community Need is legacy/near-empty (1
    row system-wide) — the real logistics-need pipeline writes to RN
    Logistic Need instead, so its differently-named fields get mapped onto
    what _group_rows() expects rather than forking the grouping logic.

    `disaster_event`: restrict to one event (open/active statuses only —
    the live rollup / a fresh rebuild).
    `names`: restrict to an explicit prior set of IDs regardless of current
    status — replaying a frozen historical snapshot against whatever those
    records look like *now* (a record edited since the snapshot shows its
    current values, not a frozen-at-the-time copy — nothing is duplicated
    to avoid that drift; see RN Consolidated Need Snapshot's docstring).
    """
    if names is not None:
        community_filters = {"name": ["in", names]}
        logistic_filters = {"name": ["in", names]}
    else:
        community_filters = {"status": ["in", ["open", "in_progress"]]}
        logistic_filters = {"need_status": ["in", ["open", "needs_review"]]}

        if disaster_event:
            community_filters["disaster_event"] = disaster_event
            logistic_filters["disaster_event"] = disaster_event

    community_rows = frappe.get_all(
        "RN Community Need",
        filters=community_filters,
        fields=_COMMUNITY_NEED_FIELDS,
        limit_page_length=5000,
    )
    for row in community_rows:
        row["_doctype"] = "RN Community Need"

    logistic_rows = frappe.get_all(
        "RN Logistic Need",
        filters=logistic_filters,
        fields=_LOGISTIC_NEED_FIELDS,
        limit_page_length=5000,
    )
    for row in logistic_rows:
        row["_doctype"] = "RN Logistic Need"
        row["requester_user"] = row.get("created_by_user")
        row["need_type"] = row.get("item_name")
        row["raw_need_text"] = row.get("raw_item_text")

    return community_rows + logistic_rows


@frappe.whitelist()
def control_centre_summary():
    rn_actor()

    rows = _fetch_need_rows()

    return {
        "raw_need_count": len(rows),
        "groups": _group_rows(rows),
        "rule": "MAX_OVERLAP_SAFE",
        "warning": (
            "Consolidated values are derived estimates, "
            "not replacements for raw reports."
        ),
    }


@frappe.whitelist()
def rebuild_consolidated_needs(disaster_event):
    """"Rebuild Consolidated Needs" on Data Konsolidasi. Does NOT persist a
    copy of the computed numbers (that would drift from the raw records
    and just be more data to keep in sync) — it snapshots which raw need
    IDs were included right now (a few hundred bytes of names, not a
    result blob), so `consolidated_need_snapshot_detail` can replay the
    exact same MAX-rule computation against the original records later,
    keeping the original detail traceable instead of duplicated."""
    actor = rn_actor()
    event = resolve_disaster_event(disaster_event) or disaster_event

    if not event:
        frappe.throw("Disaster Event tidak ditemukan")

    rows = _fetch_need_rows(disaster_event=event)
    groups = _group_rows(rows)

    doc = frappe.get_doc({
        "doctype": "RN Consolidated Need Snapshot",
        "disaster_event": event,
        "rule": "MAX_OVERLAP_SAFE",
        "raw_need_count": len(rows),
        "group_count": len(groups),
        "need_ids_json": json.dumps([r["name"] for r in rows]),
        "triggered_by": getattr(actor, "name", None) or frappe.session.user,
    })
    doc.flags.ignore_permissions = True
    doc.insert(ignore_permissions=True)
    frappe.db.commit()

    return {
        "ok": True,
        "snapshot": doc.name,
        "disaster_event": event,
        "raw_need_count": len(rows),
        "group_count": len(groups),
        "created": doc.creation,
    }


@frappe.whitelist()
def consolidated_need_snapshots(disaster_event):
    """Riwayat (history) list — metadata only, no recompute."""
    rn_actor()
    event = resolve_disaster_event(disaster_event) or disaster_event

    rows = frappe.get_all(
        "RN Consolidated Need Snapshot",
        filters={"disaster_event": event} if event else {},
        fields=[
            "name", "disaster_event", "rule", "raw_need_count",
            "group_count", "triggered_by", "creation",
        ],
        order_by="creation desc",
        limit_page_length=200,
    )

    return rows


@frappe.whitelist()
def consolidated_need_snapshot_detail(name):
    """Replays one snapshot's frozen ID set through the same grouping
    logic as the live rollup — the historical view, computed fresh from
    whatever those original records look like today rather than from a
    stored copy."""
    rn_actor()

    if not frappe.db.exists("RN Consolidated Need Snapshot", name):
        frappe.throw("Snapshot tidak ditemukan")

    snap = frappe.get_doc("RN Consolidated Need Snapshot", name)

    try:
        need_ids = json.loads(snap.need_ids_json or "[]")
    except ValueError:
        need_ids = []

    rows = _fetch_need_rows(names=need_ids) if need_ids else []
    missing = len(need_ids) - len(rows)

    return {
        "snapshot": snap.name,
        "disaster_event": snap.disaster_event,
        "rule": snap.rule,
        "created": snap.creation,
        "triggered_by": snap.triggered_by,
        "raw_need_count_at_snapshot": snap.raw_need_count,
        "raw_need_count_now": len(rows),
        "missing_since_snapshot": max(0, missing),
        "groups": _group_rows(rows),
    }
