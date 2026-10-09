"""ADR-0005 A.5 / Fase 9c D.2: petakan RN Posko + RN Community Report dari nama -> kode Kemendagri.
Yang tidak cocok TIDAK ditebak: admin_area_id dikosongkan, teks lama disimpan di area_legacy_text, area_unmatched=1."""

import frappe

from rescue_net.services.admin_areas import remap_existing


def execute():
    if not frappe.db.has_column("RN Posko", "area_unmatched") or not frappe.db.has_column("RN Community Report", "area_unmatched"):
        return
    if not frappe.db.count("RN Admin Area"):
        return
    print("[map_admin_areas_by_code]", remap_existing(dry_run=False))
