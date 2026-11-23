"""Rollback one explicitly identified DMS exercise event with the RN cleanup manifest."""
import frappe

from rescue_net.dms_sim.seed import SOURCE, STARTS
from rescue_net.services.drill_tools import delete_manifest, preview_linked_cleanup


def preview(event):
    if event not in STARTS or not frappe.db.exists("RN Disaster Event", {
        "name": event, "drill_scope": "dms", "is_drill": 1, "legacy_source": SOURCE,
    }):
        frappe.throw("Kejadian seed simulasi DMS tidak ditemukan.")
    return preview_linked_cleanup(event)


def run(event, confirm_total):
    return delete_manifest(preview(event), confirm_total)
