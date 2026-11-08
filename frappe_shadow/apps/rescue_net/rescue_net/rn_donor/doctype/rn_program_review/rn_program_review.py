import frappe
from frappe.model.document import Document


class RNProgramReview(Document):
    def autoname(self):
        self.name = "rn-review-" + frappe.generate_hash(length=12)

    def validate(self):
        if not (1 <= int(self.rating or 0) <= 5):
            frappe.throw("Nilai harus 1 sampai 5 bintang.")
