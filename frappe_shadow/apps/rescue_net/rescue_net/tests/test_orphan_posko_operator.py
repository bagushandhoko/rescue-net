"""Owner 2026-11-08 ("beri petugas"): a posko without any manager (no org managers, no operator) is no longer a dead
end — a logged-in user asks to run it, the request shows in the Verification queue, the super admin approves."""

import frappe

from rescue_net import api_operator_approval as op
from rescue_net import api_verification as ver
from rescue_net.tests.factories import RNTestCase, as_user, make_actor, make_event, make_org, make_posko


class TestOrphanPoskoOperator(RNTestCase):
    def setUp(self):
        super().setUp()
        self.event = make_event(event_status="active")
        self.orphan_org = make_org()                                   # no owner membership
        self.orphan = make_posko(self.event, self.orphan_org)
        self.org = make_org(verification_status="verified")
        self.managed = make_posko(self.event, self.org)
        make_actor(org=self.org, org_role="owner")
        self.person = make_actor(role="")
        frappe.set_user("Administrator")

    def test_request_and_super_admin_approval(self):
        with as_user(self.person.user):
            self.assertTrue(op.posko_operator_status(self.orphan.name)["can_request"])
            r = op.request_posko_operator(self.orphan.name)
            self.assertEqual(r["result"], "operator_request_pending")
            self.assertTrue(op.posko_operator_status(self.orphan.name)["pending"])
        queue = ver.approval_queue()
        self.assertIn(self.person.account, [q["name"] for q in queue["queue"] if q["kind"] == "user"])
        detail = ver.approval_item_detail("user", self.person.account)
        self.assertIn("Posko Diminta", frappe.as_json(detail))
        frappe.set_user("Administrator")
        ver.approval_action("user", self.person.account, "approve")
        self.assertEqual(frappe.db.get_value("RN Posko Assignment",
                         {"user_account": self.person.account, "posko": self.orphan.name}, "status"), "approved")
        with as_user(self.person.user):
            self.assertTrue(op.posko_operator_status(self.orphan.name)["is_operator"])

    def test_managed_posko_goes_through_its_organisation(self):
        with as_user(self.person.user):
            st = op.posko_operator_status(self.managed.name)
            self.assertFalse(st["can_request"])
            self.assertIn("Ajukan keanggotaan", st["reason"])
            with self.assertRaisesRegex(frappe.ValidationError, "Ajukan keanggotaan"):
                op.request_posko_operator(self.managed.name)

    def test_reject(self):
        with as_user(self.person.user):
            op.request_posko_operator(self.orphan.name)
        frappe.set_user("Administrator")
        ver.approval_action("user", self.person.account, "reject", note="tidak dikenal")
        self.assertEqual(frappe.db.get_value("RN Posko Assignment",
                         {"user_account": self.person.account, "posko": self.orphan.name}, "status"), "rejected")
