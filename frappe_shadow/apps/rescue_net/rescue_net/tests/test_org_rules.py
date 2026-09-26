"""Membership decisions follow from→to, org links need the other side's consent, posko rights
only after an approved assignment (phase 2: O-2, O-4, O-9, O-10)."""

import frappe

from rescue_net import api_community_cluster as api
from rescue_net import api_control_centre as cc
from rescue_net import api_operator_approval as approval
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


class TestPoskoRightsNeedApprovedAssignment(RNTestCase):
    def create(self, actor, **kw):
        with as_user(actor.user):
            return api.create_posko(title="Posko Uji Hak", posko_type="logistics",
                                    address="Jl. Uji 1", **kw)

    def test_creator_waits_for_approval_before_editing(self):
        creator = make_actor(role="viewer")
        res = self.create(creator, functions='["logistics", "kitchen"]', logistics_role="receiver")
        self.assertEqual(res["assignment_status"], "pending")
        # the creator's form choice is applied at creation
        self.assertEqual(frappe.db.get_value("RN Posko", res["posko"], "rn_fn_kitchen"), 1)
        with as_user(creator.user):
            for fn, kw in ((api.update_posko, {"notes": "diubah"}),
                           (cc.set_posko_functions, {"functions": '["shelter"]'}),
                           (api.delete_posko, {})):
                with self.assertRaises(frappe.PermissionError):
                    fn(res["posko"], **kw)
        frappe.db.set_value("RN User Account", creator.account,
                            {"requested_role": "posko_operator", "role_request_status": "pending"})
        approval.approve_posko_operator(creator.account, res["posko"])
        with as_user(creator.user):
            api.update_posko(res["posko"], notes="diubah")
        self.assertEqual(frappe.db.get_value("RN Posko", res["posko"], "notes"), "diubah")

    def test_effective_operator_gets_a_new_posko_only_after_approval(self):
        operator = make_actor()  # global posko_operator role
        res = self.create(operator)
        self.assertEqual(res["assignment_status"], "pending")
        with as_user(operator.user), self.assertRaises(frappe.PermissionError):
            api.update_posko(res["posko"], notes="diubah")
        waiting = {(r["user_account"], r["posko"]) for r in
                   (dict(r, user_account=r["name"]) for r in approval.pending_requests())}
        self.assertIn((operator.account, res["posko"]), waiting)
        approval.approve_posko_operator(operator.account, res["posko"])
        with as_user(operator.user):
            api.update_posko(res["posko"], notes="diubah")

    def test_rejecting_an_operator_new_posko_keeps_the_role(self):
        operator = make_actor()
        res = self.create(operator)
        approval.reject_posko_operator(operator.account, res["posko"])
        self.assertEqual(frappe.db.get_value("RN User Account", operator.account, "role"), "posko_operator")
        with as_user(operator.user), self.assertRaises(frappe.PermissionError):
            api.update_posko(res["posko"], notes="diubah")
