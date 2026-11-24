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


class TestOwnerTwoFactor(RNTestCase):
    """owner 2026-11-24: 2FA wajib hanya pemilik organisasi tertutup (bukan akun demo), tanpa mengunci login."""

    def _owner(self, privacy="closed", org_role="owner"):
        from rescue_net.tests.factories import make_org
        org = make_org(privacy_mode=privacy)
        return make_actor(org=org, org_role=org_role).user

    def _call(self, path):
        import types
        frappe.local.request = types.SimpleNamespace(path=path)
        try:
            api_twofa.before_request()
        finally:
            del frappe.local.request

    def _sid(self, sid):
        frappe.session.sid = sid

    def test_only_closed_org_owner_required(self):
        self.assertTrue(api_twofa.closed_org_owner(self._owner(), use_cache=False))
        self.assertFalse(api_twofa.closed_org_owner(self._owner(privacy="open"), use_cache=False))
        self.assertFalse(api_twofa.closed_org_owner(self._owner(org_role="member"), use_cache=False))
        self.assertFalse(api_twofa.closed_org_owner(make_actor().user, use_cache=False))

    def test_demo_account_exempt(self):
        from rescue_net.tests.factories import make_org, make_user
        org = make_org(privacy_mode="closed")
        demo = make_actor(org=org, org_role="owner", user=make_user(email="pemilik-x@rescue-net.local")).user
        self.assertFalse(api_twofa.closed_org_owner(demo, use_cache=False))

    def test_owner_blocked_until_setup_then_verified_session(self):
        u = self._owner()
        with as_user(u):
            self._sid("sid-owner-1")
            self.assertEqual(api_twofa.required_state(), "setup")
            with self.assertRaisesRegex(frappe.PermissionError, "RN_2FA_WAJIB"):
                self._call("/api/method/rescue_net.api_posko_manage.my_managed_poskos")
            # API 2FA & sesi tetap terbuka (tidak terkunci)
            self._call("/api/method/rescue_net.api_twofa.status")
            self._call("/api/method/rescue_net.api_auth.session_info")
            secret = api_twofa.setup_start()["secret"]
            st = api_twofa.setup_verify(pyotp.TOTP(secret).now())
            self.assertIsNone(st["required_state"])
            self._call("/api/method/rescue_net.api_posko_manage.my_managed_poskos")
        # peran 2FA Frappe aktif -> login sandi berikutnya meminta kode
        self.assertIn(api_twofa.OWNER_ROLE, frappe.get_roles(u))
        from frappe.twofactor import two_factor_is_enabled
        self.assertTrue(two_factor_is_enabled(user=u))
        # orang lain tidak terkena 2FA Frappe
        self.assertFalse(two_factor_is_enabled(user=make_actor().user))

    def test_new_session_needs_code_and_wrong_code_refused(self):
        u = self._owner()
        with as_user(u):
            self._sid("sid-a")
            secret = api_twofa.setup_start()["secret"]
            api_twofa.setup_verify(pyotp.TOTP(secret).now())
            self._sid("sid-b")  # sesi baru (mis. login Google)
            self.assertEqual(api_twofa.required_state(), "verify")
            with self.assertRaises(frappe.PermissionError):
                self._call("/api/method/rescue_net.api_events.disasters")
            with self.assertRaises(frappe.ValidationError):
                api_twofa.verify_session("000000")
            api_twofa.verify_session(pyotp.TOTP(secret).now())
            self.assertIsNone(api_twofa.required_state())

    def test_admin_toggle_off_keeps_owner_2fa(self):
        u = self._owner()
        with as_user(u):
            self._sid("sid-c")
            secret = api_twofa.setup_start()["secret"]
            api_twofa.setup_verify(pyotp.TOTP(secret).now())
        s2 = api_twofa.setup_start()["secret"]  # Administrator
        api_twofa.setup_verify(pyotp.TOTP(s2).now())
        api_twofa.set_admin_enforcement(1)
        api_twofa.set_admin_enforcement(0)
        self.assertEqual(int(frappe.db.get_single_value("System Settings", "enable_two_factor_auth")), 1)

    def test_reset_user_by_system_manager(self):
        u = self._owner()
        with as_user(u):
            self._sid("sid-d")
            secret = api_twofa.setup_start()["secret"]
            api_twofa.setup_verify(pyotp.TOTP(secret).now())
            with self.assertRaises(frappe.PermissionError):
                api_twofa.reset_user(u)
        api_twofa.reset_user(u)
        self.assertNotIn(api_twofa.OWNER_ROLE, frappe.get_roles(u))
        with as_user(u):
            self._sid("sid-e")
            self.assertEqual(api_twofa.required_state(), "setup")
