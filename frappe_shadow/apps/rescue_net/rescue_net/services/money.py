"""Program money totals (phase 2: L-9, L-17).

Totals on RN Donor Program only ever grow by an increment applied in SQL, so
two concurrent updates cannot overwrite each other (read-modify-write lost one).
"""

import frappe
from frappe.utils import flt, now_datetime

PROGRAM_TOTALS = {"current_amount", "budget_received", "budget_spent"}


def add_to_program(program, field, amount, **also):
    """Atomically add `amount` to a program total; returns the new total."""
    if field not in PROGRAM_TOTALS:
        frappe.throw(f"Total program tidak dikenal: {field}")
    amount = flt(amount)
    if amount < 0:
        frappe.throw("Jumlah tidak boleh negatif.")
    sets, values = [f"`{field}` = IFNULL(`{field}`, 0) + %s", "`modified` = %s"], [amount, now_datetime()]
    for k, v in also.items():
        if not frappe.get_meta("RN Donor Program").has_field(k):
            continue
        sets.append(f"`{k}` = %s")
        values.append(v)
    frappe.db.sql(f"UPDATE `tabRN Donor Program` SET {', '.join(sets)} WHERE name = %s",
                  (*values, program))
    return flt(frappe.db.get_value("RN Donor Program", program, field))


def lock(doctype, name):
    """Row lock for the rest of the request (a second decision waits, then sees the first)."""
    if not frappe.db.sql(f"SELECT name FROM `tab{doctype}` WHERE name=%s FOR UPDATE", (name,)):
        frappe.throw(f"{doctype} tidak ditemukan")
