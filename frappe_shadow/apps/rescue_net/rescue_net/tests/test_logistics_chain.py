"""Logistic Need → Aid Offer → Distribution Flow → Evidence, through the
whitelisted API (the path the frontend uses), plus valid/invalid status
transitions and who may drive them."""

import frappe

from rescue_net import api_logistics as api
from rescue_net.tests.factories import (
    RNTestCase,
    api_call,
    as_guest,
    as_user,
    known_bug,
    make_actor,
    make_transport_space,
    make_world,
)


class LogisticsTestCase(RNTestCase):
    def setUp(self):
        super().setUp()
        self.w = make_world()
        self.op_a = make_actor(posko=self.w.posko_a)            # operator of posko A
        self.op_b = make_actor(posko=self.w.posko_b)            # operator of posko B (other org)
        self.owner_a = make_actor(org=self.w.org_a, org_role="owner")
        self.member_a = make_actor(org=self.w.org_a, org_role="member")
        self.outsider = make_actor()                            # logged in, no affiliation

    def need_at_a(self, **kw):
        with as_user(self.op_a.user):
            return api.create_need(self.w.posko_a.name, kw.pop("item", "Beras 5 kg"),
                                   quantity=kw.pop("quantity", 10), unit="karung",
                                   urgency=kw.pop("urgency", "urgent"), **kw)["need"]

    def offer_to_a(self):
        with as_user(self.member_a.user):
            return api.create_aid_offer(self.w.posko_a.name, "Donatur Uji", "Beras 5 kg",
                                        quantity=10, unit="karung")["aid_offer"]

    def flow_to_a(self, need=None, offer=None):
        with as_user(self.op_a.user):
            return api.create_flow(self.w.posko_a.name, "Beras 5 kg", quantity=10, unit="karung",
                                   logistic_need=need, aid_offer=offer)["flow"]

    def move(self, flow, *statuses, user=None):
        with as_user(user or self.op_a.user):
            for status in statuses:
                api.update_flow_status(flow, status)

    def status(self, doctype, name, field):
        return frappe.db.get_value(doctype, name, field)


class TestNeed(LogisticsTestCase):
    def test_operator_creates_open_need_scoped_to_posko_event(self):
        need = self.need_at_a(jiwa_terdampak=40)
        doc = frappe.get_doc("RN Logistic Need", need)
        self.assertEqual(doc.need_status, "open")
        self.assertEqual(doc.posko, self.w.posko_a.name)
        # inherited from the posko (regression: create_need never set it before 2026-09-25)
        self.assertEqual(doc.disaster_event, self.w.event.name)
        self.assertEqual(doc.jiwa_terdampak, 40)

    def test_org_member_may_contribute_a_need(self):
        with as_user(self.member_a.user):
            need = api.create_need(self.w.posko_a.name, "Air mineral", quantity=5, unit="dus")["need"]
        self.assertTrue(frappe.db.exists("RN Logistic Need", need))

    def test_outsider_and_other_org_operator_are_refused(self):
        for actor in (self.outsider, self.op_b):
            with as_user(actor.user), self.assertRaises(frappe.PermissionError):
                api.create_need(self.w.posko_a.name, "Beras", quantity=1, unit="kg")

    def test_guest_is_refused(self):
        with as_guest(), self.assertRaises(frappe.ValidationError):
            api.create_need(self.w.posko_a.name, "Beras", quantity=1, unit="kg")


