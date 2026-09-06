import re

import frappe
from frappe.rate_limiter import rate_limit

from rescue_net.access_policy import (
    rn_actor,
    is_system_manager,
)


# Public self-registration. A new account is always created with an
# empty effective `role` (so `_effective_role` resolves to "viewer",
# read-only) and the chosen role parked in `requested_role` /
# `role_request_status = "pending"` for the existing
# verification-approval flow to grant.
PUBLIC_SIGNUP_ROLES = {
    "relawan": "volunteer",
    "donatur": "viewer",
    "organisasi": "viewer",
    "petugas_posko": "viewer",
}


ROLE_MATRIX = [
    {
        "role": "viewer",
        "scope": "assigned",
        "can_verify": False,
        "can_view_sensitive": False,
    },
    {
        "role": "volunteer",
        "scope": "assigned",
        "can_verify": False,
        "can_view_sensitive": False,
    },
    {
        "role": "posko_operator",
        "scope": "posko",
        "can_verify": True,
        "can_view_sensitive": True,
    },
    {
        "role": "medical_operator",
        "scope": "posko",
        "can_verify": True,
        "can_view_sensitive": True,
    },
    {
        "role": "shelter_operator",
        "scope": "posko",
        "can_verify": True,
        "can_view_sensitive": True,
    },
    {
        "role": "command_center",
        "scope": "global",
        "can_verify": True,
        "can_view_sensitive": True,
    },
]


def _require_login():
    user = frappe.session.user

    if not user or user == "Guest":
        frappe.throw(
            "Login Frappe diperlukan",
            frappe.AuthenticationError,
        )

    return user


def _actor_doc():
    user = _require_login()

    if (
        user == "Administrator"
        or is_system_manager(user)
    ):
        return None

    actor = rn_actor()

    if not actor:
        frappe.throw(
            "RN User Account aktif diperlukan",
            frappe.PermissionError,
        )

    return actor


def _value(doc, fieldname, default=None):
    if doc is None:
        return default

    value = getattr(doc, fieldname, None)

    return default if value is None else value


def _effective_role(actor):
    user = frappe.session.user

    if (
        user == "Administrator"
        or is_system_manager(user)
    ):
        return "system_manager"

    return _value(actor, "role", "viewer") or "viewer"


def _memberships(actor):
    if actor is None:
        return []

    return frappe.get_all(
        "RN Organization Membership",
        filters={
            "user_account": actor.name,
            "status": "approved",
        },
        fields=[
            "name",
            "organization",
            "membership_role",
            "status",
        ],
        limit_page_length=500,
    )


def _assignments(actor):
    if actor is None:
        return []

    return frappe.get_all(
        "RN Posko Assignment",
        filters={
            "user_account": actor.name,
            "status": "approved",
        },
        fields=[
            "name",
            "posko",
            "assignment_role",
            "status",
        ],
        limit_page_length=500,
    )


def _primary_organization(actor, memberships):
    direct = _value(actor, "organization")

    if direct:
        return direct

    for row in memberships:
        if row.get("organization"):
            return row.get("organization")

    return None


def _primary_posko(actor, assignments):
    direct = _value(actor, "posko")

    if direct:
        return direct

    for row in assignments:
        if row.get("posko"):
            return row.get("posko")

    return None


def _capabilities(role):
    if role == "system_manager":
        return {
            "scope": "global",
            "can_verify": True,
            "can_view_sensitive": True,
        }

    row = next(
        (
            item
            for item in ROLE_MATRIX
            if item["role"] == role
        ),
        None,
    )

    if not row:
        return {
            "scope": "assigned",
            "can_verify": False,
            "can_view_sensitive": False,
        }

    return {
        "scope": row["scope"],
        "can_verify": row["can_verify"],
        "can_view_sensitive":
            row["can_view_sensitive"],
    }


@frappe.whitelist()
def roles():
    _require_login()

    return {
        "roles": ROLE_MATRIX,
    }


