"""Armada capacity: bookings fit the free space, never on a departed/cancelled armada,
a flow that ends frees the armada only when no other flow rides it (phase 2: L-6, L-12)."""

import frappe

from rescue_net import api_logistics as api
from rescue_net.tests.factories import _insert, as_user, make_transport_space
from rescue_net.tests.test_logistics_chain import LogisticsTestCase


class TestArmadaCapacity(LogisticsTestCase):
    def setUp(self):
        super().setUp()
        self.space = make_transport_space(self.w.posko_a, capacity_weight_kg=100, booking_policy="open")

    def book(self, space=None, **qty):
        with as_user(self.op_b.user):
            return api.book_transport_space(space or self.space.name, cargo_desc="Beras",
                                            delivery_method="self_deliver", **qty)

    def test_requested_and_confirmed_bookings_share_the_space(self):
        self.book(qty_weight_kg=60)
        with self.assertRaises(frappe.ValidationError):
            self.book(qty_weight_kg=50)
        self.book(qty_weight_kg=40)

    def test_armada_without_declared_capacity_is_not_bookable(self):
        bare = make_transport_space(self.w.posko_a, capacity_weight_kg=0)
        with self.assertRaises(frappe.ValidationError):
            self.book(bare.name, qty_weight_kg=10)
        # a kg-only armada does not take a booking expressed only in m3
        with self.assertRaises(frappe.ValidationError):
            self.book(qty_volume_m3=2)

    def test_cancelled_or_departed_armada_takes_no_booking(self):
        for status in ("cancelled", "in_transit", "completed"):
            frappe.db.set_value("RN Transport Space", self.space.name, "transport_status", status)
            with self.assertRaises(frappe.ValidationError):
                self.book(qty_weight_kg=10)

    def test_raising_a_quantity_on_a_direct_save_is_rechecked(self):
        name = self.book(qty_weight_kg=60)["booking"]
        self.book(qty_weight_kg=30)
        doc = frappe.get_doc("RN Transport Booking", name)
        doc.qty_weight_kg = 80
        with self.assertRaises(frappe.ValidationError):
            doc.save(ignore_permissions=True)

    def test_a_cancelled_booking_is_final(self):
        name = self.book(qty_weight_kg=10)["booking"]
        with as_user(self.op_b.user):
            api.cancel_transport_booking(name)
        doc = frappe.get_doc("RN Transport Booking", name)
        doc.status = "confirmed"
        with self.assertRaises(frappe.ValidationError):
            doc.save(ignore_permissions=True)


class TestArmadaSharedByFlows(LogisticsTestCase):
    def test_cancelling_one_flow_keeps_the_armada_for_the_other(self):
        space = make_transport_space(self.w.posko_a)
        with as_user(self.op_a.user):
            first = api.create_flow(self.w.posko_a.name, "Terpal", quantity=3, unit="lembar",
                                    transport_space=space.name)["flow"]
        second = _insert("RN Distribution Flow", title="Tenda", destination_posko=self.w.posko_a.name,
                         disaster_event=self.w.event.name, item_name="Tenda", quantity=1,
                         flow_status="planned").name
        with as_user(self.op_a.user):
            api.claim_distribution_flow(second, transport_space=space.name)
        self.move(first, "cancelled")
        self.assertEqual(self.status("RN Transport Space", space.name, "transport_status"), "reserved")
        self.move(second, "cancelled")
        self.assertEqual(self.status("RN Transport Space", space.name, "transport_status"), "available")

    def test_cancelled_armada_cannot_be_claimed_for_a_flow(self):
        space = make_transport_space(self.w.posko_a, transport_status="cancelled")
        flow = self.flow_to_a()
        with as_user(self.op_a.user), self.assertRaises(frappe.ValidationError):
            api.claim_distribution_flow(flow, transport_space=space.name)
