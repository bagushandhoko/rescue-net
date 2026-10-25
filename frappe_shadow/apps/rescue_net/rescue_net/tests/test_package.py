"""Paket multi-barang (owner 2026-10-26): several items in one shipment with
one resi / label / armada; each item checked against stock and received on
its own."""

import frappe

from rescue_net.api_control_centre import flow_trace
from rescue_net.logistics.flows import update_flow_status
from rescue_net.logistics.package import create_package
from rescue_net.logistics.transport import confirm_transport_booking
from rescue_net.tests.factories import (RNTestCase, _insert, as_guest, as_user, make_actor, make_posko,
                                        make_transport_space, make_world)


class TestPackage(RNTestCase):
    def setUp(self):
        super().setUp()
        self.w = make_world()
        self.src = make_posko(self.w.event, self.w.org_a, posko_type="logistics")
        self.dst = make_posko(self.w.event, self.w.org_b, posko_type="logistics")
        self.tp_b = make_posko(self.w.event, self.w.org_b, posko_type="transport")
        self.arm_b = make_transport_space(self.tp_b, disaster_event=self.w.event.name)
        self.op = make_actor(posko=self.src)
        for item, qty, unit in (("Beras", 100, "karung"), ("Air Mineral", 50, "dus"), ("Selimut", 30, "lembar")):
            _insert("RN Stock Observation", title="Stok " + item, posko=self.src.name, item_name=item,
                    quantity=qty, unit=unit, observed_at="2026-10-01 08:00:00")

    def send(self, items, **kw):
        with as_user(self.op.user):
            return create_package(destination_posko=self.dst.name, items=items, source_posko=self.src.name, **kw)

    ITEMS = [{"item_text": "Beras", "quantity": 10, "unit": "karung"},
             {"item_text": "Air Mineral", "quantity": 5, "unit": "dus"},
             {"item_text": "Selimut", "quantity": 3, "unit": "lembar"}]

    def test_one_package_one_booking_members_follow_the_armada(self):
        r = self.send(self.ITEMS, transport_space=self.arm_b.name, weight_kg=600)
        self.assertEqual(len(r["flows"]), 3)
        lead, members = r["flows"][0], r["flows"][1:]
        self.assertEqual(frappe.db.count("RN Transport Booking", {"distribution_flow": ["in", r["flows"]]}), 1)
        self.assertIn("Selimut", frappe.db.get_value("RN Transport Booking", r["booking"], "cargo_desc"))
        for m in members:
            self.assertEqual(frappe.db.get_value("RN Distribution Flow", m, "package_flow"), lead)
        with as_user(make_actor(posko=self.tp_b).user):
            confirm_transport_booking(r["booking"])
        for m in members:
            self.assertEqual(frappe.db.get_value("RN Distribution Flow", m, "transport_space"), self.arm_b.name)

    def test_members_follow_status_and_are_received_one_by_one(self):
        r = self.send(self.ITEMS)
        lead, m1 = r["flows"][0], r["flows"][1]
        with as_user(self.op.user):
            for st in ("assigned_pickup", "in_transit"):
                update_flow_status(lead, st)
            with self.assertRaisesRegex(frappe.ValidationError, "mengikuti kiriman utama"):
                update_flow_status(m1, "arrived_at_posko")
            update_flow_status(lead, "arrived_at_posko")
        self.assertEqual(frappe.db.get_value("RN Distribution Flow", m1, "flow_status"), "arrived_at_posko")
        with as_user(make_actor(posko=self.dst).user):
            update_flow_status(lead, "received", received_quantity=10)
            update_flow_status(m1, "received", received_quantity=5)
        self.assertEqual(frappe.db.get_value("RN Distribution Flow", r["flows"][2], "flow_status"), "arrived_at_posko")

    def test_any_item_over_stock_creates_nothing(self):
        before = frappe.db.count("RN Distribution Flow")
        items = self.ITEMS[:1] + [{"item_text": "Selimut", "quantity": 31, "unit": "lembar"}]
        with self.assertRaisesRegex(frappe.ValidationError, "Stok tidak cukup"):
            self.send(items)
        self.assertEqual(frappe.db.count("RN Distribution Flow"), before)

    def test_trace_lists_the_package_with_the_main_resi(self):
        r = self.send(self.ITEMS)
        with as_guest():
            t = flow_trace(flow=r["flows"][2])
        self.assertEqual(t["package"]["flow"], r["flows"][0])
        self.assertFalse(t["package"]["is_main"])
        self.assertEqual([i["item"] for i in t["package"]["items"]], ["Beras", "Air Mineral", "Selimut"])
        with as_guest():
            self.assertIsNone(flow_trace(flow=self.send(self.ITEMS[:1])["flow"])["package"])

    def test_duplicate_item_is_refused(self):
        with self.assertRaisesRegex(frappe.ValidationError, "dua kali"):
            self.send(self.ITEMS[:1] * 2)
