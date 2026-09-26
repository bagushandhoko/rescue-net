"""Laporan Masyarakat: a narrative becomes the form (rules or AI), the report is
routed to the relevant posko with its reason, only the reporter / routed posko
add follow-ups, and a guest cannot report."""

import json
from unittest import mock

import frappe

from rescue_net import api_ai
from rescue_net import api_reports as api
from rescue_net.services import llm, report_intake
from rescue_net.tests.factories import RNTestCase, api_call, as_guest, as_user, make_actor, make_event, make_org, make_posko

KEY = "fake-byok-PLATFORM-0123456789abcdefWXYZ"


class TestRulesExtract(RNTestCase):
    def test_landslide_blocking_the_road(self):
        f = report_intake.rules_extract(
            "Longsor menutup jalan di Desa Sukamaju sepanjang 200 meter, 3 orang terjebak. Butuh excavator segera.")
        self.assertEqual(f["report_type"], "blocked_access")
        self.assertEqual(f["priority"], "critical")
        self.assertEqual(f["affected_people_count"], 3)
        self.assertEqual((f["damage_scale_value"], f["damage_scale_unit"]), (200.0, "meter"))
        self.assertIn("excavator", f["urgent_needs"])
        self.assertIn("Desa Sukamaju", f["location_text"])

    def test_drought_counts_families_as_people(self):
        f = report_intake.rules_extract("Sumur kering sudah 2 bulan, 50 KK kekurangan air bersih di Dusun Oebelo.")
        self.assertEqual(f["report_type"], "water_shortage")
        self.assertEqual(f["affected_people_count"], 200)
        self.assertTrue(f["notes"])
        self.assertEqual(f["urgent_needs"], "air bersih")

    def test_medical_words_win(self):
        f = report_intake.rules_extract("Ada 12 warga demam dan diare di pengungsian, butuh obat dan dokter.")
        self.assertEqual(f["report_type"], "medical_case")


