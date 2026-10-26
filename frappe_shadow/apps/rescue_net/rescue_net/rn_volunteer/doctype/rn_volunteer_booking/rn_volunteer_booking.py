import frappe
from frappe.model.document import Document

KINDS = {"transport", "akomodasi"}


class RNVolunteerBooking(Document):
    def autoname(self):
        self.name = "rn-vol-book-" + frappe.generate_hash(length=16)

    def validate(self):
        if self.booking_kind not in KINDS:
            frappe.throw("Jenis booking relawan tidak valid")
        if self.booking_kind == "transport" and not self.transport_space:
            frappe.throw("Pilih armada")
        if self.booking_kind == "akomodasi" and not self.accommodation:
            frappe.throw("Pilih tempat menginap")
        if self.date_from and self.date_to and str(self.date_to) < str(self.date_from):
            frappe.throw("Tanggal selesai harus setelah tanggal mulai")
