"""Program Khusus plan: milestones, locations, needs, support cards, output check, board KPIs."""

import frappe

from rescue_net import api_donor_program as api
from rescue_net.tests.factories import RNTestCase, api_call, as_guest, as_user, make_actor, make_event, make_org, make_posko


class TestProgramPlan(RNTestCase):
    def setUp(self):
        super().setUp()
        self.event = make_event()
        self.org = make_org(verification_status="verified")
        posko = make_posko(self.event, self.org)
        self.owner = make_actor(org=self.org, org_role="owner", posko=posko)
        self.other = make_actor()
        with as_user(self.owner.user):
            self.program = api.create_special_program(
                self.event.name, "PLTS darurat", owner_type="organization", owner_id=self.org.name,
                budget_target=1_000_000, end_date="2020-01-01")["program"]
        frappe.db.set_value("RN Donor Program", self.program, {"public_visibility": "summary_public", "status": "active"})

    def add(self, item_type, **values):
        with as_user(self.owner.user):
            return api.save_plan_item(self.program, item_type, values=values)["name"]

    def board(self):
        with as_guest():
            return api_call("rescue_net.api_donor_program.program_board", disaster_event=self.event.name)

    def detail(self):
        with as_guest():
            return api_call("rescue_net.api_donor_program.program_detail", program=self.program)

    def test_only_owner_edits_the_plan(self):
        with as_user(self.other.user):
            with self.assertRaises(frappe.PermissionError):
                api.save_plan_item(self.program, "milestone", values={"title": "x"})
        with as_guest():
            with self.assertRaises((frappe.PermissionError, frappe.ValidationError)):
                api.save_plan_item(self.program, "milestone", values={"title": "x"})

    def test_milestone_rules_and_late_kpi(self):
        # no milestones: the old rule (end date passed) still marks it late
        self.assertEqual(self.board()["totals"]["milestone_terlambat"], 1)
        m = self.add("milestone", title="Pengadaan", due_date="2999-01-01", milestone_status="berjalan", progress_percent=40)
        self.assertEqual(self.board()["totals"]["milestone_terlambat"], 0)   # its own milestones decide now
        with as_user(self.owner.user):
            api.save_plan_item(self.program, "milestone", name=m, values={"due_date": "2020-02-02"})
        self.assertEqual(self.board()["totals"]["milestone_terlambat"], 1)
        with as_user(self.owner.user):
            api.save_plan_item(self.program, "milestone", name=m, values={"milestone_status": "selesai"})
        self.assertEqual(frappe.db.get_value("RN Program Milestone", m, "progress_percent"), 100)
        self.assertEqual(self.board()["totals"]["milestone_terlambat"], 0)
        with self.assertRaises(frappe.ValidationError):
            self.add("milestone", title="Salah", milestone_status="berjalan", progress_percent=100)

    def test_unserved_locations_and_detail_totals(self):
        a = self.add("location", title="Posko 1", latitude=-6.2, longitude=106.8)
        self.add("location", title="Posko 2")
        self.assertEqual(self.board()["totals"]["lokasi_belum_terlayani"], 2)
        with as_user(self.owner.user):
            api.save_plan_item(self.program, "location", name=a, values={"location_status": "terlayani"})
        self.assertEqual(self.board()["totals"]["lokasi_belum_terlayani"], 1)
        tot = self.detail()["plan"]["location_totals"]
        self.assertEqual((tot["total"], tot["served"], tot["unserved"]), (2, 1, 1))
        with self.assertRaises(frappe.ValidationError):
            self.add("location", title="Salah", latitude=999)

    def test_needs_and_support_cards(self):
        self.add("need", item="Panel Surya 100Wp", kind="material", qty_needed=18, qty_available=14, unit="unit")
        self.add("need", item="Truk", kind="distribusi", qty_needed=2, qty_available=0, unit="unit")
        self.add("need", item="Teknisi", kind="relawan", qty_needed=6, qty_available=6, unit="orang")
        plan = self.detail()["plan"]
        self.assertEqual(plan["needs"][0]["shortfall"], 4)
        self.assertEqual(plan["support"]["distribusi"]["status"], "butuh_support")
        self.assertEqual(plan["support"]["relawan"]["status"], "terpenuhi")
        self.assertEqual(plan["support"]["alat_kerja"]["status"], "tidak_ada")
        self.assertEqual(self.board()["totals"]["butuh_support"], 1)
        with self.assertRaises(frappe.ValidationError):
            self.add("need", item="Negatif", qty_needed=-1)

    def test_output_verification_cannot_exceed_target(self):
        with as_user(self.owner.user):
            api.set_output_verification(self.program, status="dalam_proses", output_target=12, output_verified=6, verifier="BPBD")
            with self.assertRaises(frappe.ValidationError):
                api.set_output_verification(self.program, output_verified=13)
        v = self.detail()["plan"]["verification"]
        self.assertEqual((v["status"], v["output_target"], v["output_verified"]), ("dalam_proses", 12, 6))

    def test_an_item_of_another_program_is_not_touched(self):
        m = self.add("milestone", title="Milik saya")
        with as_user(self.owner.user):
            other = api.create_special_program(self.event.name, "Program lain", owner_type="organization",
                                               owner_id=self.org.name)["program"]
            with self.assertRaises(frappe.PermissionError):
                api.delete_plan_item(other, "milestone", m)
