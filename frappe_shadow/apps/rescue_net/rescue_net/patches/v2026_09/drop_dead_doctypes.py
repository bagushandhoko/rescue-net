"""Phase 4: four FastAPI-era DocTypes that no code reads or writes are
deleted (with their tables). Their rows were exported first to
/volume1/docker/osiun-backups/rescue-net-legacy/export-*.tsv."""

import frappe

DEAD = ("RN Volunteer", "RN User Session", "RN War Room Snapshot", "RN Trusted Verification Request")


def execute():
    for name in DEAD:
        if frappe.db.exists("DocType", name):
            frappe.delete_doc("DocType", name, force=True, ignore_permissions=True, ignore_missing=True)
        # deleting a standard DocType leaves its table behind
        frappe.db.sql_ddl(f"DROP TABLE IF EXISTS `tab{name}`")
