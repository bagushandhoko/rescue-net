import hashlib

from frappe.model.document import Document


class RNAIUserSetting(Document):
    def autoname(self):
        raw = (
            f"{(self.user_id or '').strip().lower()}|"
            f"{(self.provider or 'openai').strip().lower()}"
        )
        digest = hashlib.sha256(raw.encode()).hexdigest()[:24]
        self.name = "rn-ai-" + digest
