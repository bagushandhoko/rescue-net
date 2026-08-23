import hashlib

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


VULNERABLE_FIELDS = (
    "infants_count",
    "children_count",
    "elderly_count",
    "pregnant_count",
    "disability_count",
)

VALID_STATUS = {
    "checked_in",
    "moved",
    "checked_out",
}


def actor_name():
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


class RNShelterHousehold(Document):
    def autoname(self):
        seed = (
            f"{self.posko}:"
            f"{self.household_code}:"
            f"{frappe.generate_hash(length=12)}"
        )

        self.name = (
            "rn-shelter-household-"
            + hashlib.sha256(
                seed.encode()
            ).hexdigest()[:20]
        )

    def before_insert(self):
        self.check_in_at = (
            self.check_in_at
            or now_datetime()
        )

        self.created_by_user = (
            self.created_by_user
            or actor_name()
        )

    def validate(self):
        members = int(
            self.members_count or 0
        )

        if members <= 0:
            frappe.throw(
                "Jumlah anggota harus lebih dari 0"
            )

        if self.household_status not in VALID_STATUS:
            frappe.throw(
                "Status keluarga tidak valid"
            )

        for fieldname in VULNERABLE_FIELDS:
            value = int(
                getattr(
                    self,
                    fieldname,
                    0,
                ) or 0
            )

            if value < 0:
                frappe.throw(
                    f"{fieldname} tidak boleh negatif"
                )

            if value > members:
                frappe.throw(
                    f"{fieldname} melebihi jumlah anggota"
                )
