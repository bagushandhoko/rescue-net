"""Owner 2026-10-26 ("lengkapi konversi"): common relief packages, so receipts
in another unit convert automatically (services/units.py). Adds a row only
when no enabled row exists for the same scope / item / from_unit."""

import frappe

ROWS = [
    # (scope_type, canonical_item, canonical_group, from_unit, to_base_unit, factor, certainty, note)
    ("canonical_item", "Gula Pasir", "", "karung", "kg", 50, "perkiraan", "Karung gula umumnya 50 kg"),
    ("canonical_item", "Gula Pasir", "", "sak", "kg", 50, "perkiraan", ""),
    ("canonical_item", "Tepung Terigu", "", "karung", "kg", 25, "perkiraan", ""),
    ("canonical_item", "Telur", "", "tray", "butir", 30, "standar", "1 tray = 30 butir"),
    ("canonical_item", "Telur", "", "peti", "butir", 300, "perkiraan", "10 tray"),
    ("canonical_item", "Minyak Goreng", "", "pouch", "liter", 2, "perkiraan", "Pouch 2 liter"),
    ("canonical_item", "Air Bersih", "", "tangki", "liter", 5000, "perkiraan", "Truk tangki 5.000 liter"),
    ("canonical_item", "Air Bersih", "", "jerigen", "liter", 20, "perkiraan", ""),
    ("canonical_item", "Air Bersih", "", "toren", "liter", 1000, "perkiraan", ""),
    ("canonical_item", "Air Minum Kemasan", "", "karton", "liter", 5.76, "perkiraan", "24 × 240 ml"),
    ("canonical_group", "", "Bahan Pangan", "sak", "kg", 25, "perkiraan", ""),
    ("global", "", "", "rim", "lembar", 500, "standar", ""),
    ("global", "", "", "lusin", "pcs", 12, "standar", ""),
]


def execute():
    if not frappe.db.exists("DocType", "RN Unit Conversion"):
        return
    for st, item, group, fu, tu, factor, cert, note in ROWS:
        f = {"scope_type": st, "from_unit": fu, "enabled": 1}
        if item:
            f["canonical_item"] = item
        if group:
            f["canonical_group"] = group
        if frappe.db.exists("RN Unit Conversion", f):
            continue
        frappe.get_doc({
            "doctype": "RN Unit Conversion", "conversion_name": "%s %s → %s" % (item or group or "Semua", fu, tu),
            "enabled": 1, "scope_type": st, "canonical_item": item or None, "canonical_group": group or None,
            "from_unit": fu, "to_base_unit": tu, "factor": factor, "certainty": cert, "priority": 10, "notes": note,
        }).insert(ignore_permissions=True)
