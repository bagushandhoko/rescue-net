import hashlib

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


STATUS = {
    "requested",
    "assigned",
    "en_route_pickup",
    "patient_on_board",
    "arrived_hospital",
    "handover_complete",
    "cancelled",
}


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


class RNMedicalEvacuation(Document):
    def autoname(self):
        seed = (
            f"{self.medical_case}:"
            f"{self.destination_facility}:"
            f"{frappe.generate_hash(length=12)}"
        )

        self.name = (
            "rn-medical-evac-"
            + hashlib.sha256(
                seed.encode()
            ).hexdigest()[:20]
        )

    def before_insert(self):
        self.requested_at = (
            self.requested_at
            or now_datetime()
        )

        self.created_by_user = (
            self.created_by_user or _actor()
        )

    def validate(self):
        if self.evacuation_status not in STATUS:
            frappe.throw(
                "Status evakuasi tidak valid"
            )
