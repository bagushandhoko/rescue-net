"""Laporan Masyarakat: a phone number the verifier can call. Mandatory for a Google login
(owner 2026-10-08), optional for others, normalised, remembered on the account, shown by session_info."""

import frappe

from rescue_net import api_auth
from rescue_net import api_reports as api
from rescue_net.services import reporter
from rescue_net.tests.factories import RNTestCase, as_user, make_actor, make_event

TEXT = "Sumur di Dusun Oebelo kering sejak 2 bulan, 50 KK kekurangan air bersih."


def link_google(user):
    doc = frappe.get_doc("User", user)
    doc.append("social_logins", {"provider": "google", "userid": "g-" + user})
    doc.save(ignore_permissions=True)


class TestNormalize(RNTestCase):
    def test_accepts_common_indonesian_forms(self):
        for raw in ("081234567890", "+62 812-3456-7890", "6281234567890", "(0812) 3456 7890"):
            self.assertEqual(reporter.normalize_phone(raw), "081234567890", raw)

    def test_rejects_non_mobile_or_garbage(self):
        for raw in ("", None, "12345", "021123456", "abc", "0712345678901", "+1 555 123 4567"):
            self.assertIsNone(reporter.normalize_phone(raw), raw)


class TestPhoneOnReports(RNTestCase):
    def setUp(self):
        super().setUp()
        self.event = make_event()

    def submit(self, user, **kw):
        with as_user(user):
            return api.submit_community_report(description=TEXT, intake_mode="narrative",
                                               disaster_event=self.event.name, **kw)

    def test_google_login_without_phone_is_refused(self):
        actor = make_actor(role="citizen")
        link_google(actor.user)
        with self.assertRaises(frappe.ValidationError):
            self.submit(actor.user)

    def test_google_login_with_phone_stores_it_and_remembers_it(self):
        actor = make_actor(role="citizen")
        link_google(actor.user)
        out = self.submit(actor.user, reporter_phone="+62 812-3456-7890")
        self.assertEqual(frappe.db.get_value("RN Community Report", out["name"], "reporter_phone"), "081234567890")
        self.assertEqual(frappe.db.get_value("RN User Account", actor.account, "phone"), "081234567890")
        # next report needs no typing: the number saved on the account is used
        out2 = self.submit(actor.user)
        self.assertEqual(frappe.db.get_value("RN Community Report", out2["name"], "reporter_phone"), "081234567890")

    def test_invalid_number_is_refused_even_for_password_login(self):
        actor = make_actor(role="citizen")
        with self.assertRaises(frappe.ValidationError):
            self.submit(actor.user, reporter_phone="12345")

    def test_password_login_may_leave_it_empty(self):
        actor = make_actor(role="citizen")
        out = self.submit(actor.user)
        self.assertFalse(frappe.db.get_value("RN Community Report", out["name"], "reporter_phone"))

    def test_session_info_tells_the_page_which_rule_applies(self):
        actor = make_actor(role="citizen", phone="081200000001")
        link_google(actor.user)
        with as_user(actor.user):
            info = api_auth.session_info()
        self.assertEqual(info["login_provider"], "google")
        self.assertEqual(info["phone"], "081200000001")
        plain = make_actor(role="citizen")
        with as_user(plain.user):
            info = api_auth.session_info()
        self.assertEqual(info["login_provider"], "password")
        self.assertIsNone(info["phone"])
