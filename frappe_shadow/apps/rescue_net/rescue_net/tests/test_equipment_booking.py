"""Booking angkutan alat berat mob/demob (owner 2026-11-14)."""

import frappe

from rescue_net import api_equipment_booking as eb
from rescue_net.tests.factories import RNTestCase, _insert, as_guest, as_user, make_actor, make_world


class TestEquipmentBooking(RNTestCase):
    def setUp(self):
        super().setUp()
        self.w = make_world()
        self.pemilik = make_actor()
        self.tool = _insert("RN Resource Profile", resource_name="Ekskavator uji", resource_type="equipment",
                            category="alat_berat", owner_type="individual", owner_id=self.pemilik.account,
                            disaster_event=self.w.event.name, quantity=1, availability_status="available")
        self.tool2 = _insert("RN Resource Profile", resource_name="Bulldozer uji", resource_type="equipment",
                             category="alat_berat", owner_type="individual", owner_id=self.pemilik.account,
                             disaster_event=self.w.event.name, quantity=1, availability_status="available")
        self.armada = _insert("RN Transport Space", title="Lowbed uji", provider_name="Lowbed uji",
                              disaster_event=self.w.event.name, coordination_posko=self.w.posko_a.name,
                              transport_type="darat", transport_status="available", capacity_weight_kg=20000,
                              carries_heavy_equipment=1, heavy_max_ton=20, heavy_deck_type="lowbed", heavy_trip="mob_demob")
        self.armada_mob = _insert("RN Transport Space", title="Tongkang mob saja", provider_name="Tongkang",
                                  disaster_event=self.w.event.name, coordination_posko=self.w.posko_a.name,
                                  transport_type="laut", transport_status="available", capacity_weight_kg=50000,
                                  carries_heavy_equipment=1, heavy_max_ton=50, heavy_trip="mob")
        self.pengelola = make_actor(posko=self.w.posko_a)

    def test_owner_books_and_armada_owner_decides(self):
        with as_user(self.pemilik.user):
            r = eb.book(self.tool.name, self.armada.name, "mob", weight_ton=15, destination="Lokasi kerja A")
        self.assertEqual(r["status"], "requested")
        with as_user(self.pengelola.user):
            inc = eb.incoming()
            self.assertTrue(inc["can_manage"])
            self.assertIn(r["booking"], [b["name"] for b in inc["bookings"]])
            eb.decide(r["booking"], "confirm")
        with as_user(self.pemilik.user):
            mine = eb.my_bookings()["bookings"]
            self.assertEqual([b["status"] for b in mine if b["name"] == r["booking"]], ["confirmed"])
            with self.assertRaisesRegex(frappe.ValidationError, "sisa"):
                eb.book(self.tool2.name, self.armada.name, "mob", weight_ton=10)   # sisa 5 ton
            r2 = eb.book(self.tool2.name, self.armada.name, "demob", weight_ton=10)  # arah lain: muatan sendiri
            self.assertEqual(r2["status"], "requested")

    def test_rules(self):
        with as_user(make_actor().user):
            with self.assertRaises(frappe.PermissionError):
                eb.book(self.tool.name, self.armada.name, "mob", weight_ton=5)
        with as_user(self.pemilik.user):
            with self.assertRaisesRegex(frappe.ValidationError, "tidak melayani"):
                eb.book(self.tool.name, self.armada_mob.name, "demob", weight_ton=5)
            with self.assertRaisesRegex(frappe.ValidationError, "berat"):
                eb.book(self.tool.name, self.armada.name, "mob", weight_ton=0)
            r = eb.book(self.tool.name, self.armada.name, "mob", weight_ton=5)
            with self.assertRaisesRegex(frappe.ValidationError, "aktif"):
                eb.book(self.tool.name, self.armada.name, "mob", weight_ton=5)
        with as_user(make_actor().user):
            with self.assertRaises(frappe.PermissionError):
                eb.decide(r["booking"], "confirm")
        with as_user(self.pemilik.user):
            self.assertEqual(eb.cancel(r["booking"])["status"], "cancelled")

    def test_public_list_has_no_contacts(self):
        with as_guest():
            out = eb.heavy_armada(self.w.event.name)
        ids = [a["id"] for a in out["armada"]]
        self.assertIn(self.armada.name, ids)
        self.assertNotIn("phone", frappe.as_json(out).lower())
        with as_guest():
            only_demob = eb.heavy_armada(self.w.event.name, trip="demob")
        self.assertNotIn(self.armada_mob.name, [a["id"] for a in only_demob["armada"]])
