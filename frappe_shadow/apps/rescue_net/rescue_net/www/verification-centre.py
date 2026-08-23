import frappe


def get_context(context):
    context.no_cache = 1
    context.title = "Verification Centre"

    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = (
            "/login?redirect-to=/verification-centre"
        )
        raise frappe.Redirect
