import frappe
from frappe.model.document import Document


class RNAidReceipt(Document):
    """Catatan penerimaan bantuan per keluarga per putaran. Append-only; satu keluarga satu penerimaan per putaran
    dijamin indeks unik `round_household`."""

    def before_save(self):
        if not self.is_new():
            frappe.throw("Catatan penerimaan tidak dapat diubah.")

    def on_trash(self):
        frappe.throw("Catatan penerimaan tidak dapat dihapus.")
