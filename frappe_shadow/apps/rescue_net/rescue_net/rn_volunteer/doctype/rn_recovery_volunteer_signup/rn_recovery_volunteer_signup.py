import frappe
from frappe.model.document import Document
from frappe.utils import getdate

TRANSITIONS = {
    "requested": {"confirmed", "rejected", "cancelled"},
    "confirmed": {"rejected", "cancelled"},
    "rejected": set(),
    "cancelled": set(),
}


class RNRecoveryVolunteerSignup(Document):
    def validate(self):
        from rescue_net.services.guards import assert_transition

        assert_transition(self, "status", TRANSITIONS, "Status pendaftaran relawan", initial={"requested"})
        if self.date_from and self.date_to and getdate(self.date_to) < getdate(self.date_from):
            frappe.throw("Tanggal selesai tidak boleh sebelum tanggal mulai.")
