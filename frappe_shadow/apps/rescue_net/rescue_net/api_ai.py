import hashlib
import json

import frappe
import requests
from frappe.utils import now_datetime

from rescue_net.access_policy import (
    is_system_manager,
    rn_actor,
)


DEFAULT_MODEL = "gpt-4o-mini"


def _require_login():
    user = frappe.session.user
    if not user or user == "Guest":
        frappe.throw("Authentication required", frappe.PermissionError)
    return user


def _is_manager(user):
    return (
        user == "Administrator"
        or "System Manager" in frappe.get_roles(user)
    )


def _require_control():
    user = _require_login()

    if _is_manager(user):
        return user

    if frappe.db.exists("DocType", "RN User Account"):
        meta = frappe.get_meta("RN User Account")

        if (
            meta.has_field("frappe_user")
            and meta.has_field("role")
        ):
            role = frappe.db.get_value(
                "RN User Account",
                {"frappe_user": user},
                "role",
            )

            if role == "command_center":
                return user

    frappe.throw(
        "AI Situation Analyst hanya untuk Control Centre",
        frappe.PermissionError,
    )


def _assert_self(user_id):
    actor = _require_login()
    user_id = (user_id or "").strip()

    if not user_id:
        frappe.throw("User ID wajib diisi")

    if user_id != actor and not _is_manager(actor):
        frappe.throw(
            "AI setting hanya dapat dikelola oleh pemiliknya",
            frappe.PermissionError,
        )

    return actor, user_id


def _setting_name(user_id, provider):
    raw = (
        f"{user_id.strip().lower()}|"
        f"{(provider or 'openai').strip().lower()}"
    )
    return "rn-ai-" + hashlib.sha256(
        raw.encode()
    ).hexdigest()[:24]


def _safe_setting(doc):
    return {
        "id": doc.name,
        "user_id": doc.user_id,
        "organization_id": doc.organization_id,
        "provider": doc.provider,
        "model_name": doc.model_name,
        "api_key_last4": doc.api_key_last4,
        "api_key_label": doc.api_key_label,
        "status": doc.status,
        "created_at": doc.creation,
        "updated_at": doc.modified,
    }


@frappe.whitelist()
def session_info():
    from frappe.sessions import get_csrf_token

    user = _require_login()
    organization_id = None

    if frappe.db.exists("DocType", "RN User Account"):
        meta = frappe.get_meta("RN User Account")

        if meta.has_field("frappe_user"):
            for fieldname in (
                "organization",
                "organization_id",
            ):
                if meta.has_field(fieldname):
                    organization_id = frappe.db.get_value(
                        "RN User Account",
                        {"frappe_user": user},
                        fieldname,
                    )
                    if organization_id:
                        break

    return {
        "user": user,
        "organization_id": organization_id,
        "csrf_token": get_csrf_token(),
    }


@frappe.whitelist()
def save_user_key(
    user_id,
    api_key,
    organization_id=None,
    provider="openai",
    model_name=DEFAULT_MODEL,
    api_key_label=None,
):
    actor, user_id = _assert_self(user_id)

    provider = (provider or "openai").strip().lower()
    api_key = (api_key or "").strip()

    if len(api_key) < 20:
        frappe.throw("API key is too short")

    name = _setting_name(user_id, provider)

    if frappe.db.exists("RN AI User Setting", name):
        doc = frappe.get_doc(
            "RN AI User Setting",
            name,
        )
    else:
        doc = frappe.new_doc(
            "RN AI User Setting"
        )
        doc.user_id = user_id
        doc.provider = provider

    doc.organization_id = organization_id
    doc.model_name = model_name or DEFAULT_MODEL

    # Password field -> Frappe encrypted storage.
    doc.api_key = api_key
    doc.api_key_last4 = api_key[-4:]
    doc.api_key_label = api_key_label

    doc.status = "active"
    doc.owner_type = "user"
    doc.owner_id = user_id

    if doc.is_new():
        doc.created_by_user_id = actor

    doc.updated_by_user_id = actor

    if doc.is_new():
        doc.insert(ignore_permissions=True)
    else:
        doc.save(ignore_permissions=True)

    return {
        "status": "saved",
        "message": (
            "AI key saved encrypted. "
            "Secret key is not returned."
        ),
        "setting": _safe_setting(doc),
    }


