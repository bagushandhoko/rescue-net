"""logistics_operator / distribution_operator manage volunteers at their OWN posko
(E2E 2026-10-25: "Hak operator diperlukan"); still refused at another posko."""

import frappe

from rescue_net import api_volunteer
from rescue_net.tests.factories import RNTestCase, as_guest, as_user, make_actor, make_world


class TestPoskoWorkerRoles(RNTestCase):
    def setUp(self):
        super().setUp()
        self.w = make_world()
        with as_guest():
            self.vol = api_volunteer.register_volunteer(volunteer_name="Relawan Uji", contact="0812000", main_skill="logistik",
                                                        disaster_event=self.w.event.name)["volunteer"]

    def test_logistics_operator_assigns_at_own_posko(self):
        op = make_actor(role="logistics_operator", posko=self.w.posko_a)
        with as_user(op.user):
            r = api_volunteer.create_assignment(self.vol, self.w.posko_a.name, "Bongkar muat")
        self.assertTrue(r)

    def test_refused_at_other_posko(self):
        op = make_actor(role="distribution_operator", posko=self.w.posko_a)
        with as_user(op.user), self.assertRaises(frappe.PermissionError):
            api_volunteer.create_assignment(self.vol, self.w.posko_b.name, "Bongkar muat")

    def test_assignment_gets_the_disaster_and_shows_on_the_board(self):
        op = make_actor(role="logistics_operator", posko=self.w.posko_a)
        with as_user(op.user):
            r = api_volunteer.create_assignment(self.vol, self.w.posko_a.name, "Angkut terpal")
        name = r.get("assignment") or r.get("name")
        self.assertEqual(frappe.db.get_value("RN Volunteer Assignment", name, "disaster_event"), self.w.event.name)
        with as_guest():
            board = api_volunteer.volunteer_board(self.w.event.name)
        self.assertIn("Angkut terpal", [p["task_title"] for p in board["papan_penugasan"]])
