import frappe
from frappe.model.document import Document

_MUTABLE = {"verification_status", "verified_by", "modified", "modified_by"}


class RNAccessStatus(Document):
    """Riwayat status akses: append-only (status baru = baris baru; hanya penandaan terverifikasi yang boleh mengubah)."""

    def validate(self):
        if self.is_new():
            return
        before = self.get_doc_before_save()
        for df in self.meta.fields:
            if df.fieldname in _MUTABLE or df.fieldtype in ("Section Break", "Column Break"):
                continue
            if before is not None and self.get(df.fieldname) != before.get(df.fieldname):
                frappe.throw("Riwayat status akses tidak dapat diubah (buat laporan baru).")

    def on_trash(self):
        frappe.throw("Riwayat status akses tidak dapat dihapus.")
