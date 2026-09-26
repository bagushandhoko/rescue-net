"""Shelter rules hold on every save, not only in api_shelter (phase 2: S-2, S-3, S-5, S-6)."""

import frappe
from frappe.utils import now_datetime

from rescue_net import api_shelter as api
from rescue_net.tests.factories import RNTestCase, _insert, as_user, make_actor, make_posko, make_world


class TestShelterRules(RNTestCase):
    def setUp(self):
        super().setUp()
        self.w = make_world()
        self.shelter = make_posko(self.w.event, self.w.org_a, posko_type="shelter")
        self.op = make_actor(posko=self.shelter)

    def household(self, **fields):
        return _insert("RN Shelter Household", posko=self.shelter.name, household_code="KK-UJI",
                       members_count=3, household_status="checked_in", check_in_at=now_datetime(), **fields)

    def need(self, **fields):
        return _insert("RN Shelter Need", posko=self.shelter.name, item_name="Selimut",
                       quantity_mode="unknown", need_status="open", **fields)

    def occupancy(self, **fields):
        return _insert("RN Shelter Occupancy", posko=self.shelter.name, shelter_name="Aula Uji", **fields)

    # S-5 household
    def test_household_moved_is_final_on_direct_save(self):
        doc = self.household()
        doc.household_status = "moved"
        doc.destination = "Shelter lain"
        doc.save(ignore_permissions=True)
        doc.household_status = "checked_in"
        with self.assertRaises(frappe.ValidationError):
            doc.save(ignore_permissions=True)

    def test_household_move_needs_destination_on_direct_save(self):
        doc = self.household()
        doc.household_status = "moved"
        with self.assertRaises(frappe.ValidationError):
            doc.save(ignore_permissions=True)

    def test_household_starts_checked_in(self):
        with self.assertRaises(frappe.ValidationError):
            _insert("RN Shelter Household", posko=self.shelter.name, household_code="KK-X",
                    members_count=1, household_status="moved", destination="x")

    def test_household_api_still_follows_graph(self):
        hh = self.household().name
        with as_user(self.op.user):
            api.update_household_status(hh, "checked_out")
            with self.assertRaises(frappe.ValidationError):
                api.update_household_status(hh, "moved", destination="x")
        self.assertEqual(frappe.db.get_value("RN Shelter Household", hh, "household_status"), "checked_out")

    # S-6 need
    def test_need_met_is_final_on_direct_save(self):
        doc = self.need()
        doc.need_status = "met"
        doc.save(ignore_permissions=True)
        doc.need_status = "open"
        with self.assertRaises(frappe.ValidationError):
            doc.save(ignore_permissions=True)

    def test_need_starts_open(self):
        with self.assertRaises(frappe.ValidationError):
            _insert("RN Shelter Need", posko=self.shelter.name, item_name="X",
                    quantity_mode="unknown", need_status="met")

    # S-3 functional <= total
    def test_functional_toilets_never_exceed_total(self):
        with self.assertRaises(frappe.ValidationError):
            self.occupancy(toilet_total=2, toilet_functional=3)
        with self.assertRaises(frappe.ValidationError):
            self.occupancy(water_point_total=0, water_point_functional=1)
        doc = self.occupancy(toilet_total=4, toilet_functional=4)
        doc.toilet_functional = 5
        with self.assertRaises(frappe.ValidationError):
            doc.save(ignore_permissions=True)

    # S-2 over capacity: accepted and flagged
    def test_over_capacity_is_accepted_and_flagged(self):
        doc = self.occupancy(capacity_total=50, current_occupancy=60)
        self.assertEqual(doc.over_capacity, 1)
        doc.current_occupancy = 40
        doc.save(ignore_permissions=True)
        self.assertEqual(doc.over_capacity, 0)
        self.assertEqual(self.occupancy(capacity_total=0, current_occupancy=10).over_capacity, 0)
        with as_user(self.op.user):
            out = api.create_occupancy(self.shelter.name, "Aula API", capacity_total=10, current_occupancy=12)
        self.assertTrue(out["over_capacity"])
