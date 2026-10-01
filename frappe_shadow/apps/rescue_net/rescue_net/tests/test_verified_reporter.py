"""Pelapor Terverifikasi (owner 2026-10-01): a verified outsider (BNPB officer,
police chief, dedicated citizen) may ONLY report needs, at any posko; the need
shows on that posko labelled and unconfirmed until the posko decides."""

import frappe

from rescue_net import api_auth, api_logistics, api_verification, api_verifier
from rescue_net.control_centre.posko import logistik_board
from rescue_net.services import reporter
from rescue_net.tests.factories import (
    RNTestCase, _insert, as_user, make_actor, make_user, make_world, uid,
)


def make_reporter(**fields):
    return make_actor(role=reporter.ROLE, reporter_agency="BPBD Aceh Barat", reporter_position="Kepala Seksi Kedaruratan",
                      **fields)


class TestReporterSignupAndApproval(RNTestCase):
    def pending(self):
        user = make_user()
        return _insert("RN User Account", title="Kapolsek Samatiga", frappe_user=user, email=user,
                       role="", requested_role="pelapor", role_request_status="pending",
                       status="pending_verification", reporter_agency="Polsek Samatiga",
                       reporter_position="Kapolsek", reporter_area="Samatiga")

    def test_signup_requires_agency_and_position(self):
        with as_user("Guest"), self.assertRaises(frappe.ValidationError):
            api_auth.register(full_name="Budi", email=f"{uid('p')}@test.rescue-net.local",
                              password="Rn-Test-Pass-2026!x", role="pelapor")

    def test_admin_approval_grants_reporter_role(self):
        acc = self.pending()
        api_verification.approval_action("user", acc.name, "approve")
        acc.reload()
        self.assertEqual((acc.role, acc.status, acc.role_request_status), (reporter.ROLE, "active", "approved"))
        self.assertTrue(acc.reporter_verified_at)

    def test_senior_verifier_can_approve_junior_cannot(self):
        acc = self.pending()
        senior, junior = make_actor(role="viewer"), make_actor(role="viewer")
        for who, tl in ((senior, 2), (junior, 1)):
            _insert("RN Verifier Profile", title=uid("Verifikator"), user=who.account,
                    verifier_status="active", trust_level=tl, wilayah="Samatiga")
        with as_user(junior.user), self.assertRaises(frappe.PermissionError):
            api_verifier.decide_reporter(acc.name, "approve")
        with as_user(senior.user):
            rows = api_verifier.reporter_requests()["requests"]
            self.assertIn(acc.name, [r.name for r in rows])
            api_verifier.decide_reporter(acc.name, "approve")
        self.assertEqual(frappe.db.get_value("RN User Account", acc.name, "role"), reporter.ROLE)

    def test_pending_reporter_cannot_report(self):
        w = make_world()
        acc = self.pending()
        with as_user(acc.frappe_user), self.assertRaises(Exception):
            api_logistics.create_need(w.posko_a.name, "Air bersih", quantity=500, unit="liter")


class TestReporterRights(RNTestCase):
    def setUp(self):
        super().setUp()
        self.w = make_world()
        self.rep = make_reporter()
        self.op = make_actor(posko=self.w.posko_a)

    def report(self, posko=None):
        with as_user(self.rep.user):
            return api_logistics.create_need(posko or self.w.posko_a.name, "Air bersih", quantity=500,
                                             unit="liter", urgency="urgent", jiwa_terdampak=120)["need"]

    def test_reports_at_any_posko_labelled_and_pending(self):
        for posko in (self.w.posko_a, self.w.posko_b):
            need = frappe.get_doc("RN Logistic Need", self.report(posko.name))
            self.assertEqual(need.posko, posko.name)
            self.assertEqual((need.report_channel, need.reporter_confirmation), (reporter.CHANNEL, "pending"))
            self.assertIn("BPBD Aceh Barat", need.reporter_label)
            self.assertEqual(need.created_by_user, self.rep.account)

    def test_cannot_touch_stock_or_confirm(self):
        need = self.report()
        with as_user(self.rep.user):
            with self.assertRaises(frappe.PermissionError):
                api_logistics.create_stock_observation(self.w.posko_a.name, "Solar", quantity=10, unit="liter")
            with self.assertRaises(frappe.PermissionError):
                api_logistics.confirm_reported_need(need, "confirm")

    def test_posko_confirms_or_rejects(self):
        keep, drop = self.report(), self.report()
        with as_user(self.op.user):
            api_logistics.confirm_reported_need(keep, "confirm")
            api_logistics.confirm_reported_need(drop, "reject", note="sudah terpenuhi")
        self.assertEqual(frappe.db.get_value("RN Logistic Need", keep, "reporter_confirmation"), "confirmed")
        self.assertEqual(frappe.db.get_value("RN Logistic Need", drop, ["reporter_confirmation", "need_status"]),
                         ("rejected", "cancelled"))
        # other posko's operator may not decide
        other = make_actor(posko=self.w.posko_b)
        late = self.report()
        with as_user(other.user), self.assertRaises(frappe.PermissionError):
            api_logistics.confirm_reported_need(late, "reject")

    def test_board_label_and_can_report(self):
        self.report()
        with as_user(self.rep.user):
            board = logistik_board(self.w.posko_a.name)
        self.assertTrue(board["can_report"])
        self.assertFalse(board["can_manage"])
        row = next(r for r in board["urgent_needs"] if r["report_channel"])
        self.assertEqual(row["reporter_confirmation"], "pending")
        with as_user("Guest"):
            guest = logistik_board(self.w.posko_a.name)
        self.assertFalse(guest["can_report"])
        grow = next(r for r in guest["urgent_needs"] if r["report_channel"])
        self.assertNotIn(frappe.db.get_value("RN User Account", self.rep.account, "title"), grow["reporter_label"])
        self.assertIn("BPBD Aceh Barat", grow["reporter_label"])
