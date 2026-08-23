import frappe


def _actor():
    user = frappe.session.user

    if user in ("Guest", "Administrator"):
        frappe.throw("Login pengguna Rescue-Net diperlukan")

    actor = frappe.db.get_value(
        "RN User Account",
        {"frappe_user": user, "status": "active"},
        [
            "name",
            "role",
            "requested_role",
            "role_request_status",
        ],
        as_dict=True,
    )

    if not actor:
        frappe.throw("Akun Rescue-Net aktif tidak ditemukan")

    return actor


@frappe.whitelist()
def request_posko_operator(posko):
    actor = _actor()

    if actor.role == "posko_operator":
        return {
            "result": "already_effective_operator",
            "role": actor.role,
        }

    assignment_name = frappe.db.get_value(
        "RN Posko Assignment",
        {
            "user_account": actor.name,
            "posko": posko,
        },
        "name",
    )

    if not assignment_name:
        frappe.throw(
            "Anda belum memiliki assignment pada Posko tersebut"
        )

    assignment = frappe.get_doc(
        "RN Posko Assignment",
        assignment_name,
    )

    if assignment.status == "approved":
        frappe.throw(
            "Assignment Posko sudah approved tetapi role operator "
            "belum efektif. Perlu pemeriksaan administrator."
        )

    assignment.assignment_role = "posko_operator"
    assignment.status = "pending"
    assignment.save(ignore_permissions=True)

    frappe.db.set_value(
        "RN User Account",
        actor.name,
        {
            "requested_role": "posko_operator",
            "role_request_status": "pending",
        },
    )

    return {
        "result": "operator_request_pending",
        "user_account": actor.name,
        "posko": posko,
        "requested_role": "posko_operator",
        "role_request_status": "pending",
        "effective_role": actor.role,
    }


def _system_manager_only():
    if (
        frappe.session.user != "Administrator"
        and "System Manager" not in frappe.get_roles()
    ):
        frappe.throw(
            "System Manager diperlukan",
            frappe.PermissionError,
        )


@frappe.whitelist()
def pending_requests():
    _system_manager_only()

    users = frappe.get_all(
        "RN User Account",
        filters={
            "requested_role": "posko_operator",
            "role_request_status": "pending",
            "status": "active",
        },
        fields=[
            "name",
            "title",
            "email",
            "frappe_user",
            "role",
            "requested_role",
            "role_request_status",
        ],
        order_by="modified asc",
        limit_page_length=200,
    )

    result = []

    for user in users:
        assignments = frappe.get_all(
            "RN Posko Assignment",
            filters={
                "user_account": user.name,
                "status": "pending",
            },
            fields=[
                "name",
                "posko",
                "assignment_role",
                "status",
            ],
            order_by="creation asc",
            limit_page_length=100,
        )

        for assignment in assignments:
            row = dict(user)
            row.update({
                "assignment": assignment.name,
                "posko": assignment.posko,
                "assignment_role": assignment.assignment_role,
                "assignment_status": assignment.status,
            })
            result.append(row)

    return result


def _lock_request(user_account, posko):
    rows = frappe.db.sql(
        """
        SELECT name
        FROM `tabRN User Account`
        WHERE name=%s
        FOR UPDATE
        """,
        (user_account,),
    )

    if not rows:
        frappe.throw("RN User Account tidak ditemukan")

    user = frappe.get_doc(
        "RN User Account",
        user_account,
    )

    assignment_name = frappe.db.get_value(
        "RN Posko Assignment",
        {
            "user_account": user_account,
            "posko": posko,
        },
        "name",
    )

    if not assignment_name:
        frappe.throw("Posko Assignment tidak ditemukan")

    frappe.db.sql(
        """
        SELECT name
        FROM `tabRN Posko Assignment`
        WHERE name=%s
        FOR UPDATE
        """,
        (assignment_name,),
    )

    assignment = frappe.get_doc(
        "RN Posko Assignment",
        assignment_name,
    )

    return user, assignment


@frappe.whitelist()
def approve_posko_operator(user_account, posko):
    _system_manager_only()

    user, assignment = _lock_request(
        user_account,
        posko,
    )

    if user.requested_role != "posko_operator":
        frappe.throw("User tidak meminta role posko_operator")

    if user.role_request_status != "pending":
        frappe.throw("Role request bukan pending")

    if assignment.status != "pending":
        frappe.throw("Posko assignment bukan pending")

    user.role = "posko_operator"
    user.role_request_status = "approved"
    user.save(ignore_permissions=True)

    assignment.assignment_role = "posko_operator"
    assignment.status = "approved"

    approver = frappe.db.get_value(
        "RN User Account",
        {"frappe_user": frappe.session.user},
        "name",
    )

    if approver:
        assignment.approved_by = approver

    assignment.save(ignore_permissions=True)

    return {
        "result": "approved",
        "user_account": user.name,
        "effective_role": user.role,
        "role_request_status": user.role_request_status,
        "posko": assignment.posko,
        "assignment_status": assignment.status,
    }


@frappe.whitelist()
def reject_posko_operator(user_account, posko):
    _system_manager_only()

    user, assignment = _lock_request(
        user_account,
        posko,
    )

    if user.role == "posko_operator":
        frappe.throw(
            "Operator yang sudah efektif tidak dapat ditolak "
            "melalui pending request"
        )

    user.role_request_status = "rejected"
    user.save(ignore_permissions=True)

    assignment.assignment_role = "posko_operator"
    assignment.status = "rejected"
    assignment.save(ignore_permissions=True)

    return {
        "result": "rejected",
        "user_account": user.name,
        "effective_role": user.role,
        "role_request_status": user.role_request_status,
        "posko": assignment.posko,
        "assignment_status": assignment.status,
    }
