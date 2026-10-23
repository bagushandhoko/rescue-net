"""Owner 2026-10-23: an organisation owner appoints staff (with wilayah/bagian) who
may approve or reject join requests - and nothing else."""

import frappe

from rescue_net import api_community_cluster as cc
from rescue_net.tests.factories import RNTestCase, _insert, as_user, make_actor, make_org


class TestOrgStaff(RNTestCase):
    def setUp(self):
        super().setUp()
        self.org = make_org()
        self.owner = make_actor(org=self.org, org_role="owner")
        self.member = make_actor(org=self.org, org_role="member")
        self.staff = make_actor(org=self.org, org_role="member")
        self.applicant = make_actor()
        with as_user(self.applicant.user):
            cc.request_membership(self.org.name)

    def mid(self, who):
        return frappe.db.get_value("RN Organization Membership",
                                   {"user_account": who.account.name, "organization": self.org.name}, "name")

    def appoint(self):
        with as_user(self.owner.user):
            return cc.set_org_staff(self.mid(self.staff), 1, "BPBD Provinsi Kalbar", "verifikasi relawan")

    def test_owner_appoints_staff_with_area_and_note(self):
        out = self.appoint()
        self.assertEqual((out["membership_role"], out["staff_area"], out["staff_note"]),
                         ("staff", "BPBD Provinsi Kalbar", "verifikasi relawan"))

    def test_plain_member_and_staff_cannot_appoint_staff(self):
        self.appoint()
        for who in (self.member, self.staff):
            with as_user(who.user), self.assertRaises(frappe.PermissionError):
                cc.set_org_staff(self.mid(self.member), 1, "x")

    def test_staff_sees_and_decides_join_requests(self):
        self.appoint()
        with as_user(self.staff.user):
            data = cc.org_membership_admin()
            self.assertTrue(data["is_org_admin"])
            self.assertEqual(data["can_manage_staff"], [])
            pending = [m for m in data["memberships"] if m["status"] == "pending"]
            self.assertEqual(len(pending), 1)
            self.assertEqual(cc.decide_membership(pending[0]["name"], "approve")["status"], "approved")

    def test_staff_cannot_touch_owner_or_other_staff(self):
        self.appoint()
        other = make_actor(org=self.org, org_role="member")
        with as_user(self.owner.user):
            cc.set_org_staff(self.mid(other), 1, "Wilayah B")
        with as_user(self.staff.user):
            for target in (self.owner, other):
                with self.assertRaises(frappe.PermissionError):
                    cc.decide_membership(self.mid(target), "revoke", note="x")

    def test_plain_member_cannot_decide_and_sees_no_admin_view(self):
        with as_user(self.member.user):
            self.assertFalse(cc.org_membership_admin()["is_org_admin"])
            pend = frappe.db.get_value("RN Organization Membership",
                                       {"user_account": self.applicant.account.name}, "name")
            with self.assertRaises(frappe.PermissionError):
                cc.decide_membership(pend, "approve")

    def test_dismissed_staff_loses_the_right_and_the_area(self):
        self.appoint()
        with as_user(self.owner.user):
            out = cc.set_org_staff(self.mid(self.staff), 0)
        self.assertEqual((out["membership_role"], out["staff_area"]), ("member", None))
        with as_user(self.staff.user):
            self.assertFalse(cc.org_membership_admin()["is_org_admin"])

    def test_owner_cannot_be_made_staff(self):
        with as_user(self.owner.user), self.assertRaises(frappe.ValidationError):
            cc.set_org_staff(self.mid(self.owner), 1)
