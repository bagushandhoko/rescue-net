"""Owner 2026-11-08: SOP bergabung organisasi — (1) mendaftar sendiri lalu disetujui, atau (2) langsung ditambahkan
pengelola. Jalur 2: add_member_direct."""

import frappe

from rescue_net import api_community_cluster as cc
from rescue_net.tests.factories import RNTestCase, as_user, make_actor, make_org, make_user


class TestAddMemberDirect(RNTestCase):
    def setUp(self):
        super().setUp()
        self.org = make_org(verification_status="verified")
        self.owner = make_actor(org=self.org, org_role="owner")
        self.staff = make_actor(org=self.org, org_role="staff")
        self.stranger = make_actor()

    def _m(self, account):
        return frappe.db.get_value("RN Organization Membership", {"user_account": account, "organization": self.org.name},
                                   ["status", "member_verified", "decision_note"], as_dict=True)

    def test_owner_adds_registered_user_directly(self):
        person = make_actor()
        with as_user(self.owner.user):
            r = cc.add_member_direct(self.org.name, person.user, member_verified=1)
        self.assertEqual(r["status"], "approved")
        self.assertFalse(r["created_account"])
        m = self._m(person.account)
        self.assertEqual((m.status, m.member_verified), ("approved", 1))
        self.assertIn("langsung", m.decision_note)

    def test_owner_creates_new_account_with_temporary_password(self):
        email = "anggota-baru-%s@example.org" % frappe.generate_hash(length=6)
        with as_user(self.owner.user):
            r = cc.add_member_direct(self.org.name, email, full_name="Anggota Baru", phone="081200000001")
        self.assertTrue(r["created_account"])
        self.assertTrue(r["temporary_password"])
        self.assertTrue(frappe.db.exists("User", email))
        self.assertEqual(self._m(r["user_account"]).status, "approved")

    def test_staff_limits_and_strangers(self):
        person = make_actor()
        with as_user(self.staff.user):
            r = cc.add_member_direct(self.org.name, person.user, member_verified=1)
            self.assertEqual(self._m(person.account).member_verified, 0)       # only HQ attests identity
            with self.assertRaises(frappe.PermissionError):
                cc.add_member_direct(self.org.name, "baru-staf@example.org", full_name="X")
        with as_user(self.stranger.user):
            with self.assertRaises(frappe.PermissionError):
                cc.add_member_direct(self.org.name, make_user(), full_name="Y")

    def test_pending_request_is_approved_by_direct_add(self):
        person = make_actor()
        with as_user(person.user):
            cc.request_membership(self.org.name)
        self.assertEqual(self._m(person.account).status, "pending")
        with as_user(self.owner.user):
            cc.add_member_direct(self.org.name, person.user)
        self.assertEqual(self._m(person.account).status, "approved")
