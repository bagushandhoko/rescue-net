from frappe.model.document import Document


DONATION_TRANSITIONS = {
    "pending": {"received", "rejected", "cancelled"},
    "received": set(),
    "rejected": set(),
    "cancelled": set(),
}


class RNCashDonation(Document):
    def validate(self):
        # L-17: a donation is decided once — confirming twice would count the money twice
        from rescue_net.services.guards import assert_positive, assert_transition, bypass

        assert_transition(self, "status", DONATION_TRANSITIONS, "Status donasi", initial={"pending"})
        if not bypass(self):
            assert_positive(self, "amount")
