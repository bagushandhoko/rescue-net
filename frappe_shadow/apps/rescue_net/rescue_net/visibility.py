"""Effective Control Centre visibility for a Posko / Organisation.

An organisation decides how much of its poskos the Control Centre exposes:

    RN Organization.control_centre_share
        "aggregate"        -> only summary / rollup across the org's poskos
        "full_authorized"  -> full posko detail to any authorised viewer

    RN Organization.allow_posko_public_choice (check)
        when set, a posko may override the org via its own RN Posko.public_detail
        ("public" -> full, "private" -> summary, "inherit" -> follow the org)

A viewer who owns the posko (assigned to it, member of its org, or a System
Manager) always gets full detail regardless of the sharing setting.
"""

import frappe

try:
    from rescue_net.access_policy import (
        approved_member,
        approved_posko_assignment,
        is_system_manager,
    )
except Exception:  # pragma: no cover - access_policy always present in app
    approved_member = None
    approved_posko_assignment = None

    def is_system_manager(user=None):
        user = user or frappe.session.user
        return (
            user == "Administrator"
            or "System Manager" in frappe.get_roles(user)
        )


FULL = "full"
SUMMARY = "summary"


def _org_row(org):
    if not org:
        return {}

    return frappe.db.get_value(
        "RN Organization",
        org,
        [
            "name",
            "control_centre_share",
            "allow_posko_public_choice",
            "privacy_mode",
        ],
        as_dict=True,
    ) or {}


def effective_posko_share(posko_name, actor=None):
    """Return {"mode": "full"|"summary", "organization": str|None, "reason": str}."""

    if not posko_name:
        return {"mode": SUMMARY, "organization": None, "reason": "no_posko"}

    posko = frappe.db.get_value(
        "RN Posko",
        posko_name,
        ["name", "organization", "public_detail"],
        as_dict=True,
    ) or {}

    org_name = posko.get("organization")
    org = _org_row(org_name)

    # 1. Owner / operator / system manager always sees full detail.
    if is_system_manager():
        return {"mode": FULL, "organization": org_name, "reason": "system_manager"}

    if actor:
        actor_posko = actor.get("posko") if isinstance(actor, dict) else getattr(actor, "posko", None)
        actor_org = actor.get("organization") if isinstance(actor, dict) else getattr(actor, "organization", None)
        actor_ua = actor.get("name") if isinstance(actor, dict) else getattr(actor, "name", None)

        if actor_posko and actor_posko == posko_name:
            return {"mode": FULL, "organization": org_name, "reason": "posko_operator"}

        if actor_org and org_name and actor_org == org_name:
            return {"mode": FULL, "organization": org_name, "reason": "org_member"}

        if actor_ua and callable(approved_posko_assignment) and approved_posko_assignment(actor_ua, posko_name):
            return {"mode": FULL, "organization": org_name, "reason": "posko_assignment"}

        if actor_ua and org_name and callable(approved_member) and approved_member(actor_ua, org_name):
            return {"mode": FULL, "organization": org_name, "reason": "org_membership"}

    # 2. Posko-level override, only when the org allows it.
    if org.get("allow_posko_public_choice"):
        choice = (posko.get("public_detail") or "inherit").lower()

        if choice == "public":
            return {"mode": FULL, "organization": org_name, "reason": "posko_public"}

        if choice == "private":
            return {"mode": SUMMARY, "organization": org_name, "reason": "posko_private"}

    # 3. Fall back to the org's coordination-sharing setting.
    share = (org.get("control_centre_share") or "aggregate").lower()

    if share == "full_authorized":
        return {"mode": FULL, "organization": org_name, "reason": "org_full_authorized"}

    return {"mode": SUMMARY, "organization": org_name, "reason": "org_aggregate"}


def posko_share_map(posko_names, actor=None):
    """Batch helper: {posko_name: "full"|"summary"}."""

    out = {}

    for name in set(filter(None, posko_names or [])):
        out[name] = effective_posko_share(name, actor)["mode"]

    return out
