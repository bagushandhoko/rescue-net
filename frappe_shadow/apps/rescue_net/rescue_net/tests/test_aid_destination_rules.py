"""Aid reaches the posko it was meant for, and only open needs take new aid (phase 2: L-19, L-20)."""

import frappe

from rescue_net import api_control_centre as cc
from rescue_net import api_logistics as api
from rescue_net.tests.factories import _insert, as_user, make_transport_space
from rescue_net.tests.test_logistics_chain import LogisticsTestCase


class TestPickupDestination(LogisticsTestCase):
    def setUp(self):
        super().setUp()
        make_transport_space(self.w.posko_b, service_mode="courier_pickup")

    def claim(self, offer, destination):
        with as_user(self.op_b.user):
            return api.claim_aid_pickup(self.w.posko_b.name, offer, destination)

    def test_targeted_offer_cannot_be_driven_elsewhere(self):
        offer = self.offer_to_a()
        with self.assertRaises(frappe.ValidationError):
            self.claim(offer, self.w.posko_b.name)
        self.claim(offer, self.w.posko_a.name)
        self.assertEqual(self.status("RN Aid Offer", offer, "offer_status"), "pickup_claimed")

    def test_untargeted_offer_takes_the_chosen_destination(self):
        offer = _insert("RN Aid Offer", title="Donasi lepas", disaster_event=self.w.event.name,
                        donor_name="Donatur Uji", item_name="Air", quantity=5, unit="dus",
                        offer_status="need_pickup").name
        self.claim(offer, self.w.posko_a.name)
        self.assertEqual(self.status("RN Aid Offer", offer, "target_posko"), self.w.posko_a.name)


class TestClosedNeeds(LogisticsTestCase):
    def test_closed_need_takes_no_new_aid(self):
        need = self.need_at_a()
        frappe.db.set_value("RN Logistic Need", need, "need_status", "fulfilled")
        with as_user(self.member_a.user), self.assertRaises(frappe.ValidationError):
            cc.fulfill_need(need, "Donatur Uji", 5)
        with self.assertRaises(frappe.ValidationError):
            self.flow_to_a(need=need)

    def test_open_need_still_takes_aid(self):
        need = self.need_at_a()
        with as_user(self.member_a.user):
            cc.fulfill_need(need, "Donatur Uji", 5)
        self.flow_to_a(need=need)
