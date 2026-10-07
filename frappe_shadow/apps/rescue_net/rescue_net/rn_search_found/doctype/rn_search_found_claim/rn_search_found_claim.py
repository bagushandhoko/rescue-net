import frappe
from frappe.model.document import Document

CLAIM_TRANSITIONS = {
    "menunggu_verifikasi": {"terverifikasi", "ditolak"},
    "terverifikasi": {"siap_diserahkan", "ditolak"},
    "siap_diserahkan": {"selesai", "ditolak"},
    "selesai": set(),
    "ditolak": set(),
}


class RNSearchFoundClaim(Document):
    def validate(self):
        from rescue_net.services.guards import assert_transition
        assert_transition(self, "claim_status", CLAIM_TRANSITIONS, "Status klaim",
                          initial={"menunggu_verifikasi"})
