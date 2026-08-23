import hashlib

import frappe
from frappe.model.document import Document


class RNSearchFoundMatch(Document):
    def autoname(self):
        if self.legacy_id:
            self.name = self.legacy_id
            return

        seed = (
            f"{self.missing_report}:"
            f"{self.found_report}:"
            f"{frappe.generate_hash(length=12)}"
        )

        self.name = (
            "rn-search-match-"
            + hashlib.sha256(
                seed.encode()
            ).hexdigest()[:20]
        )

    def validate(self):
        if self.match_status not in {
            "proposed",
            "confirmed",
            "rejected",
            "reunited",
        }:
            frappe.throw(
                "Status pencocokan tidak valid"
            )
