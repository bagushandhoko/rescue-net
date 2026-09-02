import hashlib

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


TYPES = {"mess", "rumah_singgah", "tenda", "hotel", "lainnya"}
SAFETY_STATUS = {"aman", "perlu_perhatian", "darurat"}


def actor_name():
    if frappe.session.user in ("Guest", "Administrator"):
        return None

    return frappe.db.get_value(
        "RN User Account",
        {"frappe_user": frappe.session.user, "status": "active"},
        "name",
    )


class RNVolunteerAccommodation(Document):
    def autoname(self):
        if self.legacy_id:
            self.name = self.legacy_id
            return

        seed = (
            f"{self.disaster_event}:{self.location_name}:"
            f"{frappe.generate_hash(length=12)}"
        )

        self.name = (
            "rn-vol-accom-"
            + hashlib.sha256(seed.encode()).hexdigest()[:20]
        )

    def before_insert(self):
        if self.legacy_id:
            return

        self.observed_at = self.observed_at or now_datetime()
        self.created_by_user = self.created_by_user or actor_name()

    def validate(self):
        if self.accommodation_type and self.accommodation_type not in TYPES:
            frappe.throw("Jenis akomodasi tidak valid")

        if self.safety_status and self.safety_status not in SAFETY_STATUS:
            frappe.throw("Status keselamatan tidak valid")

        if self.capacity_beds is not None and float(self.capacity_beds) < 0:
            frappe.throw("Kapasitas tidak boleh negatif")

        if self.occupants_count is not None and float(self.occupants_count) < 0:
            frappe.throw("Jumlah menginap tidak boleh negatif")
