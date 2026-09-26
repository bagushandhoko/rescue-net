"""Resource tools — dashboards (Alat Kerja board, Control Centre, resource profile board, personal resources)."""

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
    ACTIVE_DEPLOYMENT,
    DEFAULT_DEMO_PROFILE_USER,
    _CATEGORY_LABELS,
    _CATEGORY_ORDER,
    _DEPLOY_STATUS_LABEL,
    _FUEL_KEYWORDS,
    _LEGEND_BY_STATUS,
    _PERSONAL_CATEGORIES,
    _PRIORITY_LABEL,
    _PRIORITY_RANK,
    _actor_name,
    _is_control_manager,
    _is_manager,
    _resource_capacity,
)
from rescue_net.resource_tools.resources import (  # noqa: F401
    _visible_request,
    _visible_resource,
)


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def dashboard(disaster_event=None):
    # RN_CANONICAL_EVENT disaster_event = resolve_disaster_event(disaster_event)
    disaster_event = resolve_disaster_event(disaster_event)
    actor = rn_actor(required=False)

    resource_filters = {}
    request_filters = {}

    if disaster_event:
        resource_filters[
            "disaster_event"
        ] = disaster_event

        request_filters[
            "disaster_event"
        ] = disaster_event

    resources = frappe.get_all(
        "RN Resource Profile",
        filters=resource_filters,
        fields=[
            "name",
            "disaster_event",
            "owner_type",
            "owner_id",
            "resource_name",
            "resource_type",
            "category",
            "quantity",
            "unit",
            "capacity_description",
            "availability_status",
            "current_location",
            "coverage_area",
            "verification_status",
        ],
        order_by="creation desc",
        limit_page_length=3000,
    )

    requests = frappe.get_all(
        "RN Work Tool Request",
        filters=request_filters,
        fields=[
            "name",
            "disaster_event",
            "requested_by_type",
            "requested_by_id",
            "tool_name",
            "tool_type",
            "quantity",
            "unit",
            "location",
            "needed_for",
            "priority",
            "required_operator_skill",
            "request_status",
            "verification_status",
        ],
        order_by="creation desc",
        limit_page_length=3000,
    )

    visible_resources = [
        x
        for x in resources
        if _visible_resource(
            actor,
            x,
        )
    ]

    visible_requests = [
        x
        for x in requests
        if _visible_request(
            actor,
            x,
        )
    ]

    resource_names = {
        x.name
        for x in visible_resources
    }

    request_names = {
        x.name
        for x in visible_requests
    }

    deployments = frappe.get_all(
        "RN Work Tool Deployment",
        fields=[
            "name",
            "work_tool_request",
            "resource_profile",
            "quantity_assigned",
            "unit",
            "deployment_status",
            "destination_location",
            "operator_skill",
            "deployed_at",
            "completed_at",
            "verification_status",
        ],
        order_by="creation desc",
        limit_page_length=3000,
    )

    visible_deployments = [
        x
        for x in deployments
        if (
            _is_control_manager(actor)
            or x.resource_profile
            in resource_names
            or x.work_tool_request
            in request_names
        )
    ]

    resource_output = []

    for row in visible_resources:
        item = dict(row)

        capacity = _resource_capacity(
            row.name
        )

        item[
            "active_allocated"
        ] = capacity[
            "active_allocated"
        ]

        item[
            "available_quantity"
        ] = capacity[
            "available_quantity"
        ]

        # PIC deliberately omitted.
        resource_output.append(item)

    return {
        "mode": (
            "control"
            if _is_control_manager(actor)
            else (
                "manager"
                if _is_manager(actor)
                else "viewer"
            )
        ),
        "resources": resource_output,
        "requests": visible_requests,
        "deployments":
            visible_deployments,
        "privacy": (
            "PIC phone tidak dikirim melalui dashboard. "
            "Gunakan restricted_resource bila berwenang."
        ),
    }


