"""Phase 4: every DocType now lives in an RN <Domain> module; the old
catch-all module "Rescue Net" is empty and its Module Def goes — unless some
record (report, page, workspace, …) still points at it, then it stays and
the leftover is logged."""

import frappe

OLD = "Rescue Net"


def execute():
    if not frappe.db.exists("Module Def", OLD):
        return
    users = [dt for dt in ("DocType", "Report", "Page", "Workspace", "Print Format", "Web Form", "Dashboard Chart")
             if frappe.db.exists(dt, {"module": OLD})]
    if users:
        frappe.log_error(title="Module Def 'Rescue Net' kept", message=f"still used by: {users}")
        return
    frappe.delete_doc("Module Def", OLD, force=True, ignore_permissions=True)
