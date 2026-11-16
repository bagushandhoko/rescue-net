"""Jalankan langsung dengan python3; tanpa site/AI/DB. Endpoint memakai mock.

Panggilan model wajib dipatch pada rescue_net.ai.analysis._tanya, sama dengan
jalur publik. Ini bukan uji integrasi Frappe atau browser login sungguhan.
"""
import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest
from datetime import datetime
from unittest.mock import Mock, patch

BASE = Path(__file__).resolve().parents[1] / "ai"
if not (BASE / "analysis_nala_calc.py").exists():
    BASE = Path(__file__).resolve().parent  # salinan pengujian tanpa site


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


calc = load("nala_calc_test", BASE / "analysis_nala_calc.py")


def stock(name="s1", qty=100, day=1, posko="P1", item="beras", unit="kg", **kw):
    return dict(name=name, quantity=qty, observed_at=f"2026-11-{day:02d} 00:00:00", posko=posko,
                canonical_item=item, unit=unit, **kw)


class TestStok(unittest.TestCase):
    def test_tren_dan_kritis(self):
        r = calc.hitung_stok([stock(qty=100), stock("s2", 20, 3)])[0]
        self.assertEqual((r["pemakaian_per_hari"], r["sisa_hari"], r["status"]), (40, .5, "kritis"))

    def test_batas_status(self):
        for days, expected in [(0, "kritis"), (3, "kritis"), (3.01, "waspada"), (7, "waspada"), (7.01, "cukup")]:
            with self.subTest(days=days):
                self.assertEqual(calc.hitung_stok([stock(qty=days*10, rn_daily_consumption=10)])[0]["status"], expected)

    def test_prioritas_laju_eksplisit(self):
        r = calc.hitung_stok([stock(qty=100), stock("s2", 40, 3, rn_daily_consumption=5)])[0]
        self.assertEqual(r["sisa_hari"], 8)
        self.assertEqual(r["sumber_laju"], "rn_daily_consumption")

    def test_nol_stok_dengan_laju(self):
        self.assertEqual(calc.hitung_stok([stock(qty=0, rn_daily_consumption=10)])[0]["sisa_hari"], 0)

    def test_konversi_daily_dari_unit_asli(self):
        r = calc.hitung_stok([stock(qty=4, unit="karung", base_quantity=100, base_unit="kg", conversion_status="ok", rn_daily_consumption=1)])[0]
        self.assertEqual((r["stok"], r["pemakaian_per_hari"], r["sisa_hari"]), (100, 25, 4))

    def test_base_zero_tidak_fallback(self):
        r = calc.hitung_stok([stock(qty=99, base_quantity=0, base_unit="kg", conversion_status="ok")])[0]
        self.assertEqual(r["stok"], 0)

    def test_konversi_belum_ditinjau(self):
        r = calc.hitung_stok([stock(qty=4, unit="karung", base_quantity=100, base_unit="kg", conversion_status="needs_review")])[0]
        self.assertEqual((r["stok"], r["unit"]), (4, "karung"))

    def test_tidak_campur_unit_dan_posko(self):
        result = calc.hitung_stok([stock(qty=100), stock("s2", 1, 2, unit="karung"), stock("s3", 1, 2, posko="P2")])
        self.assertEqual(len(result), 3)
        self.assertTrue(all(r["pemakaian_per_hari"] is None for r in result))

    def test_tambahan_stok_bukan_pemakaian_negatif(self):
        r = calc.hitung_stok([stock(qty=10), stock("s2", 100, 2)])[0]
        self.assertIsNone(r["sisa_hari"])

    def test_timestamp_sama(self):
        self.assertIsNone(calc.hitung_stok([stock(qty=100), stock("s2", 1)])[0]["sisa_hari"])

    def test_data_rusak_dilewati(self):
        self.assertEqual(calc.hitung_stok([stock(qty=-1), stock(qty=float("nan")), stock(observed_at_bad=True, qty=None)]), [])

    def test_stok_rusak_dan_jumlah_tidak_pasti_dilewati(self):
        self.assertEqual(calc.hitung_stok([stock(stock_state="damaged"), stock(quantity_mode="unknown")]), [])

    def test_surplus_dan_unit(self):
        rows = [stock(qty=20, rn_daily_consumption=10), stock("s2", 400, posko="P2", rn_daily_consumption=10), stock("s3", 900, posko="P3", unit="karung", rn_daily_consumption=1)]
        result = calc.hitung_stok(rows)
        self.assertEqual(result[0]["sumber_realokasi"], ["P2"])
        self.assertTrue(result[1]["calon_surplus"])

    def test_surplus_tanpa_laju_dan_umur(self):
        result = calc.hitung_stok([stock(qty=10), stock("s2", 1000, posko="P2")], now="2026-11-03")
        self.assertTrue(result[1]["calon_surplus"])
        self.assertEqual(result[0]["umur_hari"], 2)


