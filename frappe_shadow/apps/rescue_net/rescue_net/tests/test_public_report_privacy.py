"""Public endpoints that carry community reports never say who reported (name / phone / email / legacy JSON);
operator-level viewers keep the names on the evidence board."""

import json

import frappe

from rescue_net import api_control_centre as cc
from rescue_net.tests.factories import RNTestCase, _insert, as_guest, as_user, make_actor, make_event, make_org, make_posko

PHONE, MAIL, NAME = "081111110088", "pelapor.privasi@test.rescue-net.local", "NAMA-PELAPOR-PRIVASI"


class TestPublicReportPrivacy(RNTestCase):
    def setUp(self):
        super().setUp()
        self.event = make_event()
        self.posko = make_posko(event=self.event, org=make_org())
        reporter = make_actor(role="citizen", phone=PHONE)
        self.report = _insert(
            "RN Community Report", title="Laporan privasi", description="Sumur kering", disaster_event=self.event.name,
            posko=self.posko.name, report_type="water_shortage", status="submitted", reporter_name=NAME,
            reporter_user=reporter.account, reporter_phone=PHONE, reporter_email=MAIL, consent_to_contact=1,
            affected_people_count=5, latitude=-6.2, longitude=106.8,
            legacy_payload=json.dumps({"reporter_phone": PHONE, "reporter_email": MAIL, "reporter_name": NAME,
                                       "evidence": {"image": "/files/foto.jpg", "caption": "Foto sumur"}}))
        self.operator = make_actor(posko=self.posko)

    def blob(self, fn, **kw):
        return json.dumps(fn(**kw), default=str)

    def test_guest_gets_no_reporter_identity_from_any_public_report_endpoint(self):
        with as_guest():
            for blob in (self.blob(cc.public_dashboard, disaster_event_id=self.event.name),
                         self.blob(cc.evidence_board, disaster_event=self.event.name),
                         self.blob(cc.active_disasters_board)):
                for secret in (PHONE, MAIL, NAME):
                    self.assertNotIn(secret, blob)

    def test_the_public_dashboard_still_shows_the_report_and_its_photo(self):
        with as_guest():
            out = cc.public_dashboard(disaster_event_id=self.event.name)
        row = next(r for r in out["community_reports"] if r["name"] == self.report.name)
        self.assertEqual(row["reporter_name"], "Pelapor")
        self.assertEqual(row["title"], "Laporan privasi")
        self.assertEqual(row["legacy_payload"], {"evidence": {"image": "/files/foto.jpg", "caption": "Foto sumur"}})

    def test_operator_keeps_names_on_the_evidence_board_but_never_the_phone_or_email(self):
        with as_user(self.operator.user):
            blob = self.blob(cc.evidence_board, disaster_event=self.event.name)
        self.assertNotIn(PHONE, blob)
        self.assertNotIn(MAIL, blob)
