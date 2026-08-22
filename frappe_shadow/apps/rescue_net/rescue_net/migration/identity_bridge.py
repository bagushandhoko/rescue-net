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
