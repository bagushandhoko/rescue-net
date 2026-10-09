"""Lanjutan map_admin_areas_by_code: baris yang tadinya 'tak cocok' tetapi sebagian namanya cocok (mis. provinsi+kabupaten
cocok, desanya tidak ada di data) kini memakai tingkat terdalam yang pasti; tetap ditandai area_unmatched untuk dilengkapi."""

import frappe

from rescue_net.services.admin_areas import remap_existing


def execute():
    if not frappe.db.has_column("RN Posko", "area_unmatched") or not frappe.db.count("RN Admin Area"):
        return
    print("[map_admin_areas_partial]", remap_existing(dry_run=False))
