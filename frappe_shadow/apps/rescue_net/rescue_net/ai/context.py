"""AI — the operational context built for an event (scoped to the asker's poskos)."""

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

from rescue_net.ai.common import (  # noqa: F401
    _require_login,
)


def _member_orgs(actor):
    if not actor or not actor.name:
        return []

    result = frappe.get_all(
        "RN Organization Membership",
        filters={
            "user_account": actor.name,
            "status": "approved",
        },
        pluck="organization",
        limit_page_length=500,
    )

    if getattr(actor, "organization", None):
        result.append(actor.organization)

    return list(set(x for x in result if x))


def _ai_scope_poskos(refresh=False):
    cache_key = "_rn_ai_scope_poskos"
    missing = "__rn_ai_scope_missing__"

    if not refresh:
        cached = getattr(
            frappe.local,
            cache_key,
            missing,
        )
        if cached != missing:
            return cached

    actor = rn_actor()

    # None = unrestricted/global Control Centre context.
    if (
        is_system_manager()
        or getattr(actor, "role", None)
        == "command_center"
    ):
        scope = None
    elif not actor or not actor.name:
        scope = []
    else:
        result = set()

        for org in _member_orgs(actor):
            result.update(
                frappe.get_all(
                    "RN Posko",
                    filters={
                        "organization": org
                    },
                    pluck="name",
                    limit_page_length=1000,
                )
            )

        result.update(
            frappe.get_all(
                "RN Posko Assignment",
                filters={
                    "user_account": actor.name,
                    "status": "approved",
                },
                pluck="posko",
                limit_page_length=500,
            )
        )

        if getattr(actor, "posko", None):
            result.add(actor.posko)

        scope = sorted(result)

    setattr(
        frappe.local,
        cache_key,
        scope,
    )

    return scope


def _rows(
    doctype,
    disaster_event_id,
    fields,
    limit=100,
):
    if not frappe.db.exists(
        "DocType",
        doctype,
    ):
        return []

    meta = frappe.get_meta(doctype)

    actual = ["name"]

    for field in fields:
        if (
            field != "name"
            and meta.has_field(field)
        ):
            actual.append(field)

    filters = {}

    scope_poskos = _ai_scope_poskos()

    if scope_poskos is not None:
        if not scope_poskos:
            return []

        if doctype == "RN Posko":
            filters["name"] = [
                "in",
                scope_poskos,
            ]
        elif meta.has_field("posko"):
            filters["posko"] = [
                "in",
                scope_poskos,
            ]
        else:
            # Never expose non-Posko-scoped event records
            # to ordinary scoped users.
            return []

    if meta.has_field("disaster_event"):
        filters["disaster_event"] = (
            disaster_event_id
        )
    elif meta.has_field(
        "disaster_event_id"
    ):
        filters["disaster_event_id"] = (
            disaster_event_id
        )

    return [
        dict(x)
        for x in frappe.get_all(
            doctype,
            filters=filters,
            fields=actual,
            order_by="modified desc",
            limit_page_length=limit,
        )
    ]


def _status(row):
    for key in (
        "status",
        "need_status",
        "flow_status",
        "case_status",
        "request_status",
        "availability_status",
    ):
        if row.get(key):
            return str(
                row.get(key)
            ).lower()

    return ""


def _active_count(rows):
    terminal = {
        "completed",
        "cancelled",
        "closed",
        "fulfilled",
        "received",
        "deleted",
        "reunited",
    }

    return sum(
        1
        for row in rows
        if _status(row) not in terminal
    )


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _enrich_needs(rows):
    """Surface real realisasi/gap for the Control Centre critical-needs table.

    RN Logistic Need has no fulfilled column; the seeds keep the real numbers
    in legacy_payload (required_quantity / realized_quantity / gap). Expose
    them as clean numeric fields and normalise priority/status aliases, then
    drop the raw payload so nothing private leaks to the public dashboard.
    """
    import json

    for row in rows:
        payload = row.pop("legacy_payload", None)

        if isinstance(payload, str) and payload.strip():
            try:
                payload = json.loads(payload)
            except (ValueError, TypeError):
                payload = None

        if not isinstance(payload, dict):
            payload = {}

        required = _num(
            payload.get("required_quantity")
            or payload.get("quantity_needed")
            or payload.get("quantity_final")
            or row.get("quantity")
        )

        realized = _num(
            payload.get("realized_quantity")
            or payload.get("fulfilled_quantity")
            or payload.get("delivered_quantity")
        )

        if realized > required > 0:
            realized = required

        gap = max(0.0, required - realized)

        row["required_quantity"] = required
        row["quantity_required"] = required
        row["realized_quantity"] = realized
        row["fulfilled_quantity"] = realized
        row["gap"] = gap
        row["realization_percent"] = (
            round(realized / required * 100, 1)
            if required > 0
            else 0.0
        )

        row["priority"] = (
            row.get("priority")
            or row.get("urgency")
            or payload.get("priority")
            or "normal"
        )
        row["status"] = (
            row.get("status")
            or row.get("need_status")
            or payload.get("status")
            or "open"
        )


