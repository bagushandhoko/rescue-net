import frappe
from frappe.model.document import Document

from rescue_net.services import admin_area_codes as codes


class RNAdminArea(Document):
    """Kode Kemendagri bertitik = kunci kanonik (ADR-0005). Checked when the code/level/parent/validity changes,
    so a row imported long ago never blocks an unrelated edit."""

    def validate(self):
        if not (self.is_new() or self.has_value_changed("code") or self.has_value_changed("level")
                or self.has_value_changed("parent_code") or self.has_value_changed("valid_to")
                or self.has_value_changed("valid_from") or self.has_value_changed("replaced_by")):
            return
        self.code = codes.normalize_code(self.code)
        if not codes.validate_code(self.code):
            frappe.throw(f"Kode wilayah '{self.code}' tidak valid (contoh: 11, 11.71, 11.71.02, 11.71.02.1001).")
        if self.level != codes.level_of(self.code):
            frappe.throw(f"Tingkat '{self.level}' tidak cocok dengan kode {self.code} (seharusnya {codes.level_of(self.code)}).")
        expected = codes.parent_of(self.code)
        self.parent_code = (self.parent_code or expected).strip() if self.parent_code else expected
        if self.parent_code != expected:
            frappe.throw(f"Induk {self.parent_code} tidak sesuai kode {self.code} (seharusnya {expected or 'tidak ada'}).")
        if expected and not frappe.db.exists("RN Admin Area", expected):
            frappe.throw(f"Induk {expected} belum ada; impor wilayah dari tingkat atas.")
        if self.valid_from and self.valid_to and str(self.valid_to) < str(self.valid_from):
            frappe.throw("'Berlaku Sampai' tidak boleh sebelum 'Berlaku Dari'.")
        if self.replaced_by:
            if not self.valid_to:
                frappe.throw("'Digantikan Oleh' hanya untuk wilayah yang sudah berakhir (isi 'Berlaku Sampai').")
            if self.replaced_by == self.name:
                frappe.throw("Wilayah tidak bisa menggantikan dirinya sendiri.")
