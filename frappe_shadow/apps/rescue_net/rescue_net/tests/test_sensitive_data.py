"""Medical, victim (shelter household), phone and Search & Found data must not
be readable by a role that has no business with it — including Guest.

BUG-1..6 in the docstrings below were leaks found by this suite on
2026-09-26 and fixed the same day on the owner's go-ahead; the tests now
guard against regressions."""

import frappe
from frappe.utils import now_datetime

from rescue_net import api_medical, api_search_found, api_shelter
from rescue_net.tests.factories import (
    RNTestCase,
    _insert,
    api_call,
    as_guest,
    as_user,
    contains_value,
    make_actor,
    make_medical_case,
    make_posko,
    make_transport_space,
    make_world,
    walk,
)

PHONE = "+62811-0000-7777"
PIN = "PIN-4827"


class TestMedicalData(RNTestCase):
    def setUp(self):
        super().setUp()
        self.w = make_world()
        self.med_a = make_posko(self.w.event, self.w.org_a, posko_type="medical")
        self.case = make_medical_case(self.med_a, patient_code="PX-RAHASIA-01")
        self.medic = make_actor(role="medical_operator", posko=self.med_a)
        self.op_b = make_actor(posko=self.w.posko_b)
        self.member_a = make_actor(org=self.w.org_a, org_role="member")
        self.outsider = make_actor(role="viewer")

    def test_assigned_medic_sees_cases(self):
        with as_user(self.medic.user):
            data = api_medical.dashboard()
        self.assertIn(self.case.name, [c.name for c in data["cases"]])

    def test_unrelated_actors_see_no_cases(self):
        for actor in (self.outsider, self.op_b, self.member_a):
            with as_user(actor.user):
                data = api_medical.dashboard()
            self.assertFalse(contains_value(data, "PX-RAHASIA-01"), actor)

    def test_unrelated_actor_cannot_open_the_posko(self):
        for actor in (self.outsider, self.op_b):
            with as_user(actor.user), self.assertRaises(frappe.PermissionError):
                api_medical.dashboard(posko=self.med_a.name)

    def test_guest_cannot_call_medical_endpoints(self):
        for fn in ("dashboard", "create_case", "update_case_status", "control_centre_medical"):
            with as_guest(), self.assertRaises(frappe.PermissionError):
                api_call(f"rescue_net.api_medical.{fn}", posko=self.med_a.name)

    def test_unrelated_actor_cannot_write_cases(self):
        with as_user(self.op_b.user), self.assertRaises(frappe.PermissionError):
            api_medical.create_case(posko=self.med_a.name, patient_code="PX-2", complaint="Luka")
        with as_user(self.op_b.user), self.assertRaises(frappe.PermissionError):
            api_medical.update_case_status(self.case.name, "closed")

    def test_control_centre_medical_does_not_expose_patients(self):
        with as_user(self.outsider.user):
            try:
                data = api_medical.control_centre_medical()
            except frappe.PermissionError:
                return
        self.assertFalse(contains_value(data, "PX-RAHASIA-01"))
        self.assertFalse(any(k in ("complaint", "treatment_notes") for _p, k, _v in walk(data)))


class TestSearchFound(RNTestCase):
    def setUp(self):
        super().setUp()
        self.w = make_world()
        self.report = _insert(
            "RN Missing Person Report",
            disaster_event=self.w.event.name,
            posko=self.w.posko_a.name,
            person_code="MP-UJI-01",
            person_name="Nama Rahasia Uji",
            report_status="missing",
            observed_at=now_datetime(),
        )
        self.op_a = make_actor(posko=self.w.posko_a)
        self.op_b = make_actor(posko=self.w.posko_b)
        self.viewer = make_actor(role="viewer")

    def test_guest_dashboard_hides_identity(self):
        with as_guest():
            data = api_call("rescue_net.api_search_found.dashboard", disaster_event=self.w.event.name)
        self.assertTrue(contains_value(data, "MP-UJI-01"))          # the case itself is public
        self.assertFalse(contains_value(data, "Nama Rahasia Uji"))
        self.assertFalse(any(k == "person_name" for _p, k, _v in walk(data)))

    def test_restricted_record_needs_the_posko(self):
        with as_user(self.op_a.user):
            doc = api_search_found.restricted_record("RN Missing Person Report", self.report.name)
        self.assertTrue(contains_value(doc, "Nama Rahasia Uji"))

        with as_guest(), self.assertRaises(frappe.PermissionError):
            api_call("rescue_net.api_search_found.restricted_record",
                     doctype="RN Missing Person Report", name=self.report.name)
        for actor in (self.viewer, self.op_b):
            with as_user(actor.user), self.assertRaises(frappe.PermissionError):
                api_search_found.restricted_record("RN Missing Person Report", self.report.name)