def _resolve_disaster_event(value):
    if not value:
        return value

    value = str(value).strip()

    if frappe.db.exists(
        "RN Disaster Event",
        value,
    ):
        return value

    candidates = [value]

    if not value.startswith(
        "disaster_events:"
    ):
        candidates.append(
            "disaster_events:" + value
        )

    for legacy_id in candidates:
        name = frappe.db.get_value(
            "RN Disaster Event",
            {"legacy_id": legacy_id},
            "name",
        )

        if name:
            return name

        if frappe.db.exists(
            "RN Disaster Event",
            legacy_id,
        ):
            return legacy_id

    return value


def _disaster_summary(name):
    if not name:
        return None

    if not frappe.db.exists(
        "RN Disaster Event",
        name,
    ):
        return None

    meta = frappe.get_meta(
        "RN Disaster Event"
    )

    candidates = (
        "title",
        "status",
        "disaster_type",
        "severity",
        "location",
        "start_date",
        "end_date",
    )

    fields = ["name"]

    for fieldname in candidates:
        if meta.has_field(fieldname):
            fields.append(fieldname)

    row = frappe.db.get_value(
        "RN Disaster Event",
        name,
        fields,
        as_dict=True,
    )

    return dict(row) if row else None


# Private helper — NOT whitelisted: with public=True it skips the AI scope and
# returns data before _public_scrub. Callers: context() / public_context().
def _build_context(disaster_event_id, public=False):
    # RN_CANONICAL_REF disaster_event_id = resolve_disaster_event(disaster_event_id)
    disaster_event_id = resolve_disaster_event(disaster_event_id)
    if public:
        # Guest viewer Control Centre:
        # global read scope, but result will
        # be sanitized before leaving API.
        setattr(
            frappe.local,
            "_rn_ai_scope_poskos",
            None,
        )
    else:
        _require_login()
        _ai_scope_poskos(
            refresh=True
        )

    resolved_event = _resolve_disaster_event(
        disaster_event_id
    )

    disaster = _disaster_summary(
        resolved_event
    )

    poskos = _rows(
        "RN Posko",
        resolved_event,
        [
            "posko_name",
            "location",
            "operational_status",
            "verification_status",
        ],
    )

    needs = _rows(
        "RN Logistic Need",
        resolved_event,
        [
            "item_name",
            "quantity",
            "unit",
            "priority",
            "status",
            "need_status",
            "urgency",
            "location",
            "needed_before",
            "legacy_payload",
        ],
    )

    _enrich_needs(needs)

    # Laporan Masyarakat yang sudah punya perkiraan skala kerusakan/jumlah
    # terdampak -> perkiraan kebutuhan heuristik ikut jadi konteks AI
    # Analyst, supaya jawabannya bisa mempertimbangkan sinyal warga yang
    # belum sempat diverifikasi manual (owner ask: "link juga ke AI").
    community_reports_ctx = []
    try:
        from rescue_net.api_reports import predict_report_needs

        report_rows = _rows(
            "RN Community Report", resolved_event,
            ["title", "report_type", "status", "priority", "location_text",
             "affected_people_count", "damage_scale_value", "damage_scale_unit"],
        )
        for r in report_rows:
            predicted = predict_report_needs(
                r.get("report_type"), r.get("damage_scale_value"), r.get("affected_people_count"),
            )
            if predicted:
                community_reports_ctx.append({**r, "predicted_needs": predicted})
    except Exception:
        community_reports_ctx = []

    offers = _rows(
        "RN Aid Offer",
        resolved_event,
        [
            "item_name",
            "quantity",
            "unit",
            "status",
        ],
    )

    flows = _rows(
        "RN Distribution Flow",
        resolved_event,
        [
            "item_name",
            "quantity",
            "unit",
            "flow_status",
            "status",
        ],
    )

    stock = _rows(
        "RN Stock Observation",
        resolved_event,
        [
            "item_name",
            "quantity",
            "unit",
            "posko",
            "observed_at",
        ],
    )

    kitchen = _rows(
        "RN Kitchen Production",
        resolved_event,
        [
            "meal_name",
            "portions",
            "production_status",
            "status",
        ],
        50,
    )

    medical = _rows(
        "RN Medical Case",
        resolved_event,
        [
            "triage_level",
            "case_status",
            "status",
            "posko",
        ],
        50,
    )

    volunteers = _rows(
        "RN Volunteer Assignment",
        resolved_event,
        [
            "status",
            "assignment_type",
            "posko",
        ],
        200,
    )

    shelter_occ = _rows(
        "RN Shelter Occupancy",
        resolved_event,
        [
            "shelter_name",
            "capacity_total",
            "current_occupancy",
            "families_count",
        ],
        50,
    )

    shelter_needs = _rows(
        "RN Shelter Need",
        resolved_event,
        [
            "item_name",
            "quantity",
            "unit",
            "priority",
            "status",
        ],
        50,
    )

    # Privacy-safe Search & Found context:
    # no names, contacts or identity attributes.
    missing = _rows(
        "RN Missing Person Report",
        resolved_event,
        ["status"],
        50,
    )

    found = _rows(
        "RN Found Person Report",
        resolved_event,
        ["status"],
        50,
    )

    matches = _rows(
        "RN Search Found Match",
        resolved_event,
        [
            "status",
            "match_status",
            "confidence",
        ],
        50,
    )

    resources = _rows(
        "RN Resource Profile",
        resolved_event,
        [
            "resource_name",
            "resource_type",
            "availability_status",
            "status",
            "capacity_description",
            "owner_type",
            "owner_id",
        ],
        80,
    )

    recovery = _rows(
        "RN Recovery Project",
        resolved_event,
        [
            "project_name",
            "project_type",
            "location",
            "progress_percent",
            "status",
            "priority",
            "target_amount",
            "current_amount",
        ],
        80,
    )

    programs = _rows(
        "RN Donor Program",
        resolved_event,
        [
            "program_name",
            "program_type",
            "status",
            "priority",
            "target_amount",
            "current_amount",
            "budget_target",
            "budget_spent",
        ],
        80,
    )

    special_programs = [
        x for x in programs
        if x.get("program_type")
        == "special_program"
    ]

    program_updates = _rows(
        "RN Donor Program Update",
        resolved_event,
        [
            "program",
            "update_type",
            "update_title",
            "progress_percent",
            "amount_spent",
            "amount_unit",
            "update_notes",
            "observed_at",
        ],
        80,
    )

    open_needs = (
        _active_count(needs)
        + _active_count(shelter_needs)
    )

    summary = {
        "posko_count": len(poskos),
        "open_need_count": open_needs,
        "open_needs_count": open_needs,
        "aid_offer_count": len(offers),
        "distribution_flow_count":
            len(flows),
        "medical_case_count":
            len(medical),
        "volunteer_count":
            len(volunteers),
        "volunteer_assignment_count":
            len(volunteers),
        "shelter_occupancy_count":
            len(shelter_occ),
        "shelter_need_count":
            len(shelter_needs),
        "search_found_report_count":
            len(missing) + len(found),
        "resource_profile_count":
            len(resources),
        "recovery_project_count":
            len(recovery),
        "program_count":
            len(programs),
        "special_program_count":
            len(special_programs),
        "stock_item_count":
            len(stock),
        "meal_production_count":
            len(kitchen),
        "missing_person_count":
            len(missing),
        "found_person_count":
            len(found),
    }

    alerts = []
    recommendations = []

    if open_needs:
        alerts.append({
            "type": "open_needs",
            "message":
                f"{open_needs} kebutuhan masih aktif.",
        })

    unavailable = [
        x for x in resources
        if _status(x)
        and _status(x) != "available"
    ]

    if unavailable:
        alerts.append({
            "type":
                "resource_availability",
            "message":
                f"{len(unavailable)} resource "
                "tidak available.",
        })

    recovery_active = [
        x for x in recovery
        if _status(x)
        not in {
            "completed",
            "cancelled",
        }
    ]

    # ----------------------------------------------------------
    # Priority decisions - real records first, computed fallback.
    # Each item is {title, reason} so the Control Centre panel
    # renders text instead of a bare "Prioritas" label.
    # ----------------------------------------------------------
    urgent_terms = {"critical", "urgent", "high", "tinggi", "darurat"}

    ranked_needs = sorted(
        (
            row for row in needs
            if _status(row) not in {
                "fulfilled", "closed", "cancelled", "completed",
            }
        ),
        key=lambda row: (
            0 if str(row.get("priority", "")).lower() in urgent_terms else 1,
            -_num(row.get("gap")),
        ),
    )

    for row in ranked_needs[:3]:
        item = (
            row.get("item_name")
            or row.get("title")
            or "Kebutuhan"
        )
        gap = _num(row.get("gap"))
        pct = _num(row.get("realization_percent"))
        unit = row.get("unit") or ""
        recommendations.append({
            "title": f"Tutup gap: {item}",
            "reason": (
                f"Realisasi {pct:.0f}%, sisa "
                f"{gap:,.0f} {unit}".strip()
                + (
                    f" - {row.get('location')}"
                    if row.get("location") else ""
                )
            ),
            "priority": row.get("priority") or "urgent",
        })

    action_plans = _rows(
        "RN Action Plan",
        resolved_event,
        [
            "title",
            "category",
            "priority",
            "status",
            "target_quantity",
            "target_unit",
            "assigned_to",
            "notes",
        ],
        20,
    )

    for plan in action_plans:
        if _status(plan) in {"completed", "cancelled", "done"}:
            continue
        target = _num(plan.get("target_quantity"))
        bits = [b for b in [
            plan.get("category"),
            (
                f"target {target:,.0f} {plan.get('target_unit') or ''}".strip()
                if target else None
            ),
            (
                f"PIC {plan.get('assigned_to')}"
                if plan.get("assigned_to") else None
            ),
            plan.get("status"),
        ] if b]
        recommendations.append({
            "title": plan.get("title") or "Rencana Aksi",
            "reason": " - ".join(bits) or (plan.get("notes") or ""),
            "priority": plan.get("priority") or "high",
        })

    for project in recovery_active:
        recommendations.append({
            "title": (
                project.get("project_name")
                or "Proyek recovery"
            ),
            "reason": (
                f"Progress {_num(project.get('progress_percent')):.0f}% - "
                f"{project.get('status') or 'aktif'}"
            ),
            "priority": project.get("priority") or "normal",
        })

    if not recommendations and open_needs:
        recommendations.append({
            "title": "Prioritaskan kebutuhan aktif",
            "reason": (
                f"{open_needs} kebutuhan masih terbuka - "
                "urutkan berdasarkan urgensi dan bukti."
            ),
            "priority": "high",
        })

    summary["alert_count"] = len(alerts)

    return {
        "generated_at": now_datetime(),
        "disaster_event_id":
            resolved_event,
        "disaster":
            disaster,
        "summary": summary,
        "alerts": alerts,
        "recommendations":
            recommendations,
        "poskos": poskos,
        "stock_summary": stock,
        "logistic_needs": needs,
        "aid_offers": offers,
        "distribution_flows": flows,
        "kitchen_meal_productions":
            kitchen,
        "kitchen_productions":
            kitchen,
        "medical_cases": medical,
        "shelter_occupancies":
            shelter_occ,
        "shelter_needs":
            shelter_needs,
        "missing_person_reports":
            missing,
        "found_person_reports":
            found,
        "search_found_matches":
            matches,
        "resource_profiles":
            resources,
        "recovery_projects":
            recovery,
        "donor_programs":
            programs,
        "donor_program_updates":
            program_updates,
        "special_programs":
            special_programs,
        "community_reports_predicted_needs":
            community_reports_ctx,
    }


def _public_scrub(value):
    """
    Remove private/contact/credential fields
    recursively from public Control Centre data.
    """
    blocked_parts = (
        "phone",
        "email",
        "contact",
        "password",
        "token",
        "secret",
        "api_key",
        "identity",
        "created_by_user",
        "last_updated_by_user",
    )

    if isinstance(value, list):
        return [
            _public_scrub(x)
            for x in value
        ]

    if isinstance(value, dict):
        result = {}

        for key, item in value.items():
            low = str(key).lower()

            if any(
                part in low
                for part in blocked_parts
            ):
                continue

            result[key] = (
                _public_scrub(item)
            )

        return result

    return value


@frappe.whitelist()
def context(disaster_event_id):
    return _build_context(
        disaster_event_id,
        public=False,
    )
