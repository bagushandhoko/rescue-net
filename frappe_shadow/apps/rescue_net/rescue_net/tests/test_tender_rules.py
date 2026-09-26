"""Procurement tender lifecycle on every save path (phase 2: L-16)."""

import frappe
from frappe.utils import add_days, now_datetime

from rescue_net import api_tender as api
from rescue_net.tests.factories import RNTestCase, _insert, as_user, make_actor, make_org


class TestTenderRules(RNTestCase):
    def setUp(self):
        super().setUp()
        self.org = make_org(verification_status="verified")
        self.owner = make_actor(org=self.org, org_role="owner")

    def tender(self, org=None, status="open"):
        return _insert("RN Procurement Tender", title="Jembatan darurat", organization=(org or self.org).name,
                       rab_total=1e8, bidding_closes_at=add_days(now_datetime(), 7), status=status)

    def bid(self, tender, amount):
        return api.submit_bid(tender.name, "CV Uji", amount)["bid"]

    def status(self, doctype, name):
        return frappe.db.get_value(doctype, name, "status")

    def test_unverified_org_cannot_open_bidding(self):
        org = make_org(verification_status="unverified")
        owner = make_actor(org=org, org_role="owner")
        t = self.tender(org, status="draft")
        with as_user(owner.user), self.assertRaises(frappe.ValidationError):
            api.update_tender_status(t.name, "open")
        self.assertEqual(self.status("RN Procurement Tender", t.name), "draft")
        with as_user(self.owner.user):
            api.update_tender_status(self.tender(status="draft").name, "open")

    def test_award_needs_a_bid_and_the_graph(self):
        t = self.tender(status="draft")
        with as_user(self.owner.user), self.assertRaises(frappe.ValidationError):
            api.update_tender_status(t.name, "awarded")
        t.reload()
        t.status = "evaluation"                                     # skips open
        with self.assertRaises(frappe.ValidationError):
            t.save(ignore_permissions=True)

    def test_one_winner_and_the_result_is_final(self):
        t = self.tender()
        b1, b2 = self.bid(t, 9e7), self.bid(t, 8e7)
        with as_user(self.owner.user):
            api.set_bid_status(b1, "awarded")
            self.assertEqual(self.status("RN Procurement Tender", t.name), "awarded")
            self.assertEqual(self.status("RN Tender Bid", b2), "rejected")
            for bid, status in ((b2, "awarded"), (b1, "submitted")):
                with self.assertRaises(frappe.ValidationError):
                    api.set_bid_status(bid, status)
            with self.assertRaises(frappe.ValidationError):
                api.update_tender_status(t.name, "open")
        self.assertEqual(self.status("RN Tender Bid", b1), "awarded")
