"""Community report decisions follow from→to and never by the reporter (phase 2: C-1)."""

import frappe

from rescue_net import api_reports as reports
from rescue_net import api_verification as api
from rescue_net.tests.factories import RNTestCase, as_user, make_actor, make_world


class TestCommunityReportDecisions(RNTestCase):
    def setUp(self):
        super().setUp()
        self.w = make_world()
        # an operator who reports what they see on the ground
        self.reporter = make_actor(posko=self.w.posko_a)
        self.verifier = make_actor(posko=self.w.posko_b)
        with as_user(self.reporter.user):
            self.report = reports.submit_community_report(
                title="Jembatan putus", description="Akses desa terputus (data uji)",
            )["name"]

    def act(self, actor, action, notes="uji"):
        with as_user(actor.user):
            return api.act(self.report, action, notes=notes)

    def status(self):
        return frappe.db.get_value("RN Community Report", self.report, "status")

    def test_reporter_cannot_decide_own_report(self):
        for action in ("verify", "reject", "triage"):
            with self.assertRaises(frappe.PermissionError):
                self.act(self.reporter, action)
        self.assertEqual(self.status(), "submitted")

    def test_verified_and_rejected_are_final(self):
        self.act(self.verifier, "triage")
        self.act(self.verifier, "verify")
        for action in ("reject", "triage", "escalate", "verify"):
            with self.assertRaises(frappe.ValidationError):
                self.act(self.verifier, action)
        self.assertEqual(self.status(), "verified")

    def test_escalated_report_can_still_be_decided(self):
        self.act(self.verifier, "escalate")
        self.act(self.verifier, "reject")
        self.assertEqual(self.status(), "rejected")
        with self.assertRaises(frappe.ValidationError):
            self.act(self.verifier, "verify")

    def test_direct_save_by_reporter_is_refused(self):
        doc = frappe.get_doc("RN Community Report", self.report)
        doc.status = "verified"
        with as_user(self.reporter.user), self.assertRaises(frappe.PermissionError):
            doc.save(ignore_permissions=True)
