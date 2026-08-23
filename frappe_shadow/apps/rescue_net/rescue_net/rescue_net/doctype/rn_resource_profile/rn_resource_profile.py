import hashlib

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class RNResourceProfile(Document):
    def autoname(self):
        if self.legacy_id:
            self.name = self.legacy_id
            return

        seed = (
            f"{self.resource_name}:"
            f"{frappe.generate_hash(length=12)}"
        )

        self.name = (
            "rn-resource-"
            + hashlib.sha256(
                seed.encode()
            ).hexdigest()[:20]
        )

    def validate(self):
        if self.owner_type not in {
            "organization",
            "posko",
            "individual",
            "external",
        }:
            frappe.throw(
                "Owner type resource tidak valid"
            )

        if self.availability_status not in {
            "available",
            "limited",
            "unavailable",
            "maintenance",
        }:
            frappe.throw(
                "Availability resource tidak valid"
            )

        if flt(self.quantity) <= 0:
            frappe.throw(
                "Quantity resource harus lebih dari 0"
            )
