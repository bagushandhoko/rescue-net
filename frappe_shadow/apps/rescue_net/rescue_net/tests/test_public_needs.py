"""Public needs board: derived gap, 'jangan kirim', public-only, no leaks."""

import json

import frappe

from rescue_net import api_public_needs as pn
from rescue_net.tests.factories import RNTestCase, _insert, as_guest, make_event, make_posko


class TestPublicNeeds(RNTestCase):
    def setUp(self):
        super().setUp()
        self.ev = make_event()
        self.pub = make_posko(self.ev, public_detail="public", city_name="Kota Uji")
        self.priv = make_posko(self.ev, public_detail="private")

    def need(self, posko, item, qty, unit="karung", **kw):
        status = kw.pop("need_status", "open")
        doc = _insert("RN Logistic Need", title=item, posko=posko.name, disaster_event=self.ev.name,
                      item_name=item, quantity=qty, unit=unit, **kw)
        if status != "open":
            frappe.db.set_value("RN Logistic Need", doc.name, "need_status", status)
        return doc

    def board(self):
        with as_guest():
            return pn.board(event=self.ev.name)

    def test_gap_is_need_minus_stock_minus_incoming(self):
        self.need(self.pub, "Beras", 100)
        _insert("RN Stock Observation", title="s", posko=self.pub.name, disaster_event=self.ev.name,
                item_name="Beras", quantity=30, unit="karung", stock_state="available")
        _insert("RN Distribution Flow", title="f", destination_posko=self.pub.name, disaster_event=self.ev.name,
                item_name="Beras", quantity=20, unit="karung", flow_status="planned")
        row = self.board()["needs"][0]
        self.assertEqual(row["gap"], 50)

    def test_covered_item_goes_to_enough_list(self):
        self.need(self.pub, "Air mineral", 10, unit="dus")
        _insert("RN Stock Observation", title="s", posko=self.pub.name, disaster_event=self.ev.name,
                item_name="Air mineral", quantity=15, unit="dus", stock_state="available")
        b = self.board()
        self.assertEqual(b["needs"], [])
        self.assertIn("Air", b["enough"][0]["item"])

    def test_closed_needs_and_private_poskos_are_hidden(self):
        self.need(self.pub, "Selimut", 5, need_status="fulfilled")
        self.need(self.priv, "RAHASIA-ITEM", 5)
        b = self.board()
        self.assertNotIn("RAHASIA-ITEM", json.dumps(b))
        self.assertEqual(b["needs"] + b["enough"], [])

    def test_no_contact_or_reporter_fields(self):
        self.need(self.pub, "Beras", 10, reporter_label="PELAPOR-SENTINEL")
        self.assertNotIn("PELAPOR-SENTINEL", json.dumps(self.board()))