class TestIntakeAndRouting(RNTestCase):
    def setUp(self):
        super().setUp()
        self.event = make_event(event_status="active")
        org = make_org()
        self.near = make_posko(self.event, org, title="Posko Sukamaju", village_name="Sukamaju",
                               district_name="Cibeber", city_name="Cianjur", posko_type="logistics",
                               latitude=-6.90, longitude=107.10)
        self.medical = make_posko(self.event, org, title="Posko Medis Cibeber", district_name="Cibeber",
                                  city_name="Cianjur", posko_type="medical", latitude=-6.95, longitude=107.12)
        self.far = make_posko(self.event, org, title="Posko Kota", city_name="Bandung", posko_type="logistics",
                              latitude=-6.91, longitude=107.61)
        self.reporter = make_actor(role="viewer")
        self.op_near = make_actor(posko=self.near)
        self.op_far = make_actor(posko=self.far)

    def submit(self, text, **kw):
        with as_user(self.reporter.user):
            return api.submit_community_report(description=text, intake_mode="narrative",
                                               disaster_event=self.event.name, **kw)

    def test_guest_cannot_report_or_draft(self):
        for fn in ("submit_community_report", "draft_community_report", "my_community_reports"):
            with as_guest(), self.assertRaises(frappe.PermissionError):
                api_call(f"rescue_net.api_reports.{fn}", description="x" * 20, narrative="x" * 20)

    def test_narrative_is_filled_and_routed_to_the_village_posko(self):
        out = self.submit("Banjir setinggi 1 meter merendam Desa Sukamaju, 40 orang mengungsi ke masjid, "
                          "butuh selimut dan makanan.", latitude=-6.901, longitude=107.101)
        doc = frappe.get_doc("RN Community Report", out["name"])
        self.assertEqual(doc.intake_mode, "narrative")
        self.assertEqual(doc.intake_parser, "rules")
        self.assertEqual(doc.report_type, "shelter_need")
        self.assertEqual(doc.affected_people_count, 40)
        self.assertEqual(doc.posko, self.near.name)
        self.assertIn("desa Sukamaju", doc.routing_reason)
        self.assertEqual(doc.routing_mode, "auto")

    def test_medical_report_goes_to_the_medical_posko_of_the_district(self):
        out = self.submit("Ada 5 warga luka dan demam tinggi di Kecamatan Cibeber, butuh dokter.",
                          latitude=-6.951, longitude=107.121)
        self.assertEqual(out["posko"], self.medical.name)

    def test_nothing_near_stays_unrouted(self):
        out = self.submit("Butuh bantuan makanan untuk 10 warga di tempat terpencil.", latitude=-8.5, longitude=115.2)
        self.assertIsNone(out["posko"])
        self.assertIn("triase", out["routing_reason"])

    def test_draft_saves_nothing_and_suggests_the_posko(self):
        before = frappe.db.count("RN Community Report")
        with as_user(self.reporter.user):
            d = api.draft_community_report("Jalan desa tertutup longsor 150 meter di Desa Sukamaju.",
                                           disaster_event=self.event.name, latitude=-6.9, longitude=107.1)
        self.assertEqual(frappe.db.count("RN Community Report"), before)
        self.assertEqual(d["fields"]["report_type"], "blocked_access")
        self.assertEqual(d["suggested_posko"], self.near.name)
        self.assertTrue(any(n["category"] == "excavator" for n in d["predicted_needs"]))

    def test_reviewed_draft_is_sent_as_is(self):
        with mock.patch.object(report_intake, "extract", side_effect=AssertionError("no re-parse")):
            out = self.submit("uraian yang sudah ditinjau pelapor", title="Judul ditinjau",
                              report_type="affected_need_help", intake_parser="ai:anthropic",
                              latitude=-6.9, longitude=107.1)
        doc = frappe.get_doc("RN Community Report", out["name"])
        self.assertEqual((doc.title, doc.intake_parser), ("Judul ditinjau", "ai:anthropic"))

    def test_platform_ai_key_parses_the_narrative(self):
        api_ai.save_platform_key(KEY, provider="anthropic")
        answer = {"content": [{"type": "text", "text": json.dumps({
            "title": "Kekeringan Dusun Oebelo", "report_type": "water_shortage", "priority": "urgent",
            "affected_people_count": 320, "urgent_needs": ["air bersih 5000 liter", "jerigen"],
            "damage_scale_value": None, "damage_scale_unit": None, "location_text": "Dusun Oebelo",
            "notes": []})}], "stop_reason": "end_turn", "usage": {"input_tokens": 50, "output_tokens": 40}}
        resp = mock.Mock(status_code=200, ok=True, json=lambda: answer)
        with as_user(self.reporter.user), mock.patch.object(llm.requests, "post", return_value=resp) as post:
            d = api.draft_community_report("Warga Dusun Oebelo sudah 3 bulan tidak ada air, sumur kering semua.")
        self.assertIn("api.anthropic.com", post.call_args.args[0])
        self.assertEqual(d["parser"], "ai:anthropic")
        self.assertEqual(d["fields"]["report_type"], "water_shortage")
        self.assertEqual(d["fields"]["affected_people_count"], 320)
        self.assertEqual(d["fields"]["urgent_needs"], "air bersih 5000 liter, jerigen")

    def test_ai_failure_falls_back_to_rules(self):
        api_ai.save_platform_key(KEY, provider="gemini")
        with as_user(self.reporter.user), mock.patch.object(llm.requests, "post",
                                                             return_value=mock.Mock(status_code=500, ok=False)):
            d = api.draft_community_report("Sumur kering, 30 orang kekurangan air bersih.")
        self.assertEqual(d["parser"], "rules")
        self.assertEqual(d["fields"]["report_type"], "water_shortage")

    def test_follow_ups_by_reporter_and_routed_posko_only(self):
        report = self.submit("Banjir di Desa Sukamaju, 40 orang mengungsi, butuh selimut.",
                             latitude=-6.9, longitude=107.1)["name"]
        with as_user(self.reporter.user):
            api.add_community_report_update(report, "Sekarang 60 orang, butuh susu bayi juga.",
                                            update_type="additional_need", urgent_needs="susu bayi",
                                            affected_people_count=60)
            mine = api.my_community_reports()
        with as_user(self.op_near.user):
            out = api.add_community_report_update(report, "Tim menuju lokasi.")
        self.assertEqual([u.author_role for u in out["updates"]], ["reporter", "posko"])
        self.assertEqual(mine[0]["updates"][0]["urgent_needs"], "susu bayi")
        for stranger in (self.op_far, make_actor()):
            with as_user(stranger.user), self.assertRaises(frappe.PermissionError):
                api.add_community_report_update(report, "bukan urusan saya")

    def test_reroute_by_current_posko_only(self):
        report = self.submit("Banjir di Desa Sukamaju, 40 orang mengungsi.", latitude=-6.9, longitude=107.1)["name"]
        with as_user(self.op_far.user), self.assertRaises(frappe.PermissionError):
            api.reroute_community_report(report, self.far.name)
        with as_user(self.op_near.user):
            api.reroute_community_report(report, self.medical.name)
        doc = frappe.get_doc("RN Community Report", report)
        self.assertEqual((doc.posko, doc.routing_mode), (self.medical.name, "manual"))

    def test_drought_report_predicts_water_trucks(self):
        needs = api.predict_report_needs("water_shortage", None, 1000)
        by = {n["category"]: n for n in needs}
        self.assertEqual(by["air_bersih"]["predicted_qty"], 15000)
        self.assertEqual(by["truk_tangki_air"]["predicted_qty"], 3)
