import frappe
from frappe.model.document import Document


class RNPosko(Document):
    def autoname(self):
        legacy_id = (self.legacy_id or "").strip()
        if legacy_id:
            self.name = legacy_id
            return

        self.name = "rn-posko-" + frappe.generate_hash(length=20)

    def before_insert(self):
        if self.legacy_id:
            return

        self.legacy_source = None
        self.migration_status = None
        if not self.verification_status:
            self.verification_status = "self_reported"
        if not self.operational_status:
            self.operational_status = "active"
        if not self.identity_verification_status:
            self.identity_verification_status = "self_reported"


    # RN_PRIVACY_GUARD_V1
    def validate(self):
        if not self.public_detail:
            self.public_detail = "inherit"

        if not self.organization:
            return

        org = frappe.db.get_value(
            "RN Organization",
            self.organization,
            [
                "privacy_mode",
                "allow_posko_public_choice",
            ],
            as_dict=True,
        )

        if (
            self.public_detail == "public"
            and org
            and (
                org.privacy_mode != "open"
                or not org.allow_posko_public_choice
            )
        ):
            frappe.throw(
                "Posko tidak dapat dibuka ke publik karena "
                "kebijakan Kelompok tidak mengizinkannya"
            )
