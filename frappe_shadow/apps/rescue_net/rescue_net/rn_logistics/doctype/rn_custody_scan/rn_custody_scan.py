import frappe
from frappe.model.document import Document


class RNCustodyScan(Document):
    """Append-only chain-of-custody record: no edits, no deletes."""

    def before_save(self):
        if not self.is_new():
            frappe.throw("Catatan rantai bukti tidak dapat diubah.")

    def on_trash(self):
        frappe.throw("Catatan rantai bukti tidak dapat dihapus.")
