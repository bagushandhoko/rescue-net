import frappe


def get_context(context):
    context.no_cache = 1
    context.title = "Approval Operator Posko"

    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login"
        raise frappe.Redirect

    if (
        frappe.session.user != "Administrator"
        and "System Manager" not in frappe.get_roles()
    ):
        frappe.throw(
            "System Manager diperlukan",
            frappe.PermissionError,
        )
