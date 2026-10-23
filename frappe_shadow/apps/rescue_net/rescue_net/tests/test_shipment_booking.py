"""Kirim stok via armada = booking (owner 2026-10-19): same organisation is
approved at once, another organisation's posko distribusi confirms; armada
choices follow the disaster, the posko logistik and the send window."""

import frappe

from rescue_net.api_control_centre import logistik_dispatch_options
from rescue_net.logistics.flows import create_flow
from rescue_net.logistics.transport import confirm_transport_booking, update_transport_space
from rescue_net.tests.factories import (RNTestCase, _insert, as_guest, as_user, make_actor, make_event,
                                        make_posko, make_transport_space, make_world)


class _ShipmentWorld(RNTestCase):
    def setUp(self):
        super().setUp()
        self.w = make_world()
        self.src = make_posko(self.w.event, self.w.org_a, posko_type="logistics")
        self.dst = make_posko(self.w.event, self.w.org_b, posko_type="logistics")
        self.tp_a = make_posko(self.w.event, self.w.org_a, posko_type="transport")
        self.tp_b = make_posko(self.w.event, self.w.org_b, posko_type="transport")
        self.arm_a = make_transport_space(self.tp_a, disaster_event=self.w.event.name,
                                          departure_at="2026-11-02 08:00:00")
        self.arm_b = make_transport_space(self.tp_b, disaster_event=self.w.event.name,
                                          departure_at="2026-11-05 08:00:00")
        self.op = make_actor(posko=self.src)
        _insert("RN Stock Observation", posko=self.src.name, item_name="Beras", quantity=1000, unit="karung",
                observed_at="2026-10-01 08:00:00")

    def send(self, armada, **kw):
        with as_user(self.op.user):
            return create_flow(destination_posko=self.dst.name, item_text="Beras", quantity=10, unit="karung",
                               quantity_mode="exact", source_posko=self.src.name,
                               transport_space=armada.name, weight_kg=kw.pop("weight_kg", 500), **kw)


class TestShipmentBooking(_ShipmentWorld):
    def test_same_org_armada_is_a_confirmed_booking(self):
        r = self.send(self.arm_a, window_from="2026-11-01 00:00:00", window_to="2026-11-03 23:59:59")
        self.assertEqual(r["booking_status"], "confirmed")
        b = frappe.get_doc("RN Transport Booking", r["booking"])
        self.assertEqual(b.distribution_flow, r["flow"])
        self.assertEqual(str(b.window_from)[:10], "2026-11-01")
        self.assertEqual(frappe.db.get_value("RN Distribution Flow", r["flow"], "transport_space"), self.arm_a.name)

    def test_other_org_armada_waits_for_its_posko(self):
        r = self.send(self.arm_b)
        self.assertEqual(r["booking_status"], "requested")
        self.assertFalse(r["verification_pin"])
        self.assertFalse(frappe.db.get_value("RN Distribution Flow", r["flow"], "transport_space"))
        # the sender cannot confirm it; the armada's posko can, without a PIN
        with as_user(self.op.user), self.assertRaises(frappe.PermissionError):
            confirm_transport_booking(r["booking"])
        coord = make_actor(posko=self.tp_b)
        with as_user(coord.user):
            confirm_transport_booking(r["booking"])
        self.assertEqual(frappe.db.get_value("RN Distribution Flow", r["flow"], "transport_space"), self.arm_b.name)

    def test_flow_takes_the_chosen_disaster_only_if_served(self):
        e2 = make_event()
        with self.assertRaisesRegex(frappe.ValidationError, "tidak menangani"):
            self.send(self.arm_a, disaster_event=e2.name)
        doc = frappe.get_doc("RN Posko", self.src.name)
        doc.append("served_events", {"disaster_event": e2.name})
        doc.save(ignore_permissions=True)
        r = self.send(self.arm_a, disaster_event=e2.name)
        self.assertEqual(frappe.db.get_value("RN Distribution Flow", r["flow"], "disaster_event"), e2.name)

    def test_options_follow_disaster_posko_and_window(self):
        with as_guest():
            ids = lambda **kw: [a["id"] for a in logistik_dispatch_options(
                self.w.event.name, source_posko=self.src.name, **kw)["armada"]]
            both = ids()
            nov1to3 = ids(window_from="2026-11-01", window_to="2026-11-03")
        self.assertTrue({self.arm_a.name, self.arm_b.name} <= set(both))
        self.assertIn(self.arm_a.name, nov1to3)
        self.assertNotIn(self.arm_b.name, nov1to3)
        # armada B now serves only another posko logistik -> not offered to src
        coord = make_actor(posko=self.tp_b)
        with as_user(coord.user):
            update_transport_space(self.arm_b.name, served_poskos=[self.dst.name])
        with as_guest():
            self.assertNotIn(self.arm_b.name, ids())
        # armada A moved to another disaster only -> gone from this one
        e2 = make_event()
        coord_a = make_actor(posko=self.tp_a)
        with as_user(coord_a.user):
            update_transport_space(self.arm_a.name, served_events=[e2.name])
        with as_guest():
            self.assertNotIn(self.arm_a.name, ids())
            opt = logistik_dispatch_options(e2.name)
        self.assertIn(self.arm_a.name, [a["id"] for a in opt["armada"]])

    def test_armada_that_cannot_take_cargo_is_not_offered(self):
        frappe.db.set_value("RN Transport Space", self.arm_b.name, "transport_status", "in_transit")
        with as_guest():
            ids = [a["id"] for a in logistik_dispatch_options(self.w.event.name, source_posko=self.src.name)["armada"]]
        self.assertNotIn(self.arm_b.name, ids)
        self.assertIn(self.arm_a.name, ids)


