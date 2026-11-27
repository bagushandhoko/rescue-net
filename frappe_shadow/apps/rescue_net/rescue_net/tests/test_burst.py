"""Tombol Burst ke VPS (Protokol Burst VPS, owner 2026-11-27)."""

import frappe

from rescue_net import api_burst
from rescue_net.tests.factories import RNTestCase, as_guest, as_user, make_actor

TOK = "b" * 32


class TestBurst(RNTestCase):
    def setUp(self):
        super().setUp()
        frappe.db.delete("RN Burst Request")
        self._old = frappe.conf.get("burst_agent_token")
        frappe.conf.burst_agent_token = TOK

    def tearDown(self):
        frappe.conf.burst_agent_token = self._old
        super().tearDown()

    def test_only_system_manager_can_request(self):
        actor = make_actor("burst-user")
        with as_user(actor["user"]), self.assertRaises(frappe.PermissionError):
            api_burst.request_burst("203.0.113.9", "rahasia", "siaga")
        with as_guest(), self.assertRaises(frappe.PermissionError):
            api_burst.request_burst("203.0.113.9", "rahasia", "siaga")

    def test_validation(self):
        with as_user("Administrator"):
            with self.assertRaises(frappe.ValidationError):
                api_burst.request_burst("bukan-ip", "x", "siaga")
            with self.assertRaises(frappe.ValidationError):
                api_burst.request_burst("203.0.113.9", "", "siaga")
            with self.assertRaises(frappe.ValidationError):
                api_burst.request_burst("203.0.113.9", "x", "hapus-semua")
            with self.assertRaises(frappe.ValidationError):
                api_burst.request_burst("203.0.113.9", "x", "siaga", ssh_user="root;rm")

    def test_agent_gets_code_once_and_it_is_erased(self):
        with as_user("Administrator"):
            r = api_burst.request_burst("203.0.113.9", "kode-rahasia-123", "gladi")
            self.assertNotIn("kode-rahasia-123", frappe.as_json(api_burst.list_requests()))
            with self.assertRaises(frappe.ValidationError):   # satu per satu
                api_burst.request_burst("203.0.113.10", "x", "gladi")
        with as_guest(), self.assertRaises(frappe.PermissionError):
            api_burst.agent_next(token="salah")
        with as_guest():
            job = api_burst.agent_next(token=TOK)["job"]
        self.assertEqual((job["name"], job["ip"], job["mode"], job["login_code"]), (r["name"], "203.0.113.9", "gladi", "kode-rahasia-123"))
        self.assertFalse(frappe.db.exists("__Auth", {"doctype": "RN Burst Request", "name": r["name"]}))
        with as_guest():
            self.assertIsNone(api_burst.agent_next(token=TOK)["job"])
            api_burst.agent_update(token=TOK, name=r["name"], status="Selesai", log="[10s] SELESAI\n")
        with as_user("Administrator"):
            row = api_burst.list_requests()["requests"][0]
        self.assertEqual(row["status"], "Selesai")
        self.assertIn("SELESAI", row["log"])

    def test_cancel(self):
        with as_user("Administrator"):
            r = api_burst.request_burst("203.0.113.9", "x", "siaga")
            self.assertEqual(api_burst.cancel_request(r["name"])["status"], "Dibatalkan")
        with as_guest():
            self.assertIsNone(api_burst.agent_next(token=TOK)["job"])
