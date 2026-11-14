"""Optional aid batch uploads: anonymous submission, privacy and edit-code access."""
import base64
import io
import json
from unittest import mock
from werkzeug.wrappers import Request

import frappe
from PIL import Image
from pypdf import PdfWriter
from rescue_net import api_files
from rescue_net.logistics import guest
from rescue_net.logistics.aid_attachments import MAX_BYTES, attachment_rows, can_read_attachments, validate_attachments
from rescue_net.tests.factories import RNTestCase, as_guest, as_user, make_actor, make_world, make_org, make_posko


def photo():
    out = io.BytesIO()
    Image.new("RGB", (3, 3), "red").save(out, format="PNG")
    return {"filename": "barang.png", "content_base64": base64.b64encode(out.getvalue()).decode()}


class TestAidAttachments(RNTestCase):
    def setUp(self):
        super().setUp()
        self.w = make_world()
        frappe.db.set_value("RN Posko", self.w.posko_a.name, {"public_detail": "public", "public_participation": 1, "accept_goods": 1})
        frappe.db.set_value("RN Organization", self.w.org_a.name, "allow_posko_public_choice", 1)
        self.op = make_actor(posko=self.w.posko_a)
        self.member = make_actor(org=self.w.org_a)
        self.other = make_actor(posko=self.w.posko_b)
        self.owner = make_actor(org=self.w.org_a, org_role="owner")

    def submit(self, attachments=None, user="Guest"):
        with as_user(user):
            return guest.submit_guest_aid_offer_multi(
                self.w.event.name, "Pengirim lampiran", "081355500011",
                json.dumps([{"item_text": "Beras", "quantity": 2, "unit": "kg"},
                            {"item_text": "Air", "quantity": 3, "unit": "L"}]),
                target_posko=self.w.posko_a.name, attachments_json=json.dumps(attachments or []))

    def test_no_attachment_keeps_existing_submission(self):
        out = self.submit()
        self.assertEqual(out["count"], 2)
        self.assertEqual(out["attachments"], [])

    def test_guest_files_private_and_shared_by_batch_not_by_public_lists(self):
        pdf = io.BytesIO()
        writer = PdfWriter(); writer.add_blank_page(width=100, height=100); writer.write(pdf)
        out = self.submit([photo(), {"filename": "daftar.pdf", "content_base64": base64.b64encode(pdf.getvalue()).decode()}])
        first, second = [r["aid_offer"] for r in out["aid_offers"]]
        rows = attachment_rows(frappe.get_doc("RN Aid Offer", second))
        self.assertEqual(len(rows), 2)
        for row in rows:
            f = frappe.get_doc("File", row.name)
            self.assertEqual(f.is_private, 1)
            self.assertNotEqual(f.owner, "Guest")
            self.assertTrue(f.file_url.startswith("/private/files/bantuan-"))
            self.assertEqual(f.attached_to_name, first)
        with as_guest():
            view = guest.get_guest_aid_offer(second, out["edit_code"], "081355500011")
            self.assertEqual(len(view["attachments"]), 2)
            self.assertNotIn("file_url", view["attachments"][0])
            self.assertFalse(api_files._can_read_private(rows[0]))
        for actor, expected in [(self.op, True), (self.owner, True), (self.member, False), (self.other, False)]:
            with as_user(actor.user):
                self.assertEqual(can_read_attachments(first), expected)
                self.assertEqual(api_files._can_read_private(rows[0]), expected)
                if expected:
                    self.assertEqual(len(guest.aid_attachments(second)), 2)
                else:
                    with self.assertRaises(frappe.PermissionError):
                        guest.aid_attachments(first)

    def test_shared_batch_covers_sibling_destination_but_not_unrelated_posko(self):
        out = self.submit([photo()])
        first, second = [r["aid_offer"] for r in out["aid_offers"]]
        # The form initially has one destination. A later operational reroute of
        # a sibling must not strand the batch evidence at only its first posko.
        frappe.db.set_value("RN Aid Offer", second, "target_posko", self.w.posko_b.name)
        third = make_posko(self.w.event, make_org())
        unrelated = make_actor(posko=third)
        file_row = attachment_rows(frappe.get_doc("RN Aid Offer", first))[0]
        with as_user(self.other.user):
            self.assertTrue(can_read_attachments(first))
            self.assertTrue(api_files._can_read_private(file_row))
        with as_user(unrelated.user):
            self.assertFalse(can_read_attachments(first))
            self.assertFalse(api_files._can_read_private(file_row))

    def test_same_private_bytes_can_be_submitted_in_another_guest_batch(self):
        first = self.submit([photo()])
        second = self.submit([photo()])
        self.assertNotEqual(first["aid_offers"][0]["aid_offer"], second["aid_offers"][0]["aid_offer"])
        self.assertNotEqual(first["attachments"][0]["name"], second["attachments"][0]["name"])
        with as_guest():
            self.assertFalse(api_files._can_read_private(attachment_rows(frappe.get_doc("RN Aid Offer", second["aid_offers"][0]["aid_offer"]))[0]))

    def test_same_bytes_as_public_file_stays_private(self):
        from frappe.utils.file_manager import save_file
        payload = photo()
        # Use the normalized image bytes, exactly as the attachment path saves them.
        normalized = validate_attachments([payload])[0][2]
        public = save_file("public-photo.png", normalized, None, None, is_private=0)
        out = self.submit([payload])
        private = frappe.get_doc("File", out["attachments"][0]["name"])
        self.assertTrue(public.file_url.startswith("/files/"))
        self.assertTrue(private.file_url.startswith("/private/files/"))
        self.assertNotEqual(private.file_url, public.file_url)
        self.assertEqual(private.is_private, 1)

    def test_logged_sender_can_read_without_posko_membership(self):
        out = self.submit([photo()], user=self.other.user)
        first = out["aid_offers"][0]["aid_offer"]
        with as_user(self.other.user):
            self.assertTrue(can_read_attachments(first))

    def test_guest_download_requires_right_code_phone_and_attachment(self):
        out = self.submit([photo()])
        first = out["aid_offers"][0]["aid_offer"]
        name = out["attachments"][0]["name"]
        with as_guest(), mock.patch.object(frappe.local, "request_ip", "attachment-" + frappe.generate_hash(length=10), create=True), mock.patch.object(frappe.local, "request", Request.from_values(method="POST", base_url="http://rescuenet-test.localhost"), create=True):
            result = guest.guest_aid_attachment(first, out["edit_code"], "081355500011", name)
            self.assertEqual(result["file_name"], "barang.png")
            self.assertTrue(base64.b64decode(result["content_base64"]).startswith(b"\x89PNG"))
            for code, phone, attachment in [("WRONG", "081355500011", name), (out["edit_code"], "080000000", name),
                                             (out["edit_code"], "", name), (out["edit_code"], "081355500011", "other")]:
                with self.assertRaises(frappe.PermissionError):
                    guest.guest_aid_attachment(first, code, phone, attachment)
        with as_guest(), mock.patch.object(frappe.local, "request_ip", "attachment-" + frappe.generate_hash(length=10), create=True), mock.patch.object(frappe.local, "request", Request.from_values(method="GET", base_url="http://rescuenet-test.localhost"), create=True):
            with self.assertRaises(frappe.PermissionError):
                guest.guest_aid_attachment(first, out["edit_code"], "081355500011", name)

    def test_image_metadata_is_removed_and_active_pdf_refused(self):
        from PIL.PngImagePlugin import PngInfo
        meta = PngInfo(); meta.add_text("GPS", "private test coordinates")
        image = io.BytesIO()
        Image.new("RGB", (2, 2), "blue").save(image, format="PNG", pnginfo=meta)
        clean = validate_attachments([{"filename": "camera.png", "content_base64": base64.b64encode(image.getvalue()).decode()}])[0][2]
        self.assertNotIn("GPS", Image.open(io.BytesIO(clean)).info)
        writer = PdfWriter(); writer.add_blank_page(width=100, height=100); writer.add_js("app.alert('test')")
        doc = io.BytesIO(); writer.write(doc)
        with self.assertRaises(frappe.ValidationError):
            validate_attachments([{"filename": "active.pdf", "content_base64": base64.b64encode(doc.getvalue()).decode()}])

    def test_invalid_upload_rejected_before_aid_insert(self):
        before = frappe.db.count("RN Aid Offer")
        with self.assertRaises(frappe.ValidationError):
            self.submit([{"filename": "fake.png", "content_base64": base64.b64encode(b"<script>bad</script>").decode()}])
        self.assertEqual(frappe.db.count("RN Aid Offer"), before)

    def test_limits_type_paths_and_base64(self):
        valid = photo()
        for value in [[valid] * 4, [{**valid, "filename": "../image.png"}], [{**valid, "filename": "file.html"}], [{**valid, "filename": "a" * 141 + ".png"}],
                      [{**valid, "filename": "wrong.jpg"}], [{**valid, "content_base64": "!invalid!"}],
                      [{**valid, "content_base64": ""}], [{**valid, "content_base64": "A" * ((MAX_BYTES + 2) // 3 * 4 + 4)}],
                      {"filename": "bad"}, "not json"]:
            with self.subTest(value_type=type(value).__name__), self.assertRaises(frappe.ValidationError):
                validate_attachments(value)
