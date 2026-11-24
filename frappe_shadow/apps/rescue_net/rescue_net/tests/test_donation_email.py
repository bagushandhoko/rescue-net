"""Email ke donatur (owner 24 Nov 2026): terkirim saat donasi dikirim & saat diputuskan; tanpa akun email keluar
tidak ada yang diantrekan; akun demo/uji tidak dikirimi; galat email tidak menggagalkan donasi."""

from unittest.mock import patch

import frappe

from rescue_net import api_donor_program as api
from rescue_net.services import donation_email as de
from rescue_net.tests.factories import RNTestCase, as_user, make_actor, make_event, make_org, make_posko


class TestDonationEmail(RNTestCase):
    def setUp(self):
        super().setUp()
        ev = make_event(event_status="active")
        org = make_org(verification_status="verified")
        make_posko(ev, org)
        self.lazis = make_actor(org=org, org_role="member")
        frappe.db.set_value("RN Organization Membership", {"user_account": self.lazis.account}, "member_verified", 1)
        self.donor = make_actor(role="donatur")
        with as_user(self.lazis.user):
            self.program = api.create_special_program(ev.name, "Air bersih", owner_type="organization", owner_id=org.name)["program"]
            api.set_program_bank(self.program, bank_name="BSI", account_number="7000123456", account_holder="LAZISMU")

    def _donate(self, **kw):
        with as_user(self.donor.user):
            return api.create_cash_donation(self.program, 50_000, donor_name="Budi", **kw)

    def test_created_and_decided_emails(self):
        with patch.object(de, "outgoing_ready", return_value=True), patch("frappe.sendmail") as sm:
            r = self._donate(donor_contact="Budi@Contoh.id")
            self.assertTrue(r["emailed"])
            kw = sm.call_args.kwargs
            self.assertEqual(kw["recipients"], ["budi@contoh.id"])
            self.assertIn("Rp 50.000", kw["subject"])
            self.assertIn("7000123456", kw["message"])
            with as_user(self.lazis.user):
                api.decide_cash_donation(r["donation"], "confirm")
            self.assertEqual(sm.call_count, 2)
            self.assertIn("sudah diterima", sm.call_args.kwargs["subject"])

    def test_no_outgoing_account_or_demo_address_sends_nothing(self):
        with patch.object(de, "outgoing_ready", return_value=False), patch("frappe.sendmail") as sm:
            self.assertFalse(self._donate(donor_contact="budi@contoh.id")["emailed"])
        with patch.object(de, "outgoing_ready", return_value=True), patch("frappe.sendmail") as sm2:
            self.assertFalse(self._donate()["emailed"])                    # akun uji @test.rescue-net.local
            self.assertFalse(self._donate(donor_contact="08123456789")["emailed"])
        sm.assert_not_called(); sm2.assert_not_called()

    def test_email_failure_never_blocks_donation(self):
        with patch.object(de, "outgoing_ready", return_value=True), patch("frappe.sendmail", side_effect=Exception("smtp")):
            r = self._donate(donor_contact="budi@contoh.id")
        self.assertFalse(r["emailed"])
        self.assertTrue(frappe.db.exists("RN Cash Donation", r["donation"]))
