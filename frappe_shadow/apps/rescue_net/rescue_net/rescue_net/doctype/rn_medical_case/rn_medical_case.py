import hashlib

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


TRIAGE = {"green", "yellow", "red", "black"}

SEVERITY = {
    "mild",
    "moderate",
    "severe",
    "critical",
}

CASE_STATUS = {
    "active",
    "stabilized",
    "referred",
    "evacuating",
    "admitted",
    "discharged",
    "deceased",
    "closed",
}


CASE_TRANSITIONS = {
    "active": {"stabilized", "referred", "evacuating", "discharged", "deceased", "closed"},
    "stabilized": {"referred", "evacuating", "admitted", "discharged", "closed"},
    "referred": {"evacuating", "admitted", "closed"},
    "evacuating": {"admitted", "discharged", "deceased", "closed"},
    "admitted": {"discharged", "deceased", "closed"},
    "discharged": {"closed"},
    "deceased": {"closed"},
    "closed": set(),
}

TERMINAL = {"discharged", "deceased", "closed"}

# a cancelled evacuation hands the patient back to the posko
EVAC_REVERT = {"referred": {"active"}, "evacuating": {"active"}}


def cascade_case_status(case_name, new_status, revert=False):
    """Move a case because its evacuation moved. Goes through validate(); a
    step the case graph does not allow (e.g. the case was closed meanwhile)
    is skipped, never forced (M-2)."""
    case = frappe.get_doc("RN Medical Case", case_name)
    old = case.case_status
    graph = EVAC_REVERT if revert else CASE_TRANSITIONS
    if old == new_status or new_status not in graph.get(old, ()):
        return False
    case.case_status = new_status
    case.source_updated_at = now_datetime()
    case.flags.rn_evac_revert = revert
    case.save(ignore_permissions=True)
    return True


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


class RNMedicalCase(Document):
    def autoname(self):
        if self.legacy_id:
            self.name = self.legacy_id
            return

        seed = (
            f"{self.patient_code}:"
            f"{self.posko}:"
            f"{frappe.generate_hash(length=12)}"
        )

        self.name = (
            "rn-medical-case-"
            + hashlib.sha256(
                seed.encode()
            ).hexdigest()[:20]
        )

    def before_insert(self):
        if self.legacy_id:
            return

        self.created_by_user = (
            self.created_by_user or _actor()
        )

        self.observed_at = (
            self.observed_at or now_datetime()
        )

        self.source_updated_at = (
            self.source_updated_at
            or self.observed_at
        )

    def validate(self):
        if self.triage_status not in TRIAGE:
            frappe.throw(
                "Status triase tidak valid"
            )

        if self.severity not in SEVERITY:
            frappe.throw(
                "Severity tidak valid"
            )

        if self.case_status not in CASE_STATUS:
            frappe.throw(
                "Status kasus tidak valid"
            )

        from rescue_net.services.guards import assert_transition
        graph = EVAC_REVERT if self.flags.get("rn_evac_revert") else CASE_TRANSITIONS
        assert_transition(self, "case_status", graph, "Status kasus")
