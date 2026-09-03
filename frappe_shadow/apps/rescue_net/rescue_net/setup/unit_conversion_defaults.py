import frappe

# 1 <from_unit> = <factor> <to_base_unit>. Editable later in Frappe Desk
# (RN Unit Conversion). certainty "perkiraan" -> panel marks needs_review.
RULES = [
    # --- Air Minum Kemasan -> liter -------------------------------------
    ("Air Minum Kemasan: gelas",   "canonical_item", "Air Minum Kemasan", "", "gelas",   "liter", 0.24, "perkiraan", 200),
    ("Air Minum Kemasan: botol",   "canonical_item", "Air Minum Kemasan", "", "botol",   "liter", 0.6,  "perkiraan", 200),
    ("Air Minum Kemasan: dus",     "canonical_item", "Air Minum Kemasan", "", "dus",     "liter", 5.76, "perkiraan", 200),
    ("Air Minum Kemasan: karton",  "canonical_item", "Air Minum Kemasan", "", "karton",  "liter", 5.76, "perkiraan", 200),
    ("Air Minum Kemasan: galon",   "canonical_item", "Air Minum Kemasan", "", "galon",   "liter", 19.0, "standar",   200),
    ("Air Minum Kemasan: jerigen", "canonical_item", "Air Minum Kemasan", "", "jerigen", "liter", 19.0, "perkiraan", 200),
    # --- Mie Instan -> bungkus ----------------------------------------
    ("Mie Instan: dus",     "canonical_item", "Mie Instan", "", "dus",     "bungkus", 40.0, "perkiraan", 200),
    ("Mie Instan: karton",  "canonical_item", "Mie Instan", "", "karton",  "bungkus", 40.0, "perkiraan", 200),
    ("Mie Instan: pak",     "canonical_item", "Mie Instan", "", "pak",     "bungkus", 5.0,  "standar",   200),
    ("Mie Instan: renceng", "canonical_item", "Mie Instan", "", "renceng", "bungkus", 10.0, "perkiraan", 200),
    # --- Beras -> kg -------------------------------------------------
    ("Beras: karung", "canonical_item", "Beras", "", "karung", "kg", 25.0, "perkiraan", 200),
    ("Beras: sak",    "canonical_item", "Beras", "", "sak",    "kg", 25.0, "perkiraan", 200),
    ("Beras: liter",  "canonical_item", "Beras", "", "liter",  "kg", 0.8,  "perkiraan", 200),
    # --- Minyak Goreng -> liter ------------------------------------
    ("Minyak Goreng: dus",     "canonical_item", "Minyak Goreng", "", "dus",     "liter", 12.0, "perkiraan", 200),
    ("Minyak Goreng: jerigen", "canonical_item", "Minyak Goreng", "", "jerigen", "liter", 18.0, "perkiraan", 200),
    ("Minyak Goreng: botol",   "canonical_item", "Minyak Goreng", "", "botol",   "liter", 1.0,  "perkiraan", 200),
    # --- group-level fallbacks -----------------------------------------
    ("Air Minum: dus",       "canonical_group", "", "Air Minum",    "dus",    "liter", 5.76, "perkiraan", 100),
    ("Bahan Pangan: karung", "canonical_group", "", "Bahan Pangan", "karung", "kg",    25.0, "perkiraan", 100),
    # --- global constants --------------------------------------------
    ("Global: lusin", "global", "", "", "lusin", "pcs", 12.0,  "standar", 50),
    ("Global: kodi",  "global", "", "", "kodi",  "pcs", 20.0,  "standar", 50),
    ("Global: gross", "global", "", "", "gross", "pcs", 144.0, "standar", 50),
]


def install_defaults():
    if not frappe.db.exists("DocType", "RN Unit Conversion"):
        return {"created": [], "existing": [], "status": "doctype_not_ready"}

    created, existing = [], []
    for (name, scope, item, group, from_u, to_u, factor, certainty, prio) in RULES:
        if frappe.db.exists("RN Unit Conversion", name):
            existing.append(name)
            continue
        frappe.get_doc({
            "doctype": "RN Unit Conversion",
            "conversion_name": name,
            "enabled": 1,
            "scope_type": scope,
            "canonical_item": item,
            "canonical_group": group,
            "from_unit": from_u,
            "to_base_unit": to_u,
            "factor": factor,
            "certainty": certainty,
            "priority": prio,
        }).insert(ignore_permissions=True)
        created.append(name)

    return {
        "created": created,
        "existing": existing,
        "total_defaults": len(RULES),
        "status": "PASS",
    }
