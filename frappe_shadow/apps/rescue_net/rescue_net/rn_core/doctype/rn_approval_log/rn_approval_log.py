from frappe.model.document import Document


class RNApprovalLog(Document):
    """Append-only record of one approve / reject / revise / escalate decision."""

    def before_save(self):
        if not self.is_new():
            import frappe
            frappe.throw("Log persetujuan tidak boleh diubah.")
