"""Owner 2026-11-19: Sub Admin organisasi menjalankan penuh posko dalam cakupannya.

- posko pilihan + posko di bawahnya (parent_posko) -> can_manage_posko True;
- posko lain di organisasi yang sama -> False;
- sub_admin_all -> semua posko organisasi;
- dicabut -> False lagi.
"""
import json

import frappe

from rescue_net.access_policy import can_manage_posko, is_sub_admin_of_posko
from rescue_net.tests.factories import RNTestCase, _insert, as_user, make_actor, make_org, make_posko


class TestSubAdmin(RNTestCase):
    def setUp(self):
        super().setUp()
        self.org = make_org()
        self.account = make_actor(role="member")
        self.induk = make_posko(org=self.org, title="Uji Induk").name
        self.anak = make_posko(org=self.org, title="Uji Anak", parent_posko=self.induk).name
        self.lain = make_posko(org=self.org, title="Uji Lain").name
        self.m = _insert("RN Organization Membership", user_account=self.account.account,
                         organization=self.org.name, membership_role="sub_admin", status="approved",
                         sub_admin_scope=json.dumps([self.induk]))
        self.actor = frappe._dict(name=self.account.account, organization=None, role="member")

    def test_cakupan_pilihan_dan_anak(self):
        self.assertTrue(is_sub_admin_of_posko(self.actor, self.induk))
        self.assertTrue(is_sub_admin_of_posko(self.actor, self.anak))
        self.assertFalse(is_sub_admin_of_posko(self.actor, self.lain))

    def test_semua_posko(self):
        self.m.db_set("sub_admin_all", 1)
        self.assertTrue(is_sub_admin_of_posko(self.actor, self.lain))

    def test_dicabut(self):
        with as_user(self.account.user):
            self.assertTrue(can_manage_posko(self.actor, self.induk))
        self.m.db_set("membership_role", "member")
        with as_user(self.account.user):
            self.assertFalse(can_manage_posko(self.actor, self.induk))


class TestSubAdminBuatPosko(TestSubAdmin):
    """Owner 2026-11-19: Sub Admin boleh membuat posko baru di bawah posko yang dikelolanya."""
    def test_posko_baru_di_bawah_cakupan(self):
        from rescue_net.api_community_cluster import _create_posko_impl
        with as_user(self.account.user):
            res = _create_posko_impl(self.actor, "Uji Posko Baru", "logistics", "Jl. Uji", self.org.name,
                                     parent_posko=self.induk)
        self.assertEqual(frappe.db.get_value("RN Posko", res["posko"], "parent_posko"), self.induk)
        self.assertTrue(is_sub_admin_of_posko(self.actor, res["posko"]))
        self.assertEqual(res["assignment_status"], "approved")
