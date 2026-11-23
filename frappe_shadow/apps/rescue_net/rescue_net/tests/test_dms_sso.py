# Uji serah sesi Google RN -> DMS (Ming Ming 2026-11-23).
import frappe
from frappe.tests.utils import FrappeTestCase

from rescue_net import api_auth


class TestDmsSso(FrappeTestCase):
    def test_safe_next_hanya_halaman_lokal(self):
        self.assertEqual(api_auth._dms_safe_next("war-room.html?event=x"), "war-room.html?event=x")
        for bad in ("https://evil.example/x.html", "//evil.example", "../x.html", "dms-login.html", "javascript:alert(1)", ""):
            self.assertEqual(api_auth._dms_safe_next(bad), "")

    def test_start_tanpa_login_kembali_ke_login_dms(self):
        frappe.set_user("Guest")
        api_auth.dms_sso_start(next="war-room.html", n="a" * 64)
        self.assertEqual(frappe.local.response["type"], "redirect")
        self.assertIn("sso_error=1", frappe.local.response["location"])
        self.assertTrue(frappe.local.response["location"].startswith(api_auth.DMS_ORIGIN))

    def test_tiket_sekali_pakai_dan_terikat_nonce(self):
        frappe.set_user("Administrator")
        nonce = "n" * 32
        api_auth.dms_sso_start(next="war-room.html", n=api_auth._sha(nonce))
        loc = frappe.local.response["location"]
        self.assertIn("sso=", loc)
        ticket = loc.split("sso=")[1].split("&")[0]
        data = frappe.cache.get_value("dms_sso:" + ticket)
        self.assertEqual(data["user"], "Administrator")
        # nonce salah -> ditolak, dan tiket hangus
        frappe.set_user("Guest")
        frappe.local.request_ip = "127.0.0.1"
        frappe.local.request = frappe._dict(cookies={"dms_sso_nonce": "salah"})
        with self.assertRaises(frappe.AuthenticationError):
            api_auth.dms_sso_claim(ticket)
        with self.assertRaises(frappe.AuthenticationError):
            api_auth.dms_sso_claim(ticket)

    def test_tiket_benar_dengan_nonce_benar_login(self):
        frappe.set_user("Administrator")
        nonce = "b" * 32
        api_auth.dms_sso_start(next="", n=api_auth._sha(nonce))
        ticket = frappe.local.response["location"].split("sso=")[1].split("&")[0]
        frappe.set_user("Guest")
        frappe.local.request_ip = "127.0.0.1"
        frappe.local.request = frappe._dict(cookies={"dms_sso_nonce": nonce})
        calls = []
        frappe.local.login_manager = frappe._dict(login_as=lambda user: calls.append(user))
        frappe.local.cookie_manager = frappe._dict(delete_cookie=lambda k: None)
        self.assertEqual(api_auth.dms_sso_claim(ticket), {"user": "Administrator"})
        self.assertEqual(calls, ["Administrator"])
        with self.assertRaises(frappe.AuthenticationError):  # sekali pakai
            api_auth.dms_sso_claim(ticket)

    def test_tiket_format_salah(self):
        frappe.local.request_ip = "127.0.0.1"
        with self.assertRaises(frappe.AuthenticationError):
            api_auth.dms_sso_claim("../../x")
