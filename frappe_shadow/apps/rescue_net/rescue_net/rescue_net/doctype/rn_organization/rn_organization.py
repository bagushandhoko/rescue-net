import frappe
from frappe.model.document import Document


class RNOrganization(Document):
    def autoname(self):
        legacy_id = (self.legacy_id or "").strip()
        if legacy_id:
            self.name = legacy_id
            return

        self.name = "rn-org-" + frappe.generate_hash(length=20)

    def before_insert(self):
        if self.legacy_id:
            return

        self.legacy_source = None
        self.migration_status = None
        if not self.status:
            self.status = "pending"
        if not self.trust_level:
            self.trust_level = "unverified"
        if not self.identity_verification_status:
            self.identity_verification_status = "unverified"


    # RN_PRIVACY_GUARD_V1
    def validate(self):
        if not self.privacy_mode:
            self.privacy_mode = "closed"

        if self.privacy_mode == "closed":
            self.allow_posko_public_choice = 0

        if not self.control_centre_share:
            self.control_centre_share = "aggregate"
