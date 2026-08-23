import hashlib

import frappe
from frappe.model.document import Document


STATUS = {
    "planned",
    "accepted",
    "checked_in",
    "in_progress",
    "completed",
    "cancelled",
}


class RNVolunteerAssignment(Document):
    def autoname(self):
        if self.legacy_id:
            self.name = self.legacy_id
            return

        seed = (
            f"{self.volunteer}:"
            f"{self.posko}:"
            f"{self.task_title}:"
            f"{frappe.generate_hash(length=12)}"
        )

        self.name = (
            "rn-volunteer-assignment-"
            + hashlib.sha256(
                seed.encode()
            ).hexdigest()[:20]
        )

    def validate(self):
        if self.assignment_status not in STATUS:
            frappe.throw(
                "Status penugasan tidak valid"
            )
