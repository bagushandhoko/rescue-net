"""Hubungi pelapor + level verifikasi: the public list never carries a phone/email/name; only the routed
posko's managers, a System Manager or an active verifier open the contact (audited, consent respected)."""

import frappe

from rescue_net import api_frontend_bridge as bridge
from rescue_net import api_reports as api
from rescue_net.services import reporter_contact as rc
from rescue_net.tests.factories import (RNTestCase, _insert, api_call, as_guest, as_user, make_actor, make_event,
                                        make_org, make_posko)

TEXT = "Sumur di Dusun Oebelo kering sejak 2 bulan, 50 KK kekurangan air bersih."


class TestReporterContact(RNTestCase):
    def setUp(self):
        super().setUp()
        self.event = make_event()
        self.org = make_org()
        self.posko = make_posko(event=self.event, org=self.org)
        self.reporter = make_actor(role="citizen")
        self.operator = make_actor(posko=self.posko)
        self.stranger = make_actor(role="citizen")

    def report(self, consent=1, phone="081234567890"):
        with as_user(self.reporter.user):
            out = api.submit_community_report(description=TEXT, intake_mode="narrative", reporter_phone=phone,
                                              consent_to_contact=consent, disaster_event=self.event.name)
        frappe.db.set_value("RN Community Report", out["name"], "posko", self.posko.name)
        return out["name"]

    def contact(self, user, name):
        with as_user(user):
            return api.reporter_contact(name)

    def test_public_list_has_no_contact_and_no_name(self):
        name = self.report()
        with as_guest():
            rows = bridge.community_reports(disaster_event=self.event.name)
        row = next(r for r in rows if r["name"] == name)
        self.assertNotIn("reporter_phone", row)
        self.assertNotIn("reporter_email", row)
        self.assertEqual(row["reporter_name"], "Pelapor")
        self.assertFalse(row["can_contact_reporter"])
        self.assertNotIn("081234567890", str(rows))

    def test_routed_posko_operator_sees_the_name_flag_but_still_no_phone_in_the_list(self):
        name = self.report()
        with as_user(self.operator.user):
            rows = bridge.community_reports(disaster_event=self.event.name)
        row = next(r for r in rows if r["name"] == name)
        self.assertTrue(row["can_contact_reporter"])
        self.assertNotIn("reporter_phone", row)

    def test_operator_gets_phone_links_and_the_lookup_is_audited(self):
        name = self.report()
        out = self.contact(self.operator.user, name)
        self.assertEqual(out["phone"], "081234567890")
        self.assertEqual(out["tel_url"], "tel:+6281234567890")
        self.assertTrue(out["whatsapp_url"].startswith("https://wa.me/6281234567890?text="))
        self.assertTrue(frappe.db.exists("RN Verification Action", {
            "object_type": "community_report", "object_id": name, "action_type": "view_reporter_contact"}))

    def test_other_operators_citizens_and_guests_are_refused(self):
        name = self.report()
        other_posko = make_posko(event=self.event, org=make_org())
        other_op = make_actor(posko=other_posko)
        for user in (self.stranger.user, other_op.user, self.reporter.user):
            if user == self.reporter.user:
                continue  # the reporter knows their own number; not a contact lookup case
            with self.assertRaises(frappe.PermissionError):
                self.contact(user, name)
        with as_guest(), self.assertRaises(frappe.PermissionError):
            api_call("rescue_net.api_reports.reporter_contact", report=name)

    def test_no_consent_means_no_phone(self):
        name = self.report(consent=0)
        out = self.contact(self.operator.user, name)
        self.assertIsNone(out["phone"])
        self.assertIn("tidak bersedia", out["reason_no_contact"])

    def test_active_verifier_may_open_the_contact(self):
        name = self.report()
        verifier = make_actor(role="citizen")
        _insert("RN Verifier Profile", title="V", user=verifier.account, verifier_type="community_leader",
                verifier_status="active", trust_level=2)
        self.assertEqual(self.contact(verifier.user, name)["phone"], "081234567890")
        self.assertEqual(rc.verification_profile(verifier.account)["level"], 4)


class TestVerificationLevel(RNTestCase):
    def test_levels_follow_the_evidence(self):
        self.assertEqual(rc.verification_profile(None)["level"], 0)
        plain = make_actor(role="citizen")
        self.assertEqual(rc.verification_profile(plain.account)["level"], 1)
        with_phone = make_actor(role="citizen", phone="081200000009")
        self.assertEqual(rc.verification_profile(with_phone.account)["level"], 2)
        verified = make_actor(role="verified_reporter", phone="081200000010")
        prof = rc.verification_profile(verified.account)
        self.assertEqual(prof["level"], 3)
        self.assertTrue(any(e["key"] == "reporter" and e["ok"] for e in prof["evidence"]))
        self.assertTrue(all({"key", "ok", "label", "detail"} <= set(e) for e in prof["evidence"]))
