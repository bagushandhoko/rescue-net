import frappe
from frappe.model.document import Document


TENDER_TRANSITIONS = {
    "draft": {"open", "cancelled"},
    "open": {"evaluation", "awarded", "cancelled"},
    "evaluation": {"open", "awarded", "cancelled"},
    "awarded": set(),
    "cancelled": set(),
}


class RNProcurementTender(Document):
    def validate(self):
        # L-16: draft → open → evaluation → awarded, one award, verified org only
        from rescue_net.services.guards import assert_transition, bypass, changed, is_privileged

        assert_transition(self, "status", TENDER_TRANSITIONS, "Status tender")
        if bypass(self):
            return
        opening = self.status == "open" and (self.is_new() or changed(self, "status"))
        if opening and not is_privileged():
            from rescue_net.api_donor_program import _owner_verified
            if not _owner_verified("organization", self.organization):
                frappe.throw("Tender hanya bisa dibuka oleh organisasi yang sudah terverifikasi.")
        if self.status == "awarded":
            if not self.awarded_bid or frappe.db.get_value(
                    "RN Tender Bid", self.awarded_bid, "tender") != self.name:
                frappe.throw("Tender yang ditetapkan wajib punya penawaran pemenang dari tender ini.")
