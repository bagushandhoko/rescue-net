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
        self._fill_event()
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

    def _fill_event(self):
        """An assignment belongs to a disaster (the Relawan boards filter on it;
        E2E 2026-10-25: create_assignment left it empty, so new assignments
        never showed). The volunteer's own disaster when the posko serves it,
        else the posko's main disaster."""
        if self.disaster_event or not self.posko:
            return
        from rescue_net.control_centre.common import posko_served_events
        served = posko_served_events(self.posko)
        vol_ev = frappe.db.get_value("RN Volunteer Profile", self.volunteer, "disaster_event") if self.volunteer else None
        self.disaster_event = vol_ev if vol_ev in served else (served[0] if served else None)
