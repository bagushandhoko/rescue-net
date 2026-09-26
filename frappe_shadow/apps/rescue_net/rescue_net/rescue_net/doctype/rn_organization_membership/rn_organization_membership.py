import hashlib
import frappe
from frappe.model.document import Document


# O-2: a decision follows from→to; a rejected / revoked member asks again
# (back to pending) before anyone can approve them
MEMBERSHIP_TRANSITIONS = {
    "pending": {"approved", "rejected"},
    "approved": {"revoked"},
    "rejected": {"pending"},
    "revoked": {"pending"},
}


class RNOrganizationMembership(Document):
    def autoname(self):
        legacy_id = (self.legacy_id or "").strip()
        if legacy_id:
            self.name = legacy_id
            return

        seed = ":".join([
            str(getattr(self, "user_account", "") or ""),
            str(getattr(self, "organization", "") or ""),
            str(getattr(self, "posko", "") or ""),
            str(getattr(self, "report", "") or ""),
            frappe.generate_hash(length=12),
        ])
        self.name = "rn-organization-membership-" + hashlib.sha256(
            seed.encode()
        ).hexdigest()[:20]

    def validate(self):
        from rescue_net.services.guards import assert_transition
        assert_transition(self, "status", MEMBERSHIP_TRANSITIONS, "Status keanggotaan")
