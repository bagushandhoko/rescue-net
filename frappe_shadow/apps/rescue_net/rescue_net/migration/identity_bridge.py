import frappe


LOCAL_DOMAIN_SUFFIX = ".local"


def _normalize_email(value):
    return (value or "").strip().lower()


def evaluate_identity_bridge():
    accounts = frappe.get_all(
        "RN User Account",
        fields=[
            "legacy_id",
            "email",
            "status",
            "role",
            "requested_role",
            "role_request_status",
            "frappe_user",
        ],
        order_by="legacy_id asc",
        limit_page_length=10000,
    )

    users = frappe.get_all(
        "User",
        fields=["name", "email", "enabled"],
        limit_page_length=10000,
    )

    users_by_email = {}
    for user in users:
        email = _normalize_email(user.get("email"))
        if email:
            users_by_email.setdefault(email, []).append(user)

    counts = {}
    rows = []

    for account in accounts:
        status, candidate = _classify(account, users_by_email)
        counts[status] = counts.get(status, 0) + 1

        rows.append({
            "legacy_id": account.get("legacy_id"),
            "email": account.get("email"),
            "source_status": account.get("status"),
            "role": account.get("role"),
            "requested_role": account.get("requested_role"),
            "role_request_status": account.get("role_request_status"),
            "frappe_user": account.get("frappe_user"),
            "bridge_status": status,
            "candidate_user": candidate,
        })

    return {
        "mode": "read-only",
        "total_accounts": len(accounts),
        "counts": counts,
        "rows": rows,
    }


def _classify(account, users_by_email):
    if account.get("status") != "active":
        return "source_not_active", None

    email = _normalize_email(account.get("email"))

    if not email or "@" not in email:
        return "missing_or_invalid_email", None

    domain = email.rsplit("@", 1)[1]

    if domain.endswith(LOCAL_DOMAIN_SUFFIX):
        return "local_shadow_only", None

    current_user = account.get("frappe_user")

    if current_user:
        if frappe.db.exists("User", current_user):
            return "already_linked", current_user
        return "broken_link", current_user

    matches = users_by_email.get(email, [])

    if not matches:
        return "no_existing_frappe_user", None

    if len(matches) > 1:
        return "ambiguous_frappe_email", None

    target = matches[0]

    if not target.get("enabled"):
        return "existing_frappe_user_disabled", target.get("name")

    return "existing_frappe_user_candidate", target.get("name")


def evaluate_login_identity(user):
    """Read-only decision for an authenticated Frappe User."""
    user = _normalize_email(user)

    result = {
        "mode": "read-only",
        "user": user or None,
        "status": None,
        "rn_account": None,
        "candidate_frappe_user": None,
    }

    if not user or "@" not in user:
        result["status"] = "invalid_or_system_user"
        return result

    domain = user.rsplit("@", 1)[1]
    if domain.endswith(LOCAL_DOMAIN_SUFFIX):
        result["status"] = "local_shadow_only"
        return result

    frappe_user = frappe.db.get_value(
        "User",
        user,
        ["name", "email", "enabled"],
        as_dict=True,
    )

    if not frappe_user:
        result["status"] = "frappe_user_missing"
        return result

    if not frappe_user.get("enabled"):
        result["status"] = "frappe_user_disabled"
        return result

    frappe_user_name = frappe_user.get("name")
    result["candidate_frappe_user"] = frappe_user_name

    email = _normalize_email(frappe_user.get("email") or user)

    accounts = frappe.get_all(
        "RN User Account",
        filters={"email": email},
        fields=[
            "name",
            "legacy_id",
            "email",
            "status",
            "role",
            "requested_role",
            "role_request_status",
            "frappe_user",
        ],
        limit_page_length=10,
    )

    if not accounts:
        result["status"] = "no_rn_account"
        return result

    if len(accounts) != 1:
        result["status"] = "ambiguous_rn_account"
        return result

    account = accounts[0]
    result["rn_account"] = account.get("name")

    if account.get("status") != "active":
        result["status"] = "rn_account_not_active"
        return result

    current = account.get("frappe_user")

    if current:
        if current == frappe_user_name:
            result["status"] = "already_linked"
        else:
            result["status"] = "link_conflict"
        return result

    reverse_links = frappe.get_all(
        "RN User Account",
        filters={"frappe_user": frappe_user_name},
        fields=["name", "legacy_id", "email"],
        limit_page_length=10,
    )

    if reverse_links:
        result["status"] = "frappe_user_already_in_use"
        return result

    result["status"] = "eligible_to_link"
    return result


