"""Kedaluwarsa stok per posko (Fase 10d) — hanya operator posko (data stok tidak publik)."""

import frappe

from rescue_net.access_policy import rn_actor
from rescue_net.logistics.common import _can_operate
from rescue_net.services import expiry


def _assert_operator(posko):
    actor = rn_actor()
    if not frappe.db.exists("RN Posko", posko):
        frappe.throw("Posko tidak ditemukan.", frappe.DoesNotExistError)
    if "System Manager" not in frappe.get_roles() and not _can_operate(actor, posko):
        frappe.throw("Akses posko ditolak", frappe.PermissionError)


@frappe.whitelist()
def expiring(posko, days=None):
    _assert_operator(posko)
    return expiry.expiring_report(posko, int(days) if days else None)


@frappe.whitelist(methods=["POST"])
def add_lot(posko, item_name, unit, quantity, expiry_date, batch_no=None):
    """Beri tanggal kedaluwarsa pada stok yang sudah ada (tidak mengubah jumlah stok)."""
    _assert_operator(posko)
    item_name, unit = str(item_name or "").strip(), str(unit or "").strip()
    if not item_name or not unit:
        frappe.throw("Barang dan satuan wajib diisi.")
    name = expiry.record_lot(posko, item_name, unit, quantity, expiry_date, batch_no, source="manual:" + frappe.session.user)
    if not name:
        frappe.throw("Jumlah harus > 0 dan tanggal kedaluwarsa wajib.")
    return {"lot": name, "report": expiry.expiring_report(posko)}
