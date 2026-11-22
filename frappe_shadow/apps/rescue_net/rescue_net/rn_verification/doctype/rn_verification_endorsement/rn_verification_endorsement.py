import frappe
from frappe.model.document import Document


class RNVerificationEndorsement(Document):
    def before_insert(self):
        # owner 2026-11-20: setiap endorsement punya masa berlaku (bawaan 1 tahun) kecuali diisi lain
        if not self.expires_at:
            from rescue_net.services.endorsement import default_expiry

            self.expires_at = default_expiry(self.verified_at)
