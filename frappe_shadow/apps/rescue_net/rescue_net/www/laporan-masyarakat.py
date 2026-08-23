import frappe


def get_context(context):
    context.no_cache = 1
    context.title = "Laporan Masyarakat"

    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = (
            "/login?redirect-to=/laporan-masyarakat"
        )
        raise frappe.Redirect
