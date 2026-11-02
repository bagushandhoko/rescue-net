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

    def test_rab_several_pages_pdf_or_image(self):
        """Owner 2026-11-02: "anggaran bisa beberapa halaman"."""
        with as_user(self.owner.user):
            first = api.upload_program_file(self.program, "rab", "RAB hal 1.pdf", PDF)["rab"]
            api.upload_program_file(self.program, "rab", "RAB hal 2.png", PNG, label="Halaman 2")
            r = api.upload_program_file(self.program, "gambar", "denah.png", PNG)
        self.assertEqual([p["name"] for p in r["rab_pages"]], ["RAB hal 1.pdf", "RAB hal 2.png"])
        self.assertEqual(r["rab"], first)                              # first page stays the "main" RAB file
        self.assertEqual([d["name"] for d in r["drawings"]], ["denah.png"])  # RAB pages never mix with drawings
        self.assertEqual(frappe.db.get_value("RN Donor Program", self.program, "rab_file_url"), first)
        with as_user(self.owner.user):
            r = api.remove_program_file(self.program, "rab", first)
        self.assertEqual([p["name"] for p in r["rab_pages"]], ["RAB hal 2.png"])
        self.assertEqual(frappe.db.get_value("RN Donor Program", self.program, "rab_file_url"), r["rab"])
        self.assertEqual(len(self._detail()["documents"]["rab_pages"]), 1)

    def test_old_single_rab_pdf_is_page_one(self):
        frappe.db.set_value("RN Donor Program", self.program, "rab_file_url", "/files/rab-lama.pdf")
        with as_user(self.owner.user):
            r = api.upload_program_file(self.program, "rab", "lampiran.pdf", PDF)
        self.assertEqual([p["url"] for p in r["rab_pages"]][0], "/files/rab-lama.pdf")
        self.assertEqual(len(r["rab_pages"]), 2)

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


class TestProgramKpi(RNTestCase):
    """Owner 2026-11-02: the three Program Khusus menus summarised in the Control Centre KPI."""

    def test_kpi_matches_the_three_boards(self):
        event = make_event(event_status="active")
        org = make_org(verification_status="verified")
        owner = make_actor(org=org, org_role="owner", posko=make_posko(event, org))
        with as_user(owner.user):
            p = api.create_special_program(event.name, "Dapur umum", owner_type="organization", owner_id=org.name,
                                           budget_target=10_000_000)["program"]
        frappe.db.set_value("RN Donor Program", p, "public_visibility", "summary_public")
        donor = make_actor()
        with as_user(donor.user):
            d1 = api.create_cash_donation(p, 1_000_000)["donation"]
            d2 = api.create_cash_donation(p, 500_000, is_anonymous=1)["donation"]
        with as_user(owner.user):
            api.decide_cash_donation(d1, "confirm")
            api.decide_cash_donation(d2, "confirm")
        with as_guest():
            k = api.program_kpi(event.name)
            don = api.donation_summary(event.name)
            wall = api.program_donations(p)
        self.assertEqual(k["donor"]["received"], 1_500_000)
        self.assertEqual(k["donor"]["received"], don["received_total"])
        self.assertEqual(k["donor"]["donors"], 2)
        self.assertIn("Donatur Anonim", [r["donor_name"] for r in wall["public"]])
        self.assertEqual(wall["total_received"], 1_500_000)
        for part in ("donor", "tender", "tracking"):
            self.assertIn(part, k)


class TestProgramPhotoEvidence(RNTestCase):
    """Owner 2026-11-02 (simulasi bukti foto Krakatau): a photo uploaded on Bukti Lapangan and linked to a
    program shows up among that program's bukti."""

    def test_linked_photo_is_program_evidence(self):
        from rescue_net.frontend_bridge.map_evidence import upload_evidence
        event = make_event(event_status="active")
        org = make_org(verification_status="verified")
        posko = make_posko(event, org)
        owner = make_actor(org=org, org_role="owner", posko=posko)
        with as_user(owner.user):
            p = api.create_special_program(event.name, "Sekolah darurat", owner_type="organization", owner_id=org.name,
                                           budget_target=10_000_000)["program"]
            upload_evidence("foto.png", PNG, event.name, node_id=posko.name, linked_object_type="donor_program",
                            linked_object_id=p, evidence_type="photo", caption="Lokasi sekolah darurat (simulasi)")
            other = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x01" * 40).decode()   # different file
            upload_evidence("lain.png", other, event.name, node_id=posko.name, caption="Foto lain")
        frappe.db.set_value("RN Donor Program", p, "public_visibility", "summary_public")
        with as_user(owner.user):
            bukti = api.program_detail(p)["bukti"]
        self.assertEqual([b.get("caption") for b in bukti], ["Lokasi sekolah darurat (simulasi)"])