@frappe.whitelist()
def control_centre_resources():
    actor = rn_actor()

    if not _is_control_manager(actor):
        frappe.throw(
            "Akses Control Centre ditolak",
            frappe.PermissionError,
        )

    resources = frappe.get_all(
        "RN Resource Profile",
        fields=[
            "resource_type",
            "availability_status",
            "quantity",
        ],
        limit_page_length=5000,
    )

    requests = frappe.get_all(
        "RN Work Tool Request",
        fields=[
            "priority",
            "request_status",
        ],
        limit_page_length=5000,
    )

    deployments = frappe.get_all(
        "RN Work Tool Deployment",
        fields=[
            "deployment_status",
            "quantity_assigned",
        ],
        limit_page_length=5000,
    )

    resource_status = defaultdict(int)
    request_status = defaultdict(int)
    deployment_status = defaultdict(int)

    for row in resources:
        resource_status[
            row.availability_status
        ] += 1

    for row in requests:
        request_status[
            row.request_status
        ] += 1

    for row in deployments:
        deployment_status[
            row.deployment_status
        ] += 1

    urgent_open = sum(
        1
        for row in requests
        if (
            row.priority in {
                "urgent",
                "critical",
            }
            and row.request_status
            not in {
                "fulfilled",
                "cancelled",
            }
        )
    )

    return {
        "resource_count":
            len(resources),
        "request_count":
            len(requests),
        "deployment_count":
            len(deployments),
        "urgent_open":
            urgent_open,
        "resource_status":
            dict(resource_status),
        "request_status":
            dict(request_status),
        "deployment_status":
            dict(deployment_status),
        "privacy": (
            "Aggregate only. Tidak ada PIC/contact."
        ),
    }


def _fuel_status(qty, basis):
    if qty is None:
        return "tidak diketahui"
    if qty <= 0:
        return "kritis"
    if basis:
        ratio = flt(qty) / flt(basis)
        if ratio < 0.34:
            return "kritis"
        if ratio < 0.6:
            return "waspada"
    return "aman"


