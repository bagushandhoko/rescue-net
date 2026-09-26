import hashlib

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


CATEGORIES = {
    "ht", "repeater", "telepon_satelit", "starlink",
    "vsat", "router_4g5g", "antena_mast",
}
STATUS = {"active", "spare", "inactive", "needs_attention"}


def actor_name():
    if frappe.session.user in ("Guest", "Administrator"):
        return None

    return frappe.db.get_value(
        "RN User Account",
        {"frappe_user": frappe.session.user, "status": "active"},
        "name",
    )


class RNCommsDevice(Document):
    def autoname(self):
        if self.legacy_id:
            self.name = self.legacy_id
            return

        seed = (
            f"{self.disaster_event}:{self.device_name}:"
            f"{frappe.generate_hash(length=12)}"
        )

        self.name = (
            "rn-comms-device-"
            + hashlib.sha256(seed.encode()).hexdigest()[:20]
        )

    def before_insert(self):
        if self.legacy_id:
            return

        self.observed_at = self.observed_at or now_datetime()
        self.created_by_user = self.created_by_user or actor_name()

    def validate(self):
        if self.category and self.category not in CATEGORIES:
            frappe.throw("Kategori alat komunikasi tidak valid")

        if self.status and self.status not in STATUS:
            frappe.throw("Status alat tidak valid")

        if self.battery_pct is not None and not (0 <= float(self.battery_pct) <= 100):
            frappe.throw("Baterai harus antara 0-100%")
