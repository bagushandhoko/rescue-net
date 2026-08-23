import hashlib

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


AVAILABILITY = {
    "available",
    "limited",
    "assigned",
    "unavailable",
}


class RNVolunteerProfile(Document):
    def autoname(self):
        if self.legacy_id:
            self.name = self.legacy_id
            return

        seed = (
            f"{self.user_account or ''}:"
            f"{self.volunteer_name}:"
            f"{frappe.generate_hash(length=12)}"
        )

        self.name = (
            "rn-volunteer-"
            + hashlib.sha256(
                seed.encode()
            ).hexdigest()[:20]
        )

    def before_insert(self):
        if self.legacy_id:
            return

        self.observed_at = (
            self.observed_at
            or now_datetime()
        )

        self.source_updated_at = (
            self.source_updated_at
            or self.observed_at
        )

    def validate(self):
        if (
            self.availability_status
            not in AVAILABILITY
        ):
            frappe.throw(
                "Availability relawan tidak valid"
            )
