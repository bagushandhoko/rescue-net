"""Regression tests for two bugs the real-login e2e (scripts/komando-tests/flows_e2e.py) found:
1. the operator-queue buttons (set_community_report_status / convert_community_report) only required a login;
2. revoke_endorsement could be repeated and overwrote the first revocation's audit fields."""

import frappe

from rescue_net import api_frontend_bridge as bridge
from rescue_net import api_verifier as verifier_api
from rescue_net.tests.factories import RNTestCase, _insert, api_call, as_guest, as_user, make_actor, make_event, make_org, make_posko


class TestReportQueueGuards(RNTestCase):
    def setUp(self):
        super().setUp()
        self.event = make_event()
        self.posko = make_posko(event=self.event, org=make_org())
        self.operator = make_actor(posko=self.posko)
        self.other_op = make_actor(posko=make_posko(event=self.event, org=make_org()))
        self.plain = make_actor(role="citizen")
        self.control = make_actor(role="command_center")
        self.report = _insert("RN Community Report", title="Laporan uji", description="x" * 30, disaster_event=self.event.name,
                              report_type="shelter_need", priority="medium", affected_people_count=5, posko=self.posko.name,
                              status="submitted").name
        self.unrouted = _insert("RN Community Report", title="Laporan tanpa posko", description="x" * 30,
                                disaster_event=self.event.name, report_type="shelter_need", priority="medium",
                                affected_people_count=5, status="submitted").name

    def test_wrong_roles_and_guest_are_refused(self):
        for user in (self.plain.user, self.other_op.user):
            with as_user(user):
                with self.assertRaises(frappe.PermissionError):
                    bridge.set_community_report_status(self.report, "verified")
                with self.assertRaises(frappe.PermissionError):
                    bridge.convert_community_report(self.report)
        with as_guest():
            with self.assertRaises(frappe.PermissionError):
                api_call("rescue_net.api_frontend_bridge.set_community_report_status", report=self.report, status="verified")
        self.assertEqual(frappe.db.get_value("RN Community Report", self.report, "status"), "submitted")
        self.assertFalse(frappe.db.exists("RN Community Need", {"source_report": self.report}))

    def test_routed_operator_system_manager_and_control_centre_may(self):
        with as_user(self.operator.user):
            self.assertEqual(bridge.set_community_report_status(self.report, "verified")["status"], "verified")
            self.assertTrue(bridge.convert_community_report(self.report)["created"])
        with as_user(self.control.user):
            bridge.set_community_report_status(self.unrouted, "verified")
        other = _insert("RN Community Report", title="Laporan SM", description="x" * 30, disaster_event=self.event.name,
                        report_type="shelter_need", priority="medium", affected_people_count=5, status="submitted").name
        bridge.set_community_report_status(other, "verified")  # Administrator = System Manager

    def test_unrouted_report_is_not_open_to_a_posko_operator(self):
        with as_user(self.operator.user), self.assertRaises(frappe.PermissionError):
            bridge.set_community_report_status(self.unrouted, "verified")


class TestRevokeTwice(RNTestCase):
    def test_second_revoke_is_refused_and_keeps_the_first_audit_trail(self):
        v = make_actor(role="citizen")
        _insert("RN Verifier Profile", title="V", user=v.account, verifier_type="community_leader",
                verifier_status="active", trust_level=1)
        target = make_actor(role="citizen")
        with as_user(v.user):
            end = verifier_api.endorse_reporter(target.account, statement="kenal langsung sejak lama")["endorsement"]
            verifier_api.revoke_endorsement(end, reason="alasan pertama")
            with self.assertRaises(frappe.ValidationError):
                verifier_api.revoke_endorsement(end, reason="alasan kedua")
        self.assertEqual(frappe.db.get_value("RN Verification Endorsement", end, "revoke_reason"), "alasan pertama")
