import frappe
from frappe.model.document import Document

TRIPS = {"mob", "demob"}
STATUSES = {"requested", "confirmed", "rejected", "cancelled", "done"}


class RNEquipmentTransportBooking(Document):
    def autoname(self):
        self.name = "rn-eq-book-" + frappe.generate_hash(length=16)

    def validate(self):
        if self.trip not in TRIPS:
            frappe.throw("Arah harus mob (ke lokasi) atau demob (pulang)")
        if self.status not in STATUSES:
            frappe.throw("Status booking tidak valid")
        if self.weight_ton is not None and float(self.weight_ton or 0) < 0:
            frappe.throw("Berat tidak boleh negatif")
