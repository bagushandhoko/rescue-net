"""Menu Cadangan & Pindah Server (owner 2026-11-13): jenis data/lengkap, unduh database & paket pindah server."""

import io
import tarfile

import frappe

from rescue_net import api_system_admin as sa
from rescue_net.tests.factories import RNTestCase, as_user, make_actor


class TestCadanganMenu(RNTestCase):
    def test_data_only_and_full_package(self):
        frappe.set_user("Administrator")
        r = sa.trigger_backup("data")
        data = r["backups"][0]
        self.assertEqual(data["jenis"], "data")
        self.assertEqual(set(data["files"]), {"database"})
        with self.assertRaisesRegex(frappe.ValidationError, "LENGKAP"):
            sa.unduh_cadangan(data["timestamp"], "paket")
        sa.unduh_cadangan(data["timestamp"], "database")
        self.assertTrue(frappe.local.response.filename.endswith("database.sql.gz"))

        import time; time.sleep(1.1)   # stempel waktu per detik
        r = sa.trigger_backup("lengkap")
        full = r["backups"][0]
        self.assertEqual(full["jenis"], "lengkap")
        sa.unduh_cadangan(full["timestamp"], "paket")
        self.assertTrue(frappe.local.response.filename.endswith(".tar"))
        with tarfile.open(fileobj=io.BytesIO(frappe.local.response.filecontent)) as tar:
            names = [m.name.split("/", 1)[1] for m in tar.getmembers()]
            conf = tar.extractfile([m for m in tar.getmembers() if m.name.endswith("/site_config.json")][0]).read()
        self.assertIn("site_config.json", names)
        self.assertIn("PULIHKAN.txt", names)
        self.assertIn("SHA256SUMS", names)
        self.assertTrue(any(n.endswith("database.sql.gz") for n in names))
        self.assertIn(b"encryption_key", conf)

    def test_bad_name_and_non_admin(self):
        frappe.set_user("Administrator")
        with self.assertRaisesRegex(frappe.ValidationError, "tidak valid"):
            sa.unduh_cadangan("../../etc", "database")
        with as_user(make_actor().user), self.assertRaises(frappe.PermissionError):
            sa.unduh_cadangan("20260101-000000", "database")
        with as_user(make_actor().user), self.assertRaises(frappe.PermissionError):
            sa.trigger_backup("data")
