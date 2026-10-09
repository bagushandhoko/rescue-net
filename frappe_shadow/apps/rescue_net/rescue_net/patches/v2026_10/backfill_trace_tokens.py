"""Beri setiap RN Distribution Flow yang belum punya kode lacak acak sebuah token. Label QR lama (8 karakter terakhir
nama) tetap berlaku lewat jalur cadangan di _resolve_flow_by_trace."""

import frappe

from rescue_net.services.trace import unique_token


def execute():
    if not frappe.db.has_column("RN Distribution Flow", "trace_token"):
        return
    for name in frappe.get_all("RN Distribution Flow", filters={"trace_token": ["is", "not set"]}, pluck="name",
                               limit_page_length=0):
        frappe.db.set_value("RN Distribution Flow", name, "trace_token", unique_token(), update_modified=False)
