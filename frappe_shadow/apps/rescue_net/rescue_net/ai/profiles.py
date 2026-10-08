"""AI — RN AI Profile: who may run AI, on which provider, with which budget (ADR-0002 section 4)."""

import json

import frappe

from rescue_net.access_policy import is_system_manager
from rescue_net.ai.common import _assert_self, _require_login
from rescue_net.ai.keys import _assert_org_admin
from rescue_net.rn_intelligence.doctype.rn_ai_profile.rn_ai_profile import PLATFORM_OWNER, profile_name

LEVELS = ("personal", "organization", "platform")


def _authorise(level, owner_id, *, local):
    """The profile owner (or the one who manages it) only. A local-model URL
    is called by the server itself, so only an organisation admin or a System
    Manager may set one; a personal profile may use it only for a System Manager."""
    if level not in LEVELS:
        frappe.throw("Level profil AI tidak dikenal.")
    if level == "platform":
        if not is_system_manager():
            frappe.throw("Hanya System Manager yang dapat mengatur profil AI platform.", frappe.PermissionError)
        return PLATFORM_OWNER
    if level == "organization":
        _assert_org_admin(owner_id)
        return owner_id
    _actor, owner_id = _assert_self(owner_id)
    if local and not is_system_manager():
        frappe.throw("Model lokal personal hanya dapat diatur oleh System Manager.", frappe.PermissionError)
    return owner_id


def _safe_profile(doc):
    return {
        "id": doc.name, "level": doc.level, "owner_id": doc.owner_id, "provider": doc.provider,
        "model_name": doc.model_name, "base_url": doc.base_url,
        "has_key": bool(doc.key_setting), "allowed_tools": json.loads(doc.allowed_tools or "[]"),
        "data_scope": doc.data_scope, "daily_budget_tokens": doc.daily_budget_tokens,
        "monthly_budget_tokens": doc.monthly_budget_tokens, "status": doc.status,
        "updated_at": doc.modified,
    }


@frappe.whitelist()
def save_ai_profile(level, owner_id=None, provider="openai", model_name=None, base_url=None,
                    allowed_tools=None, daily_budget_tokens=0, monthly_budget_tokens=0, status="active"):
    _require_login()
    owner_id = _authorise(level, owner_id, local=(provider or "").strip().lower() == "local")
    name = profile_name(level, owner_id)
    doc = frappe.get_doc("RN AI Profile", name) if frappe.db.exists("RN AI Profile", name) \
        else frappe.new_doc("RN AI Profile")
    doc.level, doc.owner_id = level, owner_id
    doc.provider, doc.model_name, doc.base_url = provider, model_name, base_url
    if allowed_tools is not None:
        doc.allowed_tools = allowed_tools if isinstance(allowed_tools, str) else json.dumps(allowed_tools)
    doc.daily_budget_tokens = int(daily_budget_tokens or 0)
    doc.monthly_budget_tokens = int(monthly_budget_tokens or 0)
    doc.status = status if status in ("active", "disabled") else "active"
    doc.updated_by_user_id = frappe.session.user
    doc.save(ignore_permissions=True)
    return {"status": "saved", "profile": _safe_profile(doc)}


@frappe.whitelist()
def get_ai_profile(level, owner_id=None):
    _require_login()
    owner_id = _authorise(level, owner_id, local=False)
    name = profile_name(level, owner_id)
    if not frappe.db.exists("RN AI Profile", name):
        return {"exists": False, "level": level, "owner_id": owner_id}
    return {"exists": True, "profile": _safe_profile(frappe.get_doc("RN AI Profile", name))}
