import hashlib

import frappe
from frappe.model.document import Document


class RNCommunityNeed(Document):
    def autoname(self):
        legacy_id = (self.legacy_id or "").strip()
        if legacy_id:
            self.name = legacy_id
            return

        seed = (
            f"{self.source_report or ''}:"
            f"{self.requester_user or ''}:"
            f"{frappe.generate_hash(length=12)}"
        )
        digest = hashlib.sha256(seed.encode()).hexdigest()[:20]
        self.name = f"rn-need-{digest}"

    def before_insert(self):
        if self.legacy_id:
            return

        self.legacy_source = None
        self.migration_status = None

        user = frappe.session.user

        if user not in ("Guest", "Administrator"):
            rn_user = frappe.db.get_value(
                "RN User Account",
                {"frappe_user": user, "status": "active"},
                ["name", "organization"],
                as_dict=True,
            )

            if rn_user:
                if not self.requester_user:
                    self.requester_user = rn_user.name

                if not self.community_owner:
                    self.community_owner = rn_user.organization

                if not self.community_owner:
                    memberships = frappe.get_all(
                        "RN Organization Membership",
                        filters={
                            "user_account": rn_user.name,
                            "status": "approved",
                        },
                        fields=["organization"],
                        order_by="approved_at desc, creation asc",
                        limit_page_length=1,
                    )
                    if memberships:
                        self.community_owner = memberships[0].organization

                if not self.community_owner:
                    memberships = frappe.get_all(
                        "RN Organization Membership",
                        filters={
                            "user_account": rn_user.name,
                            "status": "approved",
                        },
                        fields=["organization"],
                        order_by="approved_at desc, creation asc",
                        limit_page_length=1,
                    )
                    if memberships:
                        self.community_owner = memberships[0].organization

        if not self.handling_mode:
            self.handling_mode = "community"

        if not self.takeover_status:
            self.takeover_status = "none"

        if not self.status:
            self.status = "open"

    def validate(self):
        if self.handling_mode == "community":
            self.handling_posko = None

        if self.handling_mode == "posko" and not self.handling_posko:
            frappe.throw(
                "Posko wajib dipilih bila handling mode adalah posko"
            )

        if self.takeover_status == "accepted":
            if self.handling_mode != "posko" or not self.handling_posko:
                frappe.throw(
                    "Take over hanya dapat diterima bila Posko sudah menjadi penangan"
                )