@frappe.whitelist()
def get_user_key_status(
    user_id,
    provider="openai",
):
    _actor, user_id = _assert_self(user_id)

    provider = (provider or "openai").strip().lower()
    name = _setting_name(user_id, provider)

    if not frappe.db.exists(
        "RN AI User Setting",
        name,
    ):
        return {
            "user_id": user_id,
            "provider": provider,
            "key_exists": False,
            "message":
                "No active AI key configured",
        }

    doc = frappe.get_doc(
        "RN AI User Setting",
        name,
    )

    if doc.status != "active":
        return {
            "user_id": user_id,
            "provider": provider,
            "key_exists": False,
            "message":
                "No active AI key configured",
        }

    return {
        "user_id": user_id,
        "provider": provider,
        "key_exists": True,
        "masked_key":
            "****" + (doc.api_key_last4 or ""),
        "setting": _safe_setting(doc),
    }


@frappe.whitelist()
def update_user_model(
    user_id,
    model_name,
    provider="openai",
):
    actor, user_id = _assert_self(user_id)

    provider = (provider or "openai").strip().lower()
    name = _setting_name(user_id, provider)

    if not frappe.db.exists(
        "RN AI User Setting",
        name,
    ):
        frappe.throw(
            "AI user setting not found"
        )

    doc = frappe.get_doc(
        "RN AI User Setting",
        name,
    )

    if doc.status != "active":
        frappe.throw(
            "AI user setting not found"
        )

    doc.model_name = (
        model_name or DEFAULT_MODEL
    )
    doc.updated_by_user_id = actor
    doc.save(ignore_permissions=True)

    return _safe_setting(doc)


@frappe.whitelist()
def delete_user_key(
    user_id,
    provider="openai",
):
    actor, user_id = _assert_self(user_id)

    provider = (provider or "openai").strip().lower()
    name = _setting_name(user_id, provider)

    if not frappe.db.exists(
        "RN AI User Setting",
        name,
    ):
        return {
            "status": "not_found",
            "user_id": user_id,
            "provider": provider,
        }

    doc = frappe.get_doc(
        "RN AI User Setting",
        name,
    )

    if doc.status != "active":
        return {
            "status": "not_found",
            "user_id": user_id,
            "provider": provider,
        }

    doc.status = "deleted"

    # Security hardening over legacy:
    # deleting a key removes the secret too.
    doc.api_key = None
    doc.api_key_last4 = None

    doc.updated_by_user_id = actor
    doc.save(ignore_permissions=True)

    return {
        "status": "deleted",
        "setting": _safe_setting(doc),
    }


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


@frappe.whitelist()
def context(disaster_event_id):
    _require_login()
    _ai_scope_poskos(refresh=True)

    poskos = _rows(
        "RN Posko",
        disaster_event_id,
        [
            "posko_name",
            "location",
            "operational_status",
            "verification_status",
        ],
    )

    needs = _rows(
        "RN Logistic Need",
        disaster_event_id,
        [
            "item_name",
            "quantity",
            "unit",
            "priority",
            "status",
            "need_status",
            "location",
        ],
    )

    offers = _rows(
        "RN Aid Offer",
        disaster_event_id,
        [
            "item_name",
            "quantity",
            "unit",
            "status",
        ],
    )

    flows = _rows(
        "RN Distribution Flow",
        disaster_event_id,
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
        disaster_event_id,
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
        disaster_event_id,
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
        disaster_event_id,
        [
            "triage_level",
            "case_status",
            "status",
            "posko",
        ],
        50,
    )

    shelter_occ = _rows(
        "RN Shelter Occupancy",
        disaster_event_id,
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
        disaster_event_id,
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
        disaster_event_id,
        ["status"],
        50,
    )

    found = _rows(
        "RN Found Person Report",
        disaster_event_id,
        ["status"],
        50,
    )

    matches = _rows(
        "RN Search Found Match",
        disaster_event_id,
        [
            "status",
            "match_status",
            "confidence",
        ],
        50,
    )

    resources = _rows(
        "RN Resource Profile",
        disaster_event_id,
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
        disaster_event_id,
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
        disaster_event_id,
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
    }

    alerts = []
    recommendations = []

    if open_needs:
        alerts.append({
            "type": "open_needs",
            "message":
                f"{open_needs} kebutuhan masih aktif.",
        })
        recommendations.append(
            "Prioritaskan kebutuhan aktif "
            "berdasarkan urgensi dan bukti."
        )

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

    if recovery_active:
        recommendations.append(
            f"Pantau {len(recovery_active)} "
            "proyek recovery aktif."
        )

    summary["alert_count"] = len(alerts)

    return {
        "generated_at": now_datetime(),
        "disaster_event_id":
            disaster_event_id,
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
        "special_programs":
            special_programs,
    }


