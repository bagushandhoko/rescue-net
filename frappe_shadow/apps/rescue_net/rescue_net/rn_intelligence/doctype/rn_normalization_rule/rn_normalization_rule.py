import frappe
from frappe.model.document import Document
from frappe.utils import cint


class RNNormalizationRule(Document):
    def validate(self):
        self.rule_name = (self.rule_name or "").strip()
        self.canonical_category = (
            self.canonical_category or ""
        ).strip()
        self.canonical_group = (
            self.canonical_group or ""
        ).strip()
        self.canonical_item = (
            self.canonical_item or ""
        ).strip()

        confidence = cint(self.confidence)

        if confidence < 0 or confidence > 100:
            frappe.throw(
                "Rule Confidence harus antara 0 dan 100"
            )

        self.confidence = confidence

        aliases = [
            x.strip()
            for x in (self.aliases or "").splitlines()
            if x.strip()
        ]

        if not aliases:
            frappe.throw(
                "Minimal satu alias harus diisi"
            )

        normalized = [x.casefold() for x in aliases]

        if len(normalized) != len(set(normalized)):
            frappe.throw(
                "Alias duplikat dalam rule yang sama"
            )

        self.aliases = "\n".join(aliases)
