import hashlib

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


MODES = {
    "exact",
    "estimated",
    "range",
    "unknown",
}

# a shelter need is met or cancelled once; both are final
TRANSITIONS = {
    "open": {"partially_met", "met", "cancelled"},
    "partially_met": {"met", "cancelled"},
    "met": set(),
    "cancelled": set(),
}

STATUS = set(TRANSITIONS)


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


class RNShelterNeed(Document):
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
            "rn-shelter-need-"
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

        self.created_by_user = (
            self.created_by_user
            or actor_name()
        )

    def validate(self):
        if self.quantity_mode not in MODES:
            frappe.throw(
                "Mode jumlah tidak valid"
            )

        if self.need_status not in STATUS:
            frappe.throw(
                "Status kebutuhan tidak valid"
            )

        from rescue_net.services.guards import assert_transition
        assert_transition(self, "need_status", TRANSITIONS, "Status kebutuhan", initial={"open"})

        if self.quantity_mode in {
            "exact",
            "estimated",
        }:
            if (
                self.quantity_needed is None
                or float(self.quantity_needed) <= 0
            ):
                frappe.throw(
                    "Jumlah wajib untuk exact/estimated"
                )

        if self.quantity_mode == "range":
            if (
                self.quantity_min is None
                or self.quantity_max is None
            ):
                frappe.throw(
                    "Minimum dan maksimum wajib untuk range"
                )

            if float(
                self.quantity_min
            ) > float(
                self.quantity_max
            ):
                frappe.throw(
                    "Minimum tidak boleh melebihi maksimum"
                )
