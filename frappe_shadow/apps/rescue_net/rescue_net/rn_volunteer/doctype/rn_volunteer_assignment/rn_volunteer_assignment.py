import hashlib

import frappe
from frappe.model.document import Document


# a volunteer assignment moves forward only; completed / cancelled are final
TRANSITIONS = {
    "planned": {"accepted", "cancelled"},
    "accepted": {"checked_in", "cancelled"},
    "checked_in": {"in_progress", "completed", "cancelled"},
    "in_progress": {"completed", "cancelled"},
    "completed": set(),
    "cancelled": set(),
}

STATUS = set(TRANSITIONS)

ACTIVE = {"planned", "accepted", "checked_in", "in_progress"}


class RNVolunteerAssignment(Document):
    def autoname(self):
        if self.legacy_id:
            self.name = self.legacy_id
            return

        seed = (
            f"{self.volunteer}:"
            f"{self.posko}:"
            f"{self.task_title}:"
            f"{frappe.generate_hash(length=12)}"
        )

        self.name = (
            "rn-volunteer-assignment-"
            + hashlib.sha256(
                seed.encode()
            ).hexdigest()[:20]
        )

    def validate(self):
        if self.assignment_status not in STATUS:
            frappe.throw(
                "Status penugasan tidak valid"
            )

        from rescue_net.services.guards import assert_transition
        assert_transition(self, "assignment_status", TRANSITIONS, "Status penugasan", initial={"planned"})
        self.assert_single_active()

    def assert_single_active(self):
        """A volunteer holds at most one active assignment. The volunteer's
        profile row is locked first, so two managers assigning the same
        volunteer at once cannot both pass the check."""
        from rescue_net.services.guards import bypass, changed
        if bypass(self) or self.assignment_status not in ACTIVE:
            return
        if not (self.is_new() or changed(self, "volunteer")):
            return
        frappe.db.get_value("RN Volunteer Profile", self.volunteer, "name", for_update=True)
        other = frappe.db.exists(
            "RN Volunteer Assignment",
            {
                "volunteer": self.volunteer,
                "assignment_status": ["in", list(ACTIVE)],
                "name": ["!=", self.name or ""],
            },
        )
        if other:
            frappe.throw("Relawan sudah memiliki penugasan aktif")
