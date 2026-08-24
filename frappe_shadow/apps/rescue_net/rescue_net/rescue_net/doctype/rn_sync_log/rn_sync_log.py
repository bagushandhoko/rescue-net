import hashlib

from frappe.model.document import Document


class RNSyncLog(Document):
    def autoname(self):
        seed = self.event_id or self.name or "sync"
        self.name = (
            "rn-sync-"
            + hashlib.sha256(
                seed.encode()
            ).hexdigest()[:24]
        )
