"""Owner 2026-11-19: Sub Admin organisasi menjalankan penuh posko dalam cakupannya.

- posko pilihan + posko di bawahnya (parent_posko) -> can_manage_posko True;
- posko lain di organisasi yang sama -> False;
- sub_admin_all -> semua posko organisasi;
- dicabut -> False lagi.
"""
import json

import frappe
from frappe.tests.utils import FrappeTestCase

from rescue_net.access_policy import can_manage_posko, is_sub_admin_of_posko


class TestSubAdmin(FrappeTestCase):
    def setUp(self):
        frappe.set_user("Administrator")
        self.org = frappe.get_doc({"doctype": "RN Organization", "title": "Uji Sub Admin Org"}).insert(ignore_permissions=True)
        self.acc = frappe.get_doc({"doctype": "RN User Account", "username": "uji-subadmin",
                                   "email": "uji-subadmin@example.org", "status": "active"}).insert(ignore_permissions=True)

        def posko(judul, induk=None):
            return frappe.get_doc({"doctype": "RN Posko", "title": judul, "organization": self.org.name,
                                   "parent_posko": induk}).insert(ignore_permissions=True).name
        self.induk = posko("Uji Induk")
        self.anak = posko("Uji Anak", self.induk)
        self.lain = posko("Uji Lain")
        self.m = frappe.get_doc({"doctype": "RN Organization Membership", "user_account": self.acc.name,
                                 "organization": self.org.name, "membership_role": "sub_admin", "status": "approved",
                                 "sub_admin_scope": json.dumps([self.induk])}).insert(ignore_permissions=True)
        self.actor = frappe._dict(name=self.acc.name, organization=None, role="member")

    def tearDown(self):
        frappe.db.rollback()

    def test_cakupan_pilihan_dan_anak(self):
        self.assertTrue(is_sub_admin_of_posko(self.actor, self.induk))
        self.assertTrue(is_sub_admin_of_posko(self.actor, self.anak))
        self.assertFalse(is_sub_admin_of_posko(self.actor, self.lain))

    def test_semua_posko(self):
        self.m.db_set("sub_admin_all", 1)
        self.assertTrue(is_sub_admin_of_posko(self.actor, self.lain))

    def test_dicabut(self):
        self.m.db_set("membership_role", "member")
        frappe.set_user("Guest")
        self.assertFalse(can_manage_posko(self.actor, self.induk))


class TestSubAdminBuatPosko(TestSubAdmin):
    """Owner 2026-11-19: Sub Admin boleh membuat posko baru di bawah posko yang dikelolanya."""
    def test_posko_baru_di_bawah_cakupan(self):
        from rescue_net.api_community_cluster import _create_posko_impl
        actor = frappe._dict(name=self.acc.name, organization=None, role="member")
        res = _create_posko_impl(actor, "Uji Posko Baru", "logistics", "Jl. Uji", self.org.name,
                                 parent_posko=self.induk)
        self.assertEqual(frappe.db.get_value("RN Posko", res["posko"], "parent_posko"), self.induk)
        self.assertTrue(is_sub_admin_of_posko(self.actor, res["posko"]))
        self.assertEqual(res["assignment_status"], "approved")
