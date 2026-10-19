"""Kirim stok via armada = booking (owner 2026-10-19): same organisation is
approved at once, another organisation's posko distribusi confirms; armada
choices follow the disaster, the posko logistik and the send window."""

import frappe

from rescue_net.api_control_centre import logistik_dispatch_options
from rescue_net.logistics.flows import create_flow
from rescue_net.logistics.transport import confirm_transport_booking, update_transport_space
from rescue_net.tests.factories import (RNTestCase, as_guest, as_user, make_actor, make_event,
                                        make_posko, make_transport_space, make_world)


class TestShipmentBooking(RNTestCase):
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

    def send(self, armada, **kw):
        with as_user(self.op.user):
            return create_flow(destination_posko=self.dst.name, item_text="Beras", quantity=10, unit="karung",
                               quantity_mode="exact", source_posko=self.src.name,
                               transport_space=armada.name, weight_kg=kw.pop("weight_kg", 500), **kw)

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
