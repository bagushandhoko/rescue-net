"""Membership decisions follow from→to, org links need the other side's consent (phase 2: O-2, O-4)."""

import frappe

from rescue_net import api_community_cluster as api
from rescue_net.tests.factories import RNTestCase, as_user, make_actor, make_org


class TestMembershipDecisions(RNTestCase):
    def setUp(self):
        super().setUp()
        self.org = make_org()
        self.owner = make_actor(org=self.org, org_role="owner")
        self.user = make_actor()
        with as_user(self.user.user):
            self.m = api.request_membership(self.org.name)["name"]

    def decide(self, action, note="uji"):
        with as_user(self.owner.user):
            return api.decide_membership(self.m, action, note=note)

    def status(self):
        return frappe.db.get_value("RN Organization Membership", self.m, "status")

    def test_rejected_member_must_ask_again_before_approval(self):
        self.decide("reject")
        with self.assertRaises(frappe.ValidationError):
            self.decide("approve")
        with as_user(self.user.user):
            self.assertEqual(api.request_membership(self.org.name)["status"], "pending")
        self.decide("approve")
        self.assertEqual(self.status(), "approved")

    def test_revoked_member_is_not_reapproved_directly(self):
        self.decide("approve")
        self.decide("revoke")
        with self.assertRaises(frappe.ValidationError):
            self.decide("approve")
        self.assertEqual(self.status(), "revoked")

    def test_pending_request_cannot_be_revoked(self):
        with self.assertRaises(frappe.ValidationError):
            self.decide("revoke")


class TestOrgLinkConsent(RNTestCase):
    def setUp(self):
        super().setUp()
        self.parent, self.child = make_org(), make_org()
        self.parent_owner = make_actor(org=self.parent, org_role="owner")
        self.child_owner = make_actor(org=self.child, org_role="owner")
        self.child_co_owner = make_actor(org=self.child, org_role="owner")

    def parent_of(self, org):
        return frappe.db.get_value("RN Organization", org.name, "parent_organization")

    def test_requester_side_cannot_approve_its_own_attach(self):
        with as_user(self.child_owner.user):
            req = api.set_org_parent(self.child.name, self.parent.name)["request"]
        with as_user(self.child_co_owner.user), self.assertRaises(frappe.PermissionError):
            api.decide_org_link(req, "approve")
        self.assertIsNone(self.parent_of(self.child))
        with as_user(self.parent_owner.user):
            api.decide_org_link(req, "approve")
        self.assertEqual(self.parent_of(self.child), self.parent.name)

    def test_parent_pulling_a_child_needs_the_child(self):
        with as_user(self.parent_owner.user):
            req = api.set_org_parent(self.child.name, self.parent.name)["request"]
        parent_co_owner = make_actor(org=self.parent, org_role="owner")
        with as_user(parent_co_owner.user), self.assertRaises(frappe.PermissionError):
            api.decide_org_link(req, "approve")
        with as_user(self.child_co_owner.user):
            api.decide_org_link(req, "approve")
        self.assertEqual(self.parent_of(self.child), self.parent.name)
