import frappe
from frappe.utils import cint


def is_system_manager(user=None):
    user = user or frappe.session.user
    return (
        user == "Administrator"
        or "System Manager" in frappe.get_roles(user)
    )


def rn_actor(required=True):
    user = frappe.session.user

    if user == "Guest":
        if required:
            frappe.throw("Login diperlukan")
        return None

    if (
        user == "Administrator"
        or "System Manager" in frappe.get_roles(user)
    ):
        return frappe._dict({
            "name": None,
            "frappe_user": user,
            "role": "system_manager",
            "organization": None,
            "posko": None,
        })

    actor = frappe.db.get_value(
        "RN User Account",
        {"frappe_user": user, "status": "active"},
        [
            "name", "frappe_user", "role",
            "organization", "posko"
        ],
        as_dict=True,
    )

    if required and not actor:
        frappe.throw("Akun Rescue-Net aktif tidak ditemukan")

    return actor


def approved_member(user_account, organization):
    if not user_account or not organization:
        return False

    direct = frappe.db.get_value(
        "RN User Account",
        user_account,
        "organization",
    )

    if direct == organization:
        return True

    return bool(
        frappe.db.exists(
            "RN Organization Membership",
            {
                "user_account": user_account,
                "organization": organization,
                "status": "approved",
            },
        )
    )


def approved_posko_assignment(user_account, posko):
    if not user_account or not posko:
        return False

    direct = frappe.db.get_value(
        "RN User Account",
        user_account,
        "posko",
    )

    if direct == posko:
        return True

    return bool(
        frappe.db.exists(
            "RN Posko Assignment",
            {
                "user_account": user_account,
                "posko": posko,
                "status": "approved",
            },
        )
    )


def can_manage_organization(actor, organization):
    if is_system_manager():
        return True

    if not actor or not actor.name:
        return False

    return bool(
        frappe.db.exists(
            "RN Organization Membership",
            {
                "user_account": actor.name,
                "organization": organization,
                "membership_role": "owner",
                "status": "approved",
            },
        )
    )


def can_manage_posko(actor, posko):
    if is_system_manager():
        return True

    if not actor or not actor.name:
        return False

    return approved_posko_assignment(
        actor.name,
        posko,
    )


def public_posko_allowed(posko_name):
    posko = frappe.db.get_value(
        "RN Posko",
        posko_name,
        [
            "organization",
            "public_detail",
        ],
        as_dict=True,
    )

    if not posko:
        return False

    if posko.organization:
        org = frappe.db.get_value(
            "RN Organization",
            posko.organization,
            [
                "privacy_mode",
                "allow_posko_public_choice",
            ],
            as_dict=True,
        )

        if org:
            if org.privacy_mode != "open":
                return False

            if not cint(org.allow_posko_public_choice):
                return False

    return posko.public_detail == "public"
