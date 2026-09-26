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


        # RN_NORMALIZATION_V1
        if not self.raw_need_text:
            self.raw_need_text = (
                self.description
                or self.title
                or ""
            )

        from rescue_net.intelligence.normalization import classify_text

        suggestion = classify_text(self.raw_need_text)

        if not self.item_kind or self.item_kind == "tidak_diketahui":
            self.item_kind = suggestion["item_kind"]

        if not self.canonical_category:
            self.canonical_category = suggestion["canonical_category"]

        if not self.canonical_group:
            self.canonical_group = suggestion["canonical_group"]

        if not self.canonical_item:
            self.canonical_item = suggestion["canonical_item"]

        if (
            not self.quantity_mode
            or self.quantity_mode == "unknown"
        ):
            self.quantity_mode = suggestion["quantity_mode"]

        if self.quantity_min is None:
            self.quantity_min = suggestion["quantity_min"]

        if self.quantity_max is None:
            self.quantity_max = suggestion["quantity_max"]

        if not self.estimate_text:
            self.estimate_text = suggestion["estimate_text"]

        if not self.normalization_source:
            self.normalization_source = "rule"

        if not self.normalization_confidence:
            self.normalization_confidence = suggestion[
                "normalization_confidence"
            ]

        if not self.normalization_status:
            self.normalization_status = "suggested"

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
