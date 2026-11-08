"""Menu Saran (owner 2026-11-03): tamu boleh kirim saran, kontak pengirim tidak tampil ke publik,
status hanya diubah System Manager, saran tidak masuk forum Masukan Masyarakat per bencana."""

import frappe

from rescue_net import api_forum, api_saran
from rescue_net.tests.factories import RNTestCase, as_guest, as_user, make_actor


class TestSaran(RNTestCase):
    def submit(self, **kw):
        with as_guest():
            return api_saran.submit_suggestion(body=kw.pop("body", "Tolong tambahkan mode gelap di peta posko"),
                                               category=kw.pop("category", "fitur"), **kw)

    def test_guest_submits_and_contact_stays_private(self):
        r = self.submit(author_name="Budi", author_contact="0812-rahasia-99", page="peta-posko")
        self.assertTrue(r["saved"])
        with as_guest():
            rows = api_saran.list_suggestions()["suggestions"]
        mine = [x for x in rows if x["name"] == r["suggestion"]]
        self.assertEqual(len(mine), 1)
        self.assertEqual((mine[0]["author_name"], mine[0]["category"], mine[0]["status"], mine[0]["page"]),
                         ("Budi", "fitur", "baru", "peta-posko"))
        self.assertNotIn("author_contact", mine[0])
        self.assertNotIn("0812-rahasia-99", frappe.as_json(rows))
        with as_user("Administrator"):
            adm = [x for x in api_saran.list_suggestions()["suggestions"] if x["name"] == r["suggestion"]]
        self.assertEqual(adm[0]["author_contact"], "0812-rahasia-99")

    def test_honeypot_and_too_short(self):
        before = frappe.db.count("RN Community Feedback")
        with as_guest():
            self.assertTrue(api_saran.submit_suggestion(body="spam spam spam spam", website="http://x")["saved"])
        self.assertEqual(frappe.db.count("RN Community Feedback"), before)
        with as_guest(), self.assertRaises(frappe.ValidationError):
            api_saran.submit_suggestion(body="pendek")

    def test_only_system_manager_sets_status(self):
        name = self.submit(category="bug", body="Tombol simpan di HP tertutup menu")["suggestion"]
        other = make_actor(role="command_center")
        for ctx in (as_guest(), as_user(other.user)):
            with ctx, self.assertRaises(frappe.PermissionError):
                api_saran.set_suggestion_status(name, "selesai")
        with as_user("Administrator"):
            api_saran.set_suggestion_status(name, "dikerjakan", response="Sedang diperbaiki")
        with as_guest():
            row = [x for x in api_saran.list_suggestions()["suggestions"] if x["name"] == name][0]
        self.assertEqual((row["status"], row["response"], row["category"]), ("dikerjakan", "Sedang diperbaiki", "bug"))
        with as_user("Administrator"):
            api_saran.set_suggestion_status(name, "disembunyikan")
        with as_guest():
            self.assertNotIn(name, [x["name"] for x in api_saran.list_suggestions()["suggestions"]])

    def test_support_and_not_in_disaster_forum(self):
        name = self.submit()["suggestion"]
        with as_guest():
            self.assertEqual(api_saran.support_suggestion(name)["upvotes"], 1)
            threads = api_forum.feedback_threads()["threads"]
        self.assertNotIn(name, [t["name"] for t in threads])
