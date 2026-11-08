"""In-app notifications (owner 2026-11-08). Writes Frappe "Notification Log" rows that the 🔔 inbox
(assets/js/rn-ai-notice.js, api_inbox.my_notifications) shows. Never raises: a failed notice must not
break the action that triggered it."""

import frappe


def _user_of(account):
    if not account:
        return None
    return frappe.db.get_value("RN User Account", account, "frappe_user")


def notify_user(user, subject, link=None):
    try:
        if not user or user in ("Guest", "Administrator") or not frappe.db.exists("User", user):
            return
        doc = {"doctype": "Notification Log", "for_user": user, "type": "Alert", "subject": str(subject)[:140]}
        if link:
            doc["email_content"] = "link:" + str(link)[:400]
        frappe.get_doc(doc).insert(ignore_permissions=True)
    except Exception:
        frappe.log_error(title="rn inbox notify_user failed")


def notify_account(account, subject, link=None):
    notify_user(_user_of(account), subject, link)


def notify_org_managers(org, subject, link=None, roles=("owner", "deputy", "staff")):
    try:
        for acc in frappe.get_all("RN Organization Membership",
                                  filters={"organization": org, "status": "approved", "membership_role": ["in", list(roles)]},
                                  pluck="user_account"):
            notify_account(acc, subject, link)
    except Exception:
        frappe.log_error(title="rn inbox notify_org_managers failed")


def notify_admins(subject, link=None):
    try:
        users = set(frappe.get_all("Has Role", filters={"role": "System Manager", "parenttype": "User"}, pluck="parent"))
        for u in users - {"Guest", "Administrator"}:
            if frappe.db.get_value("User", u, "enabled"):
                notify_user(u, subject, link)
    except Exception:
        frappe.log_error(title="rn inbox notify_admins failed")
