import frappe
from frappe.model.document import Document
from frappe.utils import cint, getdate

STATUSES = {"open", "filled", "closed"}


class RNRecoveryVolunteerNeed(Document):
    def validate(self):
        if not (self.role_needed or "").strip():
            frappe.throw("Peran / keahlian relawan wajib diisi.")
        if cint(self.people_needed) < 1 or cint(self.people_needed) > 10000:
            frappe.throw("Jumlah relawan dibutuhkan harus 1–10000.")
        if self.need_status not in STATUSES:
            frappe.throw("Status kebutuhan relawan tidak valid.")
        if self.date_from and self.date_to and getdate(self.date_to) < getdate(self.date_from):
            frappe.throw("Tanggal selesai tidak boleh sebelum tanggal mulai.")