class TestReporterContact(RNTestCase):
    """Owner rule 2026-09-26: a report not tied to a posko may be opened by any
    operator, but the reporter must be reachable to confirm it."""

    def setUp(self):
        super().setUp()
        self.w = make_world()
        self.reporter = make_actor(role="viewer")                     # account without phone
        self.with_phone = make_actor(role="viewer", phone="+62811-0000-4444")
        self.op_b = make_actor(posko=self.w.posko_b)

    def test_typed_contact_is_stored_and_shown_to_operator_only(self):
        with as_user(self.reporter.user):
            r = api_search_found.create_missing_report(
                "MP-KONTAK-1", person_name="Nama Uji", disaster_event=self.w.event.name,
                reporter_name="Ibu Uji", reporter_contact="+62811-0000-3333")
        with as_user(self.op_b.user):                                 # operator of another org
            doc = api_search_found.restricted_record("RN Missing Person Report", r["missing_report"])
        self.assertEqual(doc["reporter"]["contact"], "+62811-0000-3333")
        self.assertEqual(doc["reporter"]["name"], "Ibu Uji")
        with as_guest():
            data = api_call("rescue_net.api_search_found.dashboard", disaster_event=self.w.event.name)
        self.assertTrue(contains_value(data, "MP-KONTAK-1"))
        self.assertFalse(contains_value(data, "+62811-0000-3333"))

    def test_account_contact_is_the_fallback(self):
        with as_user(self.with_phone.user):
            r = api_search_found.create_found_report("FP-KONTAK-1", disaster_event=self.w.event.name)
        self.assertEqual(frappe.db.get_value("RN Found Person Report", r["found_report"], "reporter_contact"),
                         "+62811-0000-4444")

    def test_unreachable_reporter_is_refused(self):
        frappe.db.set_value("RN User Account", self.reporter.account, "email", None)
        with as_user(self.reporter.user), self.assertRaises(frappe.ValidationError):
            api_search_found.create_missing_report("MP-KONTAK-2", disaster_event=self.w.event.name)
        self.assertFalse(frappe.db.exists("RN Missing Person Report", {"person_code": "MP-KONTAK-2"}))


class TestShelterHouseholds(RNTestCase):
    def setUp(self):
        super().setUp()
        self.w = make_world()
        self.shelter = make_posko(self.w.event, self.w.org_a, posko_type="shelter",
                                  officer_in_charge_phone=PHONE)
        self.household = _insert(
            "RN Shelter Household",
            posko=self.shelter.name,
            household_code="KK-UJI-01",
            members_count=4,
            household_status="checked_in",
            notes="Catatan pribadi uji: ibu hamil, riwayat asma",
            destination="Rumah saudara di Jl. Uji 12",
            check_in_at=now_datetime(),
        )
        self.outsider = make_actor(role="viewer")

    def test_own_operator_still_sees_household_notes(self):
        op = make_actor(posko=self.shelter)
        with as_user(op.user):
            data = api_shelter.dashboard(posko=self.shelter.name)
        self.assertTrue(contains_value(data, "riwayat asma"))

    def test_guest_still_gets_household_counts(self):
        with as_guest():
            data = api_call("rescue_net.api_shelter.dashboard", posko=self.shelter.name)
        self.assertEqual([h["members_count"] for h in data["households"]], [4])

    def test_logged_in_outsider_is_refused(self):
        with as_user(self.outsider.user), self.assertRaises(frappe.PermissionError):
            api_shelter.dashboard(posko=self.shelter.name)

    def test_guest_does_not_get_household_notes(self):
        """BUG-3: api_shelter.dashboard(posko=X) gives Guest every household
        row of ANY shelter posko incl. free-text `notes` and `destination`
        (no public_posko_allowed / share-mode check)."""
        with as_guest():
            data = api_call("rescue_net.api_shelter.dashboard", posko=self.shelter.name)
        self.assertFalse(contains_value(data, "riwayat asma"))
        self.assertFalse(contains_value(data, "Jl. Uji 12"))

    def test_guest_does_not_get_officer_phone_from_shelter_dashboard(self):
        """BUG-3 (same endpoint): officer_in_charge_phone of a posko whose org
        shares only aggregates."""
        with as_guest():
            data = api_call("rescue_net.api_shelter.dashboard", posko=self.shelter.name)
        self.assertFalse(contains_value(data, PHONE))


