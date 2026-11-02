"""Cari Armada (owner 2026-11-02): public list of armada serving a disaster — available / full / in use, time
filter, nearest first, no phone numbers; booking link needs login."""

import frappe

from rescue_net import api_armada as af
from rescue_net.tests.factories import RNTestCase, _insert, as_guest, as_user, make_actor, make_world


class TestArmadaFinder(RNTestCase):
    def setUp(self):
        super().setUp()
        self.w = make_world()
        frappe.db.set_value("RN Posko", self.w.posko_a.name, {"latitude": 4.14, "longitude": 96.13})
        frappe.db.set_value("RN Posko", self.w.posko_b.name, {"latitude": -6.2, "longitude": 106.8})

        def armada(title, posko, **kw):
            return _insert("RN Transport Space", title=title, provider_name=title, disaster_event=self.w.event.name,
                           coordination_posko=posko.name, transport_type=kw.pop("transport_type", "darat"),
                           capacity_weight_kg=kw.pop("capacity_weight_kg", 1000), handover_contact_phone="0812-9999-0000",
                           **kw)
        self.free = armada("Truk Meulaboh", self.w.posko_a, transport_status="available", departure_at="2099-11-10 08:00:00")
        self.past = armada("Truk Lama", self.w.posko_a, transport_status="available", departure_at="2020-01-01 08:00:00")
        self.full = armada("Pickup Penuh", self.w.posko_a, transport_status="available", capacity_committed_kg=1000)
        self.busy = armada("Kapal Jakarta", self.w.posko_b, transport_type="laut", transport_status="in_transit",
                           departure_at="2099-11-20 08:00:00")
        self.done = armada("Selesai", self.w.posko_b, transport_status="completed")

    def _find(self, **kw):
        with as_guest():
            return af.armada_finder(self.w.event.name, **kw)

    def test_status_and_privacy(self):
        r = self._find()
        st = {x["title"]: x["status"] for x in r["rows"]}
        self.assertEqual(st, {"Truk Meulaboh": "tersedia", "Pickup Penuh": "penuh", "Kapal Jakarta": "dipakai",
                              "Truk Lama": "lewat"})
        self.assertEqual(r["counts"], {"tersedia": 1, "penuh": 1, "dipakai": 1, "lewat": 1})
        self.assertEqual(r["rows"][-1]["title"], "Truk Lama")
        self.assertFalse(r["logged_in"])
        self.assertNotIn("0812-9999-0000", frappe.as_json(r))

    def test_filters_and_nearest(self):
        self.assertEqual([x["title"] for x in self._find(transport_type="laut")["rows"]], ["Kapal Jakarta"])
        names = [x["title"] for x in self._find(date_from="2099-11-15")["rows"]]
        self.assertNotIn("Truk Meulaboh", names)           # leaves before the range
        self.assertIn("Pickup Penuh", names)               # no fixed schedule: stays visible
        self.assertEqual([x["title"] for x in self._find(status="tersedia")["rows"]], ["Truk Meulaboh"])
        rows = self._find(lat=-6.21, lng=106.81)["rows"]
        kapal = [x for x in rows if x["title"] == "Kapal Jakarta"][0]
        self.assertLess(kapal["km"], 5)

    def test_logged_in_flag(self):
        with as_user(make_actor().user):
            self.assertTrue(af.armada_finder(self.w.event.name)["logged_in"])


class TestArmadaPosition(RNTestCase):
    """Owner 2026-11-02: the posko that runs an armada shares its GPS position; the public sees position + trail."""

    def setUp(self):
        super().setUp()
        self.w = make_world()
        self.mgr = make_actor(posko=self.w.posko_a)
        self.space = _insert("RN Transport Space", title="Truk GPS", provider_name="Truk GPS", disaster_event=self.w.event.name,
                             coordination_posko=self.w.posko_a.name, transport_type="darat", capacity_weight_kg=1000,
                             transport_status="in_transit")

    def test_only_operator_updates_and_public_sees_trail(self):
        with as_user(make_actor(posko=self.w.posko_b).user), self.assertRaises(frappe.PermissionError):
            af.update_armada_position(self.space.name, 4.14, 96.13)
        # a plain member of the same organisation (sibling posko) may not move this posko's armada
        from rescue_net.tests.factories import make_posko
        sibling = make_posko(self.w.event, self.w.org_a)
        with as_user(make_actor(org=self.w.org_a, posko=sibling).user), self.assertRaises(frappe.PermissionError):
            af.update_armada_position(self.space.name, 4.14, 96.13)
        with as_guest(), self.assertRaises(frappe.PermissionError):
            af.update_armada_position(self.space.name, 4.14, 96.13)
        with as_user(self.mgr.user):
            with self.assertRaisesRegex(frappe.ValidationError, "Koordinat"):
                af.update_armada_position(self.space.name, 120, 96.13)
            self.assertFalse(af.update_armada_position(self.space.name, 4.1400, 96.1300)["skipped"])
            self.assertTrue(af.update_armada_position(self.space.name, 4.14001, 96.13001)["skipped"])   # < 15 m, < 20 s
            self.assertFalse(af.update_armada_position(self.space.name, 4.1600, 96.1500)["skipped"])     # moved ~3 km
        with as_guest():
            trail = af.armada_trail(self.space.name)["points"]
            rows = af.armada_finder(self.w.event.name)["rows"]
        self.assertEqual([p[:2] for p in trail], [[4.14, 96.13], [4.16, 96.15]])
        row = [r for r in rows if r["name"] == self.space.name][0]
        self.assertTrue(row["pos_live"])
        self.assertEqual(row["pos"], [4.16, 96.15])
        self.assertEqual(row["status"], "dipakai")
