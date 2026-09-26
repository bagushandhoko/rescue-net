import hashlib

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


COUNT_FIELDS = (
    "capacity_total",
    "current_occupancy",
    "families_count",
    "infants_count",
    "children_count",
    "elderly_count",
    "pregnant_count",
    "disability_count",
)


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


class RNShelterOccupancy(Document):
    def autoname(self):
        if self.legacy_id:
            self.name = self.legacy_id
            return

        seed = (
            f"{self.posko}:"
            f"{self.shelter_name}:"
            f"{frappe.generate_hash(length=12)}"
        )

        self.name = (
            "rn-shelter-occ-"
            + hashlib.sha256(
                seed.encode()
            ).hexdigest()[:20]
        )

    def before_insert(self):
        if self.legacy_id:
            return

        self.observed_at = (
            self.observed_at
            or now_datetime()
        )

        self.source_updated_at = (
            self.source_updated_at
            or self.observed_at
        )

        self.created_by_user = (
            self.created_by_user
            or actor_name()
        )

    def validate(self):
        for fieldname in COUNT_FIELDS:
            value = getattr(
                self,
                fieldname,
                0,
            ) or 0

            if int(value) < 0:
                frappe.throw(
                    f"{fieldname} tidak boleh negatif"
                )

        # functional never exceeds what exists (a count left empty = not reported)
        for functional, total, label in (
            ("toilet_functional", "toilet_total", "Toilet berfungsi tidak boleh melebihi toilet tersedia."),
            ("water_point_functional", "water_point_total", "Titik air berfungsi tidak boleh melebihi titik air tersedia."),
        ):
            f, t = self.get(functional), self.get(total)
            if f not in (None, "") and t not in (None, "") and int(f) > int(t):
                frappe.throw(label)

        # shelters do overflow in the field: an occupancy above capacity is
        # accepted and flagged on the row, never refused
        capacity = int(self.capacity_total or 0)
        self.over_capacity = int(
            capacity > 0
            and int(self.current_occupancy or 0) > capacity
        )
