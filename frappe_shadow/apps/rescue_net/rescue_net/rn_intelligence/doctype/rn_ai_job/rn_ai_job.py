from frappe.model.document import Document

from rescue_net.services.guards import assert_transition

JOB_TRANSITIONS = {"pending": {"done", "failed", "cancelled"}, "failed": {"pending", "cancelled"},
                   "done": set(), "cancelled": set()}


class RNAIJob(Document):
    """Work that could not use AI when it arrived (no key, budget spent, provider down).
    ai/queue.py processes it later, a few per hour."""

    def validate(self):
        assert_transition(self, "status", JOB_TRANSITIONS, "Status antrian AI", initial=("pending", None))
