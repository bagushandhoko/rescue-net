import hashlib

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class RNKitchenIngredientUsage(Document):
    def autoname(self):
        if self.legacy_id:
            self.name = self.legacy_id
            return

        seed = (
            f"{self.production}:"
            f"{self.item_name}:"
            f"{frappe.generate_hash(length=10)}"
        )

        self.name = (
            "rn-kitchen-use-"
            + hashlib.sha256(
                seed.encode()
            ).hexdigest()[:20]
        )

    def validate(self):
        if flt(self.quantity) <= 0:
            frappe.throw(
                "Pemakaian bahan harus lebih dari 0"
            )

        if self.usage_status != "consumed":
            frappe.throw(
                "Status penggunaan bahan tidak valid"
            )
