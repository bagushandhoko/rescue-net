"""2FA without email (2026-10-26): setup on screen, enforcement only after own setup."""

import frappe
import pyotp

from rescue_net import api_twofa
from rescue_net.tests.factories import RNTestCase, as_guest, as_user, make_actor


class TestTwoFactor(RNTestCase):
    def test_setup_then_verify_marks_setup_done(self):
        u = make_actor().user
        with as_user(u):
            r = api_twofa.setup_start()
            self.assertTrue(r["qr_svg_base64"])
            self.assertFalse(api_twofa.status()["setup_done"])
            with self.assertRaises(frappe.ValidationError):
                api_twofa.setup_verify("000000")
            st = api_twofa.setup_verify(pyotp.TOTP(r["secret"]).now())
        self.assertTrue(st["setup_done"])

    def test_enforcement_needs_system_manager_and_own_setup(self):
        u = make_actor().user
        with as_user(u), self.assertRaises(frappe.PermissionError):
            api_twofa.set_admin_enforcement(1)
        # Administrator (tests run as Administrator) has not set up an app yet
        with self.assertRaisesRegex(frappe.ValidationError, "Siapkan dulu"):
            api_twofa.set_admin_enforcement(1)
        secret = api_twofa.setup_start()["secret"]
        api_twofa.setup_verify(pyotp.TOTP(secret).now())
        st = api_twofa.set_admin_enforcement(1)
        self.assertTrue(st["enforced_for_admin"])
        self.assertFalse(api_twofa.set_admin_enforcement(0)["enforced_for_admin"])

    def test_guest_refused(self):
        with as_guest(), self.assertRaises(frappe.PermissionError):
            api_twofa.status()
