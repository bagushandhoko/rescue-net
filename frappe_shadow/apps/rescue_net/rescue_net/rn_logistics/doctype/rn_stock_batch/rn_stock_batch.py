import frappe
from frappe.model.document import Document


class RNStockBatch(Document):
    """Lot stok dengan tanggal kedaluwarsa: append-only (stok keluar dihitung FEFO saat dibaca, bukan dengan mengubah lot)."""

    def validate(self):
        if not self.is_new():
            frappe.throw("Lot stok tidak dapat diubah.")

    def on_trash(self):
        frappe.throw("Lot stok tidak dapat dihapus.")
