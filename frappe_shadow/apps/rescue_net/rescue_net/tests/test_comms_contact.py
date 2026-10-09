"""Alat Komunikasi board: radio channels per posko + posko contact, contact only in full share mode."""

import frappe

from rescue_net import api_comms
from rescue_net.tests.factories import RNTestCase, _insert, as_guest, as_user, make_actor, make_world

PHONE = "0812-0000-7777"
EMAIL = "pic-sentinel@test.rescue-net.local"


class TestCommsContact(RNTestCase):
    def setUp(self):
        super().setUp()
        self.w = make_world()
        p = self.w.posko_a
        frappe.db.set_value("RN Posko", p.name, {
            "officer_in_charge_phone": PHONE, "officer_in_charge_email": EMAIL,
            "officer_in_charge_name": "Budi PIC"})
        _insert("RN Comms Device", device_name="HT-01", category="ht", status="active", posko=p.name,
                disaster_event=self.w.event.name, frequency_channel="146.020 MHz / CH 01")
        self.op = make_actor(posko=p)

    def row(self, data):
        return next(r for r in data["konektivitas"]["poskos"] if r["posko"] == self.w.posko_a.name)

    def test_radio_channel_listed_for_everyone(self):
        with as_guest():
            row = self.row(api_comms.comms_board(disaster_event=self.w.event.name))
        self.assertEqual(row["frequencies"][0]["frequency"], "146.020 MHz")
        self.assertEqual(row["frequencies"][0]["channel"], "CH 01")

    def test_channel_only_is_not_called_a_frequency(self):
        from rescue_net.api_comms import _split_radio
        self.assertEqual(_split_radio("CH 03"), ("", "CH 03"))
        self.assertEqual(_split_radio("-"), ("", ""))

    def test_location_and_coordinates_shown(self):
        frappe.db.set_value("RN Posko", self.w.posko_a.name, {
            "latitude": -6.2, "longitude": 106.8, "village_name": "Desa Uji", "city_name": "Kota Uji"})
        with as_guest():
            row = self.row(api_comms.comms_board(disaster_event=self.w.event.name))
        self.assertEqual((row["location"]["lat"], row["location"]["lng"]), (-6.2, 106.8))
        self.assertIn("Desa Uji", row["location"]["area"])

    def test_guest_gets_no_contact_in_summary_mode(self):
        with as_guest():
            data = api_comms.comms_board(disaster_event=self.w.event.name)
        self.assertIsNone(self.row(data)["contact"])
        blob = frappe.as_json(data)
        self.assertNotIn(PHONE, blob)
        self.assertNotIn(EMAIL, blob)

    def test_own_operator_gets_contact(self):
        with as_user(self.op.user):
            row = self.row(api_comms.comms_board(disaster_event=self.w.event.name))
        self.assertEqual(row["contact"]["phone"], PHONE)
        self.assertEqual(row["contact"]["email"], EMAIL)

    def test_methods_list_every_way_to_reach_posko(self):
        p = self.w.posko_a
        frappe.db.set_value("RN Posko", p.name, "officer_in_charge_whatsapp", "0813-1111-2222")
        _insert("RN Comms Device", device_name="Sat-1", category="telepon_satelit", status="active", posko=p.name,
                disaster_event=self.w.event.name, contact_id="+881600000001")
        _insert("RN Comms Device", device_name="Dish", category="starlink", status="active", posko=p.name,
                disaster_event=self.w.event.name)
        _insert("RN Comms Device", device_name="HT-9", category="ht", status="active", posko=p.name,
                disaster_event=self.w.event.name, frequency_mhz="430.1", frequency_channel="CH 07", contact_id="YB0ABC")
        with as_user(self.op.user):
            row = self.row(api_comms.comms_board(disaster_event=self.w.event.name))
        types = {m["type"] for m in row["methods"]}
        self.assertTrue({"telepon", "wa", "email", "radio", "sat", "net"} <= types)
        radio = [m["value"] for m in row["methods"] if m["type"] == "radio"]
        self.assertTrue(any("430.100 MHz" in v and "CH 07" in v and "YB0ABC" in v for v in radio))
        self.assertEqual(next(m for m in row["methods"] if m["type"] == "wa")["href"], "https://wa.me/6281311112222")

    def test_guest_sees_radio_but_no_phone_or_satellite_number(self):
        p = self.w.posko_a
        _insert("RN Comms Device", device_name="Sat-2", category="telepon_satelit", status="active", posko=p.name,
                disaster_event=self.w.event.name, contact_id="+881600000002")
        with as_guest():
            data = api_comms.comms_board(disaster_event=self.w.event.name)
        blob = frappe.as_json(data)
        self.assertNotIn("+881600000002", blob)
        self.assertNotIn(PHONE, blob)
        self.assertTrue(any(m["type"] == "radio" for m in self.row(data)["methods"]))

    def test_posko_without_any_gear_says_so(self):
        with as_guest():
            data = api_comms.comms_board(disaster_event=self.w.event.name)
        other = next(r for r in data["konektivitas"]["poskos"] if r["posko"] != self.w.posko_a.name)
        self.assertEqual(other["methods"][0]["type"], "kosong")

    def test_bad_frequency_refused(self):
        with as_user(self.op.user):
            with self.assertRaises(frappe.ValidationError):
                api_comms.create_comms_device("X", "ht", disaster_event=self.w.event.name, frequency_mhz="abc")
