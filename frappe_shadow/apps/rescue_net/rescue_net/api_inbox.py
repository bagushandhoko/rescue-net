"""🔔 Kotak pemberitahuan (owner 2026-11-08): the logged-in user's in-app notifications."""

import frappe
from frappe.rate_limiter import rate_limit
from frappe.utils import cint


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=240, seconds=60)
def my_notifications(limit=20):
    user = frappe.session.user
    if not user or user == "Guest":
        return {"logged_in": False, "unread": 0, "items": []}
    rows = frappe.get_all("Notification Log", filters={"for_user": user},
                          fields=["name", "subject", "read", "creation", "email_content"],
                          order_by="creation desc", limit_page_length=min(cint(limit) or 20, 50))
    unread = frappe.db.count("Notification Log", {"for_user": user, "read": 0})
    items = []
    for r in rows:
        link = r.email_content[5:] if (r.email_content or "").startswith("link:") else None
        items.append({"id": r.name, "subject": frappe.utils.strip_html(r.subject or ""), "read": bool(r.read),
                      "at": str(r.creation)[:16], "link": link})
    return {"logged_in": True, "unread": unread, "items": items}


@frappe.whitelist(methods=["POST"])
def mark_notifications_read(notification=None):
    user = frappe.session.user
    if not user or user == "Guest":
        frappe.throw("Login diperlukan", frappe.PermissionError)
    filters = {"for_user": user, "read": 0}
    if notification:
        filters["name"] = notification
    for n in frappe.get_all("Notification Log", filters=filters, pluck="name", limit_page_length=500):
        frappe.db.set_value("Notification Log", n, "read", 1, update_modified=False)
    return {"ok": True}
