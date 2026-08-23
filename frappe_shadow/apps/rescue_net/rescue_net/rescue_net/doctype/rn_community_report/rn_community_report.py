import frappe
from frappe.model.document import Document


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
