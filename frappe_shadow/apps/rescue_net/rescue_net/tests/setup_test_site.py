"""One-off preparation of the TEST site (never production).

Production has 12 Custom Fields on RN DocTypes that were created by hand in
Desk — they are not in any DocType JSON or fixture, so a fresh install (this
test site, or a restore onto a new server) lacks them and several endpoints
fail with "Unknown column". Reported to the owner 2026-09-26; the real fix is
to move them into the DocType JSON (or export them as fixtures).

Until then the test site gets equivalents so tests exercise the same code
paths. The field TYPES below are inferred from how the code uses them — they
are NOT copied from production and may differ in options/labels.

    bench --site rescuenet-test.localhost execute rescue_net.tests.setup_test_site.ensure_custom_fields
"""

import frappe

INFERRED_CUSTOM_FIELDS = {
    "RN Posko": [
        ("rn_comms_status", "Data"),
        ("rn_comms_last_contact", "Datetime"),
        ("rn_logistics_role", "Data"),
        ("rn_fn_kitchen", "Check"),
        ("rn_fn_shelter", "Check"),
        ("rn_fn_logistics", "Check"),
        ("rn_beneficiary_count", "Int"),
        ("rn_beneficiary_note", "Small Text"),
        ("rn_beneficiary_updated_at", "Datetime"),
    ],
    "RN Distribution Flow": [
        ("rn_movement_type", "Data"),
    ],
    "RN Stock Observation": [
        ("rn_consumption_source", "Data"),
        ("rn_daily_consumption", "Float"),
    ],
}


def ensure_custom_fields():
    if not frappe.conf.get("allow_tests") or frappe.local.site == "osiun.localhost":
        frappe.throw("setup_test_site only runs on a test site (allow_tests)")

    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

    create_custom_fields(
        {
            dt: [
                {"fieldname": name, "fieldtype": ftype, "label": name.replace("rn_", "").replace("_", " ").title()}
                for name, ftype in fields
            ]
            for dt, fields in INFERRED_CUSTOM_FIELDS.items()
        },
        update=True,
    )
    frappe.db.commit()
    print("test-site custom fields ensured:", sum(len(v) for v in INFERRED_CUSTOM_FIELDS.values()))
