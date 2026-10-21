"""Every RN Transport Space gets its current disaster_event as the first row
of served_events (owner 2026-10-19: an armada can serve several disasters)."""

import frappe


def execute():
    if not frappe.db.table_exists("RN Transport Space Event"):
        return
    have = set(frappe.get_all("RN Transport Space Event", filters={"parenttype": "RN Transport Space"},
                              pluck="parent", limit_page_length=0))
    events = set(frappe.get_all("RN Disaster Event", pluck="name", limit_page_length=0))
    for t in frappe.get_all("RN Transport Space", fields=["name", "disaster_event"], limit_page_length=0):
        if t.name in have or not t.disaster_event or t.disaster_event not in events:
            continue
        frappe.get_doc({
            "doctype": "RN Transport Space Event", "parent": t.name, "parenttype": "RN Transport Space",
            "parentfield": "served_events", "idx": 1, "disaster_event": t.disaster_event,
        }).db_insert()
