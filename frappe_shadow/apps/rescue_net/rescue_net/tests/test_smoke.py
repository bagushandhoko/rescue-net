import frappe
from frappe.tests.utils import FrappeTestCase


class TestSmoke(FrappeTestCase):
    def test_site_is_the_test_site(self):
        # Guard: this suite must never run against production.
        self.assertTrue(frappe.conf.get("allow_tests"))
        self.assertNotEqual(frappe.local.site, "osiun.localhost")

    def test_app_installed(self):
        self.assertIn("rescue_net", frappe.get_installed_apps())
