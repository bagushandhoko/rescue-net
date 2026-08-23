import hashlib

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


TRIAGE = {"green", "yellow", "red", "black"}

SEVERITY = {
    "mild",
    "moderate",
    "severe",
    "critical",
}

CASE_STATUS = {
    "active",
    "stabilized",
    "referred",
    "evacuating",
    "admitted",
    "discharged",
    "deceased",
    "closed",
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


class RNMedicalCase(Document):
    def autoname(self):
        if self.legacy_id:
            self.name = self.legacy_id
            return

        seed = (
            f"{self.patient_code}:"
            f"{self.posko}:"
            f"{frappe.generate_hash(length=12)}"
        )

        self.name = (
            "rn-medical-case-"
            + hashlib.sha256(
                seed.encode()
            ).hexdigest()[:20]
        )

    def before_insert(self):
        if self.legacy_id:
            return

        self.created_by_user = (
            self.created_by_user or _actor()
        )

        self.observed_at = (
            self.observed_at or now_datetime()
        )

        self.source_updated_at = (
            self.source_updated_at
            or self.observed_at
        )

    def validate(self):
        if self.triage_status not in TRIAGE:
            frappe.throw(
                "Status triase tidak valid"
            )

        if self.severity not in SEVERITY:
            frappe.throw(
                "Severity tidak valid"
            )

        if self.case_status not in CASE_STATUS:
            frappe.throw(
                "Status kasus tidak valid"
            )
