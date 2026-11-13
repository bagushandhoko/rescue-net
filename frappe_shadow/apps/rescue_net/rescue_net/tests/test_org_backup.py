"""Backup & restore data organisasi oleh admin organisasi (owner 2026-11-13)."""

import base64
import gzip
import json

import frappe

from rescue_net import api_org_backup as ob
from rescue_net.tests.factories import RNTestCase, _insert, as_user, make_actor, make_world


def need(posko, event, item):
    return _insert("RN Logistic Need", title=item, posko=posko, disaster_event=event, item_name=item,
                   quantity=10, unit="kg", urgency="normal")


class TestOrgBackup(RNTestCase):
    def setUp(self):
        super().setUp()
        self.w = make_world()
        self.org = self.w.posko_a.organization
        self.other_posko = self.w.posko_b
        self.n1 = need(self.w.posko_a.name, self.w.event.name, "Beras-uji-1")
        self.n2 = need(self.w.posko_a.name, self.w.event.name, "Air-uji-2")
        self.other = need(self.other_posko.name, self.w.event.name, "Milik-org-lain")
        frappe.set_user("Administrator")

    def tearDown(self):
        frappe.set_user("Administrator")
        super().tearDown()

    def test_only_org_admin(self):
        with as_user(make_actor(org=self.w.org_a).user):
            with self.assertRaises(frappe.PermissionError):
                ob.backup_organisasi(self.org)
        with as_user(make_actor().user):
            with self.assertRaises(frappe.PermissionError):
                ob.daftar_backup(self.org)

    def test_backup_contains_org_and_posko_data_only(self):
        r = ob.backup_organisasi(self.org)
        self.assertGreater(r["records"], 2)
        data = ob._load(self.org, file=r["file"])
        names = {d["name"] for d in data["records"].get("RN Logistic Need", [])}
        self.assertIn(self.n1.name, names)
        self.assertNotIn(self.other.name, names)
        self.assertIn(self.w.posko_a.name, {d["name"] for d in data["records"]["RN Posko"]})
        self.assertEqual(ob.daftar_backup(self.org)["backups"][0]["file"], r["file"])

    def test_restore_repairs_and_keeps_new_unless_asked(self):
        r = ob.backup_organisasi(self.org)
        frappe.db.set_value("RN Logistic Need", self.n1.name, "quantity", 999)   # rusak
        frappe.delete_doc("RN Logistic Need", self.n2.name, force=True)            # terhapus
        baru = need(self.w.posko_a.name, self.w.event.name, "Baru-setelah-backup")
        out = ob.pulihkan_organisasi(self.org, file=r["file"])
        self.assertEqual(frappe.db.get_value("RN Logistic Need", self.n1.name, "quantity"), 10)
        self.assertTrue(frappe.db.exists("RN Logistic Need", self.n2.name))
        self.assertTrue(frappe.db.exists("RN Logistic Need", baru.name))           # aturan 4: tidak dihapus
        self.assertGreaterEqual(out["hasil"]["dibuat"], 1)
        self.assertTrue(out["backup_sebelumnya"].startswith(ob.PREFIX))            # aturan 3
        ob.pulihkan_organisasi(self.org, file=r["file"], hapus_baru=1)
        self.assertFalse(frappe.db.exists("RN Logistic Need", baru.name))
        self.assertTrue(frappe.db.exists("RN Logistic Need", self.other.name))     # milik org lain aman

    def test_tampered_file_cannot_touch_other_org(self):
        r = ob.backup_organisasi(self.org)
        data = ob._load(self.org, file=r["file"])
        evil = json.loads(frappe.as_json(frappe.get_doc("RN Logistic Need", self.other.name).as_dict()))
        evil["quantity"] = 12345
        data["records"].setdefault("RN Logistic Need", []).append(evil)
        evil2 = dict(evil, posko=self.w.posko_a.name)                               # pura-pura milik posko sendiri
        data["records"]["RN Logistic Need"].append(evil2)
        b64 = base64.b64encode(gzip.compress(json.dumps(data).encode())).decode()
        out = ob.pulihkan_organisasi(self.org, content_base64=b64)
        self.assertEqual(frappe.db.get_value("RN Logistic Need", self.other.name, "quantity"), 10)
        self.assertEqual(frappe.db.get_value("RN Logistic Need", self.other.name, "posko"), self.other_posko.name)
        self.assertGreaterEqual(out["hasil"]["dilewati"], 2)

    def test_backup_of_other_org_rejected(self):
        other_org = self.other_posko.organization
        if not other_org or other_org == self.org:
            return
        r = ob.backup_organisasi(other_org)
        data = ob._load(other_org, file=r["file"])
        b64 = base64.b64encode(gzip.compress(json.dumps(data).encode())).decode()
        with self.assertRaises(frappe.ValidationError):
            ob.pulihkan_organisasi(self.org, content_base64=b64)
