"""Verification decisions (phase 2: VF-1, VF-2)."""

import frappe

from rescue_net.tests.factories import RNTestCase, api_call, as_user, make_actor, make_world

APPROVE = "rescue_net.api_verification.approval_action"


class TestRoleRequests(RNTestCase):
    def setUp(self):
        super().setUp()
        self.w = make_world()
        self.requester = make_actor(role="viewer")
        frappe.db.set_value("RN User Account", self.requester.account, {
            "requested_role": "command_center", "role_request_status": "pending",
        })
        self.operator = make_actor(posko=self.w.posko_b)

    def test_operator_cannot_approve_a_role_request(self):
        with as_user(self.operator.user), self.assertRaises(frappe.PermissionError):
            api_call(APPROVE, kind="user", name=self.requester.account, action="approve")
        self.assertEqual(frappe.db.get_value("RN User Account", self.requester.account, "role"), "viewer")

    def test_system_manager_approves_a_role_request(self):
        api_call(APPROVE, kind="user", name=self.requester.account, action="approve")
        self.assertEqual(frappe.db.get_value("RN User Account", self.requester.account, "role"), "command_center")

    def test_direct_save_of_a_role_change_needs_system_manager(self):
        doc = frappe.get_doc("RN User Account", self.requester.account)
        doc.role = "command_center"
        with as_user(self.operator.user), self.assertRaises(frappe.PermissionError):
            doc.save(ignore_permissions=True)


class TestPoskoVerification(RNTestCase):
    def setUp(self):
        super().setUp()
        self.w = make_world()
        self.own_op = make_actor(org=self.w.org_a, posko=self.w.posko_a)
        self.other_op = make_actor(org=self.w.org_b, posko=self.w.posko_b)

    def status(self):
        return frappe.db.get_value("RN Posko", self.w.posko_a.name, "verification_status")

    def test_operator_cannot_verify_own_posko(self):
        with as_user(self.own_op.user), self.assertRaises(frappe.PermissionError):
            api_call(APPROVE, kind="posko", name=self.w.posko_a.name, action="approve")
        self.assertNotEqual(self.status(), "official_verified")

    def test_other_organisation_operator_may_verify(self):
        with as_user(self.other_op.user):
            api_call(APPROVE, kind="posko", name=self.w.posko_a.name, action="approve")
        self.assertEqual(self.status(), "official_verified")

    def test_decided_item_is_not_re_decided_by_an_operator(self):
        frappe.db.set_value("RN Posko", self.w.posko_a.name, "verification_status", "rejected")
        with as_user(self.other_op.user), self.assertRaises(frappe.PermissionError):
            api_call(APPROVE, kind="posko", name=self.w.posko_a.name, action="approve")
        self.assertEqual(self.status(), "rejected")
