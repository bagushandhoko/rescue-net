import hashlib
import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime

def _actor():
    user = frappe.session.user
    if user in ("Guest", "Administrator"):
        return None

    return frappe.db.get_value(
        "RN User Account",
        {"frappe_user":user, "status":"active"},
        "name",
    )


def _classify(doc, raw):
    from rescue_net.intelligence.normalization_registry import classify_text

    suggestion = classify_text(raw)

    if not doc.canonical_category:
        doc.canonical_category = suggestion["canonical_category"]

    if not doc.canonical_group:
        doc.canonical_group = suggestion["canonical_group"]

    if not doc.canonical_item:
        doc.canonical_item = suggestion["canonical_item"]

    if not doc.normalization_source:
        doc.normalization_source = "rule"

    if not doc.normalization_confidence:
        doc.normalization_confidence = suggestion[
            "normalization_confidence"
        ]

    if not doc.normalization_status:
        doc.normalization_status = "suggested"

    if (
        (not doc.quantity_mode or doc.quantity_mode == "unknown")
        and suggestion["quantity_mode"] != "unknown"
    ):
        doc.quantity_mode = suggestion["quantity_mode"]

    if not doc.estimate_text and suggestion["estimate_text"]:
        doc.estimate_text = suggestion["estimate_text"]


class RNAidOffer(Document):
    def autoname(self):
        if self.legacy_id:
            self.name = self.legacy_id
            return

        seed = f"{self.donor_name or ''}:{self.item_name or ''}:{frappe.generate_hash(length=12)}"
        self.name = "rn-aid-" + hashlib.sha256(
            seed.encode()
        ).hexdigest()[:20]

    def before_insert(self):
        if self.legacy_id:
            return

        self.legacy_source = None
        self.migration_status = None

        if not self.donor_user:
            self.donor_user = _actor()

        if not self.raw_item_text:
            self.raw_item_text = self.item_name or self.title or ""

        _classify(self, self.raw_item_text)

        if self.quantity_mode == "unknown" and self.quantity:
            self.quantity_mode = "exact"

        if not self.observed_at:
            self.observed_at = now_datetime()

        if not self.source_updated_at:
            self.source_updated_at = self.observed_at

        if not self.offer_status:
            self.offer_status = "available"

        if not self.verification_status:
            self.verification_status = "self_reported"
