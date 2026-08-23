import hashlib

import frappe
from frappe.model.document import Document
from frappe.utils import cint


class RNKitchenProduction(Document):
    def autoname(self):
        if self.legacy_id:
            self.name = self.legacy_id
            return

        seed = (
            f"{self.meal_name}:"
            f"{frappe.generate_hash(length=12)}"
        )

        self.name = (
            "rn-kitchen-"
            + hashlib.sha256(
                seed.encode()
            ).hexdigest()[:20]
        )

    def validate(self):
        if cint(self.portions) <= 0:
            frappe.throw(
                "Jumlah porsi harus lebih dari 0"
            )

        if self.production_status not in {
            "prepared",
            "dispatched",
            "distributed",
        }:
            frappe.throw(
                "Status produksi tidak valid"
            )
