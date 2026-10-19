"""Every RN Posko gets its current disaster_event as the first row of the new
served_events table (owner 2026-10-19: a posko can handle several disasters).
Written directly (no doc.save) so modified/validation of old rows stay as-is."""

import frappe
from frappe.utils import now_datetime


def execute():
    if not frappe.db.table_exists("RN Posko Served Event"):
        return
    have = set(frappe.get_all("RN Posko Served Event", filters={"parenttype": "RN Posko"},
                              fields=["parent"], pluck="parent", limit_page_length=0))
    events = set(frappe.get_all("RN Disaster Event", pluck="name", limit_page_length=0))
    now = now_datetime()
    for p in frappe.get_all("RN Posko", fields=["name", "disaster_event"], limit_page_length=0):
        if p.name in have or not p.disaster_event or p.disaster_event not in events:
            continue
        frappe.get_doc({
            "doctype": "RN Posko Served Event", "parent": p.name, "parenttype": "RN Posko",
            "parentfield": "served_events", "idx": 1, "disaster_event": p.disaster_event, "added_on": now,
        }).db_insert()
