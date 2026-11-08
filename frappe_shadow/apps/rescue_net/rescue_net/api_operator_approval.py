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


def _org_managers(org):
    if not org:
        return []
    return frappe.get_all("RN Organization Membership",
                          filters={"organization": org, "status": "approved",
                                   "membership_role": ["in", ["owner", "deputy", "staff"]]},
                          pluck="user_account")


def _operator_status(posko, actor=None):
    """Can the caller ask to become this posko's operator directly (super-admin approval)?
    Only when nobody can place them: the posko has no approved operator AND its organisation (if any) has
    no manager. Otherwise the route is: join the organisation, its manager places you."""
    row = frappe.db.get_value("RN Posko", posko, ["name", "title", "organization"], as_dict=True)
    if not row:
        frappe.throw("Posko tidak ditemukan.")
    operators = frappe.get_all("RN Posko Assignment", filters={"posko": posko, "status": "approved"}, pluck="user_account")
    managers = _org_managers(row.organization)
    pending = bool(actor and frappe.db.exists("RN Posko Assignment",
                                              {"posko": posko, "user_account": actor.name, "status": "pending"}))
    mine = bool(actor and actor.name in operators)
    if mine:
        return {"can_request": False, "pending": False, "is_operator": True, "reason": "Anda sudah petugas posko ini."}
    if pending:
        return {"can_request": False, "pending": True, "is_operator": False,
                "reason": "Permohonan Anda sedang menunggu persetujuan super admin."}
    if managers:
        org_title = frappe.db.get_value("RN Organization", row.organization, "title") or row.organization
        return {"can_request": False, "pending": False, "is_operator": False, "organization": row.organization,
                "reason": f"Posko ini dikelola organisasi {org_title}. Ajukan keanggotaan ke organisasi itu; "
                          "pengelolanya yang menempatkan petugas."}
    if operators:
        return {"can_request": False, "pending": False, "is_operator": False,
                "reason": "Posko ini sudah punya petugas. Hubungi petugasnya lewat kontak posko."}
    return {"can_request": True, "pending": False, "is_operator": False,
            "reason": "Posko ini belum punya pengelola. Anda bisa mengajukan diri; super admin akan memeriksa."}


@frappe.whitelist()
def posko_operator_status(posko):
    """For the posko page: may the logged-in user ask to run this posko?"""
    user = frappe.session.user
    if user in ("Guest",):
        return {"can_request": False, "login_required": True}
    actor = frappe.db.get_value("RN User Account", {"frappe_user": user, "status": "active"}, ["name"], as_dict=True)
    return _operator_status(posko, actor)


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
        # owner 2026-11-08: a posko nobody manages (no org managers, no operator) used to be a dead end.
        # Anyone logged in may now ask to run it; the request lands in the Verification queue (super admin).
        st = _operator_status(posko, actor)
        if not st["can_request"]:
            frappe.throw(st["reason"])
        assignment = frappe.new_doc("RN Posko Assignment")
        assignment.user_account = actor.name
        assignment.posko = posko
        assignment.assignment_role = "posko_operator"
        assignment.status = "pending"
        assignment.insert(ignore_permissions=True)
        frappe.db.set_value("RN User Account", actor.name,
                            {"requested_role": "posko_operator", "role_request_status": "pending"})
        from rescue_net.services import inbox as _ib
        _ib.notify_admins("Permohonan jadi petugas posko '%s' menunggu di Verifikasi." %
                          (frappe.db.get_value("RN Posko", posko, "title") or posko), "verification-approval.html")
        return {"result": "operator_request_pending", "user_account": actor.name, "posko": posko,
                "requested_role": "posko_operator"}

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

    # O-10: an operator who is already effective and creates another posko
    # waits here too — their new assignment is pending, the role is not
    seen = {u.name for u in users}
    waiting = set(frappe.get_all(
        "RN Posko Assignment",
        filters={"status": "pending"},
        pluck="user_account",
    )) - seen
    users += [] if not waiting else frappe.get_all(
        "RN User Account",
        filters={
            "role": "posko_operator",
            "status": "active",
            "name": ["in", sorted(waiting)],
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

    if assignment.status != "pending":
        frappe.throw("Posko assignment bukan pending")

    # an already-effective operator only gets the new posko (O-10)
    if user.role != "posko_operator":
        if user.requested_role != "posko_operator":
            frappe.throw("User tidak meminta role posko_operator")

        if user.role_request_status != "pending":
            frappe.throw("Role request bukan pending")

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

    if assignment.status != "pending":
        frappe.throw("Posko assignment bukan pending")

    # an already-effective operator keeps the role; only this posko is refused
    if user.role != "posko_operator":
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