class TestFullChain(LogisticsTestCase):
    def test_need_offer_flow_receive_evidence(self):
        need = self.need_at_a()
        offer = self.offer_to_a()
        self.assertEqual(self.status("RN Aid Offer", offer, "offer_status"), "available")

        flow = self.flow_to_a(need=need, offer=offer)
        self.assertEqual(self.status("RN Distribution Flow", flow, "flow_status"), "planned")
        self.assertEqual(self.status("RN Distribution Flow", flow, "disaster_event"), self.w.event.name)
        self.assertEqual(self.status("RN Aid Offer", offer, "offer_status"), "reserved")
        self.assertEqual(self.status("RN Logistic Need", need, "need_status"), "in_progress")

        self.move(flow, "assigned_pickup", "dispatched")
        self.assertEqual(self.status("RN Aid Offer", offer, "offer_status"), "in_transit")
        self.move(flow, "arrived_at_posko")

        with as_user(self.op_a.user):
            result = api.receive_flow_and_update_stock(flow, 10, "karung", "Diterima utuh")
        self.assertEqual(self.status("RN Distribution Flow", flow, "flow_status"), "received")
        self.assertTrue(frappe.db.exists("RN Stock Observation", {"posko": self.w.posko_a.name}))
        self.assertTrue(result)

        with as_user(self.member_a.user):
            ev = api.add_evidence("RN Distribution Flow", flow, "/files/uji-serah-terima.jpg",
                                  caption="Serah terima")
        evidence = frappe.get_doc("RN Operational Evidence", ev["evidence"])
        self.assertEqual(evidence.verification_status, "pending")
        self.assertEqual(evidence.posko, self.w.posko_a.name)
        self.assertEqual(evidence.uploader_user, self.member_a.account)

    def test_received_via_status_update_marks_offer_delivered(self):
        offer = self.offer_to_a()
        flow = self.flow_to_a(offer=offer)
        self.move(flow, "assigned_pickup", "in_transit", "arrived_at_posko", "partially_received", "received")
        self.assertEqual(self.status("RN Aid Offer", offer, "offer_status"), "delivered")
        self.assertTrue(self.status("RN Distribution Flow", flow, "received_at"))

    def test_cancel_releases_offer(self):
        offer = self.offer_to_a()
        flow = self.flow_to_a(offer=offer)
        self.move(flow, "cancelled")
        self.assertEqual(self.status("RN Aid Offer", offer, "offer_status"), "available")

    def test_transport_space_follows_flow(self):
        space = make_transport_space(self.w.posko_a)
        with as_user(self.op_a.user):
            flow = api.create_flow(self.w.posko_a.name, "Terpal", quantity=3, unit="lembar",
                                   transport_space=space.name)["flow"]
        self.assertEqual(self.status("RN Transport Space", space.name, "transport_status"), "reserved")
        self.move(flow, "assigned_pickup", "in_transit")
        self.assertEqual(self.status("RN Transport Space", space.name, "transport_status"), "in_transit")
        # a busy transport cannot carry a second flow
        with as_user(self.op_a.user), self.assertRaises(frappe.ValidationError):
            api.create_flow(self.w.posko_a.name, "Tenda", quantity=1, transport_space=space.name)


class TestTransitions(LogisticsTestCase):
    def test_skipping_steps_is_refused(self):
        flow = self.flow_to_a()
        for bad in ("received", "arrived_at_posko", "dispatched", "partially_received"):
            with as_user(self.op_a.user), self.assertRaises(frappe.ValidationError):
                api.update_flow_status(flow, bad)
        self.assertEqual(self.status("RN Distribution Flow", flow, "flow_status"), "planned")

    def test_terminal_states_are_final(self):
        received = self.flow_to_a()
        self.move(received, "assigned_pickup", "in_transit", "arrived_at_posko", "received")
        cancelled = self.flow_to_a()
        self.move(cancelled, "cancelled")
        for flow in (received, cancelled):
            for status in api.TRANSITIONS:
                with as_user(self.op_a.user), self.assertRaises(frappe.ValidationError):
                    api.update_flow_status(flow, status)

    def test_no_going_back(self):
        flow = self.flow_to_a()
        self.move(flow, "assigned_pickup", "in_transit")
        for back in ("planned", "assigned_pickup", "dispatched"):
            with as_user(self.op_a.user), self.assertRaises(frappe.ValidationError):
                api.update_flow_status(flow, back)

    def test_unknown_status_refused_by_controller(self):
        flow = frappe.get_doc("RN Distribution Flow", self.flow_to_a())
        flow.flow_status = "teleported"
        with self.assertRaises(frappe.ValidationError):
            flow.save(ignore_permissions=True)

    @known_bug("GAP-P2-transitions")
    def test_transition_rules_hold_on_direct_save(self):
        """KNOWN GAP (architecture review phase 2): the transition table lives
        only in api_logistics.update_flow_status, so Desk / import / any other
        endpoint can jump planned → received. Remove @known_bug once the
        rule moves into the RN Distribution Flow controller."""
        flow = frappe.get_doc("RN Distribution Flow", self.flow_to_a())
        flow.flow_status = "received"
        with self.assertRaises(frappe.ValidationError):
            flow.save(ignore_permissions=True)

    def test_receive_requires_positive_quantity_and_arrival(self):
        flow = self.flow_to_a()
        with as_user(self.op_a.user), self.assertRaises(frappe.ValidationError):
            api.receive_flow_and_update_stock(flow, 5)          # still planned
        self.move(flow, "assigned_pickup", "in_transit", "arrived_at_posko")
        with as_user(self.op_a.user), self.assertRaises(frappe.ValidationError):
            api.receive_flow_and_update_stock(flow, 0)


