"""Template operasi organisasi (owner 2026-11-22): menu khusus Edisi Tertutup BNPB/BPBD, TNI, PMI.

- Dipilih saat registrasi organisasi (bawaan 'umum'); nilai di luar daftar ditolak.
- my_operation_template: hanya organisasi TERTUTUP yang mendapat template khusus; tamu ditolak.
- set_operation_template: hanya pemilik organisasi; anggota biasa ditolak.
"""
import frappe

from rescue_net import api_community_cluster as cluster
from rescue_net import api_org_profile as profile
from rescue_net.tests.factories import RNTestCase, as_guest, as_user, make_actor


class TestOperationTemplate(RNTestCase):
    def register(self, **kw):
        user = make_actor()
        with as_user(user.user):
            res = cluster.create_organization(title="Uji Template Org", **kw)
        return user, frappe.get_doc("RN Organization", res["organization"])

    def test_registration_default_is_umum(self):
        _, org = self.register()
        self.assertEqual(org.operation_template, "umum")

    def test_registration_can_choose_template(self):
        user, org = self.register(open_to_public="0", operation_template="TNI")
        self.assertEqual(org.operation_template, "tni")
        with as_user(user.user):
            res = profile.my_operation_template()
        self.assertEqual((res["template"], res["organization"]), ("tni", org.name))

    def test_invalid_template_rejected(self):
        user = make_actor()
        with as_user(user.user), self.assertRaises(frappe.ValidationError):
            cluster.create_organization(title="Uji Template Salah", operation_template="militer")

    def test_open_org_always_umum(self):
        user, org = self.register(open_to_public="1", operation_template="pmi")
        with as_user(user.user):
            res = profile.my_operation_template()
        self.assertEqual(res["template"], "umum")

    def test_guest_rejected(self):
        with as_guest(), self.assertRaises(frappe.ValidationError):
            profile.my_operation_template()

    def test_owner_can_change_member_cannot(self):
        owner, org = self.register(open_to_public="0")
        member = make_actor(org=org, org_role="member")
        with as_user(member.user), self.assertRaises(frappe.PermissionError):
            profile.set_operation_template(org.name, "bnpb")
        with as_user(owner.user):
            res = profile.set_operation_template(org.name, "bnpb")
        self.assertEqual(res["template"], "bnpb")
        with as_user(member.user):
            self.assertEqual(profile.my_operation_template()["template"], "bnpb")

    def test_user_without_org_gets_umum(self):
        user = make_actor()
        with as_user(user.user):
            res = profile.my_operation_template()
        self.assertEqual((res["template"], res["organization"]), ("umum", None))

    def test_kementerian_template(self):
        user, org = self.register(open_to_public="0", operation_template="kementerian")
        with as_user(user.user):
            self.assertEqual(profile.my_operation_template()["template"], "kementerian")