def _tb_drill(title, sub, href=""):
    return {"title": title, "sub": sub, "href": href}


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def tools_board(disaster_event=None):
    """Manajemen Alat Kerja dashboard (matches the DMS mock-up), guest read-only.

    One payload built from real RN Resource Profile / RN Work Tool Request /
    RN Work Tool Deployment rows plus a keyword-matched BBM/fuel slice of
    RN Stock Observation (same pattern as Dapur Umum's gas_bbm). PIC phone
    numbers are never included here — use restricted_resource() when
    authorized.
    """
    event = resolve_disaster_event(disaster_event)

    res_filters = {"disaster_event": event} if event else {}

    resources = frappe.get_all(
        "RN Resource Profile",
        filters=res_filters,
        fields=[
            "name", "resource_name", "resource_type", "category", "quantity",
            "unit", "availability_status", "current_location", "coverage_area",
            "verification_status", "modified", "owner_type", "owner_id",
            "canonical_category", "canonical_group", "canonical_item",
            "normalization_source", "normalization_confidence",
        ],
        order_by="category asc, resource_name asc",
        limit_page_length=2000,
    )

    requests = frappe.get_all(
        "RN Work Tool Request",
        filters=res_filters,
        fields=[
            "name", "tool_name", "tool_type", "quantity", "unit", "location",
            "needed_for", "priority", "required_operator_skill",
            "request_status", "verification_status",
        ],
        order_by="creation desc",
        limit_page_length=2000,
    )

    resource_names = {r.name for r in resources}
    request_names = {r.name for r in requests}

    all_deployments = frappe.get_all(
        "RN Work Tool Deployment",
        fields=[
            "name", "work_tool_request", "resource_profile", "quantity_assigned",
            "deployment_status", "destination_location", "operator_name",
            "operator_skill", "deployed_at", "completed_at",
        ],
        order_by="deployed_at desc, creation desc",
        limit_page_length=3000,
    )

    deployments = [
        d for d in all_deployments
        if d.resource_profile in resource_names or d.work_tool_request in request_names
    ]

    resource_by_name = {r.name: r for r in resources}
    request_by_name = {r.name: r for r in requests}

    # --- Totals / KPI ---
    alat_tersedia = [r for r in resources if r.availability_status == "available"]
    kebutuhan_alat = [r for r in requests if r.request_status not in ("fulfilled", "cancelled")]
    dispatch_berjalan = [d for d in deployments if d.deployment_status in ("deployed", "in_use")]
    alat_rusak = [r for r in resources if r.availability_status in ("maintenance", "unavailable")]

    active_operators = {}
    for d in deployments:
        if d.operator_name and d.deployment_status in ACTIVE_DEPLOYMENT:
            active_operators[d.operator_name] = d

    # --- Categories (6 tile inventory) ---
    cat_map = {}
    for r in resources:
        cat = cat_map.setdefault(r.category, {
            "category": r.category,
            "label": _CATEGORY_LABELS.get(r.category, r.category or "Lainnya"),
            "total": 0, "ready": 0, "assigned": 0, "maintenance": 0, "critical": 0,
        })
        cat["total"] += 1
        key = _LEGEND_BY_STATUS.get(r.availability_status)
        if key:
            cat[key] += 1
    categories = sorted(
        cat_map.values(),
        key=lambda c: _CATEGORY_ORDER.index(c["category"]) if c["category"] in _CATEGORY_ORDER else 99,
    )

    # --- BBM & Support Operasional (fuel) ---
    fuel_rows = frappe.get_all(
        "RN Stock Observation",
        filters=res_filters,
        fields=["item_name", "unit", "quantity", "quantity_max", "stock_state", "observed_at"],
        order_by="observed_at desc",
        limit_page_length=500,
    )
    seen_fuel = set()
    fuel = []
    for row in fuel_rows:
        key = (row.item_name, row.unit or "")
        if key in seen_fuel or not any(k in (row.item_name or "").lower() for k in _FUEL_KEYWORDS):
            continue
        seen_fuel.add(key)
        status = _fuel_status(flt(row.quantity) if row.quantity is not None else None, row.quantity_max)
        fuel.append({
            "item_name": row.item_name,
            "unit": row.unit,
            "stok": row.quantity,
            "kapasitas": row.quantity_max,
            "status": status,
            "observed_at": row.observed_at,
        })
    bbm_kritis = [f for f in fuel if f["status"] == "kritis"]

    totals = {
        "alat_tersedia": len(alat_tersedia),
        "kebutuhan_alat": len(kebutuhan_alat),
        "operator_aktif": len(active_operators),
        "dispatch_berjalan": len(dispatch_berjalan),
        "bbm_kritis": len(bbm_kritis),
        "alat_rusak": len(alat_rusak),
    }

    kpi_items = {
        "alat_tersedia_items": [
            _tb_drill(r.resource_name, f"{_CATEGORY_LABELS.get(r.category, r.category)} · {r.current_location or '-'}")
            for r in alat_tersedia
        ],
        "kebutuhan_alat_items": [
            _tb_drill(r.tool_name, f"{r.location or '-'} · {_PRIORITY_LABEL.get(r.priority, r.priority)} · {r.request_status}")
            for r in kebutuhan_alat
        ],
        "operator_aktif_items": [
            _tb_drill(name, f"{d.operator_skill or '-'} · {d.destination_location or '-'} · {_DEPLOY_STATUS_LABEL.get(d.deployment_status, d.deployment_status)}")
            for name, d in active_operators.items()
        ],
        "dispatch_berjalan_items": [
            _tb_drill(
                (resource_by_name.get(d.resource_profile) or {}).get("resource_name") or "Alat",
                f"{d.destination_location or '-'} · operator {d.operator_name or '-'}",
            )
            for d in dispatch_berjalan
        ],
        "bbm_kritis_items": [
            _tb_drill(f["item_name"], f"Stok {f['stok']} {f['unit']} tersisa")
            for f in bbm_kritis
        ],
        "alat_rusak_items": [
            _tb_drill(r.resource_name, f"{r.current_location or '-'} · {r.availability_status}")
            for r in alat_rusak
        ],
    }

    # --- Operator & Tenaga Teknis ---
    operators = []
    seen_ops = set()
    for d in deployments:
        if not d.operator_name or d.operator_name in seen_ops:
            continue
        seen_ops.add(d.operator_name)
        operators.append({
            "name": d.operator_name,
            "skill": d.operator_skill or "-",
            "status": d.deployment_status,
            "status_label": _DEPLOY_STATUS_LABEL.get(d.deployment_status, d.deployment_status),
            "location": d.destination_location or "-",
        })

    # --- Matching Kebutuhan Alat ---
    open_requests = sorted(
        [r for r in requests if r.request_status == "requested"],
        key=lambda r: _PRIORITY_RANK.get(r.priority, 3),
    )
    matches = []
    for r in open_requests:
        candidates = [
            x for x in resources
            if x.category == r.tool_type and x.availability_status == "available"
        ]
        matches.append({
            "request": r.name,
            "tool_name": r.tool_name,
            "location": r.location,
            "priority": r.priority,
            "priority_label": _PRIORITY_LABEL.get(r.priority, r.priority),
            "quantity": r.quantity,
            "needed_for": r.needed_for,
            "candidate_count": len(candidates),
            "candidate_resource": candidates[0].resource_name if candidates else None,
            "candidate_location": candidates[0].current_location if candidates else None,
        })

    # --- Jadwal Dispatch Alat ---
    dispatch = []
    for d in deployments:
        res = resource_by_name.get(d.resource_profile)
        req = request_by_name.get(d.work_tool_request)
        dispatch.append({
            "deployment": d.name,
            "tool_name": (res.resource_name if res else None) or (req.tool_name if req else "Alat"),
            "operator": d.operator_name or "-",
            "destination": d.destination_location or "-",
            "status": d.deployment_status,
            "status_label": _DEPLOY_STATUS_LABEL.get(d.deployment_status, d.deployment_status),
            "deployed_at": d.deployed_at,
            "completed_at": d.completed_at,
        })

    # --- Lokasi Kerja & Produktivitas ---
    by_loc = defaultdict(list)
    for d in deployments:
        if d.destination_location:
            by_loc[d.destination_location].append(d)
    sites = []
    for loc, rows in by_loc.items():
        total = len(rows)
        completed = sum(1 for x in rows if x.deployment_status == "completed")
        sites.append({
            "location": loc,
            "total": total,
            "completed": completed,
            "progress_pct": round(100.0 * completed / total, 1) if total else 0,
        })
    sites.sort(key=lambda s: -s["total"])

    # --- Hambatan Alat Kerja ---
    blockers = []
    for r in requests:
        if r.priority in ("critical", "urgent") and r.request_status == "requested":
            blockers.append({
                "type": "kebutuhan_belum_terpenuhi",
                "label": r.tool_name,
                "detail": f"{r.location or '-'} · prioritas {_PRIORITY_LABEL.get(r.priority, r.priority)}",
                "severity": r.priority,
            })
    for f in bbm_kritis:
        blockers.append({
            "type": "bbm_kritis",
            "label": f["item_name"],
            "detail": f"Stok {f['stok']} {f['unit']} tersisa",
            "severity": "critical",
        })
    for r in alat_rusak:
        if r.availability_status == "unavailable":
            blockers.append({
                "type": "alat_rusak",
                "label": r.resource_name,
                "detail": f"{r.current_location or '-'} · perlu perbaikan",
                "severity": "urgent",
            })
    blockers.sort(key=lambda b: _PRIORITY_RANK.get(b["severity"], 3))

    # --- Ringkasan Hari Ini ---
    today_str = nowdate()
    dispatch_selesai_today = sum(
        1 for d in deployments
        if d.deployment_status == "completed" and d.completed_at
        and str(d.completed_at)[:10] == today_str
    )
    kerusakan_baru = sum(
        1 for r in resources
        if r.availability_status in ("maintenance", "unavailable")
        and r.modified and str(r.modified)[:10] == today_str
    )
    total_hours = 0.0
    for d in deployments:
        if d.deployment_status == "completed" and d.deployed_at and d.completed_at \
                and str(d.completed_at)[:10] == today_str:
            try:
                total_hours += time_diff_in_hours(get_datetime(d.completed_at), get_datetime(d.deployed_at))
            except Exception:
                pass
    penggunaan_pct = round(
        100.0 * len(dispatch_berjalan) / len(resources), 1
    ) if resources else 0.0

    summary = {
        "penggunaan_pct": penggunaan_pct,
        "jam_operasional": round(total_hours, 1),
        "dispatch_selesai": dispatch_selesai_today,
        "kerusakan_baru": kerusakan_baru,
    }

    # --- Kelompok Alat (AI Normalisasi Lintas Posko) ---
    # Groups every resource (any owner_type — organization/posko/individual)
    # by a canonical group name so the same equipment scattered across many
    # posko/owners with different raw names or units still rolls up into one
    # line. Uses the stored canonical_* fields when a human/manager already
    # set them (normalization_status=accepted); otherwise falls back to the
    # same rule-based classify_text() used for RN Community Need/RN Stock
    # Observation elsewhere in the app, honestly labelled "rule"/"ai" per
    # normalization_source (this app never claims a black-box "AI" call —
    # the rules are deterministic keyword matches).
    from rescue_net.intelligence.packaging import bucket_quantity

    equip_groups = defaultdict(lambda: {
        "total_qty": 0.0, "unit_breakdown": defaultdict(float),
        "locations": set(), "confidence_scores": [], "sources": set(),
        "item_count": 0, "category": None,
        "base_breakdown": defaultdict(lambda: {"measurable": 0.0, "estimated": 0.0}),
        "unmeasurable_count": 0,
    })
    for r in resources:
        if r.canonical_group:
            group_key = r.canonical_group
            cat_label = r.canonical_category or _CATEGORY_LABELS.get(r.category, r.category)
            source = r.normalization_source or "rule"
            confidence = r.normalization_confidence
        else:
            guess = classify_text(r.resource_name or r.category or "")
            group_key = guess["canonical_group"] or _CATEGORY_LABELS.get(r.category, r.category) or "Lainnya"
            cat_label = guess["canonical_category"] or _CATEGORY_LABELS.get(r.category, r.category)
            source = "rule" if guess["canonical_group"] else "tidak_diketahui"
            confidence = guess["normalization_confidence"] if guess["canonical_group"] else None

        g = equip_groups[group_key]
        g["category"] = cat_label
        g["total_qty"] += flt(r.quantity)
        g["unit_breakdown"][normalize_unit(r.unit)] += flt(r.quantity)

        bkt = bucket_quantity(
            r.canonical_item, r.canonical_group, r.quantity, r.unit,
            None, None, None, r.resource_name or "", stored=None,
        )
        if bkt["unmeasurable"]:
            g["unmeasurable_count"] += 1
        else:
            bb = g["base_breakdown"][bkt["base_unit"] or normalize_unit(r.unit) or "unit"]
            bb["measurable"] += bkt["measurable"]
            bb["estimated"] += bkt["estimated"]

        if r.current_location:
            g["locations"].add(r.current_location)
        if confidence:
            g["confidence_scores"].append(confidence)
        g["sources"].add(source)
        g["item_count"] += 1

    groups = []
    for group_key, g in equip_groups.items():
        same_unit = len(g["unit_breakdown"]) == 1
        base_breakdown = [
            {"base_unit": bu, "measurable": round(v["measurable"], 1),
             "estimated": round(v["estimated"], 1)}
            for bu, v in sorted(
                g["base_breakdown"].items(),
                key=lambda kv: -(kv[1]["measurable"] + kv[1]["estimated"]))
        ]
        groups.append({
            "group": group_key,
            "category": g["category"],
            "item_count": g["item_count"],
            "total_qty": round(g["total_qty"], 1) if same_unit else None,
            "unit_breakdown": [
                {"unit": u, "qty": round(q, 1)} for u, q in g["unit_breakdown"].items()
            ],
            "base_breakdown": base_breakdown,
            "unmeasurable_count": g["unmeasurable_count"],
            "same_unit": same_unit,
            "posko_spread": len(g["locations"]),
            "avg_confidence": (
                round(sum(g["confidence_scores"]) / len(g["confidence_scores"]))
                if g["confidence_scores"] else None
            ),
            "source": (
                "manual" if "manual" in g["sources"]
                else "ai" if "ai" in g["sources"]
                else "rule" if "rule" in g["sources"]
                else "tidak_diketahui"
            ),
        })
    groups.sort(key=lambda x: -x["item_count"])

    return {
        "disaster_event": event,
        "generated_at": now_datetime(),
        "totals": totals,
        "kpi_items": kpi_items,
        "categories": categories,
        "operators": operators,
        "matches": matches,
        "dispatch": dispatch,
        "sites": sites,
        "fuel": fuel,
        "blockers": blockers,
        "summary": summary,
        "groups": groups,
        "groups_note": (
            "Pengelompokan otomatis lintas posko/pemilik berdasarkan nama alat "
            "(aturan kata kunci, ditandai 'rule', atau ditetapkan manual oleh "
            "operator, ditandai 'manual'). Alat dengan satuan berbeda "
            "ditampilkan terpisah per satuan, tidak dijumlahkan langsung."
        ),
        "asset_registry": [
            {
                "code": r.name,
                "resource_name": r.resource_name,
                "category": _CATEGORY_LABELS.get(r.category, r.category),
                "status": r.availability_status,
                "location": r.current_location or "-",
            }
            for r in resources
        ],
        "privacy": (
            "Aggregate only. PIC/contact tidak dikirim melalui board publik."
        ),
    }


