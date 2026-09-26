import hashlib

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class RNWorkToolRequest(Document):
    def autoname(self):
        if self.legacy_id:
            self.name = self.legacy_id
            return

        seed = (
            f"{self.tool_name}:"
            f"{frappe.generate_hash(length=12)}"
        )

        self.name = (
            "rn-tool-request-"
            + hashlib.sha256(
                seed.encode()
            ).hexdigest()[:20]
        )

    def validate(self):
        if self.requested_by_type not in {
            "posko",
            "organization",
            "other",
        }:
            frappe.throw(
                "Requested by type tidak valid"
            )

        if self.priority not in {
            "normal",
            "urgent",
            "critical",
        }:
            frappe.throw(
                "Priority tidak valid"
            )

        if self.request_status not in {
            "requested",
            "matched",
            "in_progress",
            "partially_fulfilled",
            "fulfilled",
            "cancelled",
        }:
            frappe.throw(
                "Status Work Tool Request tidak valid"
            )

        if flt(self.quantity) <= 0:
            frappe.throw(
                "Quantity request harus lebih dari 0"
            )
