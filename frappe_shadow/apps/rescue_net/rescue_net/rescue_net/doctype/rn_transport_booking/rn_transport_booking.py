import hashlib

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


STATUS = {"requested", "confirmed", "rejected", "cancelled", "completed"}


class RNTransportBooking(Document):
    def autoname(self):
        if self.legacy_id:
            self.name = self.legacy_id
            return

        seed = (
            f"{self.transport_space}:{self.cargo_desc or ''}:"
            f"{frappe.generate_hash(length=12)}"
        )
        self.name = (
            "rn-transport-booking-"
            + hashlib.sha256(seed.encode()).hexdigest()[:20]
        )

    def before_insert(self):
        if not self.requested_at:
            self.requested_at = now_datetime()
        if not self.status:
            self.status = "requested"

    def validate(self):
        if self.status and self.status not in STATUS:
            frappe.throw("Status booking tidak valid")
        for f in ("qty_weight_kg", "qty_volume_m3"):
            v = self.get(f)
            if v is not None and float(v) < 0:
                frappe.throw("Kuantitas booking tidak boleh negatif")
