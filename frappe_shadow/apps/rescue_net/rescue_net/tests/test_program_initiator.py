"""Owner 2026-11-08: "login lazismu harus langsung tampil halaman setting pemilik donasi program, masukin data,
rekening, qris, konfirmasi dana yang masuk, kemudian tampil di list". The program initiator (an approved member of
the owning organisation, without a posko) manages that ONE program; other members of the org do not."""

import base64

import frappe

from rescue_net import api_auth
from rescue_net import api_donor_program as api
from rescue_net.tests.factories import RNTestCase, as_guest, as_user, make_actor, make_event, make_org, make_posko

PNG = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32).decode()


class TestProgramInitiator(RNTestCase):
    def setUp(self):
        super().setUp()
        self.event = make_event(event_status="active")
        self.org = make_org(verification_status="verified")
        posko = make_posko(self.event, self.org)
        self.admin = make_actor(org=self.org, org_role="owner", posko=posko)
        self.lazis = make_actor(org=self.org, org_role="member")          # ortom account: member, no posko
        frappe.db.set_value("RN Organization Membership", {"user_account": self.lazis.account}, "member_verified", 1)
        self.other = make_actor(org=self.org, org_role="member")
        self.donor = make_actor(role="donatur")
        with as_user(self.lazis.user):                                    # the ortom starts its own program
            self.program = api.create_special_program(
                self.event.name, "Masker & oksigen", owner_type="organization", owner_id=self.org.name)["program"]

    def _detail(self, user):
        with as_user(user):
            return api.program_detail(self.program)

    def test_initiator_manages_program_end_to_end(self):
        self.assertTrue(self._detail(self.lazis.user)["can_manage"])
        with as_user(self.lazis.user):
            api.update_program_info(self.program, {"description": "Bantuan masker N95", "officer_in_charge_name": "Pak Amil",
                                                   "budget_target": "25000000", "program_name": "DIUBAH"})
            api.set_program_bank(self.program, bank_name="BSI", account_number="7000123456", account_holder="LAZISMU")
            api.upload_program_file(self.program, "qris", "qris.png", PNG)
        row = frappe.db.get_value("RN Donor Program", self.program,
                                  ["description", "officer_in_charge_name", "budget_target", "program_name"], as_dict=True)
        self.assertEqual(row.description, "Bantuan masker N95")
        self.assertEqual(row.budget_target, 25_000_000)
        self.assertEqual(row.program_name, "Masker & oksigen")          # name is not editable here
        with as_user(self.donor.user):
            don = api.create_cash_donation(self.program, 150_000, donor_name="Budi")["donation"]
        d = self._detail(self.lazis.user)
        self.assertEqual([p["name"] for p in d["donations"]["pending"]], [don])
        with as_user(self.lazis.user):
            api.decide_cash_donation(don, "confirm")
        with as_guest():
            pub = api.program_detail(self.program)
        self.assertEqual([r["amount"] for r in pub["donations"]["public"]], [150_000])
        self.assertTrue(pub["bank"]["qris_url"])
        self.assertEqual(pub["bank"]["account_number"], "7000123456")

    def test_other_member_and_former_member_cannot_manage(self):
        self.assertFalse(self._detail(self.other.user)["can_manage"])
        with as_user(self.other.user):
            with self.assertRaises(frappe.PermissionError):
                api.set_program_bank(self.program, bank_name="X", account_number="1234567", account_holder="Penipu")
            with self.assertRaises(frappe.PermissionError):
                api.update_program_info(self.program, {"description": "x"})
        frappe.db.set_value("RN Organization Membership",
                            {"user_account": self.lazis.account, "organization": self.org.name}, "status", "removed")
        self.assertFalse(self._detail(self.lazis.user)["can_manage"])

    def test_outsider_cannot_start_org_program(self):
        with as_user(self.donor.user):
            with self.assertRaises(frappe.PermissionError):
                api.create_special_program(self.event.name, "Palsu", owner_type="organization", owner_id=self.org.name)

    def test_unvouched_member_bank_stays_private(self):
        """A plain member the HQ hasn't vouched for may start a program, but its account/QRIS isn't published."""
        with as_user(self.other.user):
            prog = api.create_special_program(self.event.name, "Program anggota", owner_type="organization",
                                              owner_id=self.org.name)["program"]
            api.set_program_bank(prog, bank_name="BRI", account_number="1234567890", account_holder="Anggota")
            self.assertTrue(api.program_detail(prog)["can_manage"])
        with as_guest():
            try:
                bank = api.program_detail(prog)["bank"]
            except frappe.DoesNotExistError:
                bank = {}
        self.assertFalse(bank.get("account_number"))
        self.assertFalse(bank.get("shown_publicly"))

    def test_cancel_program_stops_donations(self):
        with as_user(self.donor.user):
            don = api.create_cash_donation(self.program, 10_000)["donation"]
        with as_user(self.lazis.user):
            api.set_program_status(self.program, "active")
            with self.assertRaisesRegex(frappe.ValidationError, "alasan"):
                api.set_program_status(self.program, "cancelled")
            with self.assertRaisesRegex(frappe.ValidationError, "menunggu konfirmasi"):
                api.set_program_status(self.program, "cancelled", note="Dobel")
            api.decide_cash_donation(don, "reject", note="uji")
            api.set_program_status(self.program, "cancelled", note="Program dobel, diganti program baru")
            with self.assertRaisesRegex(frappe.ValidationError, "tidak bisa diubah"):
                api.set_program_status(self.program, "active")
        with as_user(self.donor.user):
            with self.assertRaisesRegex(frappe.ValidationError, "dibatalkan"):
                api.create_cash_donation(self.program, 10_000)
        with as_user(self.other.user):
            with self.assertRaises(frappe.PermissionError):
                api.set_program_status(self.program, "completed")

    def test_cancelled_program_hidden_from_public(self):
        with as_user(self.lazis.user):
            api.set_program_status(self.program, "active")
            api.set_program_bank(self.program, bank_name="BSI", account_number="7000123456", account_holder="LAZISMU")
        with as_guest():
            self.assertIn(self.program, [p["name"] for p in api.program_board(self.event.name)["programs"]])
            self.assertEqual(api.program_detail(self.program)["bank"]["account_number"], "7000123456")   # public
        with as_user(self.lazis.user):
            api.set_program_status(self.program, "cancelled", note="dobel")
        with as_guest():
            self.assertNotIn(self.program, [p["name"] for p in api.program_board(self.event.name)["programs"]])
            with self.assertRaises(frappe.DoesNotExistError):
                api.program_detail(self.program)
        with as_user(self.lazis.user):                                    # the manager still finds it
            self.assertIn(self.program, [p["name"] for p in api.program_board(self.event.name)["programs"]])
            self.assertTrue(api.program_detail(self.program)["can_manage"])

    def test_dates_are_checked(self):
        with as_user(self.lazis.user):
            with self.assertRaisesRegex(frappe.ValidationError, "Tanggal selesai"):
                api.update_program_info(self.program, {"start_date": "2026-11-10", "end_date": "2026-11-01"})

    def test_initiator_lands_on_program_management(self):
        with as_user(self.lazis.user):
            href = api_auth.my_landing()["href"]
        self.assertTrue(href.startswith("program-khusus.html?program=" + self.program), href)
        self.assertIn("kelola=1", href)
        with as_user(self.admin.user):                                   # posko holders still land on their posko
            self.assertFalse(api_auth.my_landing()["href"].startswith("program-khusus"))