class TestFirstMile(_ShipmentWorld):
    """Langkah 3 (owner 2026-10-20): how the cargo reaches the main armada's
    handover point — antar sendiri / antrean / transporter."""

    def test_transporter_books_a_second_leg(self):
        courier = make_transport_space(self.tp_a, disaster_event=self.w.event.name)
        r = self.send(self.arm_b, first_mile="transporter", first_mile_space=courier.name)
        self.assertEqual(r["booking_status"], "requested")             # main armada, other org
        self.assertEqual(r["first_mile_status"], "confirmed")          # courier, same org
        fb = frappe.get_doc("RN Transport Booking", r["first_mile_booking"])
        self.assertEqual(fb.booking_leg, "first_mile")
        self.assertEqual(frappe.db.get_value("RN Distribution Flow", r["flow"], "first_mile_space"), courier.name)
        self.assertEqual(frappe.db.get_value("RN Transport Booking", r["booking"], "delivery_method"), "self_deliver")
        # confirming the main booking sets the main armada, not the courier
        coord = make_actor(posko=self.tp_b)
        with as_user(coord.user):
            confirm_transport_booking(r["booking"])
        flow = frappe.get_doc("RN Distribution Flow", r["flow"])
        self.assertEqual((flow.transport_space, flow.first_mile_space), (self.arm_b.name, courier.name))

    def test_transporter_without_main_armada_is_the_main_leg(self):
        r = self.send_direct(first_mile="transporter", first_mile_space=self.arm_b.name)
        self.assertEqual(frappe.db.get_value("RN Transport Booking", r["booking"], "booking_leg"), "main")
        self.assertIsNone(r["first_mile_booking"])

    def test_queue_waits_for_a_posko_distribusi_then_claim_sets_first_leg(self):
        from rescue_net.api_control_centre import posko_distribusi_board
        from rescue_net.logistics.transport import claim_distribution_flow
        r = self.send(self.arm_a, first_mile="queue")                   # main: same org, confirmed
        self.assertEqual(frappe.db.get_value("RN Distribution Flow", r["flow"], "transport_space"), self.arm_a.name)
        with as_guest():
            q = posko_distribusi_board(disaster_event=self.w.event.name)["pickup_queue"]
        row = [x for x in q if x.get("flow") == r["flow"]]
        self.assertTrue(row and row[0]["first_leg"])
        courier = make_transport_space(self.tp_b, disaster_event=self.w.event.name)
        coord = make_actor(posko=self.tp_b)
        with as_user(coord.user):
            claim_distribution_flow(r["flow"], transport_space=courier.name)
        self.assertEqual(frappe.db.get_value("RN Distribution Flow", r["flow"], "first_mile_space"), courier.name)
        with as_guest():
            q = posko_distribusi_board(disaster_event=self.w.event.name)["pickup_queue"]
        self.assertNotIn(r["flow"], [x.get("flow") for x in q])

    def test_self_delivery_and_pending_booking_stay_out_of_the_queue(self):
        from rescue_net.api_control_centre import posko_distribusi_board
        own = self.send_direct(first_mile="self_deliver")
        booked = self.send(self.arm_b)                                  # requested, no armada yet
        with as_guest():
            q = [x.get("flow") for x in posko_distribusi_board(disaster_event=self.w.event.name)["pickup_queue"]]
        self.assertNotIn(own["flow"], q)
        self.assertNotIn(booked["flow"], q)

    def send_direct(self, **kw):
        with as_user(self.op.user):
            return create_flow(destination_posko=self.dst.name, item_text="Beras", quantity=10, unit="karung",
                               quantity_mode="exact", source_posko=self.src.name, weight_kg=500, **kw)


class TestSendWithinStock(_ShipmentWorld):
    """Owner 2026-10-20: a posko never sends beyond its stock."""

    def direct(self, qty, unit="karung"):
        with as_user(self.op.user):
            return create_flow(destination_posko=self.dst.name, item_text="Beras", quantity=qty, unit=unit,
                               quantity_mode="exact", source_posko=self.src.name)

    def test_cannot_send_more_than_available(self):
        with self.assertRaisesRegex(frappe.ValidationError, "Stok tidak cukup"):
            self.direct(1001)
        self.direct(600)
        with self.assertRaisesRegex(frappe.ValidationError, "tersedia 400"):
            self.direct(500)                       # 1000 - 600 already sent
        self.direct(400)

    def test_cancelled_flow_returns_to_available(self):
        from rescue_net.logistics.flows import update_flow_status
        flow = self.direct(1000)["flow"]
        with as_user(self.op.user):
            update_flow_status(flow, "cancelled")
        self.direct(1000)

    def test_unit_and_unknown_item(self):
        with self.assertRaisesRegex(frappe.ValidationError, "Satuan"):
            self.direct(1, unit="kg")
        with as_user(self.op.user), self.assertRaisesRegex(frappe.ValidationError, "Belum ada stok"):
            create_flow(destination_posko=self.dst.name, item_text="Tenda", quantity=1, unit="unit",
                        quantity_mode="exact", source_posko=self.src.name)

    def test_send_form_shows_available_to_the_posko_only(self):
        self.direct(250)
        with as_user(self.op.user):
            st = logistik_dispatch_options(self.w.event.name, source_posko=self.src.name, item="Beras")["stock"]
        self.assertEqual((st["observed"], st["sent_since"], st["available"]), (1000, 250, 750))
        with as_guest():
            self.assertIsNone(logistik_dispatch_options(self.w.event.name, source_posko=self.src.name,
                                                        item="Beras")["stock"])
