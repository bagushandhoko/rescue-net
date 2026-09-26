import hashlib

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


VALID_STATUS = {
    "available",
    "reserved",
    "assigned",
    "in_transit",
    "arrived",
    "completed",
    "cancelled",
}


def _actor():
    if frappe.session.user in ("Guest", "Administrator"):
        return None

    return frappe.db.get_value(
        "RN User Account",
        {
            "frappe_user": frappe.session.user,
            "status": "active",
        },
        "name",
    )


class RNTransportSpace(Document):
    def autoname(self):
        if self.legacy_id:
            self.name = self.legacy_id
            return

        seed = (
            f"{self.provider_name or ''}:"
            f"{self.coordination_posko or ''}:"
            f"{frappe.generate_hash(length=12)}"
        )

        self.name = (
            "rn-transport-"
            + hashlib.sha256(seed.encode()).hexdigest()[:20]
        )

    def before_insert(self):
        if self.legacy_id:
            return

        self.legacy_source = None
        self.migration_status = None

        if not self.created_by_user:
            self.created_by_user = _actor()

        if not self.transport_status:
            self.transport_status = "available"

        if not self.observed_at:
            self.observed_at = now_datetime()

        if not self.source_updated_at:
            self.source_updated_at = self.observed_at

        if not self.verification_status:
            self.verification_status = "self_reported"

    def validate(self):
        if (
            not self.legacy_id
            and self.transport_status
            and self.transport_status not in VALID_STATUS
        ):
            frappe.throw("Status transport tidak valid")
