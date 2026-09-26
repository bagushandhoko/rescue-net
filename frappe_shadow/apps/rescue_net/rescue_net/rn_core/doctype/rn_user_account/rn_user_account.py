import hashlib

import frappe
from frappe.model.document import Document


class RNUserAccount(Document):
    def autoname(self):
        legacy_id = (self.legacy_id or "").strip()

        if legacy_id:
            self.name = legacy_id
            return

        frappe_user = (self.frappe_user or "").strip().lower()

        if not frappe_user:
            frappe.throw(
                "Frappe User is required for a native RN User Account"
            )

        digest = hashlib.sha256(
            frappe_user.encode("utf-8")
        ).hexdigest()[:24]

        self.name = f"rn-user-{digest}"

    def validate(self):
        # Owner rule (2026-09-26, VF-1): changing the role of an existing
        # account is a System Manager decision — whatever path saves it.
        from rescue_net.services.guards import bypass, changed, is_privileged
        if changed(self, "role") and not bypass(self) and not is_privileged():
            frappe.throw("Perubahan role akun hanya bisa dilakukan System Manager.", frappe.PermissionError)
