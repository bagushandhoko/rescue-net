"""AI — BYOK keys (personal, organisation, platform), key tests, usage log and summary."""

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
    PLATFORM_OWNER,
    _assert_self,
    _model_for,
    _prov,
    _require_login,
    _safe_setting,
    _setting_name,
)
from rescue_net.ai.context import (  # noqa: F401
    _member_orgs,
)


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
    model_name=None,
    api_key_label=None,
):
    actor, user_id = _assert_self(user_id)

    provider = _prov(provider)
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
    doc.model_name = _model_for(provider, model_name)

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

    provider = _prov(provider)
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

    provider = _prov(provider)
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

    doc.model_name = _model_for(provider, model_name)
    doc.updated_by_user_id = actor
    doc.save(ignore_permissions=True)

    return _safe_setting(doc)


@frappe.whitelist()
def delete_user_key(
    user_id,
    provider="openai",
):
    actor, user_id = _assert_self(user_id)

    provider = _prov(provider)
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
                 model_name=None, api_key_label=None):
    actor = _assert_org_admin(organization_id)
    provider = _prov(provider)
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
    doc.model_name = _model_for(provider, model_name)
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
    provider = _prov(provider)
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
    provider = _prov(provider)
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


def _require_system_manager():
    if not is_system_manager():
        frappe.throw("Hanya System Manager yang dapat mengatur kunci AI platform.",
                     frappe.PermissionError)


@frappe.whitelist()
def save_platform_key(api_key, provider="openai", model_name=None, api_key_label=None):
    """Platform key for public features (citizen report intake). Stored like
    an org key under PLATFORM_OWNER; the secret is never returned."""
    _require_system_manager()
    provider = _prov(provider)
    api_key = (api_key or "").strip()
    if len(api_key) < 20:
        frappe.throw("API key is too short")
    name = _org_setting_name(PLATFORM_OWNER, provider)
    if frappe.db.exists("RN AI User Setting", name):
        doc = frappe.get_doc("RN AI User Setting", name)
    else:
        doc = frappe.new_doc("RN AI User Setting")
        doc.name = name
        doc.provider = provider
        doc.created_by_user_id = frappe.session.user
    doc.user_id = "org:" + PLATFORM_OWNER  # autoname = _org_setting_name(PLATFORM_OWNER, provider)
    doc.owner_type = "platform"
    doc.owner_id = PLATFORM_OWNER
    doc.model_name = _model_for(provider, model_name)
    doc.api_key = api_key
    doc.api_key_last4 = api_key[-4:]
    doc.api_key_label = api_key_label
    doc.status = "active"
    doc.updated_by_user_id = frappe.session.user
    doc.save(ignore_permissions=True) if not doc.is_new() else doc.insert(ignore_permissions=True)
    return {"status": "saved", "setting": _safe_setting(doc)}


@frappe.whitelist()
def get_platform_key_status():
    _require_system_manager()
    out = []
    for p in llm.PROVIDERS:
        d = _active_setting(_org_setting_name(PLATFORM_OWNER, p))
        out.append({"provider": p, "key_exists": bool(d),
                    "masked_key": ("****" + (d.api_key_last4 or "")) if d else None,
                    "model_name": d.model_name if d else None,
                    "updated_at": d.modified if d else None})
    _key, model, provider = resolve_platform_key()
    return {"providers": out, "active_provider": provider, "active_model": model}


@frappe.whitelist()
def delete_platform_key(provider="openai"):
    _require_system_manager()
    name = _org_setting_name(PLATFORM_OWNER, _prov(provider))
    if not frappe.db.exists("RN AI User Setting", name):
        return {"status": "not_found"}
    doc = frappe.get_doc("RN AI User Setting", name)
    doc.status = "deleted"
    doc.api_key = None
    doc.api_key_last4 = None
    doc.updated_by_user_id = frappe.session.user
    doc.save(ignore_permissions=True)
    return {"status": "deleted"}


@frappe.whitelist()
def test_platform_key(provider="openai"):
    _require_system_manager()
    provider = _prov(provider)
    d = _active_setting(_org_setting_name(PLATFORM_OWNER, provider))
    if not d:
        return {"ok": False, "message": "Belum ada kunci platform untuk diuji."}
    ok, message = llm.test_key(provider, d.get_password("api_key"))
    return {"ok": ok, "message": message, "provider": provider}


def _active_setting(name):
    if not frappe.db.exists("RN AI User Setting", name):
        return None
    d = frappe.get_doc("RN AI User Setting", name)
    return d if d.status == "active" and d.get_password("api_key", raise_exception=False) else None


def _pick_latest(names):
    found = [d for d in (_active_setting(n) for n in names) if d]
    return max(found, key=lambda d: d.modified) if found else None


def _resolve_ai_key(user_id, provider):
    """Personal key first, then the asker's approved-org key. provider='auto'
    takes, at each level, the active key saved most recently. Returns
    (api_key, model_name, key_source, owner_type, owner_id, provider) or
    (None, ...)."""
    providers = list(llm.PROVIDERS) if provider == "auto" else [provider]

    d = _pick_latest([_setting_name(user_id, p) for p in providers])
    if d:
        p = llm.normalize_provider(d.provider)
        return d.get_password("api_key"), _model_for(p, d.model_name), "user", "user", user_id, p

    actor = rn_actor(required=False)
    org_ids = []
    if actor and actor.get("organization"):
        org_ids.append(actor.get("organization"))
    for o in _member_orgs(actor) if actor else []:
        if o and o not in org_ids:
            org_ids.append(o)
    for oid in org_ids:
        d = _pick_latest([_org_setting_name(oid, p) for p in providers])
        if d:
            p = llm.normalize_provider(d.provider)
            return d.get_password("api_key"), _model_for(p, d.model_name), "organization", "organization", oid, p
    return None, None, None, None, None, provider


def resolve_platform_key():
    """The platform key a System Manager sets for public features (citizen
    report intake) — never used for personal chat. (key, model, provider)."""
    d = _pick_latest([_org_setting_name(PLATFORM_OWNER, p) for p in llm.PROVIDERS])
    if not d:
        return None, None, None
    p = llm.normalize_provider(d.provider)
    return d.get_password("api_key"), _model_for(p, d.model_name), p


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
    provider = _prov(provider)
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
    ok, message = llm.test_key(provider, key)
    out = {"ok": ok, "message": message, "provider": provider}
    if ok:
        out["model_hint"] = _model_for(provider, doc.model_name)
    return out


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