def link_identity_on_login(login_manager=None):
    """
    Link an authenticated Frappe User to an existing eligible RN User Account.

    Does not create users, assign roles, approve role requests,
    activate disabled accounts, or link .local identities.
    """
    try:
        user = getattr(login_manager, "user", None)
        decision = evaluate_login_identity(user)

        if decision.get("status") != "eligible_to_link":
            return decision

        frappe.db.set_value(
            "RN User Account",
            decision["rn_account"],
            "frappe_user",
            decision["candidate_frappe_user"],
            update_modified=False,
        )

        decision["status"] = "linked"
        decision["mode"] = "write-link-only"
        return decision

    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            "Rescue-Net identity bridge on_login",
        )
        return {
            "mode": "safe-failure",
            "status": "bridge_error",
        }


def evaluate_native_provisioning(user):
    """Read-only decision for creating a native RN viewer account."""
    user = _normalize_email(user)

    result = {
        "mode": "read-only",
        "user": user or None,
        "status": None,
        "rn_account": None,
        "email": None,
        "user_type": None,
    }

    if user in {"guest", "administrator"}:
        result["status"] = "system_identity_not_eligible"
        return result

    if not user or "@" not in user:
        result["status"] = "invalid_identity"
        return result

    frappe_user = frappe.db.get_value(
        "User",
        user,
        ["name", "email", "enabled", "user_type", "full_name"],
        as_dict=True,
    )

    if not frappe_user:
        result["status"] = "frappe_user_missing"
        return result

    user_name = frappe_user.get("name")
    email = _normalize_email(frappe_user.get("email") or user)

    result["email"] = email
    result["user_type"] = frappe_user.get("user_type")

    if user_name in {"Guest", "Administrator"}:
        result["status"] = "system_identity_not_eligible"
        return result

    if not frappe_user.get("enabled"):
        result["status"] = "frappe_user_disabled"
        return result

    if not email or "@" not in email:
        result["status"] = "missing_or_invalid_email"
        return result

    domain = email.rsplit("@", 1)[1]
    if domain.endswith(LOCAL_DOMAIN_SUFFIX):
        result["status"] = "local_shadow_only"
        return result

    if frappe_user.get("user_type") != "Website User":
        result["status"] = "non_website_user_not_eligible"
        return result

    linked = frappe.get_all(
        "RN User Account",
        filters={"frappe_user": frappe_user.get("name")},
        fields=["name", "legacy_id", "email", "status"],
        limit_page_length=10,
    )

    if len(linked) > 1:
        result["status"] = "ambiguous_existing_link"
        return result

    if len(linked) == 1:
        result["rn_account"] = linked[0].get("name")
        result["status"] = "already_provisioned"
        return result

    by_email = frappe.get_all(
        "RN User Account",
        filters={"email": email},
        fields=[
            "name",
            "legacy_id",
            "email",
            "status",
            "frappe_user",
        ],
        limit_page_length=10,
    )

    if len(by_email) > 1:
        result["status"] = "ambiguous_rn_email"
        return result

    if len(by_email) == 1:
        result["rn_account"] = by_email[0].get("name")

        if (
            by_email[0].get("status") == "active"
            and not by_email[0].get("frappe_user")
        ):
            result["status"] = "existing_rn_account_link_candidate"
        else:
            result["status"] = "existing_rn_account_requires_review"

        return result

    result["status"] = "eligible_native_viewer"
    return result
