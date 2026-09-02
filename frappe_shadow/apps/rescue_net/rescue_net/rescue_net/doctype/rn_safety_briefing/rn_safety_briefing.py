import hashlib

import frappe
from frappe.model.document import Document


STATUS = {"scheduled", "completed", "cancelled"}


def actor_name():
    if frappe.session.user in ("Guest", "Administrator"):
        return None

    return frappe.db.get_value(
        "RN User Account",
        {"frappe_user": frappe.session.user, "status": "active"},
        "name",
    )


class RNSafetyBriefing(Document):
    def autoname(self):
        if self.legacy_id:
            self.name = self.legacy_id
            return

        seed = (
            f"{self.disaster_event}:{self.title}:"
            f"{frappe.generate_hash(length=12)}"
        )

        self.name = (
            "rn-safety-briefing-"
            + hashlib.sha256(seed.encode()).hexdigest()[:20]
        )

    def before_insert(self):
        if self.legacy_id:
            return

        self.created_by_user = self.created_by_user or actor_name()

    def validate(self):
        if self.briefing_status and self.briefing_status not in STATUS:
            frappe.throw("Status briefing tidak valid")
