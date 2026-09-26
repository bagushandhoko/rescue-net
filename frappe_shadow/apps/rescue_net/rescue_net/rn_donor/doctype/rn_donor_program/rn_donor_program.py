import frappe
from frappe.model.document import Document


class RNDonorProgram(Document):
    def autoname(self):
        self.name = (
            "rn-donor-"
            + frappe.generate_hash(length=12)
        )
