"""services.geo (owner 24 Nov 2026, langkah 1 menuju PostGIS): kotak lokasi tidak pernah membuang titik yang
sebenarnya masuk radius, dan near() sama hasilnya dengan menghitung semua baris."""

import random

from rescue_net.services import geo
from rescue_net.tests.factories import RNTestCase, make_event, make_posko


class TestGeo(RNTestCase):
    def test_km_known_distance_and_missing(self):
        # Jakarta (Monas) - Bandung (Gedung Sate) ~ 116-120 km garis lurus
        d = geo.km(-6.1754, 106.8272, -6.9025, 107.6188)
        self.assertTrue(110 < d < 125, d)
        self.assertIsNone(geo.km(None, 1, 2, 3))

    def test_bbox_never_drops_point_inside_radius(self):
        rnd = random.Random(7)
        for _ in range(3000):
            lat, lng = rnd.uniform(-11, 6), rnd.uniform(95, 141)
            r = rnd.choice([1, 10, 100, 300])
            plat, plng = lat + rnd.uniform(-4, 4), lng + rnd.uniform(-4, 4)
            d = geo.km(lat, lng, plat, plng)
            la0, la1, lo0, lo1 = geo.bbox(lat, lng, r)
            if d <= r:
                self.assertTrue(la0 <= plat <= la1 and lo0 <= plng <= lo1, (lat, lng, r, plat, plng, d))

    def test_near_matches_full_scan_sorted_and_skips_zero(self):
        ev = make_event()
        pts = [(-6.30, 106.90), (-6.21, 106.81), (-7.80, 110.36), (-2.0, 120.0)]
        made = [make_posko(ev, latitude=a, longitude=b) for a, b in pts]
        zero = make_posko(ev, latitude=0, longitude=0)
        got = geo.near("RN Posko", -6.20, 106.80, 100, fields=["title"], filters={"disaster_event": ev.name})
        names = [r.name for r in got]
        self.assertEqual(names, [made[1].name, made[0].name])
        self.assertNotIn(zero.name, names)
        self.assertTrue(all(r.km <= 100 for r in got))