@frappe.whitelist()
def ask(
    user_id,
    disaster_event_id,
    question,
    provider="openai",
):
    _actor, user_id = _assert_self(
        user_id
    )

    question = (question or "").strip()

    if not question:
        frappe.throw(
            "Question is required"
        )

    provider = (
        provider or "openai"
    ).strip().lower()

    name = _setting_name(
        user_id,
        provider,
    )

    if not frappe.db.exists(
        "RN AI User Setting",
        name,
    ):
        frappe.throw(
            "No active AI key configured "
            "for this user. Please add key "
            "in AI Settings."
        )

    setting = frappe.get_doc(
        "RN AI User Setting",
        name,
    )

    if setting.status != "active":
        frappe.throw(
            "No active AI key configured "
            "for this user. Please add key "
            "in AI Settings."
        )

    if provider != "openai":
        frappe.throw(
            "AI provider is not supported"
        )

    api_key = setting.get_password(
        "api_key"
    )

    if not api_key:
        frappe.throw(
            "No active AI key configured "
            "for this user. Please add key "
            "in AI Settings."
        )

    ctx = context(
        disaster_event_id
    )

    compact = {
        "summary":
            ctx.get("summary"),
        "alerts":
            ctx.get("alerts", [])[:30],
        "recommendations":
            ctx.get(
                "recommendations",
                [],
            )[:30],
        "stock_summary":
            ctx.get(
                "stock_summary",
                [],
            )[:80],
        "logistic_needs":
            ctx.get(
                "logistic_needs",
                [],
            )[:80],
        "aid_offers":
            ctx.get(
                "aid_offers",
                [],
            )[:80],
        "distribution_flows":
            ctx.get(
                "distribution_flows",
                [],
            )[:80],
        "kitchen_meal_productions":
            ctx.get(
                "kitchen_meal_productions",
                [],
            )[:50],
        "medical_cases":
            ctx.get(
                "medical_cases",
                [],
            )[:50],
        "shelter_occupancies":
            ctx.get(
                "shelter_occupancies",
                [],
            )[:50],
        "shelter_needs":
            ctx.get(
                "shelter_needs",
                [],
            )[:50],
        "missing_person_reports":
            ctx.get(
                "missing_person_reports",
                [],
            )[:50],
        "found_person_reports":
            ctx.get(
                "found_person_reports",
                [],
            )[:50],
        "search_found_matches":
            ctx.get(
                "search_found_matches",
                [],
            )[:50],
        "resource_profiles":
            ctx.get(
                "resource_profiles",
                [],
            )[:80],
        "recovery_projects":
            ctx.get(
                "recovery_projects",
                [],
            )[:80],
        "special_programs":
            ctx.get(
                "special_programs",
                [],
            )[:80],
    }

    system_prompt = """
You are Rescue-Net AI Situation Analyst.
Analyze disaster response data operationally.
Be concise, practical, and safety-focused.
Never expose API keys or credentials.
For medical/search-found data, do not infer
or expose unnecessary personal identity.
Prioritize urgent needs, logistics gaps,
shelter capacity, medical risk, stock
shortages, resource availability and
recovery coordination.
"""

    payload = {
        "model":
            setting.model_name
            or DEFAULT_MODEL,
        "messages": [
            {
                "role": "system",
                "content":
                    system_prompt,
            },
            {
                "role": "user",
                "content":
                    "Rescue-Net context JSON:\n"
                    + json.dumps(
                        compact,
                        default=str,
                    ),
            },
            {
                "role": "user",
                "content": question,
            },
        ],
        "temperature": 0.2,
    }

    try:
        response = requests.post(
            "https://api.openai.com/"
            "v1/chat/completions",
            headers={
                "Authorization":
                    "Bearer " + api_key,
                "Content-Type":
                    "application/json",
            },
            json=payload,
            timeout=60,
        )
    except Exception:
        frappe.throw(
            "AI request failed. Please "
            "check AI provider, model, "
            "quota, and network settings."
        )

    if response.status_code == 401:
        frappe.throw(
            "AI request failed: invalid "
            "API key. Please update your "
            "AI key in AI Settings.",
            frappe.AuthenticationError,
        )

    if not response.ok:
        frappe.throw(
            "AI request failed. Please "
            "check AI provider, model, "
            "quota, and network settings."
        )

    data = response.json()

    try:
        answer = data[
            "choices"
        ][0]["message"]["content"]
    except Exception:
        frappe.throw(
            "AI provider returned an "
            "invalid response."
        )

    return {
        "user_id": user_id,
        "provider": provider,
        "model_name":
            setting.model_name
            or DEFAULT_MODEL,
        "disaster_event_id":
            disaster_event_id,
        "question": question,
        "answer": answer,
        "context_summary":
            ctx.get("summary"),
        "alerts_count":
            len(ctx.get("alerts", [])),
        "recommendations_count":
            len(
                ctx.get(
                    "recommendations",
                    [],
                )
            ),
        "key_used":
            "****"
            + (
                setting.api_key_last4
                or ""
            ),
    }
