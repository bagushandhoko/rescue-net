import hashlib

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


ROLES = {"koordinator_radio", "operator", "teknisi"}
STATUS = {"online", "siaga", "istirahat", "offline"}


def actor_name():
    if frappe.session.user in ("Guest", "Administrator"):
        return None

    return frappe.db.get_value(
        "RN User Account",
        {"frappe_user": frappe.session.user, "status": "active"},
        "name",
    )


class RNCommsOperator(Document):
    def autoname(self):
        if self.legacy_id:
            self.name = self.legacy_id
            return

        seed = (
            f"{self.disaster_event}:{self.operator_name}:"
            f"{frappe.generate_hash(length=12)}"
        )

        self.name = (
            "rn-comms-operator-"
            + hashlib.sha256(seed.encode()).hexdigest()[:20]
        )

    def before_insert(self):
        if self.legacy_id:
            return

        self.observed_at = self.observed_at or now_datetime()
        self.created_by_user = self.created_by_user or actor_name()

    def validate(self):
        if self.role and self.role not in ROLES:
            frappe.throw("Peran operator komunikasi tidak valid")

        if self.status and self.status not in STATUS:
            frappe.throw("Status operator tidak valid")
