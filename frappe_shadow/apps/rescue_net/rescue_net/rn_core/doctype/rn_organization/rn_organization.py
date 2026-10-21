import frappe
from frappe.model.document import Document


class RNOrganization(Document):
    def autoname(self):
        legacy_id = (self.legacy_id or "").strip()
        if legacy_id:
            self.name = legacy_id
            return

        self.name = "rn-org-" + frappe.generate_hash(length=20)

    def before_insert(self):
        if self.legacy_id:
            return

        self.legacy_source = None
        self.migration_status = None
        if not self.status:
            self.status = "pending"
        if not self.trust_level:
            self.trust_level = "unverified"
        if not self.identity_verification_status:
            self.identity_verification_status = "unverified"


    # RN_PRIVACY_GUARD_V2
    def validate(self):
        if not self.privacy_mode:
            self.privacy_mode = "closed"

        if not self.control_centre_share:
            self.control_centre_share = "aggregate"

    def on_update(self):
        """O-1 cascade: `allow_posko_public_choice` is the org's permission for
        its poskos to publish their own detail. When the org REVOKES that
        permission, a posko that had chosen 'public' goes back to 'inherit' so
        the stored value stays honest.

        Note: closing the org's own default (`privacy_mode`) no longer strips a
        posko the org deliberately keeps public — a closed org may still expose
        specific poskos (e.g. a shared TNI ship) as long as it allows posko
        choice. Only turning the choice OFF cascades."""
        if self.allow_posko_public_choice:
            return
        before = self.get_doc_before_save()
        if not before or not before.allow_posko_public_choice:
            return  # choice was already off before this save (or a fresh insert)
        frappe.db.sql(
            "UPDATE `tabRN Posko` SET public_detail='inherit' WHERE organization=%s AND public_detail='public'",
            (self.name,),
        )
