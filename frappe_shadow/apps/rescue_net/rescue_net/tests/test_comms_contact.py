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
        self.assertEqual(row["frequencies"][0]["channel"], "146.020 MHz / CH 01")

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
