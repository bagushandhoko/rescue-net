from frappe.model.document import Document


class RNDisasterEvent(Document):
    def validate(self):
        if self.get("drill_scope") == "dms":
            self.is_drill = 1
            self.federation_share = 0
