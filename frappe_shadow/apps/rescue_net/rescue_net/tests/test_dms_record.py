"""Menu khusus DMS disimpan di RN (keputusan owner 22 Nov 2026).

Akses: anggota org TERTUTUP saja; menu harus sesuai template; RAHASIA hanya owner/deputy; isian divalidasi.
"""
import json

import frappe

from rescue_net import api_dms as dms
from rescue_net.tests.factories import RNTestCase, as_guest, as_user, make_actor, make_org


def _org(template="bnpb", privacy="closed"):
    org = make_org()
    frappe.db.set_value("RN Organization", org.name, {"privacy_mode": privacy, "operation_template": template})
    return frappe.get_doc("RN Organization", org.name)




class TestDMSRecord(RNTestCase):
    def setUp(self):
        super().setUp()
        self.menu = dms._catalog()["buffer-stock"]
        # isi semua isian wajib dari definisi supaya tes tidak rapuh terhadap teks Hermes
        self.data = {}
        for f in self.menu["isian"]:
            if f.get("wajib"):
                self.data[f["id"]] = {"angka": 5, "tanggal": "2026-11-22", "waktu": "08:00",
                                      "pilihan": (f.get("pilihan") or ["x"])[0], "ya_tidak": "Ya"}.get(f["jenis"], "isi uji")

    def test_member_can_save_and_list(self):
        org = _org("bnpb")
        user = make_actor(org=org)
        with as_user(user.user):
            saved = dms.save_record("buffer-stock", json.dumps(self.data), organization=org.name)
            rows = dms.list_records("buffer-stock", organization=org.name)["records"]
        self.assertEqual(saved["classification"], self.menu["klasifikasi"])
        self.assertEqual([r["name"] for r in rows], [saved["name"]])

    def test_guest_rejected(self):
        with as_guest(), self.assertRaises(frappe.ValidationError):
            dms.list_records("buffer-stock")

    def test_open_org_rejected(self):
        org = _org("bnpb", privacy="open")
        user = make_actor(org=org)
        with as_user(user.user), self.assertRaises(frappe.PermissionError):
            dms.list_records("buffer-stock", organization=org.name)

    def test_non_member_rejected(self):
        org = _org("bnpb")
        stranger = make_actor()
        with as_user(stranger.user), self.assertRaises(frappe.PermissionError):
            dms.list_records("buffer-stock", organization=org.name)

    def test_menu_outside_template_rejected(self):
        org = _org("pmi")
        user = make_actor(org=org)
        with as_user(user.user), self.assertRaises(frappe.PermissionError):
            dms.list_records("opord", organization=org.name)   # menu TNI untuk PMI

    def test_shared_and_extra_template_menus(self):
        org = _org("kementerian")
        user = make_actor(org=org)
        with as_user(user.user):
            dms.list_records("rapat-koordinasi", organization=org.name)      # bersama
            dms.list_records("klaster-nasional", organization=org.name)      # template_tambahan
            with self.assertRaises(frappe.PermissionError):
                dms.list_records("buffer-stock", organization=org.name)      # BNPB saja

    def test_secret_menu_owner_only(self):
        org = _org("bnpb")
        member = make_actor(org=org, org_role="member")
        owner = make_actor(org=org, org_role="owner")
        with as_user(member.user), self.assertRaises(frappe.PermissionError):
            dms.list_records("data-korban", organization=org.name)
        with as_user(owner.user):
            self.assertEqual(dms.list_records("data-korban", organization=org.name)["records"], [])

    def test_validation(self):
        org = _org("bnpb")
        user = make_actor(org=org)
        with as_user(user.user):
            with self.assertRaises(frappe.ValidationError):
                dms.save_record("buffer-stock", json.dumps({**self.data, "kolom_palsu": "x"}), organization=org.name)
            required = [f for f in self.menu["isian"] if f.get("wajib")]
            if required:
                broken = dict(self.data); broken.pop(required[0]["id"])
                with self.assertRaises(frappe.ValidationError):
                    dms.save_record("buffer-stock", json.dumps(broken), organization=org.name)
            numeric = [f for f in self.menu["isian"] if f["jenis"] == "angka"]
            if numeric:
                with self.assertRaises(frappe.ValidationError):
                    dms.save_record("buffer-stock", json.dumps({**self.data, numeric[0]["id"]: "banyak"}), organization=org.name)

    def test_other_org_cannot_edit_or_archive(self):
        org_a, org_b = _org("bnpb"), _org("bnpb")
        a, b = make_actor(org=org_a), make_actor(org=org_b)
        with as_user(a.user):
            saved = dms.save_record("buffer-stock", json.dumps(self.data), organization=org_a.name)
        with as_user(b.user):
            with self.assertRaises(frappe.PermissionError):
                dms.save_record("buffer-stock", json.dumps(self.data), organization=org_b.name, name=saved["name"])
            with self.assertRaises(frappe.PermissionError):
                dms.archive_record(saved["name"], organization=org_b.name)
            self.assertEqual(dms.list_records("buffer-stock", organization=org_b.name)["records"], [])

    def test_archive_hides_record(self):
        org = _org("bnpb")
        user = make_actor(org=org)
        with as_user(user.user):
            saved = dms.save_record("buffer-stock", json.dumps(self.data), organization=org.name)
            dms.archive_record(saved["name"])
            self.assertEqual(dms.list_records("buffer-stock", organization=org.name)["records"], [])
            self.assertEqual(len(dms.list_records("buffer-stock", organization=org.name, include_archived=1)["records"]), 1)