def _split_lines(text):
    return [line.strip() for line in (text or "").split("\n") if line.strip()]


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def resource_profile_board(user_account=None):
    """Profil Sumber Daya (matches the DMS mock-up) — a single volunteer/
    member's own profile: verified-contact chips, skills, personally-owned
    vehicles/facilities/aid items (RN Resource Profile, owner_type=
    individual), service areas + availability schedule (RN Volunteer
    Profile), and open personal support needs (RN Work Tool Request,
    requested_by_type=other). Guest-read; falls back to a seeded demo
    profile when no session/param identifies a user, same convention as
    every other board defaulting to event-sim-001 when no event is given.
    """
    actor = rn_actor(required=False)
    target = user_account or _actor_name(actor) or DEFAULT_DEMO_PROFILE_USER

    ua = frappe.db.get_value(
        "RN User Account", target,
        ["name", "title", "username", "phone", "email", "role", "organization", "posko", "status", "creation"],
        as_dict=True,
    )
    if not ua:
        frappe.throw("Akun tidak ditemukan", frappe.DoesNotExistError)

    org_title = (
        frappe.db.get_value("RN Organization", ua.organization, "title")
        if ua.organization else None
    )

    vp = frappe.db.get_value(
        "RN Volunteer Profile", {"user_account": target},
        ["name", "volunteer_name", "contact", "main_skill", "skill_tags", "availability_status",
         "duration_available", "current_location", "assigned_posko", "skill_category", "preferences",
         "equipment_owned", "needs_transport", "notes", "verification_status",
         "service_areas", "availability_schedule"],
        as_dict=True,
    )

    resources = frappe.get_all(
        "RN Resource Profile",
        filters={"owner_type": "individual", "owner_id": target},
        fields=["name", "resource_name", "category", "resource_type", "quantity", "unit",
                "capacity_description", "availability_status", "current_location", "notes"],
        order_by="creation desc",
        limit_page_length=200,
    )

    needs = frappe.get_all(
        "RN Work Tool Request",
        filters={"requested_by_type": "other", "requested_by_id": target},
        fields=["name", "tool_name", "tool_type", "quantity", "unit", "priority",
                "request_status", "needed_for", "location"],
        order_by="creation desc",
        limit_page_length=200,
    )

    by_cat = {c: [] for c in _PERSONAL_CATEGORIES}
    for r in resources:
        by_cat.setdefault(r.category or "lainnya", []).append(r)

    skills = []
    if vp:
        if vp.main_skill:
            skills.append(vp.main_skill)
        skills += [
            s.strip() for s in (vp.skill_tags or "").split(",")
            if s.strip() and s.strip() not in skills
        ]

    verified = bool(vp and vp.verification_status == "verified")
    name_display = (vp.volunteer_name if vp else None) or ua.title or ua.username

    can_edit = bool(actor and _actor_name(actor) == target)
    # Phone / email are shown only to the profile's owner (and System
    # Manager); everyone else — Guest included — sees the verified chips only.
    show_contacts = can_edit or is_system_manager()

    return {
        "target": target,
        "volunteer_profile": vp.name if vp else None,
        "generated_at": now_datetime(),
        "can_edit": can_edit,
        "identity": {
            "name": name_display,
            "role": (vp.main_skill if vp else None) or ua.role,
            "organization": org_title,
            "location": (vp.current_location if vp else None) or "-",
            "email": ua.email if show_contacts else None,
            "phone": (ua.phone or (vp.contact if vp else None)) if show_contacts else None,
            "about": (vp.notes if vp else None) or "-",
            "joined_at": ua.creation,
            "aktif": (vp.availability_status != "unavailable") if vp else (ua.status == "active"),
        },
        "chips": {
            "peran_utama": ((vp.main_skill if vp else None) or ua.role or "-"),
            "peran_tipe": "Relawan" if vp else "Anggota Organisasi",
            "trust_label": "Terverifikasi" if verified else "Belum Terverifikasi",
            "email_verified": bool(ua.email),
            "phone_verified": bool(ua.phone or (vp.contact if vp else None)),
            "id_verified": verified,
        },
        "skills": [
            {"label": s, "status_label": "Tersertifikasi" if verified else "Belum Tersertifikasi"}
            for s in skills
        ],
        "kendaraan": by_cat.get("kendaraan", []),
        "fasilitas": by_cat.get("fasilitas", []),
        "barang_bantuan": by_cat.get("barang_bantuan", []),
        "service_areas": _split_lines(vp.service_areas if vp else None),
        "schedule": _split_lines(vp.availability_schedule if vp else None),
        "support_needs": needs,
        "raw": {
            "skill_tags": (vp.skill_tags if vp else None) or "",
            "service_areas": (vp.service_areas if vp else None) or "",
            "availability_schedule": (vp.availability_schedule if vp else None) or "",
            "current_location": (vp.current_location if vp else None) or "",
            "notes": (vp.notes if vp else None) or "",
        },
    }


