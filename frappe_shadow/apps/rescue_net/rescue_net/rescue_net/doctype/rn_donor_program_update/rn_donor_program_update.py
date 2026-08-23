import frappe
from frappe.model.document import Document


class RNDonorProgramUpdate(Document):
    def autoname(self):
        self.name = (
            "rn-donorupd-"
            + frappe.generate_hash(length=12)
        )
