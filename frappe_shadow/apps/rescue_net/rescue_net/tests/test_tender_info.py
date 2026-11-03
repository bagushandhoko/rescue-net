"""Owner 2026-11-03: a tender carries gambar kerja uploads, a work schedule (target selesai) and the usual
tender information (syarat peserta, dokumen wajib, email penawaran, ...). Only the organiser edits it;
everyone sees it on the public detail."""

import base64

import frappe
from frappe.utils import add_days, getdate, now_datetime

from rescue_net import api_tender as api
from rescue_net.tests import test_program_documents as _docs
from rescue_net.tests.factories import RNTestCase, api_call, as_guest, as_user, make_actor, make_event, make_org

PNG = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32).decode()
PDF = _docs.PDF  # a valid PDF (module import keeps its test class out of this module)
EXE = base64.b64encode(b"MZ\x90\x00not a pdf").decode()


class TestTenderInfo(RNTestCase):
    def setUp(self):
        super().setUp()
        self.event = make_event(event_status="active")
        self.org = make_org(verification_status="verified")
        self.owner = make_actor(org=self.org, org_role="owner")
        self.stranger = make_actor()
        self.closes = add_days(now_datetime(), 7)
        with as_user(self.owner.user):
            self.tender = api.create_tender(
                self.event.name, "Rehab 2 ruang kelas", rab_total=250_000_000, organization=self.org.name,
                bidding_closes_at=str(self.closes), tender_category="construction",
                work_start_date=str(add_days(getdate(), 14)), target_completion_date=str(add_days(getdate(), 74)),
                work_duration_days=60, maintenance_days=90,
                bidder_requirements="Badan usaha berizin (NIB), SBU konstruksi BG, pengalaman 3 tahun",
                required_documents="Surat penawaran, RAB penawaran, jadwal pelaksanaan",
                bid_submission_email="Tender@Contoh.org", evaluation_method="lowest_price",
                bid_validity_days=30, payment_terms="Termin 30-40-30")["tender"]

    def test_info_is_saved_and_public(self):
        with as_guest():
            d = api_call("rescue_net.api_tender.tender_detail", tender=self.tender)
        self.assertTrue(d["found"])
        self.assertEqual(d["bid_submission_email"], "tender@contoh.org")
        self.assertIn("SBU", d["bidder_requirements"])
        self.assertEqual(d["work_duration_days"], 60)
        self.assertEqual(str(d["target_completion_date"]), str(add_days(getdate(), 74)))
        self.assertEqual(d["category_label"], "Pekerjaan Konstruksi")
        self.assertFalse(d["can_manage"])
        with as_guest():
            board = api_call("rescue_net.api_tender.tender_board", disaster_event=self.event.name)
        row = [t for t in board["tenders"] if t["name"] == self.tender][0]
        self.assertEqual(row["work_duration_days"], 60)
        self.assertNotIn("work_drawings", row)

    def test_bad_values_refused(self):
        with as_user(self.owner.user):
            for bad in ({"bid_submission_email": "bukan-email"},
                        {"tender_category": "x"},
                        {"work_duration_days": -1},
                        {"work_start_date": str(add_days(getdate(), 30)), "target_completion_date": str(add_days(getdate(), 20))},
                        {"target_completion_date": str(getdate())}):          # before bidding closes
                with self.assertRaises(frappe.ValidationError, msg=str(bad)):
                    api.update_tender_info(self.tender, **bad)

    def test_only_the_organiser_edits(self):
        with as_user(self.stranger.user), self.assertRaises(frappe.PermissionError):
            api.update_tender_info(self.tender, bidder_requirements="diganti orang lain")
        with as_user(self.stranger.user), self.assertRaises(frappe.PermissionError):
            api.upload_tender_file(self.tender, "denah.png", PNG)
        with as_guest(), self.assertRaises(frappe.PermissionError):
            api_call("rescue_net.api_tender.update_tender_info", tender=self.tender, payment_terms="x")
        with as_guest(), self.assertRaises(frappe.PermissionError):
            api_call("rescue_net.api_tender.upload_tender_file", tender=self.tender, filename="a.png",
                     content_base64=PNG)
        with as_user(self.owner.user):
            d = api.update_tender_info(self.tender, bidder_requirements="Syarat baru", payment_terms="")
        self.assertEqual(d["bidder_requirements"], "Syarat baru")
        self.assertFalse(d["payment_terms"])
        self.assertTrue(d["can_manage"])

    def test_drawings_and_rab_pages(self):
        with as_user(self.owner.user):
            docs = api.upload_tender_file(self.tender, "denah lantai.png", PNG, label="Denah")
            self.assertEqual(len(docs["drawings"]), 1)
            self.assertEqual(docs["drawings"][0]["label"], "Denah")
            docs = api.upload_tender_file(self.tender, "rab-1.pdf", PDF, kind="rab")
            self.assertEqual(len(docs["rab_pages"]), 1)
            rab_url = docs["rab_pages"][0]["url"]
            self.assertEqual(frappe.db.get_value("RN Procurement Tender", self.tender, "rab_document_url"), rab_url)
            with self.assertRaises(frappe.ValidationError):
                api.upload_tender_file(self.tender, "virus.png", EXE)
            docs = api.remove_tender_file(self.tender, rab_url)
            self.assertEqual(docs["rab_pages"], [])
            self.assertFalse(frappe.db.get_value("RN Procurement Tender", self.tender, "rab_document_url"))
        with as_guest():
            d = api_call("rescue_net.api_tender.tender_detail", tender=self.tender)
        self.assertEqual([x["label"] for x in d["drawings"]], ["Denah"])

    def test_awarded_tender_is_frozen(self):
        bid = api.submit_bid(self.tender, "CV Uji", 2e8)["bid"]
        with as_user(self.owner.user):
            api.set_bid_status(bid, "awarded")
            with self.assertRaises(frappe.ValidationError):
                api.update_tender_info(self.tender, payment_terms="ubah setelah menang")
