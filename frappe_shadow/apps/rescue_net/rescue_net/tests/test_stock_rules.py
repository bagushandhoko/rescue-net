"""Stock receipts count goods once and keep kitchen usage (phase 2: L-3, L-4)."""

import frappe
from frappe.utils import add_to_date, now_datetime

from rescue_net import api_kitchen
from rescue_net import api_logistics as api
from rescue_net.tests.factories import _insert, as_user
from rescue_net.tests.test_logistics_chain import LogisticsTestCase

ITEM, UNIT = "Beras 5 kg", "karung"


class TestStockReceipts(LogisticsTestCase):
    def stock(self):
        rows = frappe.get_all("RN Stock Observation",
                              filters={"posko": self.w.posko_a.name, "item_name": ITEM},
                              fields=["quantity"], order_by="observed_at desc, creation desc", limit=1)
        return rows[0].quantity if rows else None

    def snapshot(self, qty):
        _insert("RN Stock Observation", title=f"{ITEM} - uji", posko=self.w.posko_a.name,
                disaster_event=self.w.event.name, item_name=ITEM, quantity=qty, unit=UNIT,
                quantity_mode="exact", stock_state="available",
                observed_at=add_to_date(now_datetime(), hours=-1))

    def arrived_flow(self, offer=None):
        flow = self.flow_to_a(offer=offer)
        self.move(flow, "assigned_pickup", "dispatched", "arrived_at_posko")
        return flow

    def test_offer_received_through_its_flow_is_not_received_again(self):
        offer = self.offer_to_a()
        flow = self.arrived_flow(offer)
        with as_user(self.op_a.user):
            api.receive_flow_and_update_stock(flow, 10, UNIT)
        self.assertEqual(self.stock(), 10)
        with as_user(self.op_a.user), self.assertRaises(frappe.ValidationError):
            api.receive_aid_offer_and_update_stock(offer)
        self.assertEqual(self.stock(), 10)

    def test_offer_on_a_running_flow_cannot_be_received_directly(self):
        offer = self.offer_to_a()
        self.arrived_flow(offer)
        with as_user(self.op_a.user), self.assertRaises(frappe.ValidationError):
            api.receive_aid_offer_and_update_stock(offer)
        self.assertIsNone(self.stock())

    def test_direct_offer_without_flow_is_received_once(self):
        offer = self.offer_to_a()
        with as_user(self.op_a.user):
            api.receive_aid_offer_and_update_stock(offer)
        self.assertEqual(self.stock(), 10)
        with as_user(self.op_a.user), self.assertRaises(frappe.ValidationError):
            api.receive_aid_offer_and_update_stock(offer)
        self.assertEqual(self.stock(), 10)

    def test_receipt_keeps_kitchen_usage_since_the_snapshot(self):
        self.snapshot(20)
        with as_user(self.op_a.user):
            api_kitchen.create_production(self.w.posko_a.name, "Nasi", 50,
                                          [{"item_name": ITEM, "quantity": 5, "unit": UNIT}])
            self.assertEqual(
                api_kitchen.effective_stock(self.w.posko_a.name, ITEM, UNIT)["stock"]["available_quantity"], 15)
            result = api.receive_flow_and_update_stock(self.arrived_flow(), 10, UNIT)
        self.assertEqual(result["previous_quantity"], 15)
        self.assertEqual(self.stock(), 25)                      # was 30: usage "refunded"
        with as_user(self.op_a.user):
            self.assertEqual(
                api_kitchen.effective_stock(self.w.posko_a.name, ITEM, UNIT)["stock"]["available_quantity"], 25)
