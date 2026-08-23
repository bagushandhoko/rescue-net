import frappe
from frappe.model.document import Document


class RNPosko(Document):
    def autoname(self):
        legacy_id = (self.legacy_id or "").strip()
        if legacy_id:
            self.name = legacy_id
            return

        self.name = "rn-posko-" + frappe.generate_hash(length=20)

    def before_insert(self):
        if self.legacy_id:
            return

        self.legacy_source = None
        self.migration_status = None
        if not self.verification_status:
            self.verification_status = "self_reported"
        if not self.operational_status:
            self.operational_status = "active"
        if not self.identity_verification_status:
            self.identity_verification_status = "self_reported"

