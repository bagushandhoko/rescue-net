"""AI — provider / model helpers and the login / role guards."""

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


DEFAULT_MODEL = "gpt-4o-mini"  # OpenAI default; other providers: llm.PROVIDERS


def _prov(provider, allow_auto=False):
    """Provider name from the client. 'auto' (or empty, where allowed) means
    "whichever active key I saved last"."""
    p = (provider or "").strip().lower()
    if allow_auto and p in ("", "auto"):
        return "auto"
    try:
        return llm.normalize_provider(p or "openai")
    except llm.LLMError:
        frappe.throw("Provider AI tidak didukung. Pilih OpenAI, Claude, atau Gemini.")


def _model_for(provider, model_name):
    m = (model_name or "").strip()
    if not m:
        return llm.default_model(provider)
    # a model name of another provider (e.g. the old gpt default sent along
    # with a Claude key) falls back to this provider's default
    for other, spec in llm.PROVIDERS.items():
        if other != provider and m in spec["models"]:
            return llm.default_model(provider)
    return m


@frappe.whitelist(allow_guest=True)
def ai_providers():
    """Provider catalogue for the AI Settings page (no secrets)."""
    return llm.catalog()


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


# owner id of the platform key (System Manager) used by public features
PLATFORM_OWNER = "__platform__"
