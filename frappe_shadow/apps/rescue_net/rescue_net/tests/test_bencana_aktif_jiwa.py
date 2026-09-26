"""Bencana Aktif "Jiwa Berisiko" drill: each posko appears once, with its jiwa
(aspect counts only) and every problem listed under it."""

from rescue_net.api_control_centre import _ba_jiwa_by_posko
from rescue_net.tests.factories import RNTestCase


def _item(title, count, detail="x"):
    return {"title": title, "href": f"p.html?id={title}", "region": "R", "count": count, "detail": detail}


class TestJiwaPerPosko(RNTestCase):
    def test_a_posko_in_many_categories_is_one_row(self):
        cats = [
            {"key": "jiwa_medis", "label": "Aspek Medis — 3 jiwa", "items": [_item("Medis Kalianda", 3)]},
            {"key": "jiwa_shelter", "label": "Aspek Shelter — 210 jiwa", "items": [_item("GOR Kalianda", 210)]},
            {"key": "medis_kritis", "label": "Kasus Medis Kritis", "items": [_item("Medis Kalianda", 2)]},
            {"key": "kekurangan_obat", "label": "Kekurangan Obat & Alat Kesehatan", "items": [_item("Medis Kalianda", 2)]},
            {"key": "shelter_kritis", "label": "Shelter Kondisi Kritis", "items": [_item("GOR Kalianda", 2)]},
            {"key": "laporan_korban", "label": "Laporan Korban", "items": [_item("Laporan warga", 15)]},
        ]
        rows = _ba_jiwa_by_posko(cats)
        self.assertEqual([r["title"] for r in rows], ["GOR Kalianda", "Medis Kalianda"])
        medis = rows[1]
        self.assertEqual(medis["jiwa"], 3)  # the 2 critical cases are not added again
        self.assertEqual([p["key"] for p in medis["problems"]], ["jiwa_medis", "medis_kritis", "kekurangan_obat"])
        self.assertEqual(sum(r["jiwa"] for r in rows), 213)
