import hashlib

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


def _actor():
    if frappe.session.user in (
        "Guest",
        "Administrator",
    ):
        return None

    return frappe.db.get_value(
        "RN User Account",
        {
            "frappe_user": frappe.session.user,
            "status": "active",
        },
        "name",
    )


class RNMedicalSupplyUse(Document):
    def autoname(self):
        if self.legacy_id:
            self.name = self.legacy_id
            return

        seed = (
            f"{self.posko}:"
            f"{self.item_name}:"
            f"{frappe.generate_hash(length=12)}"
        )

        self.name = (
            "rn-medical-use-"
            + hashlib.sha256(
                seed.encode()
            ).hexdigest()[:20]
        )

    def before_insert(self):
        self.used_at = (
            self.used_at or now_datetime()
        )

        self.created_by_user = (
            self.created_by_user or _actor()
        )

    def validate(self):
        if self.quantity is None:
            frappe.throw(
                "Jumlah pemakaian wajib diisi"
            )

        if float(self.quantity) <= 0:
            frappe.throw(
                "Jumlah pemakaian harus lebih dari 0"
            )
