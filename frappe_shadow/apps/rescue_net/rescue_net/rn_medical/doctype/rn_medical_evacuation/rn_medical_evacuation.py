import hashlib

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


STATUS = {
    "requested",
    "assigned",
    "en_route_pickup",
    "patient_on_board",
    "arrived_hospital",
    "handover_complete",
    "cancelled",
}


EVAC_TRANSITIONS = {
    "requested": {"assigned", "cancelled"},
    "assigned": {"en_route_pickup", "patient_on_board", "cancelled"},
    "en_route_pickup": {"patient_on_board", "cancelled"},
    "patient_on_board": {"arrived_hospital", "cancelled"},
    "arrived_hospital": {"handover_complete"},
    "handover_complete": set(),
    "cancelled": set(),
}

EVAC_DONE = {"handover_complete", "cancelled"}


def _actor():
    if frappe.session.user in (
        "Guest",
        "Administrator",
    ):
        return None

    return frappe.db.get_value(
        "RN User Account",
        {
            "frappe_user": frappe.session.user,
            "status": "active",
        },
        "name",
    )


class RNMedicalEvacuation(Document):
    def autoname(self):
        seed = (
            f"{self.medical_case}:"
            f"{self.destination_facility}:"
            f"{frappe.generate_hash(length=12)}"
        )

        self.name = (
            "rn-medical-evac-"
            + hashlib.sha256(
                seed.encode()
            ).hexdigest()[:20]
        )

    def before_insert(self):
        self.requested_at = (
            self.requested_at
            or now_datetime()
        )

        self.created_by_user = (
            self.created_by_user or _actor()
        )

    def validate(self):
        if self.evacuation_status not in STATUS:
            frappe.throw(
                "Status evakuasi tidak valid"
            )

        from rescue_net.services.guards import assert_transition, bypass
        assert_transition(self, "evacuation_status", EVAC_TRANSITIONS,
                          "Status evakuasi", initial={"requested"})
        if self.is_new() and not bypass(self):
            self._assert_case_can_evacuate()

    def _assert_case_can_evacuate(self):
        # M-4: a live case of this posko, with no other evacuation running
        from rescue_net.rn_medical.doctype.rn_medical_case.rn_medical_case import TERMINAL
        case = frappe.db.get_value("RN Medical Case", self.medical_case,
                                   ["posko", "case_status"], as_dict=True)
        if not case:
            frappe.throw("Medical Case tidak ditemukan")
        if self.posko and case.posko != self.posko:
            frappe.throw("Medical Case berasal dari Posko yang berbeda")
        if case.case_status in TERMINAL:
            frappe.throw(f"Kasus sudah berstatus '{case.case_status}', tidak bisa dievakuasi.")
        if frappe.db.exists("RN Medical Evacuation", {
            "medical_case": self.medical_case,
            "evacuation_status": ["not in", list(EVAC_DONE)],
        }):
            frappe.throw("Kasus ini sudah punya evakuasi yang berjalan.")

    def on_update(self):
        # the case follows its evacuation, through the case's own rules (M-2/M-3)
        from rescue_net.rn_medical.doctype.rn_medical_case.rn_medical_case import cascade_case_status
        from rescue_net.services.guards import bypass, changed
        if bypass(self) or not (self.flags.in_insert or changed(self, "evacuation_status")):
            return
        step = {
            "requested": ("referred", False),
            "patient_on_board": ("evacuating", False),
            "handover_complete": ("admitted", False),
            "cancelled": ("active", True),
        }.get(self.evacuation_status)
        if step:
            cascade_case_status(self.medical_case, step[0], revert=step[1])
