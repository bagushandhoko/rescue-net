"""Volunteer assignments and profiles are changed by the volunteer or a manager of that posko (phase 2: V-4)."""

import frappe

from rescue_net import api_volunteer as api
from rescue_net.tests.factories import RNTestCase, as_user, make_actor, make_event, make_posko, make_world


class TestVolunteerRights(RNTestCase):
    def setUp(self):
        super().setUp()
        self.w = make_world()
        self.op_a = make_actor(posko=self.w.posko_a)
        self.op_b = make_actor(posko=self.w.posko_b)  # global operator, other posko
        self.volunteer = make_actor(role="viewer")
        with as_user(self.volunteer.user):
            self.profile = api.create_profile("Relawan Uji", "logistik")["volunteer"]
        with as_user(self.op_a.user):
            self.assignment = api.create_assignment(self.profile, self.w.posko_a.name, "Bongkar muat")["assignment"]

    def status(self):
        return frappe.db.get_value("RN Volunteer Assignment", self.assignment, "assignment_status")

    def test_operator_of_another_posko_cannot_touch_the_assignment(self):
        for new_status in ("accepted", "cancelled"):
            with as_user(self.op_b.user), self.assertRaises(frappe.PermissionError):
                api.update_assignment_status(self.assignment, new_status)
        self.assertEqual(self.status(), "planned")

    def test_volunteer_and_own_posko_move_it_forward(self):
        with as_user(self.volunteer.user):
            api.update_assignment_status(self.assignment, "accepted")
        with as_user(self.op_a.user):
            api.update_assignment_status(self.assignment, "checked_in")
        self.assertEqual(self.status(), "checked_in")

    def test_profile_edits_need_a_posko_relation(self):
        with as_user(self.op_b.user), self.assertRaises(frappe.PermissionError):
            api.update_profile(self.profile, notes="diubah")
        with as_user(self.op_a.user):
            api.update_profile(self.profile, notes="diubah")
        with as_user(self.volunteer.user):
            api.update_profile(self.profile, notes="saya")

    def test_pool_volunteer_is_managed_by_poskos_of_the_same_event(self):
        pool = api.register_volunteer("Pendaftar Uji", "081200000000",
                                      disaster_event=self.w.event.name, main_skill="dapur")["volunteer"]
        with as_user(self.op_a.user):
            api.set_availability(pool, "limited")
        elsewhere = make_actor(posko=make_posko(make_event()))
        with as_user(elsewhere.user), self.assertRaises(frappe.PermissionError):
            api.set_availability(pool, "unavailable")

    def test_skipping_steps_is_refused_on_a_direct_save(self):
        doc = frappe.get_doc("RN Volunteer Assignment", self.assignment)
        doc.assignment_status = "completed"
        with self.assertRaises(frappe.ValidationError):
            doc.save(ignore_permissions=True)

    # V-2: one active assignment per volunteer, also on a direct insert
    def test_second_active_assignment_is_refused_on_a_direct_insert(self):
        doc = frappe.get_doc({
            "doctype": "RN Volunteer Assignment", "volunteer": self.profile, "posko": self.w.posko_b.name,
            "task_title": "Dapur", "assignment_status": "planned",
        })
        with self.assertRaises(frappe.ValidationError):
            doc.insert(ignore_permissions=True)
        with as_user(self.op_b.user), self.assertRaises(frappe.ValidationError):
            api.create_assignment(self.profile, self.w.posko_b.name, "Dapur")

    def test_new_assignment_after_the_old_one_ends(self):
        with as_user(self.op_a.user):
            api.update_assignment_status(self.assignment, "cancelled")
        with as_user(self.op_b.user):
            api.create_assignment(self.profile, self.w.posko_b.name, "Dapur")
