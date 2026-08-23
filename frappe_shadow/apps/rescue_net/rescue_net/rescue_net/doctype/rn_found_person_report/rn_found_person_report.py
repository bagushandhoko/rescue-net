import hashlib

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class RNFoundPersonReport(Document):
    def autoname(self):
        if self.legacy_id:
            self.name = self.legacy_id
            return

        seed = (
            f"{self.person_code}:"
            f"{frappe.generate_hash(length=12)}"
        )

        self.name = (
            "rn-found-"
            + hashlib.sha256(
                seed.encode()
            ).hexdigest()[:20]
        )

    def before_insert(self):
        if not self.legacy_id:
            self.observed_at = (
                self.observed_at
                or now_datetime()
            )

    def validate(self):
        if self.report_status not in {
            "found",
            "reunited",
            "closed",
        }:
            frappe.throw(
                "Status laporan ditemukan tidak valid"
            )
