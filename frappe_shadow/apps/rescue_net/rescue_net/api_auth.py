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
@rate_limit(limit=120, seconds=60)
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


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def social_login_url(provider="google", redirect_to=None):
    """Real Google/other-provider "Login/Daftar" URL for a custom login page
    like auth.html to redirect to. `frappe.integrations.oauth2_logins.
    login_via_<provider>` is only the OAuth CALLBACK (it requires a `code`
    Google hasn't sent yet) — linking a button straight to it always 500s.
    The actual entry point is Google's own consent screen, built here from
    the site's configured Social Login Key exactly like Frappe's stock
    /login page does."""
    from frappe.utils.oauth import get_oauth2_authorize_url

    provider = (provider or "google").strip().lower()
    key = frappe.db.get_value(
        "Social Login Key", provider,
        ["name", "enable_social_login", "client_id"], as_dict=True,
    )
    if not key or not key.enable_social_login or not key.client_id:
        return {"available": False,
                "reason": "Login %s belum dikonfigurasi di server." % provider}

    try:
        url = get_oauth2_authorize_url(provider, redirect_to or "/rescue-net/pages/auth.html")
    except Exception:
        frappe.log_error(frappe.get_traceback(), "social_login_url")
        return {"available": False, "reason": "Gagal membangun URL login %s." % provider}

    return {"available": True, "url": url}


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
    consent_verification=0,
    reference_name=None,
    reference_relation=None,
    reference_contact=None,
):
    """Public self-service signup used by pages/auth.html (Daftar tab).

    Creates a Frappe Website User + an RN User Account with the chosen
    role parked as a pending request. Does not grant any operational
    role by itself. `consent_verification` is an honest opt-in signal
    (not itself a verification) shown to reviewers in the approval queue
    (`api_verification.approval_item_detail`, kind="user").

    A registrant who opts in may freely name their own reference/character
    witness (RT chief, school principal, any known public figure — NOT
    restricted to the pre-registered `RN Verifier Profile` network) as an
    `RN User Reference` row for a reviewer to actually contact. This is a
    claim by the registrant, not itself a confirmed verification.
    """
    full_name = (full_name or "").strip()
    email = (email or "").strip().lower()
    phone = (phone or "").strip() or None
    role_key = (role or "relawan").strip().lower()
    consent_verification = 1 if str(consent_verification).lower() in ("1", "true", "yes", "on") else 0
    reference_name = (reference_name or "").strip() or None
    reference_relation = (reference_relation or "").strip() or None
    reference_contact = (reference_contact or "").strip() or None

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
                "consent_verification": consent_verification,
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

    has_reference = bool(consent_verification and reference_name)
    if has_reference:
        try:
            ref = frappe.get_doc({
                "doctype": "RN User Reference",
                "user_account": account.name,
                "reference_name": reference_name,
                "reference_relation": reference_relation,
                "reference_contact": reference_contact,
                "status": "pending",
            })
            ref.flags.ignore_permissions = True
            ref.insert(ignore_permissions=True)
        except Exception:
            # Non-fatal: the account itself is already valid. Don't fail
            # the whole registration over an optional reference note.
            frappe.log_error(frappe.get_traceback(), "rescue_net.api_auth.register reference")
            has_reference = False

    frappe.db.commit()

    return {
        "ok": True,
        "email": email,
        "requested_role": role_key,
        "role_request_status": "pending",
        "reference_saved": has_reference,
        "message": (
            "Akun dibuat. Anda bisa langsung masuk; "
            "peran " + role_key + " menunggu verifikasi."
        ),
    }


@frappe.whitelist()
@rate_limit(limit=6, seconds=60 * 60)
def change_password(old_password=None, new_password=None):
    """Self-service password change on the Setting page — any logged-in
    user, own account only. Verifies `old_password` against the stored
    hash first (frappe.utils.password.check_password already raises
    frappe.AuthenticationError on mismatch); other active sessions for
    this user are logged out, current one is kept.
    """
    from frappe.utils.password import check_password, update_password

    user = _require_login()

    if not old_password or not new_password:
        frappe.throw("Password lama dan password baru wajib diisi.")

    check_password(user, old_password)
    _check_password_strength(new_password)

    update_password(user, new_password, logout_all_sessions=True)

    return {"ok": True, "message": "Password berhasil diubah."}


