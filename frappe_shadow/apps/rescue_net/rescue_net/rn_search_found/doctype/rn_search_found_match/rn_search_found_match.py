import hashlib

import frappe
from frappe.model.document import Document


MATCH_TRANSITIONS = {
    "proposed": {"confirmed", "rejected"},
    "confirmed": {"reunited", "rejected"},
    "reunited": set(),
    "rejected": set(),
}


class RNSearchFoundMatch(Document):
    def autoname(self):
        if self.legacy_id:
            self.name = self.legacy_id
            return

        seed = (
            f"{self.missing_report}:"
            f"{self.found_report}:"
            f"{frappe.generate_hash(length=12)}"
        )

        self.name = (
            "rn-search-match-"
            + hashlib.sha256(
                seed.encode()
            ).hexdigest()[:20]
        )

    def validate(self):
        if self.match_status not in {
            "proposed",
            "confirmed",
            "rejected",
            "reunited",
        }:
            frappe.throw(
                "Status pencocokan tidak valid"
            )

        from rescue_net.services.guards import assert_transition, bypass
        assert_transition(self, "match_status", MATCH_TRANSITIONS,
                          "Status match", initial={"proposed"})
        if bypass(self):
            return
        if self.is_new():
            self._assert_reports_matchable()
        if self.match_status in ("confirmed", "reunited"):
            self._assert_no_other_confirmed()

    def _reports(self):
        return (
            frappe.db.get_value("RN Missing Person Report", self.missing_report,
                                ["disaster_event", "report_status"], as_dict=True),
            frappe.db.get_value("RN Found Person Report", self.found_report,
                                ["disaster_event", "report_status"], as_dict=True),
        )

    def _assert_reports_matchable(self):
        # SF-3: same disaster event, both still open
        missing, found = self._reports()
        if not missing or not found:
            frappe.throw("Laporan orang hilang / ditemukan tidak ditemukan.")
        if missing.disaster_event != found.disaster_event:
            frappe.throw("Laporan hilang dan ditemukan harus dari kejadian bencana yang sama.")
        if missing.report_status != "missing" or found.report_status != "found":
            frappe.throw("Salah satu laporan sudah reunited / ditutup.")

    def _assert_no_other_confirmed(self):
        # SF-4: at most one confirmed / reunited match per report
        clash = frappe.get_all(
            "RN Search Found Match",
            filters={"name": ["!=", self.name or ""], "match_status": ["in", ["confirmed", "reunited"]]},
            or_filters={"missing_report": self.missing_report, "found_report": self.found_report},
            limit_page_length=1,
        )
        if clash:
            frappe.throw("Salah satu laporan sudah mempunyai match terkonfirmasi")

    def on_update(self):
        # A report is reunited exactly when one of its matches is reunited.
        # Rejecting a match never touches a report (SF-4: rejecting a
        # proposal used to reset an already-reunited person to "missing").
        if self.match_status == "reunited":
            for doctype, name in (("RN Missing Person Report", self.missing_report),
                                  ("RN Found Person Report", self.found_report)):
                frappe.db.set_value(doctype, name, "report_status", "reunited", update_modified=False)
