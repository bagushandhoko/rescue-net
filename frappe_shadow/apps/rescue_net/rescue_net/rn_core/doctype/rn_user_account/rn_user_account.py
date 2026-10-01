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
        # Exception (owner 2026-10-01): a senior verifier may grant exactly the
        # Pelapor Terverifikasi role to an account that asked for it
        # (services/reporter.activate sets the flag; api_verifier checks trust).
        reporter_grant = (self.flags.get("rn_reporter_activation") and self.role == "verified_reporter"
                          and self.requested_role == "pelapor")
        if changed(self, "role") and not bypass(self) and not is_privileged() and not reporter_grant:
            frappe.throw("Perubahan role akun hanya bisa dilakukan System Manager.", frappe.PermissionError)