class TestJarak(unittest.TestCase):
    def test_sama(self):
        self.assertEqual(calc.haversine(-6, 107, -6, 107), 0)

    def test_ekuator(self):
        self.assertAlmostEqual(calc.haversine(0, 0, 0, 1), 111.195, places=2)

    def test_jakarta_bandung(self):
        self.assertAlmostEqual(calc.haversine(-6.2, 106.8167, -6.9175, 107.6191), 119.5, delta=1)

    def test_antipode_dan_simetris(self):
        self.assertAlmostEqual(calc.haversine(0, 0, 0, 180), 20015.114, places=2)
        self.assertEqual(calc.haversine(10, 179, 10, -179), calc.haversine(10, -179, 10, 179))

    def test_invalid(self):
        for coords in [(None, 0, 0, 0), (91, 0, 0, 0), (0, 181, 0, 0), (float("nan"), 0, 0, 0)]:
            with self.subTest(coords=coords), self.assertRaises(ValueError):
                calc.haversine(*coords)


class TestKandidat(unittest.TestCase):
    def test_bantuan_48_jam_tanpa_identitas_keluar(self):
        offers = [dict(name="A", donor_name="Nama Rahasia", item_name="beras", quantity=10, unit="kg", creation="2026-11-01"),
                  dict(name="B", donor_name="NAMA RAHASIA", item_name="Beras", quantity=10, unit="kg", creation="2026-11-03")]
        result = calc.deteksi_kandidat(offers=offers)
        self.assertEqual(result[0]["rujukan"], ["A", "B"])
        self.assertNotIn("rahasia", json.dumps(result).lower())
        offers[1]["creation"] = "2026-11-03 00:00:01"
        self.assertEqual(calc.deteksi_kandidat(offers=offers), [])

    def test_batas_kandidat(self):
        rows = [dict(name=str(i), donor_name="D", item_name="beras", quantity=1, unit="kg", creation="2026-11-01") for i in range(20)]
        self.assertEqual(len(calc.deteksi_kandidat(offers=rows, max_candidates=10)), 10)

    def test_donor_kosong_atau_unit_beda(self):
        offers = [dict(name="A", donor_name="", item_name="beras", quantity=10, unit="kg", creation="2026-11-01")]*2
        self.assertEqual(calc.deteksi_kandidat(offers=offers), [])

    def test_stok_perubahan_naik_turun_dan_nol(self):
        for before, after in [(1, 6), (6, 1), (1, 0), (0, 1)]:
            with self.subTest(before=before, after=after):
                self.assertEqual(len(calc.deteksi_kandidat(stocks=[stock(qty=before), stock("s2", after, 2)])), 1)
        self.assertEqual(calc.deteksi_kandidat(stocks=[stock(qty=1), stock("s2", 5, 2)]), [])

    def test_stok_beda_satuan_tidak_dibandingkan(self):
        self.assertEqual(calc.deteksi_kandidat(stocks=[stock(qty=100), stock("s2", 1, 2, unit="karung")]), [])

    def test_need_outlier(self):
        rows = [dict(name=str(i), canonical_item="beras", unit="kg", quantity=q) for i, q in enumerate([10, 10, 101])]
        result = calc.deteksi_kandidat(needs=rows)
        self.assertEqual(result[0]["rujukan"], ["2"])
        rows[-1]["quantity"] = 100
        self.assertEqual(calc.deteksi_kandidat(needs=rows), [])

    def test_median_sampel_kecil_dan_nol(self):
        for amounts in ([1, 100], [0, 0, 100]):
            rows = [dict(name=str(i), canonical_item="beras", unit="kg", quantity=q) for i, q in enumerate(amounts)]
            self.assertEqual(calc.deteksi_kandidat(needs=rows), [])

    def test_tender_batas_dan_kelompok(self):
        rows = [dict(name=str(i), tender="T", bid_amount=q) for i, q in enumerate([49, 100, 100, 201])]
        self.assertEqual(len(calc.deteksi_kandidat(bids=rows)), 2)
        rows[0]["bid_amount"], rows[3]["bid_amount"] = 50, 200
        self.assertEqual(calc.deteksi_kandidat(bids=rows), [])
        rows[3].update(tender="OTHER", bid_amount=10000)
        self.assertEqual(calc.deteksi_kandidat(bids=rows), [])

    def test_laporan_lokasi_beda(self):
        text = "Jalan menuju desa tertutup banjir dan membutuhkan evakuasi segera"
        rows = [dict(name="R1", description=text, location_text="Desa A"), dict(name="R2", description=text.upper()+"!!!", location_text="Desa B")]
        self.assertEqual(calc.deteksi_kandidat(reports=rows)[0]["jenis"], "laporan_mirip")
        rows[1]["location_text"] = "Desa A"
        self.assertEqual(calc.deteksi_kandidat(reports=rows), [])

    def test_laporan_tanpa_lokasi_bukan_beda(self):
        text = "Jalan menuju desa tertutup banjir dan membutuhkan evakuasi segera"
        self.assertEqual(calc.deteksi_kandidat(reports=[dict(name="R1", description=text), dict(name="R2", description=text)]), [])


