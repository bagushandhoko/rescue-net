import hashlib

from frappe.model.document import Document


class RNResourceRequest(Document):
    def autoname(self):
        seed = (
            self.sync_event_id
            or self.source_object_id
            or "resource-request"
        )
        self.name = (
            "rn-resource-request-"
            + hashlib.sha256(
                seed.encode()
            ).hexdigest()[:24]
        )
