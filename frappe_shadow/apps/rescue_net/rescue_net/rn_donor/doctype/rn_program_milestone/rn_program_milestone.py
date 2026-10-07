import frappe
from frappe.model.document import Document


class RNProgramMilestone(Document):
    def validate(self):
        p = int(self.progress_percent or 0)
        if not 0 <= p <= 100:
            frappe.throw("Progres milestone harus 0-100.")
        if self.milestone_status == "selesai":
            self.progress_percent = 100
            self.completed_at = self.completed_at or frappe.utils.nowdate()
        elif self.milestone_status == "belum_mulai":
            self.progress_percent = 0
            self.completed_at = None
        else:
            self.completed_at = None
            if p >= 100:
                frappe.throw("Milestone berjalan tidak bisa 100%; tandai selesai.")
