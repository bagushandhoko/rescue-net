import hashlib

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


def _actor():
    if frappe.session.user in (
        "Guest",
        "Administrator",
    ):
        return None

    return frappe.db.get_value(
        "RN User Account",
        {
            "frappe_user": frappe.session.user,
            "status": "active",
        },
        "name",
    )


class RNMedicalEvidence(Document):
    def autoname(self):
        seed = (
            f"{self.reference_doctype}:"
            f"{self.reference_name}:"
            f"{frappe.generate_hash(length=12)}"
        )

        self.name = (
            "rn-medical-evidence-"
            + hashlib.sha256(
                seed.encode()
            ).hexdigest()[:20]
        )

    def before_insert(self):
        self.uploaded_at = (
            self.uploaded_at or now_datetime()
        )

        self.uploaded_by_user = (
            self.uploaded_by_user or _actor()
        )
