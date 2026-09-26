import frappe
from frappe.model.document import Document


BID_TRANSITIONS = {
    "submitted": {"shortlisted", "rejected", "awarded"},
    "shortlisted": {"submitted", "rejected", "awarded"},
    "rejected": {"submitted", "shortlisted"},
    "awarded": set(),
}


class RNTenderBid(Document):
    def validate(self):
        # L-16: bids are judged only while the tender runs; one winner
        from rescue_net.services.guards import assert_transition, bypass, changed

        assert_transition(self, "status", BID_TRANSITIONS, "Status penawaran",
                          initial={"submitted"})
        if bypass(self) or not changed(self, "status"):
            return
        tender_status = frappe.db.get_value("RN Procurement Tender", self.tender, "status")
        if tender_status not in ("open", "evaluation"):
            frappe.throw(f"Tender berstatus '{tender_status}' — penawaran tidak bisa dinilai lagi.")
        if self.status == "awarded" and frappe.db.exists("RN Tender Bid", {
                "tender": self.tender, "status": "awarded", "name": ["!=", self.name]}):
            frappe.throw("Tender ini sudah punya pemenang.")
