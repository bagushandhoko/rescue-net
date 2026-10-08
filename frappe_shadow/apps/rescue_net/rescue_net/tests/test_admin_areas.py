"""Wilayah berkode (ADR-0005 D.1): kode Kemendagri, impor aman (dry-run, idempoten, validasi), crosswalk,
pencocokan nama, controller, dan API pencarian."""

import json
import tempfile
from pathlib import Path

import frappe

from rescue_net import api_admin_areas as api
from rescue_net.services import admin_area_codes as codes
from rescue_net.services import admin_areas as svc
from rescue_net.tests.factories import RNTestCase, _insert, as_guest

FILE = [
    {"kode": "91", "nama": "Provinsi Uji Satu"},
    {"kode": "9171", "nama": "Kota Contoh"},
    {"kode": "917102", "nama": "Kecamatan Tengah"},
    {"kode": "9171021001", "nama": "Kelurahan Pusat"},
    {"kode": "9171021002", "nama": "Kelurahan Baru"},
    {"kode": "9172", "nama": "Kabupaten Lain"},
    {"kode": "917201", "nama": "Kecamatan Tengah"},        # same name, different parent
    {"kode": "9172011001", "nama": "Kelurahan Pusat"},      # same name, different parent
]


def rows(data=FILE):
    return [codes.normalize_row(r) for r in data]


class TestCodes(RNTestCase):
    def test_normalise_level_parent(self):
        for raw, code, level, parent in (("11", "11", "province", ""), ("1171", "11.71", "city", "11"),
                                         ("117102", "11.71.02", "district", "11.71"),
                                         ("1171021001", "11.71.02.1001", "village", "11.71.02"),
                                         ("11.71.02.1001", "11.71.02.1001", "village", "11.71.02")):
            n = codes.normalize_code(raw)
            self.assertEqual((n, codes.level_of(n), codes.parent_of(n)), (code, level, parent), raw)
        for bad in ("11.7", "abc", "1171021001x", "117", ""):
            self.assertFalse(codes.validate_code(codes.normalize_code(bad)), bad)

    def test_validation_report_blocks_bad_files(self):
        data = rows(FILE + [{"kode": "9199031001", "nama": "Desa Yatim"}, {"kode": "9171", "nama": "Nama Lain"}])
        rep = codes.validate_rows(data)
        self.assertFalse(rep["ok"])
        self.assertEqual(rep["issues"]["orphan"]["count"], 1)
        self.assertIn("duplicate_code_conflicting_name", rep["issues"])
        self.assertTrue(codes.validate_rows(rows())["ok"])
        self.assertEqual(codes.validate_rows(rows())["counts"], {"province": 1, "city": 2, "district": 2, "village": 3})

    def test_name_normalisation_for_matching(self):
        self.assertEqual(codes.normalize_name("Kabupaten Aceh Barat"), "aceh barat")
        self.assertEqual(codes.normalize_name("KOTA ADM. JAKARTA PUSAT"), "jakarta pusat")
        self.assertEqual(codes.normalize_name("Kel. Kampung  Baru"), "kampung baru")


