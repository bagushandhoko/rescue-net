import frappe
from frappe.model.document import Document

# C-1: a report is decided from→to; verified / rejected are final
REPORT_TRANSITIONS = {
    "submitted": {"triaged", "verified", "rejected", "escalated"},
    "triaged": {"verified", "rejected", "escalated"},
    "escalated": {"triaged", "verified", "rejected"},
    "verified": set(),
    "rejected": set(),
}


class RNCommunityReport(Document):
    def autoname(self):
        legacy_id = (self.legacy_id or "").strip()

        if legacy_id:
            self.name = legacy_id
            return

        self.name = f"rn-report-{frappe.generate_hash(length=20)}"

    def before_insert(self):
        if self.legacy_id:
            return

        # Native Frappe report, not a shadow-imported legacy report.
        self.legacy_source = None
        self.migration_status = None

        user = frappe.session.user

        if user in ("Guest", "Administrator"):
            return

        rn_user = frappe.db.get_value(
            "RN User Account",
            {
                "frappe_user": user,
                "status": "active",
            },
            ["name", "role"],
            as_dict=True,
        )

        if not rn_user:
            frappe.throw(
                "Active Rescue-Net user account was not found"
            )

        self.reporter_user = rn_user.name
        self.reporter_role = rn_user.role

        if not self.reporter_name:
            self.reporter_name = (
                frappe.db.get_value("User", user, "full_name")
                or user
            )

    def validate(self):
        from rescue_net.services.guards import assert_transition, bypass, changed, is_privileged

        assert_transition(self, "status", REPORT_TRANSITIONS, "Status laporan")
        if bypass(self) or not changed(self, "status") or is_privileged():
            return
        actor = frappe.db.get_value("RN User Account", {"frappe_user": frappe.session.user}, "name")
        if actor and actor == self.reporter_user:
            frappe.throw("Pelapor tidak dapat memutuskan laporannya sendiri.", frappe.PermissionError)
