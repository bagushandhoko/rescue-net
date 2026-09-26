"""DATA-1: 12 fields on RN Posko / RN Distribution Flow / RN Stock Observation
were hand-made Custom Fields that existed only in the production database.
They are now standard fields in the DocType JSON. This patch runs before the
model sync and removes only the Custom Field records — the table columns and
their data stay, and the sync takes the same columns over as standard fields."""

import frappe

FIELDS = {
    "RN Distribution Flow": ["rn_movement_type"],
    "RN Posko": [
        "rn_fn_logistics", "rn_fn_shelter", "rn_fn_kitchen", "rn_logistics_role", "rn_comms_status",
        "rn_comms_last_contact", "rn_beneficiary_count", "rn_beneficiary_note", "rn_beneficiary_updated_at",
    ],
    "RN Stock Observation": ["rn_daily_consumption", "rn_consumption_source"],
}


def execute():
    for dt, fieldnames in FIELDS.items():
        # a raw delete: Custom Field.on_trash would also touch the column
        frappe.db.delete("Custom Field", {"dt": dt, "fieldname": ["in", fieldnames]})
    frappe.clear_cache()
