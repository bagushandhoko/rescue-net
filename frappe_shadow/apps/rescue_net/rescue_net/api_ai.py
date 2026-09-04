import hashlib
import json

import frappe
from rescue_net.reference_resolver import resolve_disaster_event, resolve_posko
import requests
from frappe.utils import now_datetime

from rescue_net.access_policy import (
    can_manage_organization,
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


# ============================================================
# BYOK — organisation-scoped AI keys + usage logging.
# An AI key belongs to a personal user OR a verified organisation. Rescue-Net
# is only the orchestrator: it never returns the secret, never logs it, and
# writes an RN AI Usage Log row (counts only) per call.
# ============================================================

def _org_setting_name(organization_id, provider):
    raw = f"org:{(organization_id or '').strip().lower()}|{(provider or 'openai').strip().lower()}"
    return "rn-ai-" + hashlib.sha256(raw.encode()).hexdigest()[:24]


def _assert_org_admin(organization_id):
    actor = rn_actor(required=True)
    if not organization_id:
        frappe.throw("Organization ID wajib diisi")
    if not (is_system_manager() or can_manage_organization(actor, organization_id)):
        frappe.throw("Hanya pengelola organisasi yang dapat mengatur kunci AI organisasi.",
                     frappe.PermissionError)
    return frappe.session.user


@frappe.whitelist()
def save_org_key(organization_id, api_key, provider="openai",
                 model_name=DEFAULT_MODEL, api_key_label=None):
    actor = _assert_org_admin(organization_id)
    provider = (provider or "openai").strip().lower()
    api_key = (api_key or "").strip()
    if len(api_key) < 20:
        frappe.throw("API key is too short")

    name = _org_setting_name(organization_id, provider)
    if frappe.db.exists("RN AI User Setting", name):
        doc = frappe.get_doc("RN AI User Setting", name)
    else:
        doc = frappe.new_doc("RN AI User Setting")
        doc.name = name
        doc.provider = provider
    doc.user_id = "org:" + organization_id
    doc.organization_id = organization_id
    doc.owner_type = "organization"
    doc.owner_id = organization_id
    doc.model_name = model_name or DEFAULT_MODEL
    doc.api_key = api_key
    doc.api_key_last4 = api_key[-4:]
    doc.api_key_label = api_key_label
    doc.status = "active"
    doc.updated_by_user_id = actor
    if doc.is_new():
        doc.created_by_user_id = actor
        doc.insert(ignore_permissions=True)
    else:
        doc.save(ignore_permissions=True)
    return {"status": "saved", "message": "Kunci AI organisasi tersimpan terenkripsi.",
            "setting": _safe_setting(doc)}


@frappe.whitelist()
def get_org_key_status(organization_id, provider="openai"):
    _assert_org_admin(organization_id)
    provider = (provider or "openai").strip().lower()
    name = _org_setting_name(organization_id, provider)
    if not frappe.db.exists("RN AI User Setting", name):
        return {"organization_id": organization_id, "provider": provider, "key_exists": False}
    doc = frappe.get_doc("RN AI User Setting", name)
    if doc.status != "active":
        return {"organization_id": organization_id, "provider": provider, "key_exists": False}
    return {"organization_id": organization_id, "provider": provider, "key_exists": True,
            "masked_key": "****" + (doc.api_key_last4 or ""), "setting": _safe_setting(doc)}


@frappe.whitelist()
def delete_org_key(organization_id, provider="openai"):
    actor = _assert_org_admin(organization_id)
    provider = (provider or "openai").strip().lower()
    name = _org_setting_name(organization_id, provider)
    if not frappe.db.exists("RN AI User Setting", name):
        return {"status": "not_found"}
    doc = frappe.get_doc("RN AI User Setting", name)
    doc.status = "deleted"
    doc.api_key = None
    doc.api_key_last4 = None
    doc.updated_by_user_id = actor
    doc.save(ignore_permissions=True)
    return {"status": "deleted"}


def _resolve_ai_key(user_id, provider):
    """Personal key first, then the asker's approved-org key. Returns
    (api_key, model_name, key_source, owner_type, owner_id) or (None, ...)."""
    provider = (provider or "openai").strip().lower()

    uname = _setting_name(user_id, provider)
    if frappe.db.exists("RN AI User Setting", uname):
        d = frappe.get_doc("RN AI User Setting", uname)
        if d.status == "active":
            k = d.get_password("api_key")
            if k:
                return k, (d.model_name or DEFAULT_MODEL), "user", "user", user_id

    actor = rn_actor(required=False)
    org_ids = []
    if actor and actor.get("organization"):
        org_ids.append(actor.get("organization"))
    for o in _member_orgs(actor) if actor else []:
        if o and o not in org_ids:
            org_ids.append(o)
    for oid in org_ids:
        oname = _org_setting_name(oid, provider)
        if frappe.db.exists("RN AI User Setting", oname):
            d = frappe.get_doc("RN AI User Setting", oname)
            if d.status == "active":
                k = d.get_password("api_key")
                if k:
                    return k, (d.model_name or DEFAULT_MODEL), "organization", "organization", oid
    return None, DEFAULT_MODEL, None, None, None


def _log_ai_usage(*, owner_type, owner_id, user_id, key_source, provider,
                  model_name, disaster_event, q_chars=0, a_chars=0,
                  usage=None, outcome="ok", error_note=None):
    try:
        u = usage or {}
        doc = frappe.new_doc("RN AI Usage Log")
        doc.owner_type = owner_type or "user"
        doc.owner_id = owner_id
        doc.user_id = user_id
        doc.key_source = key_source or "user"
        doc.provider = provider
        doc.model_name = model_name
        doc.disaster_event = disaster_event
        doc.question_chars = int(q_chars or 0)
        doc.answer_chars = int(a_chars or 0)
        doc.prompt_tokens = int(u.get("prompt_tokens") or 0)
        doc.completion_tokens = int(u.get("completion_tokens") or 0)
        doc.total_tokens = int(u.get("total_tokens") or 0)
        doc.outcome = outcome
        doc.error_note = (str(error_note)[:140] if error_note else None)
        doc.insert(ignore_permissions=True)
    except Exception:
        frappe.log_error(title="rn_ai _log_ai_usage failed")


@frappe.whitelist()
def test_ai_key(user_id=None, organization_id=None, provider="openai"):
    """Validate a stored key with a tiny provider call. Never returns the key."""
    provider = (provider or "openai").strip().lower()
    if organization_id:
        _assert_org_admin(organization_id)
        name = _org_setting_name(organization_id, provider)
    else:
        _actor, user_id = _assert_self(user_id)
        name = _setting_name(user_id, provider)

    if not frappe.db.exists("RN AI User Setting", name):
        return {"ok": False, "message": "Belum ada kunci untuk diuji."}
    doc = frappe.get_doc("RN AI User Setting", name)
    key = doc.get_password("api_key") if doc.status == "active" else None
    if not key:
        return {"ok": False, "message": "Kunci tidak aktif."}
    if provider != "openai":
        return {"ok": False, "message": "Provider belum didukung untuk uji."}
    try:
        r = requests.get("https://api.openai.com/v1/models",
                         headers={"Authorization": "Bearer " + key}, timeout=20)
    except Exception:
        return {"ok": False, "message": "Gagal menghubungi provider (jaringan)."}
    if r.status_code == 401:
        return {"ok": False, "message": "Kunci ditolak (401)."}
    if not r.ok:
        return {"ok": False, "message": f"Provider mengembalikan {r.status_code}."}
    return {"ok": True, "message": "Kunci valid.", "model_hint": doc.model_name or DEFAULT_MODEL}


@frappe.whitelist()
def ai_usage_summary(user_id=None, organization_id=None, days=30):
    days = max(1, min(365, int(days or 30)))
    since = frappe.utils.add_days(now_datetime(), -days)
    filters = {"creation": [">=", since]}
    if organization_id:
        _assert_org_admin(organization_id)
        filters["owner_type"] = "organization"
        filters["owner_id"] = organization_id
    else:
        _actor, user_id = _assert_self(user_id)
        filters["user_id"] = user_id

    rows = frappe.get_all("RN AI Usage Log", filters=filters,
                          fields=["outcome", "total_tokens", "provider",
                                  "model_name", "key_source", "creation"],
                          order_by="creation desc", limit_page_length=2000)
    return {
        "days": days,
        "calls": len(rows),
        "ok": sum(1 for r in rows if r.outcome == "ok"),
        "errors": sum(1 for r in rows if r.outcome != "ok"),
        "total_tokens": sum(int(r.total_tokens or 0) for r in rows),
        "by_key_source": {
            "user": sum(1 for r in rows if r.key_source == "user"),
            "organization": sum(1 for r in rows if r.key_source == "organization"),
        },
        "recent": rows[:15],
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

@frappe.whitelist()
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


@frappe.whitelist(allow_guest=True)
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

    if provider != "openai":
        frappe.throw(
            "AI provider is not supported"
        )

    # Personal key first, then the asker's approved-organisation key (BYOK).
    api_key, model_name, key_source, key_owner_type, key_owner_id = _resolve_ai_key(
        user_id, provider
    )

    if not api_key:
        frappe.throw(
            "Belum ada kunci AI aktif untuk Anda atau organisasi Anda. "
            "Tambahkan di AI Settings."
        )

    setting = frappe._dict({"model_name": model_name})

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
        _log_ai_usage(owner_type=key_owner_type, owner_id=key_owner_id,
                      user_id=user_id, key_source=key_source, provider=provider,
                      model_name=setting.model_name or DEFAULT_MODEL,
                      disaster_event=disaster_event_id, q_chars=len(question),
                      outcome="error", error_note="network")
        frappe.throw(
            "AI request failed. Please "
            "check AI provider, model, "
            "quota, and network settings."
        )

    if response.status_code == 401:
        _log_ai_usage(owner_type=key_owner_type, owner_id=key_owner_id,
                      user_id=user_id, key_source=key_source, provider=provider,
                      model_name=setting.model_name or DEFAULT_MODEL,
                      disaster_event=disaster_event_id, q_chars=len(question),
                      outcome="auth_error", error_note="401")
        frappe.throw(
            "AI request failed: invalid "
            "API key. Please update your "
            "AI key in AI Settings.",
            frappe.AuthenticationError,
        )

    if not response.ok:
        _log_ai_usage(owner_type=key_owner_type, owner_id=key_owner_id,
                      user_id=user_id, key_source=key_source, provider=provider,
                      model_name=setting.model_name or DEFAULT_MODEL,
                      disaster_event=disaster_event_id, q_chars=len(question),
                      outcome="error", error_note=str(response.status_code))
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

    _log_ai_usage(owner_type=key_owner_type, owner_id=key_owner_id,
                  user_id=user_id, key_source=key_source, provider=provider,
                  model_name=setting.model_name or DEFAULT_MODEL,
                  disaster_event=disaster_event_id, q_chars=len(question),
                  a_chars=len(answer or ""), usage=data.get("usage"),
                  outcome="ok")

    return {
        "user_id": user_id,
        "provider": provider,
        "key_source": key_source,
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


@frappe.whitelist(allow_guest=True)
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
