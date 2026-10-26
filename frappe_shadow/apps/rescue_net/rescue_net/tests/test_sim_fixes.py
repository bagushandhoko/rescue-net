"""Fixes from the owner's simulation 2026-10-26 (laporan → logistik → apotik →
2 posko distribusi → dapur & medis)."""

import frappe

from rescue_net.frontend_bridge.reports import take_community_report
from rescue_net.logistics.flows import create_flow
from rescue_net.tests.factories import (RNTestCase, _insert, as_user, make_actor, make_posko,
                                        make_transport_space, make_world)


class TestSimulationFixes(RNTestCase):
    def setUp(self):
        super().setUp()
        self.w = make_world()
        self.medis = make_posko(self.w.event, self.w.org_b, posko_type="medical")
        self.logi = make_posko(self.w.event, self.w.org_a, posko_type="logistics")
        self.op = make_actor(posko=self.logi)

    def test_another_posko_takes_over_a_report(self):
        rep = _insert("RN Community Report", title="Butuh obat", disaster_event=self.w.event.name,
                      posko=self.medis.name, status="submitted")
        with as_user(self.op.user):
            r = take_community_report(rep.name, self.logi.name, note="Kami punya stok obat")
        self.assertEqual(r["posko"], self.logi.name)
        self.assertEqual(frappe.db.get_value("RN Community Report", rep.name, "posko"), self.logi.name)
        self.assertTrue(frappe.db.exists("RN Community Report Update", {"report": rep.name}))
        with as_user(make_actor().user), self.assertRaises(frappe.PermissionError):
            take_community_report(rep.name, self.logi.name)

    def test_stock_card_shows_what_is_left_after_sending(self):
        from rescue_net.control_centre.posko import _stock_cards
        _insert("RN Stock Observation", title="Beras", posko=self.logi.name, item_name="Beras", quantity=100,
                unit="kg", quantity_mode="exact", observed_at="2026-10-01 08:00:00")
        with as_user(self.op.user):
            create_flow(destination_posko=self.medis.name, item_text="Beras", quantity=30, unit="kg",
                        quantity_mode="exact", source_posko=self.logi.name)
        card = next(c for c in _stock_cards(self.logi.name) if c["item"] == "Beras")
        self.assertEqual(card["stok_ada"], 70)
        self.assertEqual(card["stok_tercatat"], 100)

    def test_open_armada_confirms_a_shipment_from_another_org(self):
        tp = make_posko(self.w.event, self.w.org_b, posko_type="transport")
        ship = make_transport_space(tp, disaster_event=self.w.event.name)
        frappe.db.set_value("RN Transport Space", ship.name, "booking_policy", "open")
        _insert("RN Stock Observation", title="Air", posko=self.logi.name, item_name="Air", quantity=50,
                unit="dus", quantity_mode="exact", observed_at="2026-10-01 08:00:00")
        with as_user(self.op.user):
            r = create_flow(destination_posko=self.medis.name, item_text="Air", quantity=5, unit="dus",
                            quantity_mode="exact", source_posko=self.logi.name, transport_space=ship.name, weight_kg=50)
        self.assertEqual(r["booking_status"], "confirmed")
