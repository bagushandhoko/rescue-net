"""Admin area centres (owner 2026-11-02): the patch fills empty centres from geo/admin_area_centers.json and never
overwrites an existing one; get_area returns the centre for the disaster-registration map."""

import frappe

from rescue_net.api_admin_areas import get_area
from rescue_net.patches.v2026_11 import admin_area_centers
from rescue_net.tests.factories import RNTestCase, as_guest


class TestAdminAreaCenters(RNTestCase):
    def _area(self, code, name, level, parent=None, **kw):
        if frappe.db.exists("RN Admin Area", code):
            frappe.db.set_value("RN Admin Area", code, dict({"center_lat": None, "center_lng": None}, **kw))
        else:
            frappe.get_doc(dict({"doctype": "RN Admin Area", "code": code, "area_name": name, "level": level,
                                 "parent_code": parent, "enabled": 1}, **kw)).insert(ignore_permissions=True)

    def test_fill_empty_keep_existing(self):
        self._area("32", "Jawa Barat", "province")
        self._area("32.05", "Kabupaten Garut", "city", "32")
        self._area("32.04", "Kabupaten Bandung", "city", "32", center_lat=1.0, center_lng=2.0)
        admin_area_centers.execute()
        self.assertAlmostEqual(frappe.db.get_value("RN Admin Area", "32.05", "center_lat"), -7.20267, places=3)
        self.assertEqual(frappe.db.get_value("RN Admin Area", "32.04", ["center_lat", "center_lng"]), (1.0, 2.0))
        with as_guest():
            a = get_area("32.05")["area"]
        self.assertAlmostEqual(a["center_lng"], 107.886, places=2)
