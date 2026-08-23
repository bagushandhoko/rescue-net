import hashlib
import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class RNOperationalEvidence(Document):
    def autoname(self):
        seed = f"{self.linked_doctype}:{self.linked_name}:{frappe.generate_hash(length=12)}"
        self.name = "rn-evidence-" + hashlib.sha256(
            seed.encode()
        ).hexdigest()[:20]

    def before_insert(self):
        if not self.uploaded_at:
            self.uploaded_at = now_datetime()

        if not self.observed_at:
            self.observed_at = self.uploaded_at

        if (
            not self.uploader_user
            and frappe.session.user not in ("Guest", "Administrator")
        ):
            self.uploader_user = frappe.db.get_value(
                "RN User Account",
                {
                    "frappe_user": frappe.session.user,
                    "status": "active",
                },
                "name",
            )
