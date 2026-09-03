import hashlib

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


NETWORK_TYPES = {"vhf", "uhf", "hf", "seluler", "starlink", "vsat", "lainnya"}
STATUS = {"baik", "sibuk", "lemah", "down"}


class RNCommsFrequency(Document):
    def autoname(self):
        if self.legacy_id:
            self.name = self.legacy_id
            return

        seed = (
            f"{self.disaster_event}:{self.band_label}:"
            f"{frappe.generate_hash(length=12)}"
        )

        self.name = (
            "rn-comms-freq-"
            + hashlib.sha256(seed.encode()).hexdigest()[:20]
        )

    def before_insert(self):
        if self.legacy_id:
            return

        self.observed_at = self.observed_at or now_datetime()

    def validate(self):
        if self.network_type and self.network_type not in NETWORK_TYPES:
            frappe.throw("Jenis jaringan tidak valid")

        if self.status and self.status not in STATUS:
            frappe.throw("Status frekuensi tidak valid")

        if self.load_pct is not None and not (0 <= int(self.load_pct) <= 100):
            frappe.throw("Beban jaringan harus antara 0-100%")
