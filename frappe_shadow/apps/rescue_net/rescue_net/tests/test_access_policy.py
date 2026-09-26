"""access_policy: who is an actor and who may manage which posko.
Replaces the print-only scripts scratchpad/test_coord_edit.py and
scratchpad/test_ld2_reg.py (which ran against the production sim users)."""

import frappe

from rescue_net.access_policy import can_manage_organization, can_manage_posko, rn_actor
from rescue_net.api_control_centre import posko_edit_scope
from rescue_net.tests.factories import RNTestCase, as_guest, as_user, make_actor, make_posko, make_user, make_world


class TestRnActor(RNTestCase):
    def test_guest(self):
        with as_guest():
            self.assertIsNone(rn_actor(required=False))
            with self.assertRaises(frappe.ValidationError):
                rn_actor()

    def test_user_without_active_account_is_not_an_actor(self):
        bare = make_user()
        with as_user(bare), self.assertRaises(frappe.ValidationError):
            rn_actor()
        suspended = make_actor()
        frappe.db.set_value("RN User Account", suspended.account, "status", "suspended")
        with as_user(suspended.user):
            self.assertIsNone(rn_actor(required=False))

    def test_affiliation_comes_from_membership_and_assignment(self):
        w = make_world()
        a = make_actor(org=w.org_a, posko=w.posko_a)
        with as_user(a.user):
            actor = rn_actor()
        self.assertEqual(actor.name, a.account)
        self.assertEqual(actor.organization, w.org_a.name)
        self.assertEqual(actor.posko, w.posko_a.name)

    def test_system_manager(self):
        sm = make_user(roles=["System Manager"])
        with as_user(sm):
            self.assertEqual(rn_actor().role, "system_manager")


class TestPoskoManagement(RNTestCase):
    def setUp(self):
        super().setUp()
        self.w = make_world()
        self.sibling = make_posko(self.w.event, self.w.org_a, title="Posko A2")
        self.coordinator = make_actor(role="community_coordinator", org=self.w.org_a)
        self.operator = make_actor(posko=self.w.posko_a, org=self.w.org_a)
        self.owner = make_actor(org=self.w.org_a, org_role="owner")

    def manages(self, who, posko):
        with as_user(who.user):
            return can_manage_posko(rn_actor(), posko.name)

    def test_coordinator_manages_every_posko_of_own_org_only(self):
        self.assertTrue(self.manages(self.coordinator, self.w.posko_a))
        self.assertTrue(self.manages(self.coordinator, self.sibling))
        self.assertFalse(self.manages(self.coordinator, self.w.posko_b))

    def test_operator_manages_own_posko_only(self):
        self.assertTrue(self.manages(self.operator, self.w.posko_a))
        self.assertFalse(self.manages(self.operator, self.sibling))
        self.assertFalse(self.manages(self.operator, self.w.posko_b))

    def test_owner_manages_the_organization(self):
        with as_user(self.owner.user):
            self.assertTrue(can_manage_organization(rn_actor(), self.w.org_a.name))
            self.assertFalse(can_manage_organization(rn_actor(), self.w.org_b.name))
        with as_user(self.operator.user):
            self.assertFalse(can_manage_organization(rn_actor(), self.w.org_a.name))

    def test_posko_edit_scope(self):
        """Documented model: approved members of the posko's org may edit every
        posko of that org; a member of ANOTHER org gets a read-only page."""
        with as_user(self.coordinator.user):
            scope = posko_edit_scope(posko=self.sibling.name, disaster_event=self.w.event.name)
        self.assertTrue(scope["can_edit_current"])
        with as_user(self.operator.user):   # org A member → may edit org A's other posko
            scope = posko_edit_scope(posko=self.sibling.name, disaster_event=self.w.event.name)
        self.assertTrue(scope["can_edit_current"])
        other_org = make_actor(posko=self.w.posko_b, org=self.w.org_b)
        with as_user(other_org.user):
            scope = posko_edit_scope(posko=self.w.posko_a.name, disaster_event=self.w.event.name)
        self.assertFalse(scope["can_edit_current"])
        self.assertEqual(scope["primary_posko"], self.w.posko_b.name)