class TestImport(RNTestCase):
    def test_dry_run_writes_nothing_then_apply_then_idempotent(self):
        out = svc.import_rows(rows(), "uji", dry_run=True)
        self.assertEqual((out["plan"]["new"], out["applied"]), (8, False))
        self.assertFalse(frappe.db.exists("RN Admin Area", "91"))
        out = svc.import_rows(rows(), "uji", "https://contoh", dry_run=False)
        self.assertTrue(out["applied"])
        self.assertEqual(frappe.db.get_value("RN Admin Area", "91.71.02.1001", "parent_code"), "91.71.02")
        self.assertEqual(frappe.db.get_value("RN Admin Area", "91.71", "source"), "uji")
        again = svc.import_rows(rows(), "uji", dry_run=False)
        self.assertEqual((again["plan"]["new"], again["plan"]["changed"], again["plan"]["unchanged"]), (0, 0, 8))

    def test_changed_names_update_and_missing_rows_are_left_alone(self):
        svc.import_rows(rows(), "uji", dry_run=False)
        data = [dict(r) for r in FILE if r["kode"] != "9172011001"]
        data[1]["nama"] = "Kota Contoh Raya"
        out = svc.import_rows(rows(data), "uji2", dry_run=False)
        self.assertEqual((out["plan"]["changed"], out["plan"]["not_in_file_left_untouched"]), (1, 1))
        self.assertEqual(frappe.db.get_value("RN Admin Area", "91.71", "area_name"), "Kota Contoh Raya")
        self.assertTrue(frappe.db.exists("RN Admin Area", "91.72.01.1001"))           # not deleted

    def test_a_bad_file_writes_nothing_even_when_not_a_dry_run(self):
        bad = rows(FILE + [{"kode": "9199031001", "nama": "Desa Yatim"}])
        out = svc.import_rows(bad, "uji", dry_run=False)
        self.assertEqual((out["applied"], out["validation"]["ok"]), (False, False))
        self.assertFalse(frappe.db.exists("RN Admin Area", "91"))

    def test_a_parent_already_in_the_database_satisfies_the_orphan_check(self):
        svc.import_rows(rows(FILE[:2]), "uji", dry_run=False)
        out = svc.import_rows(rows(FILE[2:4]), "uji", dry_run=False)
        self.assertTrue(out["applied"])

    def test_load_file_csv_and_json(self):
        with tempfile.TemporaryDirectory() as d:
            c = Path(d) / "w.csv"
            c.write_text("kode;nama\n91;Provinsi Uji Satu\n9171;Kota Contoh\n;kosong\n", encoding="utf-8")
            got, bad = svc.load_file(c)
            self.assertEqual(([r["code"] for r in got], bad), (["91", "91.71"], 1))
            j = Path(d) / "w.json"
            j.write_text(json.dumps({"data": FILE[:2]}), encoding="utf-8")
            self.assertEqual(len(svc.load_file(j)[0]), 2)


class TestCrosswalkAndMatching(RNTestCase):
    def setUp(self):
        super().setUp()
        svc.import_rows(rows(), "uji", dry_run=False)

    def test_crosswalk_import_resolve_and_uniqueness(self):
        out = svc.import_crosswalk([{"code": "9171", "external_code": "ID9171"}, {"code": "91", "external_code": "ID91"}],
                                   "ocha_pcode", source="HDX uji", dry_run=False)
        self.assertEqual((out["ok"], out["applied"], out["new"]), (True, True, 2))
        self.assertEqual(svc.resolve_external("ocha_pcode", "ID9171"), "91.71")
        self.assertEqual([c.external_code for c in svc.external_codes("91.71")], ["ID9171"])
        again = svc.import_crosswalk([{"code": "9171", "external_code": "ID9171"}], "ocha_pcode", dry_run=False)
        self.assertEqual((again["ok"], again["new"]), (True, 0))                            # idempotent
        clash = svc.import_crosswalk([{"code": "9172", "external_code": "ID9171"}], "ocha_pcode", dry_run=False)
        self.assertFalse(clash["ok"])
        self.assertIn("conflicts_with_existing", clash["issues"])
        unknown = svc.import_crosswalk([{"code": "9899", "external_code": "X"}], "bps", dry_run=False)
        self.assertIn("unknown_area", unknown["issues"])
        with self.assertRaises(frappe.ValidationError):                                       # the DocType guards too
            _insert("RN Admin Area Crosswalk", code_system="ocha_pcode", external_code="ID9171", area="91.72")

    def test_match_by_names_exact_ambiguous_and_missing(self):
        ok = svc.match_by_names("Provinsi Uji Satu", "Kota Contoh", "Kecamatan Tengah", "Kelurahan Pusat")
        self.assertEqual((ok["code"], ok["level"], ok["confidence"]), ("91.71.02.1001", "village", "exact"))
        # same names exist under another city: a parent-constrained walk keeps them apart
        other = svc.match_by_names("Provinsi Uji Satu", "Kabupaten Lain", "Kecamatan Tengah", "Kelurahan Pusat")
        self.assertEqual(other["code"], "91.72.01.1001")
        # without the parent the district name alone is ambiguous → no guess
        amb = svc.match_by_names(None, None, "Kecamatan Tengah")
        self.assertIsNone(amb["code"])
        self.assertEqual(sorted(amb["candidates"]), ["91.71.02", "91.72.01"])
        self.assertIsNone(svc.match_by_names("Provinsi Uji Satu", "Kota Tak Ada")["code"])
        self.assertIsNone(svc.match_by_names()["code"])

    def test_api_search_and_get_area_for_guests(self):
        svc.import_crosswalk([{"code": "9171", "external_code": "ID9171"}], "ocha_pcode", dry_run=False)
        with as_guest():
            hit = api.search_areas(q="Pusat", level="village")
            self.assertEqual({r["code"] for r in hit["rows"]}, {"91.71.02.1001", "91.72.01.1001"})
            under = api.search_areas(parent_code="91.71.02")
            self.assertEqual({r["code"] for r in under["rows"]}, {"91.71.02.1001", "91.71.02.1002"})
            self.assertEqual(api.search_areas(limit=3)["has_more"], True)
            area = api.get_area("91.71.02.1001")
        self.assertEqual([p["code"] if "code" in p else p["name"] for p in area["path"]], ["91", "91.71", "91.71.02", "91.71.02.1001"])
        city = frappe.db.get_value("RN Admin Area", "91.71", "name")
        self.assertEqual(city, "91.71")

    def test_controller_rules(self):
        def make(**kw):
            base = dict(code="91.71.02.1099", area_name="X", level="village", parent_code="91.71.02")
            base.update(kw)
            return _insert("RN Admin Area", **base)

        for kw in ({"code": "91.7"}, {"level": "district"}, {"code": "91.99.01.1001", "parent_code": "91.99.01"},
                   {"valid_from": "2026-01-01", "valid_to": "2025-01-01"}, {"replaced_by": "91.71"}):
            with self.assertRaises(frappe.ValidationError, msg=str(kw)):
                make(**kw)
        ok = make(valid_to="2026-01-01", replaced_by="91.71.02.1001")
        self.assertEqual(ok.name, "91.71.02.1099")


