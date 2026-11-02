"""Fill RN Admin Area.center_lat / center_lng (provinsi, kab/kota, kecamatan) where still empty.

Owner 2026-11-02: the disaster registration map should jump to the chosen area. Source: geo/admin_area_centers.json
built from cahyadsn/wilayah + cahyadsn/wilayah_boundaries (MIT License, (c) cahya dsn; Kepmendagri codes).
Never overwrites a centre that is already set; safe to run again."""

import json
import os

import frappe


def execute():
    path = os.path.join(frappe.get_app_path("rescue_net"), "geo", "admin_area_centers.json")
    centers = json.load(open(path, encoding="utf-8"))["centers"]
    empty = set(frappe.get_all("RN Admin Area", filters={"name": ["in", list(centers)]},
                               or_filters=[["center_lat", "is", "not set"], ["center_lat", "=", 0]],
                               pluck="name", limit_page_length=0))
    for code in empty:
        lat, lng = centers[code]
        frappe.db.set_value("RN Admin Area", code, {"center_lat": lat, "center_lng": lng}, update_modified=False)
    frappe.db.commit()
    print(f"admin_area_centers: filled {len(empty)} of {len(centers)}")