@frappe.whitelist()
def add_personal_resource(
    resource_name,
    category,
    resource_type=None,
    quantity=1,
    unit="unit",
    capacity_description=None,
    availability_status="available",
    current_location=None,
    notes=None,
    disaster_event=None,
):
    """Self-service add for Profil Sumber Daya's Kendaraan/Fasilitas/Bantuan
    Barang cards — an individual manages their own RN Resource Profile rows
    without needing a MANAGER_ROLES operator role (unlike
    create_resource_profile, which is for org/posko-owned equipment)."""
    disaster_event = resolve_disaster_event(disaster_event)
    actor = rn_actor()
    owner_id = _actor_name(actor)

    if not owner_id:
        frappe.throw("Akun Rescue-Net aktif tidak ditemukan", frappe.PermissionError)

    if category not in _PERSONAL_CATEGORIES:
        frappe.throw("Kategori tidak valid")

    doc = frappe.new_doc("RN Resource Profile")
    doc.disaster_event = disaster_event
    doc.owner_type = "individual"
    doc.owner_id = owner_id
    doc.resource_name = resource_name
    doc.resource_type = resource_type or category
    doc.category = category
    doc.quantity = flt(quantity or 1)
    doc.unit = unit
    doc.capacity_description = capacity_description
    doc.availability_status = availability_status
    doc.current_location = current_location
    doc.notes = notes
    doc.verification_status = "self_reported"
    doc.insert(ignore_permissions=True)

    return {
        "resource_profile": doc.name,
        "category": doc.category,
        "availability_status": doc.availability_status,
    }