class TestRealWorldNames(RNTestCase):
    """Names as people write them vs the official Kepmendagri spelling (checked against the real 2025 dataset)."""

    def setUp(self):
        super().setUp()
        svc.import_rows(rows([
            {"kode": "31", "nama": "Daerah Khusus Ibukota Jakarta"}, {"kode": "3171", "nama": "Kota Administrasi Jakarta Pusat"},
            {"kode": "317101", "nama": "Gambir"}, {"kode": "3171011001", "nama": "Gambir"},
            {"kode": "32", "nama": "Jawa Barat"}, {"kode": "3204", "nama": "Kabupaten Bandung"}, {"kode": "3273", "nama": "Kota Bandung"},
            {"kode": "320401", "nama": "Soreang"}, {"kode": "327301", "nama": "Bandung Kulon"},
            {"kode": "34", "nama": "Daerah Istimewa Yogyakarta"}]), "uji", dry_run=False)

    def test_province_aliases(self):
        for written, code in (("DKI Jakarta", "31"), ("Daerah Khusus Jakarta", "31"), ("D.I. Yogyakarta", "34"),
                              ("DI Yogyakarta", "34"), ("Jabar", "32"), ("Provinsi Jawa Barat", "32")):
            self.assertEqual(svc.match_by_names(written)["code"], code, written)

    def test_kota_vs_kabupaten(self):
        self.assertEqual(svc.match_by_names("Jawa Barat", "Kota Bandung")["code"], "32.73")
        self.assertEqual(svc.match_by_names("Jawa Barat", "Kab. Bandung")["code"], "32.04")
        amb = svc.match_by_names("Jawa Barat", "Bandung")                       # no kind: refuse to guess
        self.assertIsNone(amb["code"])
        self.assertEqual(sorted(amb["candidates"]), ["32.04", "32.73"])

    def test_jakarta_administrative_city_and_walk_to_village(self):
        m = svc.match_by_names("DKI Jakarta", "Jakarta Pusat", "Gambir", "Gambir")
        self.assertEqual((m["code"], m["level"]), ("31.71.01.1001", "village"))
