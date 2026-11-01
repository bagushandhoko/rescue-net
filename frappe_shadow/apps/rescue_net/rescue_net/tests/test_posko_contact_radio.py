"""Contact bar radio (owner 2026-11-01): frequency / channel / call sign public, phones login-only."""

import frappe

from rescue_net.control_centre.posko import posko_contact
from rescue_net.tests.factories import RNTestCase, _insert, as_guest, as_user, make_actor, make_world


class TestPoskoContactRadio(RNTestCase):
    def test_radio_public_phone_login_only(self):
        w = make_world()
        frappe.db.set_value("RN Posko", w.posko_a.name, "officer_in_charge_phone", "0812-5555-0001")
        _insert("RN Comms Device", posko=w.posko_a.name, device_name="HT Posko", category="ht", status="active",
                frequency_channel="146.020 MHz / CH 01", contact_id="YB0XYZ")
        _insert("RN Comms Device", posko=w.posko_a.name, device_name="HT rusak", category="ht", status="inactive",
                frequency_channel="147.500 MHz")
        with as_guest():
            g = posko_contact(w.posko_a.name)
        self.assertEqual(len(g["radio"]), 1)
        self.assertEqual((g["radio"][0]["frequency"], g["radio"][0]["channel"], g["radio"][0]["call_sign"]),
                         ("146.020 MHz", "CH 01", "YB0XYZ"))
        self.assertNotIn("0812-5555-0001", frappe.as_json(g))
        with as_user(make_actor().user):
            u = posko_contact(w.posko_a.name)
        self.assertEqual(u["contact"]["phone"], "0812-5555-0001")
        self.assertEqual(len(u["radio"]), 1)