class TestEndpointMock(unittest.TestCase):
    """Uji kontrak endpoint, pemilahan input, penyimpanan, validasi rujukan."""
    def setUp(self):
        packages = {n: types.ModuleType(n) for n in ["frappe", "frappe.utils", "rescue_net", "rescue_net.ai", "rescue_net.ai.analysis", "rescue_net.ai.context", "rescue_net.reference_resolver"]}
        for n in ("rescue_net", "rescue_net.ai", "frappe"):
            packages[n].__path__ = []
        packages["rescue_net.ai"].analysis = packages["rescue_net.ai.analysis"]
        packages["rescue_net"].ai = packages["rescue_net.ai"]
        packages["rescue_net.ai.analysis_nala_calc"] = calc
        self.modules = patch.dict(sys.modules, packages)
        self.modules.start()
        self.addCleanup(self.modules.stop)
        self.f = packages["frappe"]
        self.f.whitelist = lambda: lambda fn: fn
        self.f.throw = Mock(side_effect=ValueError)
        self.f.get_all = Mock(return_value=[])
        self.f.db = types.SimpleNamespace(exists=Mock(return_value=True))
        packages["frappe.utils"].cint = lambda v: int(v or 0)
        packages["frappe.utils"].now_datetime = lambda: datetime(2026, 11, 16, 12)
        packages["rescue_net.ai.context"]._ai_scope_poskos = Mock(return_value=None)
        packages["rescue_net.reference_resolver"].resolve_disaster_event = lambda v: v
        self.a = packages["rescue_net.ai.analysis"]
        self.a._kunci = Mock(return_value={"provider": "local", "model_name": "mock"})
        self.a._simpan = Mock(return_value="AI-TEST")
        self.a._tanya = Mock(return_value="{}")
        self.ai_patch = patch("rescue_net.ai.analysis._tanya", return_value="{}")
        self.tanya = self.ai_patch.start()
        self.addCleanup(self.ai_patch.stop)
        self.mod = load("nala_endpoint_test", BASE / "analysis_nala.py")
        self.scope = packages["rescue_net.ai.context"]._ai_scope_poskos

    def test_triase_invalid_ids_bentuk_dan_urutan(self):
        rows = [dict(name="R1", description="banjir", latitude=-6.217, longitude=107.128), dict(name="R2")]
        self.f.get_all.return_value = rows
        self.tanya.return_value = json.dumps({"klaster": [{"judul": "rendah", "laporan": ["R1", "HANTU", {}], "urgensi": 1}, {"judul": "tinggi", "laporan": ["R2"], "urgensi": 99}, {"laporan": ["HANTU"]}], "darurat": [{"id": "HANTU"}, {"id": "R1"}, {"id": {}}], "ringkasan": "contoh"})
        result = self.mod.triase_laporan("U", "E")
        self.assertEqual([c["urgensi"] for c in result["structured"]["klaster"]], [5, 1])
        self.assertEqual(result["structured"]["klaster"][1]["laporan"], ["R1"])
        self.assertEqual([d["id"] for d in result["structured"]["darurat"]], ["R1"])
        self.assertTrue(self.tanya.call_args.kwargs["json_mode"])
        self.assertEqual(self.a._simpan.call_args.args[1], "triase_laporan")
        self.assertEqual(self.f.get_all.call_args.kwargs["limit_page_length"], 150)

    def test_privasi_teks_dan_koordinat(self):
        row = dict(name="R1", title="Pasien Rahasia 081234567890 banjir", description="Pasien Rahasia sakit diabetes. hubungi test@example.org 081234567890. butuh air bersih dan evakuasi", urgent_needs="tenda untuk Rahasia", location_text="rumah Rahasia nomor 12", reporter_name="Rahasia", reporter_phone="081234567890", latitude=-6.21345, longitude=107.12345)
        self.f.get_all.return_value = [row]
        self.mod.triase_laporan("U", "E")
        data = json.loads(self.tanya.call_args.args[2])
        payload = json.dumps(data).lower()
        for secret in ("rahasia", "081234567890", "example.org", "diabetes", "reporter_name", "reporter_phone"):
            self.assertNotIn(secret, payload)
        self.assertIn("evakuasi", payload)
        self.assertEqual(data[0]["latitude"], -6.21)
        self.assertLessEqual(len(data[0]["description"]), 600)

    def test_negasi_teks_tetap_ada(self):
        self.assertEqual(self.mod._operasional("tidak perlu evakuasi, belum ada banjir, tanpa air bersih"),
                         "tidak perlu evakuasi, belum ada banjir, tanpa air bersih")

    def test_json_tidak_sah_tidak_disimpan(self):
        for reply in ("not json", "[]"):
            self.tanya.return_value = reply
            with self.assertRaises(ValueError):
                self.mod.triase_laporan("U", "E")
        self.a._simpan.assert_not_called()

    def test_laporan_tidak_terklaster(self):
        self.f.get_all.return_value = [{"name": "R1"}]
        result = self.mod.triase_laporan("U", "E")
        self.assertEqual(result["structured"]["belum_terklaster"], ["R1"])

    def test_scope_terbatas_dan_kosong(self):
        self.scope.return_value = ["P1"]
        self.mod.prakiraan_stok("U", "E")
        self.assertEqual(self.f.get_all.call_args.kwargs["filters"]["posko"], ["in", ["P1"]])
        self.f.get_all.reset_mock()
        self.scope.return_value = []
        result = self.mod.cek_kejanggalan("U", "E")
        self.f.get_all.assert_not_called()
        self.assertEqual(result["structured"]["kandidat"], [])

    def test_bencana_tidak_ada_ditolak(self):
        self.f.db.exists.return_value = False
        with self.assertRaises(ValueError):
            self.mod.prakiraan_stok("U", "HANTU")
        self.f.get_all.assert_not_called()
        self.tanya.assert_not_called()

    def test_kunci_gagal_sebelum_baca_data(self):
        self.a._kunci.side_effect = ValueError("no login")
        with self.assertRaises(ValueError):
            self.mod.prakiraan_stok("U", "E")
        self.f.get_all.assert_not_called()
        self.tanya.assert_not_called()

    def test_stok_ai_hanya_hasil_hitung(self):
        self.f.get_all.return_value = [stock(qty=10, rn_daily_consumption=5)]
        self.tanya.return_value = "Rencana"
        result = self.mod.prakiraan_stok("U", "E")
        self.assertEqual(result["structured"]["stok"][0]["sisa_hari"], 2)
        payload = self.tanya.call_args.args[2]
        self.assertNotIn('"name": "s1"', payload)
        self.assertEqual(self.a._simpan.call_args.args[1], "prakiraan_stok")

    def test_gempa_radius_aktif_urut_dan_nol(self):
        quake = dict(name="W", latitude=0, longitude=0, magnitude=6, depth_km=10, potential="Tidak berpotensi tsunami")
        poskos = [dict(name="FAR", latitude=0, longitude=3), dict(name="NEAR", latitude=0, longitude=1), dict(name="ZERO", latitude=0, longitude=0), dict(name="CLOSED", latitude=0, longitude=0, operational_status="closed"), dict(name="BAD", latitude=None, longitude=0), dict(name="EXPIRED", latitude=0, longitude=0, active_until="2026-11-15")]
        self.f.get_all.side_effect = [[quake], poskos]
        self.tanya.return_value = "Saran"
        result = self.mod.dampak_gempa("U", warning="W")
        self.assertEqual([p["posko"] for p in result["structured"]["posko"]], ["ZERO", "NEAR"])
        self.assertIn("Tidak berpotensi tsunami", self.tanya.call_args.args[2])
        self.assertEqual(self.a._simpan.call_args.args[1], "gempa")
        self.assertEqual(self.f.get_all.call_args_list[0].kwargs["filters"], {"kind": "earthquake", "name": "W"})

    def test_gempa_tidak_ada_atau_koordinat_rusak(self):
        for rows in ([], [{"latitude": None, "longitude": 10}]):
            self.f.get_all.return_value = rows
            with self.assertRaises(ValueError):
                self.mod.dampak_gempa("U")
        self.tanya.assert_not_called()

    def test_kejanggalan_penilaian_id_palsu_dibuang(self):
        def rows(doctype, **kwargs):
            if doctype == "RN Stock Observation":
                return [stock(qty=1), stock("s2", 10, 2)]
            return []
        self.f.get_all.side_effect = rows
        self.tanya.return_value = json.dumps({"penilaian": [{"id": "K0001", "tingkat": "tinggi", "penjelasan": "perlu dicek"}, {"id": "PALSU", "tingkat": "tinggi"}]})
        result = self.mod.cek_kejanggalan("U", "E")
        self.assertEqual(len(result["structured"]["kandidat"]), 1)
        self.assertEqual(result["structured"]["kandidat"][0]["penilaian"]["tingkat"], "tinggi")
        self.assertEqual(self.a._simpan.call_args.args[1], "kejanggalan")

    def test_tender_event_dan_scope_dijaga(self):
        def rows(doctype, **kw):
            return [{"name": "T1"}] if doctype == "RN Procurement Tender" else []
        self.f.get_all.side_effect = rows
        self.mod.cek_kejanggalan("U", "E")
        calls = [c for c in self.f.get_all.call_args_list if c.args[0] == "RN Tender Bid"]
        self.assertEqual(calls[0].kwargs["filters"]["tender"], ["in", ["T1"]])
        self.f.get_all.reset_mock()
        self.scope.return_value = ["P1"]
        self.mod.cek_kejanggalan("U", "E")
        self.assertFalse(any(c.args[0] in ("RN Tender Bid", "RN Procurement Tender") for c in self.f.get_all.call_args_list))


if __name__ == "__main__":
    unittest.main(verbosity=2)