@frappe.whitelist()
def add_personal_support_need(
    tool_name,
    tool_type=None,
    quantity=1,
    unit="unit",
    location=None,
    needed_for=None,
    priority="normal",
    notes=None,
    disaster_event=None,
):
    """Self-service "Ajukan Kebutuhan" for Profil Sumber Daya's Kebutuhan
    Support card — creates a real RN Work Tool Request for the logged-in
    individual (requested_by_type="other", the closest fit the doctype's
    own validate() allows for a non-posko/non-organization requester)."""
    disaster_event = resolve_disaster_event(disaster_event)
    actor = rn_actor()
    owner_id = _actor_name(actor)

    if not owner_id:
        frappe.throw("Akun Rescue-Net aktif tidak ditemukan", frappe.PermissionError)

    doc = frappe.new_doc("RN Work Tool Request")
    doc.disaster_event = disaster_event
    doc.requested_by_type = "other"
    doc.requested_by_id = owner_id
    doc.tool_name = tool_name
    doc.tool_type = tool_type
    doc.quantity = flt(quantity or 1)
    doc.unit = unit
    doc.location = location
    doc.needed_for = needed_for
    doc.priority = priority
    doc.request_status = "requested"
    doc.notes = notes
    doc.created_by_user = owner_id
    doc.verification_status = "self_reported"
    doc.insert(ignore_permissions=True)

    return {
        "work_tool_request": doc.name,
        "status": doc.request_status,
    }
