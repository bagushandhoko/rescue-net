"""Indeks gabungan (latitude, longitude) untuk penyaring kotak lokasi services.geo (owner 24 Nov 2026, langkah 1
menuju PostGIS). Hanya menambah indeks; aman diulang (add_index melewati indeks yang sudah ada)."""

import frappe

TABLES = ("RN Posko", "RN Community Report", "RN Transport Space", "RN Missing Person Report",
          "RN Found Person Report", "RN Medical Case")


def execute():
    for dt in TABLES:
        if not frappe.db.table_exists(dt):
            continue
        meta = frappe.get_meta(dt)
        if meta.has_field("latitude") and meta.has_field("longitude"):
            frappe.db.add_index(dt, ["latitude", "longitude"], "rn_lat_lng")
