import frappe
from frappe.model.document import Document

# satu-satunya yang boleh berubah setelah dibuat: check-out, penutupan otomatis, tinjauan walk-in
_MUTABLE = {"out_at", "auto_closed", "review_status", "reviewed_by", "modified", "modified_by"}


class RNVolunteerPresence(Document):
    """Catatan kehadiran relawan di posko: append-only (hanya check-out/tinjauan yang boleh mengisi), tak bisa dihapus."""

    def validate(self):
        if self.is_new():
            return
        before = self.get_doc_before_save()
        if before is None:
            return
        for df in self.meta.fields:
            if df.fieldname in _MUTABLE or df.fieldtype in ("Section Break", "Column Break"):
                continue
            if self.get(df.fieldname) != before.get(df.fieldname):
                frappe.throw("Catatan kehadiran tidak dapat diubah (hanya check-out/tinjauan).")
        if before.out_at and self.out_at != before.out_at:
            frappe.throw("Check-out sudah tercatat.")

    def on_trash(self):
        frappe.throw("Catatan kehadiran tidak dapat dihapus.")
