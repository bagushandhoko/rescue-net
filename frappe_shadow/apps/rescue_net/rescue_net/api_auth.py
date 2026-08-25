import frappe

from rescue_net.access_policy import (
    rn_actor,
    is_system_manager,
)


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


@frappe.whitelist()
def session_info():
    data = me()

    return {
        "user": data["frappe_user"],
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
