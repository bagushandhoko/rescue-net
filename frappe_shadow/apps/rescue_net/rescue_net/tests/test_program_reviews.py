"""Owner 2026-11-02 22:40 (dikerjakan 2026-11-09): ulasan publik untuk memantau kerja & respons penyelenggara program."""

import frappe

from rescue_net import api_donor_program as api
from rescue_net.tests.factories import RNTestCase, as_guest, as_user, make_actor, make_event, make_org, make_posko


class TestProgramReviews(RNTestCase):
    def setUp(self):
        super().setUp()
        self.event = make_event(event_status="active")
        self.org = make_org(verification_status="verified")
        posko = make_posko(self.event, self.org)
        self.admin = make_actor(org=self.org, org_role="owner", posko=posko)
        self.public = make_actor(role="donatur")
        self.public2 = make_actor(role="donatur")
        with as_user(self.admin.user):
            self.program = api.create_special_program(
                self.event.name, "Air bersih", owner_type="organization", owner_id=self.org.name)["program"]

    def test_review_reply_and_public_view(self):
        with as_user(self.public.user):
            api.submit_review(self.program, 4, "Respons cepat")
            out = api.submit_review(self.program, 5, "Respons cepat, laporan lengkap")   # same user -> update
        self.assertTrue(out["updated"])
        with as_user(self.public2.user):
            api.submit_review(self.program, 3, "Laporan telat", anonymous=1)
        with as_guest():
            pub = api.program_reviews(self.program)
        self.assertEqual((pub["count"], pub["average"]), (2, 4.0))
        self.assertTrue(pub["login_required"])
        self.assertIn("Anonim", [r["reviewer"] for r in pub["reviews"]])
        self.assertNotIn("user_account", pub["reviews"][0])
        rid = [r["name"] for r in pub["reviews"] if r["rating"] == 3][0]
        with as_user(self.public.user), self.assertRaises(frappe.PermissionError):
            api.reply_review(rid, "bukan pengelola")
        with as_user(self.admin.user):
            self.assertTrue(api.program_reviews(self.program)["can_reply"])
            api.reply_review(rid, "Mohon maaf, laporan sudah kami unggah.")
        with as_guest():
            r = [x for x in api.program_reviews(self.program)["reviews"] if x["name"] == rid][0]
        self.assertEqual(r["reply"], "Mohon maaf, laporan sudah kami unggah.")

    def test_rules(self):
        with as_user(self.admin.user), self.assertRaises(frappe.PermissionError):
            api.submit_review(self.program, 5, "program sendiri")
        with as_guest(), self.assertRaisesRegex(frappe.ValidationError, "Login"):
            api.submit_review(self.program, 5)
        with as_user(self.public.user), self.assertRaises(frappe.ValidationError):
            api.submit_review(self.program, 9)
        with as_user(self.public.user):
            rid = api.submit_review(self.program, 1, "spam")["review"]
        with as_user(self.public2.user), self.assertRaises(frappe.PermissionError):
            api.moderate_review(rid, "hidden", "spam")
        frappe.set_user("Administrator")
        api.moderate_review(rid, "hidden", "spam")
        with as_guest():
            self.assertEqual(api.program_reviews(self.program)["count"], 0)
