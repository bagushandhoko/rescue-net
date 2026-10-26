"""Unit conversion on stock (owner 2026-10-26)."""

import frappe

from rescue_net.services.units import convert
from rescue_net.tests.factories import RNTestCase, _insert, as_user, make_actor, make_posko, make_world


class TestUnitConversion(RNTestCase):
    def setUp(self):
        super().setUp()
        _insert("RN Unit Conversion", conversion_name="Beras karung", enabled=1, scope_type="canonical_item",
                canonical_item="Beras", from_unit="karung", to_base_unit="kg", factor=25, certainty="perkiraan")
        frappe.local._rn_unit_conversions = None

    def test_convert_both_ways_and_unknown(self):
        self.assertEqual(convert("Beras", 10, "karung", "kg")["quantity"], 250)
        self.assertEqual(convert("Beras", 50, "kg", "karung")["quantity"], 2)
        self.assertIsNone(convert("Beras", 1, "karung", "ikat"))
        self.assertIn("tabel konversi", convert("Beras", 10, "karung", "kg")["note"])

    def test_receipt_in_karung_lands_in_kg_stock(self):
        from rescue_net.logistics.flows import create_flow, update_flow_status
        from rescue_net.logistics.receipts import receive_flow_and_update_stock
        w = make_world()
        src = make_posko(w.event, w.org_a, posko_type="logistics")
        dst = make_posko(w.event, w.org_a, posko_type="kitchen")
        _insert("RN Stock Observation", title="Beras", posko=src.name, item_name="Beras", quantity=20, unit="karung",
                quantity_mode="exact", observed_at="2026-10-01 08:00:00")
        _insert("RN Stock Observation", title="Beras", posko=dst.name, item_name="Beras", quantity=30, unit="kg",
                quantity_mode="exact", observed_at="2026-10-01 08:00:00")
        op = make_actor(posko=src)
        with as_user(op.user):
            f = create_flow(destination_posko=dst.name, item_text="Beras", quantity=10, unit="karung",
                            quantity_mode="exact", source_posko=src.name)["flow"]
            for st in ("assigned_pickup", "in_transit", "arrived_at_posko"):
                update_flow_status(f, st)
        with as_user(make_actor(posko=dst).user):
            r = receive_flow_and_update_stock(f, 10, "karung")
        self.assertEqual(r["current_quantity"], 280)
        self.assertIn("Dikonversi", frappe.db.get_value("RN Stock Observation", r["stock_observation"], "notes"))


class TestKitchenUnits(RNTestCase):
    def setUp(self):
        super().setUp()
        _insert("RN Unit Conversion", conversion_name="Telur tray", enabled=1, scope_type="canonical_item",
                canonical_item="Telur", from_unit="tray", to_base_unit="butir", factor=30, certainty="standar")
        frappe.local._rn_unit_conversions = None
        w = make_world()
        self.dapur = make_posko(w.event, w.org_a, posko_type="kitchen")
        self.ev = w.event.name
        self.cook = make_actor(posko=self.dapur)
        _insert("RN Stock Observation", title="Telur", posko=self.dapur.name, item_name="Telur", quantity=2, unit="tray",
                quantity_mode="exact", observed_at="2026-10-01 08:00:00")

    def test_cook_in_butir_from_tray_stock_and_availability_drops(self):
        from rescue_net.api_kitchen import create_production
        from rescue_net.control_centre.common import stock_available
        with as_user(self.cook.user):
            create_production(posko=self.dapur.name, meal_name="Telur rebus", portions=30,
                              ingredients=[{"item_name": "Telur", "quantity": 30, "unit": "butir"}], disaster_event=self.ev)
        av = stock_available(self.dapur.name, "Telur")
        self.assertEqual(av["used_since"], 1)        # 30 butir = 1 tray
        self.assertEqual(av["available"], 1)
