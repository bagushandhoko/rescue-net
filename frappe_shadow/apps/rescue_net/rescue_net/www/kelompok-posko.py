import frappe


def get_context(context):
    context.no_cache = 1
    context.title = "Kelompok & Posko"

    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = (
            "/login?redirect-to=/kelompok-posko"
        )
        raise frappe.Redirect
