import frappe
from frappe.model.document import Document


class RNProgramNeed(Document):
    def validate(self):
        from rescue_net.services.guards import assert_non_negative
        assert_non_negative(self, "qty_needed", "qty_available")
