import hashlib
import frappe
from frappe.model.document import Document


class RNCommunityReportVerification(Document):
    def autoname(self):
        legacy_id = (self.legacy_id or "").strip()
        if legacy_id:
            self.name = legacy_id
            return

        seed = ":".join([
            str(getattr(self, "user_account", "") or ""),
            str(getattr(self, "organization", "") or ""),
            str(getattr(self, "posko", "") or ""),
            str(getattr(self, "report", "") or ""),
            frappe.generate_hash(length=12),
        ])
        self.name = "rn-community-report-verification-" + hashlib.sha256(
            seed.encode()
        ).hexdigest()[:20]
