"""A flow follows its graph from every entry point, the armada and the aid offer follow the
flow, and an offer on its way is not cancelled or rewritten by the donor (phase 2: L-10, L-11)."""

import frappe

from rescue_net import api_logistics as api
from rescue_net.tests.factories import as_user, make_transport_space
from rescue_net.tests.test_logistics_chain import LogisticsTestCase


class TestFlowFollowsGraph(LogisticsTestCase):
    def setUp(self):
        super().setUp()
        make_transport_space(self.w.posko_b, service_mode="courier_pickup")
        self.offer = self.offer_to_a()
        with as_user(self.op_b.user):
            self.flow = api.claim_aid_pickup(self.w.posko_b.name, self.offer, self.w.posko_a.name)["flow"]

    def test_claimed_pickup_moves_on_instead_of_getting_stuck(self):
        self.move(self.flow, "in_transit", "arrived_at_posko")
        self.assertEqual(self.status("RN Aid Offer", self.offer, "offer_status"), "in_transit")

    def test_claiming_a_flow_syncs_armada_and_offer(self):
        space = make_transport_space(self.w.posko_b)
        with as_user(self.op_b.user):
            api.claim_distribution_flow(self.flow, transport_space=space.name)
        self.assertEqual(self.status("RN Transport Space", space.name, "transport_status"), "assigned")
        self.assertEqual(self.status("RN Aid Offer", self.offer, "offer_status"), "reserved")

    def test_a_flow_on_its_way_cannot_be_claimed_again(self):
        self.move(self.flow, "in_transit")
        space = make_transport_space(self.w.posko_b)
        with as_user(self.op_b.user), self.assertRaises(frappe.ValidationError):
            api.claim_distribution_flow(self.flow, transport_space=space.name)


class TestOfferOnItsWay(LogisticsTestCase):
    def test_donor_cannot_cancel_or_rewrite_an_offer_riding_a_flow(self):
        offer = self.offer_to_a()
        flow = self.flow_to_a(offer=offer)
        doc = frappe.get_doc("RN Aid Offer", offer)
        doc.quantity = 99
        with self.assertRaises(frappe.ValidationError):
            doc.save(ignore_permissions=True)
        doc.reload()
        doc.offer_status = "cancelled"
        with self.assertRaises(frappe.ValidationError):
            doc.save(ignore_permissions=True)
        # once the flow is cancelled the offer is the donor's again
        self.move(flow, "cancelled")
        doc.reload()
        doc.offer_status = "cancelled"
        doc.save(ignore_permissions=True)
