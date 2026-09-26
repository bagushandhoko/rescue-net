import frappe
from frappe.model.document import Document
from frappe.utils import cint, flt


class RNUnitConversion(Document):
    def validate(self):
        self.conversion_name = (self.conversion_name or "").strip()
        self.from_unit = (self.from_unit or "").strip().lower()
        self.to_base_unit = (self.to_base_unit or "").strip().lower()
        self.canonical_item = (self.canonical_item or "").strip()
        self.canonical_group = (self.canonical_group or "").strip()

        if flt(self.factor) <= 0:
            frappe.throw("Factor harus lebih besar dari 0.")

        scope = self.scope_type or "canonical_item"
        if scope == "canonical_item" and not self.canonical_item:
            frappe.throw("Scope canonical_item butuh field Canonical Item diisi.")
        if scope == "canonical_group" and not self.canonical_group:
            frappe.throw("Scope canonical_group butuh field Canonical Group diisi.")

        self.priority = cint(self.priority) or 100
