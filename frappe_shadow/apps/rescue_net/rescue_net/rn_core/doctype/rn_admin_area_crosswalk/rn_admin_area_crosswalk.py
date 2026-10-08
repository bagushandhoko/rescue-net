import frappe
from frappe.model.document import Document


class RNAdminAreaCrosswalk(Document):
    """One external code (OCHA P-code, BPS, an older Kemendagri code) for one RN Admin Area (ADR-0005 A.3).
    An external code points at exactly one area; one area may carry many codes."""

    def validate(self):
        self.external_code = (self.external_code or "").strip()
        if not self.external_code:
            frappe.throw("Kode eksternal wajib diisi.")
        clash = frappe.db.get_value(
            "RN Admin Area Crosswalk",
            {"code_system": self.code_system, "external_code": self.external_code, "name": ["!=", self.name or ""]},
            ["name", "area"], as_dict=True)
        if clash:
            frappe.throw(f"Kode {self.code_system} {self.external_code} sudah dipetakan ke wilayah {clash.area}.")
