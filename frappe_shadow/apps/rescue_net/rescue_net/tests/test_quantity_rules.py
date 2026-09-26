"""Quantities hold on every save (phase 2: L-1, L-2): a given quantity is > 0
(stock >= 0), a range is ordered, and a flow never receives more than it sent
when both are in the same unit."""

import frappe

from rescue_net import api_logistics as api
from rescue_net.tests.factories import RNTestCase, _insert, as_user, make_actor, make_world


class TestQuantityRules(RNTestCase):
    def setUp(self):
        super().setUp()
        self.w = make_world()
        self.op = make_actor(posko=self.w.posko_a)

    def need(self, **kw):
        return _insert("RN Logistic Need", title="Beras", posko=self.w.posko_a.name,
                       disaster_event=self.w.event.name, item_name="Beras", unit="karung", need_status="open", **kw)

    def test_zero_or_negative_quantity_is_refused_on_direct_insert(self):
        for bad in (0, -5):
            with self.assertRaises(frappe.ValidationError):
                self.need(quantity=bad, quantity_mode="exact")
        with self.assertRaises(frappe.ValidationError):
            _insert("RN Aid Offer", title="Beras", target_posko=self.w.posko_a.name, donor_name="X", item_name="Beras",
                    quantity=-1, unit="karung", offer_status="available")
        self.assertTrue(self.need(quantity=3, quantity_mode="exact").name)
        self.assertTrue(self.need(quantity_mode="unknown").name)  # no number at all is fine

    def test_range_must_be_ordered(self):
        with self.assertRaises(frappe.ValidationError):
            self.need(quantity_mode="range", quantity_min=10, quantity_max=5)

    def test_stock_may_be_zero_but_not_negative(self):
        _insert("RN Stock Observation", title="Beras", posko=self.w.posko_a.name, item_name="Beras", quantity=0, unit="kg")
        with self.assertRaises(frappe.ValidationError):
            _insert("RN Stock Observation", title="Beras", posko=self.w.posko_a.name, item_name="Beras", quantity=-1, unit="kg")

    def test_legacy_row_does_not_block_an_unrelated_edit(self):
        doc = self.need(quantity=2, quantity_mode="exact")
        frappe.db.set_value("RN Logistic Need", doc.name, "quantity", 0)  # an old imported value
        doc = frappe.get_doc("RN Logistic Need", doc.name)
        doc.urgency = "urgent"
        doc.save(ignore_permissions=True)

    def flow(self):
        with as_user(self.op.user):
            flow = api.create_flow(self.w.posko_a.name, "Beras", quantity=10, unit="karung")["flow"]
            for st in ("assigned_pickup", "dispatched", "arrived_at_posko"):
                api.update_flow_status(flow, st)
        return flow

    def test_receiving_more_than_sent_is_refused(self):
        flow = self.flow()
        with as_user(self.op.user), self.assertRaises(frappe.ValidationError):
            api.receive_flow_and_update_stock(flow, 12, "karung", "lebih")
        doc = frappe.get_doc("RN Distribution Flow", flow)
        doc.received_quantity = 11
        doc.received_unit = "karung"
        with self.assertRaises(frappe.ValidationError):
            doc.save(ignore_permissions=True)

    def test_receipt_in_another_unit_or_partial_is_accepted(self):
        with as_user(self.op.user):
            api.receive_flow_and_update_stock(self.flow(), 8, "karung", "2 rusak")
        doc = frappe.get_doc("RN Distribution Flow", self.flow())
        doc.received_quantity, doc.received_unit = 250, "kg"  # weighed, not comparable to karung
        doc.save(ignore_permissions=True)
