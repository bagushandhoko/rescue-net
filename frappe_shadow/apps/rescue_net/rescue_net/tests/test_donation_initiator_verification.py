"""Pengaturan Sistem RN > Verifikasi pengelola donasi (owner 24 Nov 2026)."""

import frappe

from rescue_net import api_donor_program as api
from rescue_net.tests.factories import RNTestCase, as_user, make_actor, make_event, make_org, make_posko


class TestInitiatorVerification(RNTestCase):
    def setUp(self):
        super().setUp()
        ev = make_event(event_status="active")
        self.org = make_org(verification_status="self_reported")
        make_posko(ev, self.org)
        self.owner = make_actor(org=self.org, org_role="owner")
        with as_user(self.owner.user):
            self.program = api.create_special_program(ev.name, "Air bersih", owner_type="organization", owner_id=self.org.name)["program"]
            api.set_program_bank(self.program, bank_name="BSI", account_number="7000123456", account_holder="Kelompok")

    def _row(self):
        return next((r for r in api.initiator_queue()["rows"] if r["program"] == self.program), None)

    def test_super_admin_sees_and_verifies_unverified_org(self):
        frappe.set_user("Administrator")
        row = self._row()
        self.assertTrue(row and row["has_bank"] and not row["verified"])
        self.assertEqual(row["action"], {"type": "approve", "kind": "organisasi", "name": self.org.name})
        r = api.verify_initiator(self.program)
        self.assertTrue(r["verified"])
        self.assertIsNone(self._row())                                   # hilang dari daftar tunggu
        self.assertTrue(frappe.db.exists("RN Approval Log", {"target_name": self.org.name, "action": "approve"}))

    def test_member_creator_is_vouched(self):
        frappe.db.set_value("RN Organization", self.org.name, "verification_status", "verified")
        member = make_actor(org=self.org, org_role="member")
        ev = make_event(event_status="active")
        with as_user(member.user):
            prog = api.create_special_program(ev.name, "Program anggota", owner_type="organization", owner_id=self.org.name)["program"]
        frappe.set_user("Administrator")
        row = next(r for r in api.initiator_queue()["rows"] if r["program"] == prog)
        self.assertEqual(row["action"]["type"], "vouch")
        self.assertTrue(api.verify_initiator(prog)["verified"])

    def test_not_for_regular_users(self):
        with as_user(self.owner.user):
            with self.assertRaises(frappe.PermissionError):
                api.initiator_queue()
            with self.assertRaises(frappe.PermissionError):
                api.verify_initiator(self.program)