@frappe.whitelist()
def admin_list_users(search=None):
    """System Manager only — user picker for the admin reset-password
    tool. Excludes Administrator/service accounts and Guest. Also
    resolves each user's organization (same precedence as
    `_primary_organization`: direct `RN User Account.organization` field
    first, else the first approved `RN Organization Membership` row) so
    the frontend can offer an optional organization filter — optional
    because plenty of accounts (individual volunteers/donors) have none.
    """
    if not is_system_manager():
        frappe.throw("Hanya System Manager.", frappe.PermissionError)

    # No user_type restriction: most Rescue-Net accounts are "Website User"
    # (register() creates them that way) — filtering to "System User" here
    # left the picker showing almost nobody. "Guest" is Frappe's built-in
    # placeholder row (always present, not a real login) — exclude it too.
    filters = {"enabled": 1, "name": ("not in", ["Administrator", "Guest"])}
    or_filters = None
    search = (search or "").strip()
    if search:
        or_filters = [
            ["name", "like", f"%{search}%"],
            ["full_name", "like", f"%{search}%"],
        ]

    users = frappe.get_all(
        "User",
        filters=filters,
        or_filters=or_filters,
        fields=["name", "full_name"],
        order_by="full_name asc",
        limit_page_length=500,
    )

    if not users:
        return {"users": [], "organizations": []}

    user_names = [u.name for u in users]

    accounts = frappe.get_all(
        "RN User Account",
        filters={"frappe_user": ("in", user_names)},
        fields=["name", "frappe_user", "organization"],
    )
    account_by_user = {a.frappe_user: a for a in accounts}

    membership_org = {}
    account_names = [a.name for a in accounts]
    if account_names:
        for m in frappe.get_all(
            "RN Organization Membership",
            filters={"user_account": ("in", account_names), "status": "approved"},
            fields=["user_account", "organization"],
        ):
            membership_org.setdefault(m.user_account, m.organization)

    org_id_by_user = {}
    for user_name, account in account_by_user.items():
        org_id_by_user[user_name] = account.organization or membership_org.get(account.name)

    org_ids = sorted({v for v in org_id_by_user.values() if v})
    org_title = {}
    if org_ids:
        for o in frappe.get_all(
            "RN Organization",
            filters={"name": ("in", org_ids)},
            fields=["name", "title"],
        ):
            org_title[o.name] = o.title or o.name

    rows = [
        {
            "name": u.name,
            "full_name": u.full_name,
            "organization_id": org_id_by_user.get(u.name),
            "organization_title": org_title.get(org_id_by_user.get(u.name)),
        }
        for u in users
    ]

    organizations = [
        {"id": oid, "title": org_title.get(oid, oid)}
        for oid in org_ids
    ]

    return {"users": rows, "organizations": organizations}


@frappe.whitelist()
@rate_limit(limit=20, seconds=60 * 60)
def admin_reset_password(user=None, new_password=None):
    """System Manager only — force-set another user's password (lost
    password / support request), skipping the old-password check that
    `change_password` requires for a self-service change. All of the
    target user's existing sessions are logged out so they must
    re-authenticate with the new password."""
    from frappe.utils.password import update_password

    if not is_system_manager():
        frappe.throw("Hanya System Manager.", frappe.PermissionError)

    user = (user or "").strip()
    if not user or user == "Administrator":
        frappe.throw("User tidak valid.")

    if not frappe.db.exists("User", user):
        frappe.throw("User tidak ditemukan.")

    _check_password_strength(new_password)

    update_password(user, new_password, logout_all_sessions=True)

    frappe.logger().info(
        f"[admin_reset_password] password direset oleh {frappe.session.user} untuk {user}"
    )

    return {"ok": True, "message": "Password user berhasil direset."}
