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
        self._check_schedule()
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

    def _check_schedule(self):
        """Owner 2026-11-03: work schedule shown with the tender must be in order."""
        from frappe.utils import getdate

        for f in ("work_duration_days", "maintenance_days", "bid_validity_days"):
            if (self.get(f) or 0) < 0:
                frappe.throw("Jumlah hari tidak boleh negatif.")
        start, end = self.work_start_date, self.target_completion_date
        if start and end and getdate(end) < getdate(start):
            frappe.throw("Target selesai kerja tidak boleh sebelum rencana mulai kerja.")
        if self.bidding_closes_at and (self.is_new() or self.has_value_changed("target_completion_date")
                                       or self.has_value_changed("bidding_closes_at")):
            if end and getdate(end) < getdate(self.bidding_closes_at):
                frappe.throw("Target selesai kerja tidak boleh sebelum batas akhir penawaran.")