class TestChainPermissions(LogisticsTestCase):
    def test_only_involved_posko_may_move_a_flow(self):
        flow = self.flow_to_a()
        for actor in (self.outsider, self.op_b, self.member_a):
            with as_user(actor.user), self.assertRaises(frappe.PermissionError):
                api.update_flow_status(flow, "assigned_pickup")
        # the org owner manages every posko of the org
        self.move(flow, "assigned_pickup", user=self.owner_a.user)

    def test_other_org_cannot_create_flow_into_posko(self):
        with as_user(self.op_b.user), self.assertRaises(frappe.PermissionError):
            api.create_flow(self.w.posko_a.name, "Beras", quantity=1)

    def test_offer_and_need_must_belong_to_destination(self):
        offer = self.offer_to_a()
        need = self.need_at_a()
        with as_user(self.op_b.user):
            for kw in ({"aid_offer": offer}, {"logistic_need": need}):
                with self.assertRaises(frappe.ValidationError):
                    api.create_flow(self.w.posko_b.name, "Beras", quantity=1, **kw)

    def test_offer_cannot_be_allocated_twice(self):
        offer = self.offer_to_a()
        self.flow_to_a(offer=offer)
        with as_user(self.op_a.user), self.assertRaises(frappe.ValidationError):
            api.create_flow(self.w.posko_a.name, "Beras", quantity=1, aid_offer=offer)

    def test_evidence_needs_contributor_rights(self):
        flow = self.flow_to_a()
        for actor in (self.outsider, self.op_b):
            with as_user(actor.user), self.assertRaises(frappe.PermissionError):
                api.add_evidence("RN Distribution Flow", flow, "/files/x.jpg")
        with as_user(self.op_a.user), self.assertRaises(frappe.ValidationError):
            api.add_evidence("RN Medical Case", flow, "/files/x.jpg")   # doctype not allowed


class TestPublicDonation(LogisticsTestCase):
    """Owner rule 2026-09-26: a posko not open to the public takes no
    donations from outside (fulfill_need was the one path without the gate)."""

    def fulfill(self, need):
        with as_guest():
            return api_call("rescue_net.api_control_centre.fulfill_need", need=need,
                            donor_name="Warga Uji", quantity=2, contact="0812")

    def test_closed_posko_refuses_outside_donation(self):
        need = self.need_at_a()
        with self.assertRaises(frappe.PermissionError):
            self.fulfill(need)
        self.assertFalse(frappe.db.exists("RN Aid Offer", {"donor_name": "Warga Uji",
                                                           "target_posko": self.w.posko_a.name}))

    def test_open_posko_accepts_outside_donation(self):
        frappe.db.set_value("RN Organization", self.w.org_a.name,
                            {"privacy_mode": "open", "allow_posko_public_choice": 1})
        frappe.db.set_value("RN Posko", self.w.posko_a.name,
                            {"public_detail": "public", "public_participation": 1, "accept_goods": 1})
        need = self.need_at_a()
        self.fulfill(need)
        self.assertTrue(frappe.db.exists("RN Aid Offer", {"donor_name": "Warga Uji",
                                                          "target_posko": self.w.posko_a.name}))

    def test_open_posko_that_does_not_accept_goods_refuses(self):
        frappe.db.set_value("RN Organization", self.w.org_a.name,
                            {"privacy_mode": "open", "allow_posko_public_choice": 1})
        frappe.db.set_value("RN Posko", self.w.posko_a.name,
                            {"public_detail": "public", "public_participation": 1, "accept_goods": 0})
        with self.assertRaises(frappe.PermissionError):
            self.fulfill(self.need_at_a())

    def test_own_org_member_may_still_fulfil_a_closed_posko(self):
        need = self.need_at_a()
        with as_user(self.member_a.user):
            api_call("rescue_net.api_control_centre.fulfill_need", need=need,
                     donor_name="Gudang Org A", quantity=2)
        self.assertTrue(frappe.db.exists("RN Aid Offer", {"donor_name": "Gudang Org A",
                                                          "target_posko": self.w.posko_a.name}))
