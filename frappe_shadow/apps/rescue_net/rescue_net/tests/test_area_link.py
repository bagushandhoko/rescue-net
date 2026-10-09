"""Fase 9c D.2: admin_area_id = Link ke kode Kemendagri; tak cocok ditandai (tak pernah memblokir simpan);
patch pemetaan nama→kode idempoten; routing berbasis kode (nama kembar di kota lain tak cocok)."""

import frappe

from rescue_net.services import admin_area_codes as codes
from rescue_net.services import admin_areas as svc
from rescue_net.services import report_routing as rr
from rescue_net.tests.factories import RNTestCase, _insert, make_event, make_posko
from rescue_net.tests.test_admin_areas import FILE, rows


class TestAreaLink(RNTestCase):
    def setUp(self):
        super().setUp()
        svc.import_rows(rows(FILE), "uji", dry_run=False)
        self.ev = make_event()

    def test_valid_code_kept_and_unmatched_flag_cleared(self):
        p = make_posko(self.ev, admin_area_id="9171021001")  # tanpa titik -> dinormalkan
        self.assertEqual(frappe.db.get_value("RN Posko", p.name, "admin_area_id"), "91.71.02.1001")
        self.assertEqual(frappe.db.get_value("RN Posko", p.name, "area_unmatched"), 0)

    def test_unknown_id_never_blocks_save_and_is_flagged(self):
        p = make_posko(self.ev, admin_area_id="BUKAN-KODE-1")
        row = frappe.db.get_value("RN Posko", p.name, ["admin_area_id", "area_unmatched", "area_legacy_text"], as_dict=True)
        self.assertIsNone(row.admin_area_id)
        self.assertEqual(row.area_unmatched, 1)
        self.assertEqual(row.area_legacy_text, "BUKAN-KODE-1")

    def test_unique_names_map_to_code_ambiguous_do_not(self):
        p = make_posko(self.ev, province_name="Provinsi Uji Satu", city_name="Kota Contoh",
                       district_name="Kecamatan Tengah", village_name="Kelurahan Pusat")
        self.assertEqual(frappe.db.get_value("RN Posko", p.name, "admin_area_id"), "91.71.02.1001")
        amb = make_posko(self.ev, province_name="Provinsi Uji Satu", district_name="Kecamatan Tengah")
        row = frappe.db.get_value("RN Posko", amb.name, ["admin_area_id", "area_unmatched"], as_dict=True)
        self.assertEqual((row.admin_area_id, row.area_unmatched), ("91", 1))  # kecamatan tanpa kota: pakai provinsi yang pasti, ditandai untuk dilengkapi

    def test_report_with_unknown_area_is_still_accepted(self):
        r = _insert("RN Community Report", title="L", report_type="other", status="submitted", admin_area_id="xyz",
                    location_text="di suatu tempat")
        row = frappe.db.get_value("RN Community Report", r.name, ["admin_area_id", "area_unmatched"], as_dict=True)
        self.assertEqual((row.admin_area_id, row.area_unmatched), (None, 1))

    def test_remap_existing_is_idempotent_and_does_not_touch_valid_codes(self):
        p = make_posko(self.ev, province_name="Provinsi Uji Satu", city_name="Kota Contoh")
        frappe.db.set_value("RN Posko", p.name, {"admin_area_id": None, "area_unmatched": 0})
        ok = make_posko(self.ev, admin_area_id="91.72")
        dry = svc.remap_existing(dry_run=True)["RN Posko"]
        self.assertGreaterEqual(dry["mapped"], 1)
        self.assertIsNone(frappe.db.get_value("RN Posko", p.name, "admin_area_id"))  # dry-run tak menulis
        svc.remap_existing(dry_run=False)
        self.assertEqual(frappe.db.get_value("RN Posko", p.name, "admin_area_id"), "91.71")
        self.assertEqual(frappe.db.get_value("RN Posko", ok.name, "admin_area_id"), "91.72")
        again = svc.remap_existing(dry_run=False)["RN Posko"]
        self.assertEqual(again["mapped"], 0)

    def test_routing_prefers_codes_over_same_names(self):
        # kecamatan & kelurahan kembar nama di dua kota; kode membedakan
        a = {"admin_area_id": "91.71.02.1001", "village_name": "Kelurahan Pusat", "district_name": "Kecamatan Tengah"}
        same = {"admin_area_id": "91.71.02.1001", "village_name": "Kelurahan Pusat"}
        twin = {"admin_area_id": "91.72.01.1001", "village_name": "Kelurahan Pusat", "district_name": "Kecamatan Tengah"}
        city_only = {"admin_area_id": "91.71.02.1002"}
        far = {"admin_area_id": "91.72"}
        self.assertEqual(rr.score(a, same)[0], 40)
        self.assertEqual(rr.score(a, city_only)[0], 30)          # kecamatan sama lewat kode
        self.assertEqual(rr.score(a, far)[0], 5)                  # beda kota, provinsi sama: hanya +5
        self.assertLess(rr.score(a, twin)[0], rr.score(a, same)[0])
        self.assertEqual(rr.score(a, twin)[0], 5)                 # nama kembar di kota lain tak dihitung desa/kecamatan

    def test_routing_falls_back_to_names_without_codes(self):
        r = {"village_name": "Kelurahan Pusat"}
        p = {"village_name": "Kelurahan Pusat"}
        self.assertEqual(rr.score(r, p)[0], 40)
        self.assertEqual(rr.score({"admin_area_id": "91.71", "village_name": "Kelurahan Pusat"}, p)[0], 40)

    def test_partial_match_uses_deepest_certain_level(self):
        p = make_posko(self.ev, province_name="Provinsi Uji Satu", city_name="Kota Contoh", village_name="Desa Tidak Ada")
        row = frappe.db.get_value("RN Posko", p.name, ["admin_area_id", "area_unmatched"], as_dict=True)
        self.assertEqual((row.admin_area_id, row.area_unmatched), ("91.71", 1))