class TestPhoneNumbers(RNTestCase):
    """Org default = control_centre_share 'aggregate' → Guest gets summary only."""

    def setUp(self):
        super().setUp()
        self.w = make_world()
        frappe.db.set_value("RN Posko", self.w.posko_a.name, "officer_in_charge_phone", PHONE)
        self.op_a = make_actor(posko=self.w.posko_a)

    def test_posko_detail_hides_phone_from_guest(self):
        with as_guest():
            data = api_call("rescue_net.api_control_centre.posko_detail", posko=self.w.posko_a.name)
        self.assertEqual(data.get("share_mode"), "summary")
        self.assertFalse(contains_value(data, PHONE))

    def test_posko_detail_shows_phone_to_own_operator(self):
        with as_user(self.op_a.user):
            data = api_call("rescue_net.api_control_centre.posko_detail", posko=self.w.posko_a.name)
        self.assertTrue(contains_value(data, PHONE))

    def test_verification_checklist_hides_phone_from_guest(self):
        """BUG-2: posko_verification_checklist (allow_guest) returns the PIC's
        phone AND email as checklist values to anyone."""
        with as_guest():
            data = api_call("rescue_net.api_control_centre.posko_verification_checklist",
                            posko=self.w.posko_a.name)
        self.assertFalse(contains_value(data, PHONE))
        phone = next(i for i in data["items"] if i["key"] == "phone")
        self.assertTrue(phone["done"])            # the flag stays, only the value is hidden

    def test_verification_checklist_shows_phone_to_own_operator(self):
        with as_user(self.op_a.user):
            data = api_call("rescue_net.api_control_centre.posko_verification_checklist",
                            posko=self.w.posko_a.name)
        self.assertTrue(contains_value(data, PHONE))


class TestTransportContacts(RNTestCase):
    def setUp(self):
        super().setUp()
        self.w = make_world()
        self.transport = make_posko(self.w.event, self.w.org_a, posko_type="transport")
        self.space = make_transport_space(self.transport)
        _insert(
            "RN Transport Booking",
            transport_space=self.space.name,
            status="requested",
            booker_name="Pemesan Uji",
            contact_person="Pak Uji",
            contact_phone=PHONE,
            verification_pin=PIN,
            cargo_desc="Beras",
            qty_weight_kg=50,
        )

    def test_own_operator_still_sees_pin_and_phone(self):
        op = make_actor(posko=self.transport)
        with as_user(op.user):
            data = api_call("rescue_net.api_control_centre.posko_distribusi_board",
                            posko=self.transport.name, disaster_event=self.w.event.name)
        self.assertTrue(contains_value(data, PIN))
        self.assertTrue(contains_value(data, PHONE))

    def test_other_logged_in_user_gets_no_pin(self):
        with as_user(make_actor(posko=self.w.posko_b).user):
            data = api_call("rescue_net.api_control_centre.posko_distribusi_board",
                            posko=self.transport.name, disaster_event=self.w.event.name)
        self.assertFalse(contains_value(data, PIN))

    def board_as_guest(self):
        with as_guest():
            return api_call("rescue_net.api_control_centre.posko_distribusi_board",
                            posko=self.transport.name, disaster_event=self.w.event.name)

    def test_guest_does_not_get_booking_pin(self):
        """BUG-1: posko_distribusi_board (allow_guest) returns every booking's
        handover verification_pin — the PIN meant to prove who may collect."""
        self.assertFalse(contains_value(self.board_as_guest(), PIN))

    def test_guest_does_not_get_booking_phone(self):
        """BUG-1 (same endpoint): booker contact_phone."""
        self.assertFalse(contains_value(self.board_as_guest(), PHONE))


class TestPersonalContacts(RNTestCase):
    def setUp(self):
        super().setUp()
        self.w = make_world()
        frappe.db.set_value("RN Posko", self.w.posko_a.name, "officer_in_charge_phone", PHONE)
        self.volunteer = make_actor(role="volunteer", phone="+62811-0000-8888")
        _insert("RN Volunteer Profile", volunteer_name="Relawan Uji", main_skill="medis",
                contact="+62811-0000-9999", user_account=self.volunteer.account,
                disaster_event=self.w.event.name, assigned_posko=self.w.posko_a.name)

    def test_guest_cannot_read_any_users_profile(self):
        """BUG-5: resource_profile_board(user_account=X) (allow_guest) returns
        ANY account's phone, email, volunteer contact and owned resources."""
        with as_guest():
            data = api_call("rescue_net.api_resource_tools.resource_profile_board",
                            user_account=self.volunteer.account)
        self.assertFalse(contains_value(data, "+62811-0000-8888"))
        self.assertFalse(contains_value(data, "+62811-0000-9999"))

    def test_owner_sees_own_profile_contacts(self):
        with as_user(self.volunteer.user):
            data = api_call("rescue_net.api_resource_tools.resource_profile_board")
        self.assertTrue(contains_value(data, "+62811-0000-8888"))
        self.assertTrue(data["chips"]["phone_verified"])

    def test_guest_volunteer_dashboard_hides_contacts(self):
        """BUG-6: api_volunteer.dashboard(posko=X) (allow_guest) returns the
        posko's volunteer profiles incl. `contact`, and the PIC phone."""
        with as_guest():
            data = api_call("rescue_net.api_volunteer.dashboard", posko=self.w.posko_a.name)
        self.assertFalse(contains_value(data, "+62811-0000-9999"))
        self.assertFalse(contains_value(data, PHONE))
