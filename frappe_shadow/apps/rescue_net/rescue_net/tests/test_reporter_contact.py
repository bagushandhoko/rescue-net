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
        self.assertEqual(rc.verification_profile(verifier.account)["status"], "official_verified")


class TestVerificationStatus(RNTestCase):
    def test_status_follows_the_evidence_with_the_posko_vocabulary(self):
        self.assertEqual(rc.verification_profile(None)["status"], "self_reported")
        plain = make_actor(role="citizen", phone="081200000009")
        self.assertEqual(rc.verification_profile(plain.account)["status"], "self_reported")  # phone alone is not verification
        approved = make_actor(role="verified_reporter", phone="081200000010")
        prof = rc.verification_profile(approved.account)
        self.assertEqual(prof["status"], "community_verified")
        self.assertEqual(prof["verifiers"][0]["role_label"], "Pelapor Terverifikasi (disetujui)")
        junior = make_actor(role="citizen")
        _insert("RN Verifier Profile", title="J", user=junior.account, verifier_type="community_leader",
                verifier_status="active", trust_level=1)
        self.assertEqual(rc.verification_profile(junior.account)["status"], "community_verified")
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

    def test_one_endorsement_is_community_verified_and_public_sees_who(self):
        self.assertEqual(self.public_row()["reporter_verification_status"], "self_reported")
        self.endorse()
        row = self.public_row()
        self.assertEqual(row["reporter_verification_status"], "community_verified")
        self.assertEqual(row["reporter_verified_count"], 1)
        who = row["reporter_verifiers"][0]
        self.assertEqual((who["verifier"], who["position"], who["role_label"]),
                         ("Pak Kades", "Kepala Desa Sukamaju", "Pemerintah / aparat"))
        self.assertNotIn("reporter_user", row)
        self.assertNotIn("statement", who)                    # what the verifier says about the person stays private
        self.assertNotIn("Warga desa saya", str(row))

    def test_two_endorsements_or_a_senior_government_one_is_official(self):
        self.endorse()
        second = make_actor(role="citizen")
        _insert("RN Verifier Profile", title="Bu Rina", user=second.account, verifier_type="community_leader",
                position_title="Ketua PKK", verifier_status="active", trust_level=1)
        with as_user(second.user):
            self.av.endorse_reporter(self.reporter.account, statement="Aktif membantu warga di PKK.")
        self.assertEqual(self.public_row()["reporter_verification_status"], "official_verified")
        self.assertEqual(self.public_row()["reporter_verified_count"], 2)
        frappe.db.set_value("RN Verifier Profile", {"user": second.account}, "verifier_status", "revoked")
        frappe.db.set_value("RN Verifier Profile", {"user": self.verifier.account}, "trust_level", 2)
        self.assertEqual(self.public_row()["reporter_verification_status"], "official_verified")  # government, trust 2

    def test_operator_sees_who_verified_with_name_and_position(self):
        self.endorse()
        out = api_call_as(self.operator.user, self.report)
        ends = out["verification"]["verifiers"]
        self.assertEqual(len(ends), 1)
        self.assertEqual(ends[0]["verifier"], "Pak Kades")
        self.assertEqual(ends[0]["position"], "Kepala Desa Sukamaju")
        self.assertEqual(ends[0]["role_label"], "Pemerintah / aparat")
        self.assertIn("Warga desa saya", ends[0]["statement"])      # authorised viewers read the statement
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
        status = lambda: rc.verification_profile(self.reporter.account)["status"]
        self.assertEqual(status(), "community_verified")
        frappe.db.set_value("RN Verifier Profile", {"user": self.verifier.account}, "verifier_status", "suspended")
        self.assertEqual(status(), "self_reported")
        frappe.db.set_value("RN Verifier Profile", {"user": self.verifier.account}, "verifier_status", "active")
        self.assertEqual(status(), "community_verified")
        with as_user(self.verifier.user):
            self.av.revoke_endorsement(out["endorsement"], reason="salah orang")
        self.assertEqual(status(), "self_reported")


def api_call_as(user, report):
    with as_user(user):
        return api.reporter_contact(report)


class TestOrgRegistration(RNTestCase):
    """Verified through how they registered: member approved + identity confirmed by a verified organisation."""

    def member(self, org, confirmed):
        member = make_actor(role="citizen", org=org)
        frappe.db.set_value("RN Organization Membership", {"user_account": member.account}, "member_verified",
                            1 if confirmed else 0)
        return member

    def test_confirmed_member_of_a_verified_org_is_verified_and_the_org_is_listed(self):
        org = make_org(verification_status="verified")
        member = self.member(org, confirmed=True)
        prof = rc.verification_profile(member.account)
        self.assertEqual(prof["status"], "organization_verified")
        self.assertEqual([v["role_label"] for v in prof["verifiers"]], ["Organisasi terverifikasi"])
        self.assertEqual(prof["verifiers"][0]["verifier"], org.title)
        quick = rc.quick_status([member.account])[member.account]
        self.assertEqual((quick["status"], quick["verifiers"][0]["role_label"]),
                         ("organization_verified", "Organisasi terverifikasi"))

    def test_joined_but_identity_not_confirmed_is_not_verified(self):
        member = self.member(make_org(verification_status="verified"), confirmed=False)
        self.assertEqual(rc.verification_profile(member.account)["status"], "self_reported")
        self.assertEqual(rc.quick_status([member.account])[member.account]["status"], "self_reported")
        org_line = next(e for e in rc.verification_profile(member.account)["evidence"] if e["key"] == "org")
        self.assertIn("identitas belum dikonfirmasi", org_line["detail"])

    def test_confirmed_by_an_unverified_org_is_not_verified(self):
        member = self.member(make_org(verification_status="pending"), confirmed=True)
        self.assertEqual(rc.verification_profile(member.account)["status"], "self_reported")
        self.assertEqual(rc.quick_status([member.account])[member.account]["status"], "self_reported")
