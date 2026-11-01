"""Program Khusus (owner 2026-11-01): RAB PDF + gambar kerja uploads, initiator bank account shown only while
the initiator is verified, verified badge, donation wall shows name or "anonim" only after confirmation."""

import base64

import frappe

from rescue_net import api_donor_program as api
from rescue_net.tests.factories import RNTestCase, as_guest, as_user, make_actor, make_event, make_org, make_posko



def _pdf():
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] >>"]
    out, offs = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offs)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    return out


PDF = base64.b64encode(_pdf()).decode()
PNG = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32).decode()
EXE = base64.b64encode(b"MZ\x90\x00not a pdf").decode()


class TestProgramDocuments(RNTestCase):
    def setUp(self):
        super().setUp()
        self.event = make_event(event_status="active")
        self.org = make_org(verification_status="verified")
        posko = make_posko(self.event, self.org)
        self.owner = make_actor(org=self.org, org_role="owner", posko=posko)
        self.stranger = make_actor()
        with as_user(self.owner.user):
            self.program = api.create_special_program(
                self.event.name, "Rehab sekolah", owner_type="organization", owner_id=self.org.name,
                budget_target=50_000_000)["program"]

    def _detail(self, user=None):
        if user:
            with as_user(user):
                return api.program_detail(self.program)
        with as_guest():
            return api.program_detail(self.program)

    def test_upload_rab_pdf_and_drawings(self):
        with as_user(self.owner.user):
            with self.assertRaisesRegex(frappe.ValidationError, "PDF"):
                api.upload_program_file(self.program, "rab", "rab.pdf", EXE)
            with self.assertRaisesRegex(frappe.ValidationError, "PDF"):
                api.upload_program_file(self.program, "rab", "rab.png", PNG)
            r = api.upload_program_file(self.program, "rab", "RAB sekolah.pdf", PDF)
            self.assertTrue(r["rab"].endswith(".pdf"))
            api.upload_program_file(self.program, "gambar", "denah.png", PNG, label="Denah")
            r = api.upload_program_file(self.program, "gambar", "potongan.pdf", PDF)
            self.assertEqual([d["label"] or d["name"] for d in r["drawings"]], ["Denah", "potongan.pdf"])
            with self.assertRaisesRegex(frappe.ValidationError, "gambar"):
                api.upload_program_file(self.program, "gambar", "virus.exe", EXE)
        d = self._detail()
        self.assertTrue(d["documents"]["rab"])
        self.assertEqual(len(d["documents"]["drawings"]), 2)
        with as_user(self.owner.user):
            r = api.remove_program_file(self.program, "gambar", d["documents"]["drawings"][0]["url"])
        self.assertEqual(len(r["drawings"]), 1)

    def test_only_manager_uploads_and_sets_bank(self):
        with as_user(self.stranger.user):
            with self.assertRaises(frappe.PermissionError):
                api.upload_program_file(self.program, "rab", "rab.pdf", PDF)
            with self.assertRaises(frappe.PermissionError):
                api.set_program_bank(self.program, "BRI", "1234567890", "Yayasan Uji")

    def test_bank_public_only_when_verified(self):
        with as_user(self.owner.user):
            with self.assertRaisesRegex(frappe.ValidationError, "angka"):
                api.set_program_bank(self.program, "BRI", "12-ab", "Yayasan Uji")
            api.set_program_bank(self.program, "BRI", "0123 4567 890", "Yayasan Uji")
        g = self._detail()
        self.assertTrue(g["initiator_verified"])
        self.assertEqual(g["bank"]["account_number"], "01234567890")
        self.assertTrue(g["bank"]["shown_publicly"])

        # initiator loses verification: badge flips, number hidden from the public, owner still sees it
        frappe.db.set_value("RN Organization", self.org.name, "verification_status", "pending")
        g = self._detail()
        self.assertFalse(g["initiator_verified"])
        self.assertEqual(g["bank"]["account_number"], "")
        self.assertTrue(g["bank"]["available"])
        self.assertNotIn("01234567890", frappe.as_json(g))
        o = self._detail(self.owner.user)
        self.assertEqual(o["bank"]["account_number"], "01234567890")
        self.assertFalse(o["bank"]["shown_publicly"])

    def test_board_badge(self):
        with as_guest():
            rows = api.program_board(self.event.name)["programs"]
        row = [p for p in rows if p["name"] == self.program][0]
        self.assertTrue(row["initiator_verified"])

    def test_donation_wall_name_or_anonymous_after_confirm(self):
        donor = make_actor()
        with as_user(donor.user):
            named = api.create_cash_donation(self.program, 100_000, donor_name="Budi Uji")["donation"]
            anon = api.create_cash_donation(self.program, 50_000, is_anonymous=1, donor_name="Rahasia Uji")["donation"]
        self.assertEqual(self._detail()["donations"]["public"], [])  # not shown until the initiator checks
        with as_user(self.owner.user):
            api.decide_cash_donation(named, "confirm")
            api.decide_cash_donation(anon, "confirm")
        wall = self._detail()["donations"]
        self.assertEqual(sorted(r["donor_name"] for r in wall["public"]), ["Budi Uji", "Donatur Anonim"])
        self.assertNotIn("Rahasia Uji", frappe.as_json(wall))
