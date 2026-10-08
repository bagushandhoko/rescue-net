import hashlib

from frappe.model.document import Document


def daily_name(usage_date, owner_type, owner_id):
    raw = f"{usage_date}|{owner_type}|{(owner_id or '').strip().lower()}"
    return "rn-aiday-" + hashlib.sha256(raw.encode()).hexdigest()[:24]


class RNAIUsageDaily(Document):
    """Per-day, per-owner totals (no conversation content). Kept after the
    7-day detail retention of RN AI Usage Log; budgets are checked against it."""

    def autoname(self):
        self.name = daily_name(self.usage_date, self.owner_type, self.owner_id)
