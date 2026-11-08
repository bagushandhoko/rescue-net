"""Jaringan komunikasi (owner 2026-11-01): coverage / power on devices, posko comms support offered vs
needed (managers only), communication posko type, volunteer comms nodes (name/call sign/phone login-only),
device edits limited to posko managers / owners."""

import frappe

from rescue_net import api_comms as ac
from rescue_net.tests.factories import (RNTestCase, _insert, as_guest, as_user, make_actor, make_event, make_posko,
                                        make_world)


class TestCommsNetwork(RNTestCase):
    def setUp(self):
        super().setUp()
        self.w = make_world()
        self.mgr = make_actor(posko=self.w.posko_a)
        self.other = make_actor(posko=self.w.posko_b)

    def _board(self, user=None):
        if user:
            with as_user(user):
                return ac.comms_board(self.w.event.name)
        with as_guest():
            return ac.comms_board(self.w.event.name)

    def test_device_coverage_and_power(self):
        with as_user(self.mgr.user):
            d = ac.create_comms_device("Repeater Bukit", "repeater", disaster_event=self.w.event.name,
                                       posko=self.w.posko_a.name, frequency_mhz="146.020", coverage_km="25",
                                       power_source="plts", power_endurance_hours="48")["comms_device"]
        row = frappe.db.get_value("RN Comms Device", d, ["coverage_km", "power_source", "power_endurance_hours"])
        self.assertEqual(row, (25.0, "plts", 48.0))
        with as_user(self.mgr.user), self.assertRaisesRegex(frappe.ValidationError, "Sumber energi"):
            ac.create_comms_device("X", "ht", disaster_event=self.w.event.name, power_source="nuklir")
        with as_user(self.mgr.user), self.assertRaisesRegex(frappe.ValidationError, "Jangkauan"):
            ac.create_comms_device("X", "ht", disaster_event=self.w.event.name, coverage_km="-3")
        with as_user(self.mgr.user), self.assertRaisesRegex(frappe.ValidationError, "pemilik"):
            ac.create_comms_device("X", "ht", disaster_event=self.w.event.name, owner_type="relawan")

    def test_device_edit_only_by_manager(self):
        d = _insert("RN Comms Device", disaster_event=self.w.event.name, posko=self.w.posko_a.name,
                    device_name="HT A", category="ht", status="active").name
        with as_user(self.other.user), self.assertRaises(frappe.PermissionError):
            ac.update_comms_device(d, status="inactive")
        with as_user(self.mgr.user):
            ac.update_comms_device(d, status="spare", coverage_km="5", power_source="baterai")
        self.assertEqual(frappe.db.get_value("RN Comms Device", d, ["status", "power_source"]), ("spare", "baterai"))
        with as_user(self.other.user), self.assertRaises(frappe.PermissionError):
            ac.set_posko_comms_status(self.w.posko_a.name, "weak")

    def test_support_offered_needed_and_comms_posko(self):
        with as_user(self.other.user), self.assertRaises(frappe.PermissionError):
            ac.set_posko_comms_support(self.w.posko_a.name, offered="HT")
        comms = make_posko(self.w.event, self.w.org_a, posko_type="communication")
        mgr_c = make_actor(posko=comms)
        _insert("RN Comms Device", disaster_event=self.w.event.name, posko=comms.name, device_name="Rig HF",
                category="repeater", status="active", frequency_mhz="7.120", coverage_km=300, power_source="genset",
                power_endurance_hours=72)
        with as_user(mgr_c.user):
            ac.set_posko_comms_support(comms.name, offered="Relay HF 24 jam, 5 HT pinjaman")
        with as_user(self.mgr.user):
            r = ac.set_posko_comms_support(self.w.posko_a.name, needed="Repeater dan aki cadangan")
        self.assertEqual(r["needed"], "Repeater dan aki cadangan")

        j = self._board()["jaringan"]
        kom = [p for p in j["posko_komunikasi"] if p["posko"] == comms.name]
        self.assertEqual(len(kom), 1)
        self.assertEqual(kom[0]["max_coverage_km"], 300.0)
        self.assertIn("Genset", kom[0]["power"][0])
        self.assertIn(comms.name, [p["posko"] for p in j["menyediakan"]])
        butuh = [p for p in j["butuh"] if p["posko"] == self.w.posko_a.name]
        self.assertEqual(butuh[0]["reason"], "Repeater dan aki cadangan")
        # clearing works
        with as_user(self.mgr.user):
            ac.set_posko_comms_support(self.w.posko_a.name, needed="")
        self.assertNotIn(self.w.posko_a.name, [p["posko"] for p in self._board()["jaringan"]["butuh"]])

    def test_volunteer_node_privacy_and_scope(self):
        rel = make_actor(role="relawan")
        with as_user(rel.user):
            with self.assertRaisesRegex(frappe.ValidationError, "Lokasi"):
                ac.offer_comms_node(frequency_mhz="145.700")
            with self.assertRaisesRegex(frappe.ValidationError, "cara dihubungi"):
                ac.offer_comms_node(current_location="Kec. Uji")
            node = ac.offer_comms_node(current_location="Kec. Uji", frequency_mhz="145.700", contact_id="YB1TES",
                                       contact_phone="0813-1111-2222", disaster_event=self.w.event.name,
                                       coverage_km="20", power_source="aki", power_endurance_hours="10")["comms_device"]
            standby = ac.offer_comms_node(current_location="Kota Lain", frequency_channel="CH 05")["comms_device"]
        self.assertFalse(frappe.db.get_value("RN Comms Device", standby, "disaster_event"))

        g = self._board()
        names = [n["name"] for n in g["jaringan"]["node_relawan"]]
        self.assertIn(node, names)
        self.assertIn(standby, names)  # standby nodes can be called into any disaster
        blob = frappe.as_json(g)
        self.assertNotIn("0813-1111-2222", blob)
        self.assertNotIn("YB1TES", blob)
        # nodes are not posko inventory
        self.assertEqual(g["inventory_total"]["total"], 0)

        u = self._board(make_actor().user)
        n = [x for x in u["jaringan"]["node_relawan"] if x["name"] == node][0]
        self.assertEqual((n["call_sign"], n["phone"]), ("YB1TES", "0813-1111-2222"))
        self.assertEqual(n["frequency"], "145.700 MHz")

        # a node for another disaster is not listed here
        other_ev = make_event(event_status="active")
        with as_user(rel.user):
            elsewhere = ac.offer_comms_node(current_location="Jauh", contact_id="YB1TES",
                                            disaster_event=other_ev.name)["comms_device"]
        self.assertNotIn(elsewhere, [x["name"] for x in self._board()["jaringan"]["node_relawan"]])

    def test_node_owner_only_edit_and_withdraw(self):
        rel = make_actor(role="relawan")
        with as_user(rel.user):
            node = ac.offer_comms_node(current_location="Kec. Uji", contact_id="YB1AAA")["comms_device"]
        with as_user(make_actor(role="relawan").user):
            with self.assertRaises(frappe.PermissionError):
                ac.offer_comms_node(current_location="Ganti", contact_id="X", comms_device=node)
            with self.assertRaises(frappe.PermissionError):
                ac.withdraw_comms_node(node)
            with self.assertRaises(frappe.PermissionError):
                ac.update_comms_device(node, status="inactive")
        with as_user(rel.user):
            ac.offer_comms_node(current_location="Kec. Baru", contact_id="YB1AAA", comms_device=node)
            self.assertEqual(ac.my_comms_nodes()["nodes"][0]["location"], "Kec. Baru")
            ac.withdraw_comms_node(node)
            self.assertEqual(ac.my_comms_nodes()["nodes"], [])

    def test_node_limit_and_hidden_event(self):
        rel = make_actor(role="relawan")
        proposed = make_event(event_status="proposed")
        with as_user(rel.user):
            with self.assertRaisesRegex(frappe.ValidationError, "belum aktif"):
                ac.offer_comms_node(current_location="Kec. Uji", contact_id="A", disaster_event=proposed.name)
            for i in range(ac.MAX_NODES_PER_ACCOUNT):
                ac.offer_comms_node(current_location="Lokasi %d" % i, contact_id="A")
            with self.assertRaisesRegex(frappe.ValidationError, "Maksimal"):
                ac.offer_comms_node(current_location="Lagi", contact_id="A")

    def test_posko_device_still_needs_disaster(self):
        with self.assertRaisesRegex(frappe.ValidationError, "Disaster event"):
            _insert("RN Comms Device", posko=self.w.posko_a.name, device_name="HT", category="ht", owner_type="posko")


class TestCommsFrequencyPermission(RNTestCase):
    """owner 2026-11-09: frekuensi hanya dicatat petugas posko / pengelola organisasi / Control Centre."""

    def setUp(self):
        super().setUp()
        self.w = make_world()
        self.mgr = make_actor(posko=self.w.posko_a)
        self.plain = make_actor()

    def test_plain_user_refused_manager_allowed(self):
        with as_user(self.plain.user), self.assertRaises(frappe.PermissionError):
            ac.create_comms_frequency("Rig 2m", "vhf", disaster_event=self.w.event.name)
        with as_user(self.mgr.user):
            out = ac.create_comms_frequency("Rig 2m", "vhf", disaster_event=self.w.event.name,
                                            frequency_value="146.020")
        self.assertTrue(frappe.db.exists("RN Comms Frequency", {"band_label": "Rig 2m"}))
        with as_guest(), self.assertRaisesRegex(frappe.ValidationError, "Login"):
            ac.create_comms_frequency("X", "vhf", disaster_event=self.w.event.name)
