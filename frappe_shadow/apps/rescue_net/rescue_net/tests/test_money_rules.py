"""Program money is counted once and only grows through its own paths (phase 2: L-9, L-17)."""

import frappe

from rescue_net import api_donor_program as api
from rescue_net.tests.factories import RNTestCase, as_user, make_actor, make_event, make_org, make_posko


class TestMoneyRules(RNTestCase):
    def setUp(self):
        super().setUp()
        self.event = make_event()
        self.org = make_org(verification_status="verified")
        posko = make_posko(self.event, self.org)
        self.owner = make_actor(org=self.org, org_role="owner", posko=posko)
        self.donor = make_actor()
        with as_user(self.owner.user):
            self.program = api.create_special_program(
                self.event.name, "Dapur air bersih", owner_type="organization", owner_id=self.org.name,
                budget_target=10_000_000, budget_received=5_000_000, budget_spent=1_000_000)["program"]

    def total(self, field):
        return frappe.db.get_value("RN Donor Program", self.program, field)

    def donate(self, amount):
        with as_user(self.donor.user):
            return api.create_cash_donation(self.program, amount)["donation"]

    def test_creator_cannot_seed_received_or_spent(self):
        self.assertEqual(self.total("budget_received"), 0)
        self.assertEqual(self.total("budget_spent"), 0)

    def test_confirming_twice_counts_once(self):
        d = self.donate(250_000)
        with as_user(self.owner.user):
            api.decide_cash_donation(d, "confirm")
            with self.assertRaises(frappe.ValidationError):
                api.decide_cash_donation(d, "confirm")
        self.assertEqual(self.total("budget_received"), 250_000)

    def test_decided_donation_is_final_on_direct_save(self):
        d = frappe.get_doc("RN Cash Donation", self.donate(100_000))
        d.status = "rejected"
        d.save(ignore_permissions=True)
        d.status = "received"
        with self.assertRaises(frappe.ValidationError):
            d.save(ignore_permissions=True)

    def test_totals_add_up(self):
        for amount in (100_000, 50_000):
            with as_user(self.owner.user):
                api.decide_cash_donation(self.donate(amount), "confirm")
        self.assertEqual(self.total("budget_received"), 150_000)
        with as_user(self.owner.user):
            api.create_special_program_update(self.program, "Beli tandon", amount_spent=40_000)
            api.create_special_program_update(self.program, "Beli pipa", amount_spent=60_000)
        self.assertEqual(self.total("budget_spent"), 100_000)
