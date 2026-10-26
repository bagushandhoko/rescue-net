"""Fixes from the owner's simulation 2026-10-26 (laporan → logistik → apotik →
2 posko distribusi → dapur & medis)."""

import frappe

from rescue_net.frontend_bridge.reports import take_community_report
from rescue_net.logistics.flows import create_flow
from rescue_net.tests.factories import (RNTestCase, _insert, as_user, make_actor, make_posko,
                                        make_transport_space, make_world)


class TestSimulationFixes(RNTestCase):
    def setUp(self):
        super().setUp()
        self.w = make_world()
        self.medis = make_posko(self.w.event, self.w.org_b, posko_type="medical")
        self.logi = make_posko(self.w.event, self.w.org_a, posko_type="logistics")
        self.op = make_actor(posko=self.logi)

    def test_another_posko_takes_over_a_report(self):
        rep = _insert("RN Community Report", title="Butuh obat", disaster_event=self.w.event.name,
                      posko=self.medis.name, status="submitted")
        with as_user(self.op.user):
            r = take_community_report(rep.name, self.logi.name, note="Kami punya stok obat")
        self.assertEqual(r["posko"], self.logi.name)
        self.assertEqual(frappe.db.get_value("RN Community Report", rep.name, "posko"), self.logi.name)
        self.assertTrue(frappe.db.exists("RN Community Report Update", {"report": rep.name}))
        with as_user(make_actor().user), self.assertRaises(frappe.PermissionError):
            take_community_report(rep.name, self.logi.name)

    def test_stock_card_shows_what_is_left_after_sending(self):
        from rescue_net.control_centre.posko import _stock_cards
        _insert("RN Stock Observation", title="Beras", posko=self.logi.name, item_name="Beras", quantity=100,
                unit="kg", quantity_mode="exact", observed_at="2026-10-01 08:00:00")
        with as_user(self.op.user):
            create_flow(destination_posko=self.medis.name, item_text="Beras", quantity=30, unit="kg",
                        quantity_mode="exact", source_posko=self.logi.name)
        card = next(c for c in _stock_cards(self.logi.name) if c["item"] == "Beras")
        self.assertEqual(card["stok_ada"], 70)
        self.assertEqual(card["stok_tercatat"], 100)

    def test_open_armada_confirms_a_shipment_from_another_org(self):
        tp = make_posko(self.w.event, self.w.org_b, posko_type="transport")
        ship = make_transport_space(tp, disaster_event=self.w.event.name)
        frappe.db.set_value("RN Transport Space", ship.name, "booking_policy", "open")
        _insert("RN Stock Observation", title="Air", posko=self.logi.name, item_name="Air", quantity=50,
                unit="dus", quantity_mode="exact", observed_at="2026-10-01 08:00:00")
        with as_user(self.op.user):
            r = create_flow(destination_posko=self.medis.name, item_text="Air", quantity=5, unit="dus",
                            quantity_mode="exact", source_posko=self.logi.name, transport_space=ship.name, weight_kg=50)
        self.assertEqual(r["booking_status"], "confirmed")


class TestDisaggregatedData(RNTestCase):
    def test_intake_finds_groups_and_submit_caps_them(self):
        from rescue_net.services.report_intake import rules_extract as extract_rules
        f = extract_rules("Ada 120 jiwa mengungsi, 30 anak, 10 lansia, 5 ibu hamil, 60 perempuan dan 4 penyandang disabilitas.")
        self.assertEqual((f["affected_people_count"], f["children_count"], f["elderly_count"], f["pregnant_count"],
                          f["female_count"], f["disability_count"]), (120, 30, 10, 5, 60, 4))

    def test_group_larger_than_total_refused(self):
        from rescue_net.frontend_bridge.reports import _set_groups
        w = make_world()
        rep = _insert("RN Community Report", title="x", disaster_event=w.event.name, status="submitted")
        with self.assertRaisesRegex(frappe.ValidationError, "melebihi"):
            _set_groups({"name": rep.name}, 10, children_count=11)
        out = {"name": rep.name}
        _set_groups(out, 10, children_count=4, female_count=6)
        self.assertEqual(frappe.db.get_value("RN Community Report", rep.name, "children_count"), 4)


class TestPlaceMemberOnPosko(RNTestCase):
    def test_org_owner_places_and_removes_an_approved_member(self):
        from rescue_net.access_policy import can_manage_posko, rn_actor
        from rescue_net.api_community_cluster import assign_member_to_posko
        w = make_world()
        owner = make_actor(org=w.org_a, org_role="owner")
        member = make_actor(org=w.org_a)
        outsider = make_actor(org=w.org_b)
        with as_user(owner.user):
            assign_member_to_posko(w.posko_a.name, member.account)
            with self.assertRaisesRegex(frappe.ValidationError, "belum menjadi anggota"):
                assign_member_to_posko(w.posko_a.name, outsider.account)
        with as_user(member.user):
            self.assertTrue(can_manage_posko(rn_actor(), w.posko_a.name))
        with as_user(outsider.user), self.assertRaises(frappe.PermissionError):
            assign_member_to_posko(w.posko_a.name, outsider.account)
        with as_user(owner.user):
            assign_member_to_posko(w.posko_a.name, member.account, remove=1)
        with as_user(member.user):
            self.assertFalse(can_manage_posko(rn_actor(), w.posko_a.name))


class TestCommandAccountRequestNeedsPosko(RNTestCase):
    def test_request_without_posko_refused_up_front(self):
        from rescue_net.api_command import request_command_account
        from rescue_net.tests.factories import make_org
        w = make_world()
        frappe.db.set_value("RN Organization", w.org_a.name, "coordination_scheme", "terpusat")
        member = make_actor(org=w.org_a)
        with as_user(member.user):
            with self.assertRaisesRegex(frappe.ValidationError, "Pilih posko"):
                request_command_account(w.org_a.name, "Serda Uji", "serda-uji@example.org")
            r = request_command_account(w.org_a.name, "Serda Uji", "serda-uji@example.org", posko=w.posko_a.name)
        self.assertTrue(r.get("pending"))