@frappe.whitelist()
def me():
    user = _require_login()
    actor = _actor_doc()

    if actor is None:
        role = "system_manager"

        return {
            "id": user,
            "user_id": user,
            "frappe_user": user,
            "email": user,
            "role": role,
            "requested_role": None,
            "role_request_status": "not_required",
            "organization_id": None,
            "posko_id": None,
            "organizations": [],
            "poskos": [],
            "status": "active",
            **_capabilities(role),
        }

    memberships = _memberships(actor)
    assignments = _assignments(actor)

    role = _effective_role(actor)

    return {
        "id": actor.name,
        "user_id": user,
        "frappe_user": user,
        "email": _value(actor, "email", user),
        "role": role,

        # Pending request is never treated as effective role.
        "requested_role":
            _value(actor, "requested_role"),

        "role_request_status":
            _value(actor, "role_request_status"),

        "organization_id":
            _primary_organization(
                actor,
                memberships,
            ),

        "posko_id":
            _primary_posko(
                actor,
                assignments,
            ),

        "organizations": [
            {
                "organization_id":
                    row.get("organization"),
                "membership_role":
                    row.get("membership_role"),
                "status":
                    row.get("status"),
            }
            for row in memberships
        ],

        "poskos": [
            {
                "posko_id":
                    row.get("posko"),
                "assignment_role":
                    row.get("assignment_role"),
                "status":
                    row.get("status"),
            }
            for row in assignments
        ],

        "status":
            _value(actor, "status", "active"),

        **_capabilities(role),
    }


@frappe.whitelist(allow_guest=True)
def session_info():
    # guest-safe: the public header / auth.js loadSession() poll this on every
    # page load — return a plain Guest marker instead of a 403.
    if frappe.session.user in (None, "", "Guest"):
        return {"user": "Guest"}

    data = me()

    return {
        "user": data["frappe_user"],
        "full_name": (
            frappe.db.get_value("User", data["frappe_user"], "full_name")
            or data["frappe_user"]
        ),
        "rn_user_account": data["id"],
        "role": data["role"],
        "requested_role":
            data["requested_role"],
        "role_request_status":
            data["role_request_status"],
        "organization_id":
            data["organization_id"],
        "posko_id":
            data["posko_id"],
        "scope":
            data["scope"],
        "can_verify":
            data["can_verify"],
        "can_view_sensitive":
            data["can_view_sensitive"],
    }


def _check_password_strength(password):
    if len(password or "") < 8:
        frappe.throw("Password minimal 8 karakter.")

    if not re.search(r"[A-Z]", password):
        frappe.throw("Password harus mengandung minimal 1 huruf besar.")

    if not re.search(r"[0-9]", password):
        frappe.throw("Password harus mengandung minimal 1 angka.")


@frappe.whitelist(allow_guest=True)
@rate_limit(key="email", limit=6, seconds=60 * 60)
def register(
    full_name=None,
    email=None,
    phone=None,
    password=None,
    role=None,
):
    """Public self-service signup used by pages/auth.html (Daftar tab).

    Creates a Frappe Website User + an RN User Account with the chosen
    role parked as a pending request. Does not grant any operational
    role by itself.
    """
    full_name = (full_name or "").strip()
    email = (email or "").strip().lower()
    phone = (phone or "").strip() or None
    role_key = (role or "relawan").strip().lower()

    if not full_name or not email or not password:
        frappe.throw("Nama lengkap, email, dan password wajib diisi.")

    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        frappe.throw("Format email tidak valid.")

    _check_password_strength(password)

    if role_key not in PUBLIC_SIGNUP_ROLES:
        role_key = "relawan"

    if frappe.db.exists("User", email):
        frappe.throw("Email sudah terdaftar. Silakan masuk.")

    parts = full_name.split(" ", 1)
    first_name = parts[0]
    last_name = parts[1] if len(parts) > 1 else ""

    user = frappe.get_doc(
        {
            "doctype": "User",
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "mobile_no": phone,
            "send_welcome_email": 0,
            "user_type": "Website User",
            "new_password": password,
        }
    )
    user.flags.ignore_permissions = True
    user.insert(ignore_permissions=True)

    try:
        account = frappe.get_doc(
            {
                "doctype": "RN User Account",
                "frappe_user": user.name,
                "title": full_name,
                "username": email.split("@")[0],
                "email": email,
                "phone": phone,
                "role": "",
                "requested_role": role_key,
                "role_request_status": "pending",
                "status": "pending_verification",
            }
        )
        account.flags.ignore_permissions = True
        account.insert(ignore_permissions=True)
    except Exception:
        frappe.db.rollback()
        frappe.log_error(
            frappe.get_traceback(),
            "rescue_net.api_auth.register",
        )
        frappe.throw(
            "Pendaftaran gagal saat membuat profil Rescue-Net. "
            "Silakan coba lagi."
        )

    frappe.db.commit()

    return {
        "ok": True,
        "email": email,
        "requested_role": role_key,
        "role_request_status": "pending",
        "message": (
            "Akun dibuat. Anda bisa langsung masuk; "
            "peran " + role_key + " menunggu verifikasi."
        ),
    }
