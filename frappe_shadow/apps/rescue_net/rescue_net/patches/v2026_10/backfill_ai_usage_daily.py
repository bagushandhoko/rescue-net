"""Build RN AI Usage Daily from the RN AI Usage Log rows that exist today, so budgets
and the usage summary start from the real totals. Rows that already exist are left alone."""

import frappe

from rescue_net.rn_intelligence.doctype.rn_ai_usage_daily.rn_ai_usage_daily import daily_name


def execute():
    if not frappe.db.exists("DocType", "RN AI Usage Daily"):
        return
    rows = frappe.db.sql(
        """select date(creation) d, owner_type, owner_id, count(*) n,
                  sum(outcome != 'ok') errs, coalesce(sum(total_tokens), 0) tok
           from `tabRN AI Usage Log` where owner_id is not null and owner_id != ''
           group by date(creation), owner_type, owner_id""", as_dict=True)
    for r in rows:
        name = daily_name(r.d, r.owner_type or "user", r.owner_id)
        if frappe.db.exists("RN AI Usage Daily", name):
            continue
        frappe.get_doc({"doctype": "RN AI Usage Daily", "usage_date": r.d, "owner_type": r.owner_type or "user",
                        "owner_id": r.owner_id, "requests": r.n, "errors": int(r.errs or 0),
                        "total_tokens": int(r.tok)}).insert(ignore_permissions=True)
