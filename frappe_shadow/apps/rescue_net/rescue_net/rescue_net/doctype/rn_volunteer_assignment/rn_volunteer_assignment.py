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
