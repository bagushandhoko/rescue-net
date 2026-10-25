"""Dapur Umum: pengelola organisasi boleh mengelola dapur organisasinya, sama
seperti logistik/shelter (E2E 2026-10-25); orang luar tetap ditolak."""

import frappe

from rescue_net import api_kitchen
from rescue_net.tests.factories import RNTestCase, _insert, as_user, make_actor, make_event, make_org, make_posko


class TestKitchenAccess(RNTestCase):
    def setUp(self):
        super().setUp()
        self.ev = make_event()
        self.org = make_org()
        self.kitchen = make_posko(self.ev, self.org, posko_type="kitchen")
        _insert("RN Stock Observation", title="Beras dapur", posko=self.kitchen.name, item_name="Beras",
                quantity=50, unit="kg", stock_state="available")
        self.ing = [{"item_name": "Beras", "quantity": 5, "unit": "kg"}]

    def test_org_owner_records_production(self):
        owner = make_actor(org=self.org, org_role="owner")
        with as_user(owner.user):
            r = api_kitchen.create_production(self.kitchen.name, "Nasi bungkus", 40, self.ing, disaster_event=self.ev.name)
        self.assertTrue(r)

    def test_outsider_refused(self):
        outsider = make_actor(org=make_org())
        with as_user(outsider.user), self.assertRaises(frappe.PermissionError):
            api_kitchen.create_production(self.kitchen.name, "Nasi", 10, self.ing, disaster_event=self.ev.name)
