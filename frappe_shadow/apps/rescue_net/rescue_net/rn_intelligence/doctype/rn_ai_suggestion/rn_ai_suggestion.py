from frappe.model.document import Document

from rescue_net.services.guards import assert_transition

# ADR-0002: a suggestion is decided once by a human; accepted / rejected are final
SUGGESTION_TRANSITIONS = {"draft": {"accepted", "rejected"}, "accepted": set(), "rejected": set()}


class RNAISuggestion(Document):
    def validate(self):
        assert_transition(self, "status", SUGGESTION_TRANSITIONS, "Status saran AI", initial=("draft", None))
