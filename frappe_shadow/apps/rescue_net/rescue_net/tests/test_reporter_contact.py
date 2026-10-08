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


class TestEndorseReporter(RNTestCase):
    def setUp(self):
        super().setUp()
        from rescue_net import api_verifier as av

        self.av = av
        self.event = make_event()
        self.posko = make_posko(event=self.event, org=make_org())
        self.reporter = make_actor(role="citizen", phone="081200000077")
        self.operator = make_actor(posko=self.posko)
        self.verifier = make_actor(role="citizen")
        _insert("RN Verifier Profile", title="Pak Kades", user=self.verifier.account, verifier_type="government",
                position_title="Kepala Desa Sukamaju", verifier_status="active", trust_level=1)
        with as_user(self.reporter.user):
            out = api.submit_community_report(description=TEXT, intake_mode="narrative", consent_to_contact=1,
                                              disaster_event=self.event.name)
        self.report = out["name"]
        frappe.db.set_value("RN Community Report", self.report, "posko", self.posko.name)

    def endorse(self, user=None, **kw):
        with as_user(user or self.verifier.user):
            return self.av.endorse_reporter(self.reporter.account, statement=kw.pop("statement", "Warga desa saya, saya kenal langsung."), **kw)

    def public_row(self):
        with as_guest():
            rows = bridge.community_reports(disaster_event=self.event.name)
        return next(r for r in rows if r["name"] == self.report)

    def test_endorsement_makes_it_level_3_and_shows_blue_check_data(self):
        self.assertEqual(self.public_row()["reporter_level"], 2)
        self.endorse()
        row = self.public_row()
        self.assertEqual(row["reporter_level"], 3)
        self.assertEqual(row["reporter_verified_types"], ["Pemerintah / aparat"])
        self.assertNotIn("reporter_user", row)
        self.assertNotIn("Kades", str(row))  # the public sees the type, never the name

    def test_operator_sees_who_verified_with_name_and_position(self):
        self.endorse()
        out = api_call_as(self.operator.user, self.report)
        ends = out["verification"]["endorsements"]
        self.assertEqual(len(ends), 1)
        self.assertEqual(ends[0]["verifier_name"], "Pak Kades")
        self.assertEqual(ends[0]["position"], "Kepala Desa Sukamaju")
        self.assertEqual(ends[0]["type_label"], "Pemerintah / aparat")
        self.assertFalse(out["viewer_is_verifier"])
        self.assertTrue(api_call_as(self.verifier.user, self.report)["viewer_is_verifier"])

    def test_rules(self):
        with self.assertRaises(frappe.PermissionError):                      # not a verifier
            self.endorse(user=self.operator.user)
        with self.assertRaises(frappe.ValidationError):                      # statement required
            self.endorse(statement="ok")
        with self.assertRaises(frappe.ValidationError):                      # network vouch needs a referrer
            self.endorse(method="network_vouch")
        self.endorse()
        with self.assertRaises(frappe.ValidationError):                      # once per verifier
            self.endorse()
        with as_user(self.reporter.user), self.assertRaises(frappe.PermissionError):   # never yourself
            self.av.endorse_reporter(self.reporter.account, statement="Saya sendiri ya verifikator")

    def test_suspended_verifier_or_revoked_endorsement_no_longer_counts(self):
        out = self.endorse()
        self.assertEqual(rc.verification_profile(self.reporter.account)["level"], 3)
        frappe.db.set_value("RN Verifier Profile", {"user": self.verifier.account}, "verifier_status", "suspended")
        self.assertEqual(rc.verification_profile(self.reporter.account)["level"], 2)
        frappe.db.set_value("RN Verifier Profile", {"user": self.verifier.account}, "verifier_status", "active")
        self.assertEqual(rc.verification_profile(self.reporter.account)["level"], 3)
        with as_user(self.verifier.user):
            self.av.revoke_endorsement(out["endorsement"], reason="salah orang")
        self.assertEqual(rc.verification_profile(self.reporter.account)["level"], 2)


def api_call_as(user, report):
    with as_user(user):
        return api.reporter_contact(report)
