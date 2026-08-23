import frappe

def get_context(context):
    context.no_cache = 1
    context.title = "Logistik"
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/logistics-centre"
        raise frappe.Redirect
