"""Mode latihan (Fase 10g) — hanya System Manager (owner: yang membuat/menghapus latihan)."""

import frappe

from rescue_net.services import drill_tools


def _only_system_manager():
    if "System Manager" not in frappe.get_roles():
        frappe.throw("Hanya System Manager yang boleh mengelola mode latihan.", frappe.PermissionError)


@frappe.whitelist(methods=["POST"])
def create_drill(template="banjir"):
    _only_system_manager()
    return {"event": drill_tools.create_drill(template), "templates": sorted(drill_tools.TEMPLATES)}


@frappe.whitelist()
def drill_cleanup_preview(event):
    _only_system_manager()
    return drill_tools.preview_cleanup(event)


@frappe.whitelist(methods=["POST"])
def drill_cleanup(event, confirm_total):
    _only_system_manager()
    return drill_tools.cleanup(event, confirm_total)
