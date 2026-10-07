import frappe
from frappe.model.document import Document


class RNProgramLocation(Document):
    def validate(self):
        for f, lo, hi in (("latitude", -90, 90), ("longitude", -180, 180)):
            v = self.get(f)
            if v not in (None, "") and not lo <= float(v) <= hi:
                frappe.throw(f"{f} di luar rentang {lo}..{hi}.")
        if self.location_status == "terlayani":
            self.served_at = self.served_at or frappe.utils.nowdate()
        else:
            self.served_at = None
