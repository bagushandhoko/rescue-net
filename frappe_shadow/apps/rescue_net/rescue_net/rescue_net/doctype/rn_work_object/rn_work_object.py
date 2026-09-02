import hashlib

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


OBJECT_TYPES = {
    "longsoran", "jembatan_putus", "puing_berat",
    "pohon_tumbang", "akses_terendam", "lainnya",
}
STATUS = {"open", "in_progress", "resolved"}


def actor_name():
    if frappe.session.user in ("Guest", "Administrator"):
        return None

    return frappe.db.get_value(
        "RN User Account",
        {"frappe_user": frappe.session.user, "status": "active"},
        "name",
    )


class RNWorkObject(Document):
    def autoname(self):
        if self.legacy_id:
            self.name = self.legacy_id
            return

        seed = (
            f"{self.disaster_event}:{self.title}:"
            f"{frappe.generate_hash(length=12)}"
        )

        self.name = (
            "rn-work-object-"
            + hashlib.sha256(seed.encode()).hexdigest()[:20]
        )

    def before_insert(self):
        if self.legacy_id:
            return

        self.observed_at = self.observed_at or now_datetime()
        self.created_by_user = self.created_by_user or actor_name()

    def validate(self):
        if self.object_type and self.object_type not in OBJECT_TYPES:
            frappe.throw("Jenis object kerja tidak valid")

        if self.status and self.status not in STATUS:
            frappe.throw("Status penanganan tidak valid")

        if self.size_value is not None and float(self.size_value) <= 0:
            frappe.throw("Ukuran object kerja harus lebih dari 0")
