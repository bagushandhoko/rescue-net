"""Back Office Penanganan (control_centre.ecosystem.ecosystem_board).

Guest-readable board: groups helpers into Pemerintah / Organisasi /
Masyarakat Umum / Program Donasi and shows the gap between posko needs
and what is delivered or on the way. It must never leak a private
person's name or contact."""

import frappe

from rescue_net.tests.factories import (
    RNTestCase,
    _insert,
    api_call,
    as_guest,
    contains_value,
    make_actor,
    make_event,
    make_org,
    make_posko,
    uid,
)

DONOR = "Budi Penyumbang Rahasia"
DONOR_PHONE = "+62811-0000-5151"
VOLUNTEER = "Sari Relawan Pribadi"
METHOD = "rescue_net.api_control_centre.ecosystem_board"


class TestEcosystemBoard(RNTestCase):
    def setUp(self):
        super().setUp()
        self.event = make_event()
        self.gov = make_org(title=uid("BPBD"), organization_type="government")
        self.ngo = make_org(title=uid("Komunitas"), organization_type="community")
        self.posko_gov = make_posko(self.event, self.gov)
        self.posko_ngo = make_posko(self.event, self.ngo)

        gov_actor = make_actor(org=self.gov)
        _insert("RN Volunteer Profile", disaster_event=self.event.name,
                user_account=gov_actor.account, volunteer_name=uid("Relawan BPBD"), main_skill="Evakuasi",
                availability_status="available")
        # a private person: no organisation -> Masyarakat Umum
        _insert("RN Volunteer Profile", disaster_event=self.event.name,
                volunteer_name=VOLUNTEER, contact=DONOR_PHONE, main_skill="Dapur", availability_status="available")

        _insert("RN Logistic Need", title=uid("Butuh beras"), disaster_event=self.event.name, posko=self.posko_gov.name,
                item_name="Beras", quantity=100, unit="kg", need_status="open", urgency="critical")
        _insert("RN Aid Offer", title=uid("Offer"), disaster_event=self.event.name,
                target_posko=self.posko_gov.name, donor_name=DONOR, donor_contact=DONOR_PHONE,
                item_name="Beras", quantity=30, unit="kg", offer_status="offered")

        _insert("RN Donor Program", disaster_event=self.event.name, program_name=uid("Program"),
                owner_type="organization", owner_id=self.ngo.name, status="active",
                budget_target=1000000, budget_received=250000)

    def board(self):
        with as_guest():
            return api_call(METHOD, disaster_event=self.event.name)

    def test_groups_count_each_side(self):
        data = self.board()
        g = {x["key"]: x for x in data["groups"]}
        self.assertEqual(g["pemerintah"]["orgs"], 1)
        self.assertEqual(g["pemerintah"]["posko"], 1)
        self.assertEqual(g["pemerintah"]["relawan"], 1)
        self.assertEqual(g["organisasi"]["orgs"], 1)
        self.assertEqual(g["masyarakat"]["relawan"], 1)
        self.assertEqual(g["masyarakat"]["sumbangan"], 1)
        self.assertEqual(g["program"]["program"], 1)
        self.assertEqual(g["program"]["dana_terkumpul"], 250000)

    def test_gap_subtracts_aid_on_the_way(self):
        need = next(n for n in self.board()["needs"] if n["item"] == "Beras")
        self.assertEqual(need["dibutuhkan"], 100)
        self.assertEqual(need["menuju"], 30)
        self.assertEqual(need["gap"], 70)
        self.assertTrue(need["kritis"])

    def test_program_gap(self):
        prog = self.board()["programs"][0]
        self.assertEqual(prog["gap"], 750000)
        self.assertEqual(prog["percent"], 25.0)

    def test_guest_never_sees_private_people(self):
        data = self.board()
        for secret in (DONOR, DONOR_PHONE, VOLUNTEER):
            self.assertFalse(contains_value(data, secret), secret)

    def test_unknown_event_is_refused(self):
        with as_guest():
            self.assertRaises(frappe.DoesNotExistError, api_call, METHOD, disaster_event="tidak-ada-123")
