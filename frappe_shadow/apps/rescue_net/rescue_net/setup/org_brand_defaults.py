import frappe

# Per-organisation accent colour for the "Koordinasi Internal Organisasi" view
# (koordinasi-organisasi.html header + rn-posko-scope.js "Hanya-lihat" banner).
# Only seeds an org whose `brand_color` is still empty — a colour set in Desk is
# never overwritten. `brand_logo` is left alone: there are no first-party logo
# assets for these simulation orgs, and the initial-badge already carries identity.
#
# Colours are approximate, simulation-only accents (the orgs are [SIMULASI]);
# they are not asserted to be any institution's official brand value.
BRANDS = {
    # --- Komunitas Landrover (primary demo) --------------------------------
    "SIM-LR-ORG": "#2f6f3e",                 # heritage green (matches _ORG_BRAND_ACCENT)
    "organizations:org-landrover": "#005a2b",
    # --- Simulasi Dukungan Nasional -------------------------------------
    "SIM-NS-BNPB": "#1f5fa8",                # BNPB blue
    "SIM-NS-GARUDA": "#0f4c81",              # Garuda blue
    "SIM-NS-TNIAL": "#0b3d69",               # navy
    "SIM-NS-PELAJAR": "#b8232f",             # OSIS red
    "SIM-NS-WARGA": "#a8571e",               # warga / community warm brown
    # --- Simulasi Logistik ---------------------------------------------
    "SIM-LOG-ORG-SOLID": "#6a3d9a",          # purple
    # --- Simulasi Karhutla Kalbar ------------------------------------
    "KH-ORG-BPBD": "#1f5fa8",
    "KH-ORG-BKSDA": "#2e7d32",               # conservation green
    "KH-ORG-MANGGALA": "#e65100",            # fire orange
    "KH-ORG-MPA": "#8d6e63",                 # earthy
    "KH-ORG-TNIAU": "#4a6fa5",               # air-force blue
}


def install_defaults():
    if not frappe.db.exists("DocType", "RN Organization"):
        return {"set": [], "skipped": [], "status": "doctype_not_ready"}
    try:
        if not frappe.db.has_column("RN Organization", "brand_color"):
            return {"set": [], "skipped": [], "status": "column_not_ready"}
    except Exception:
        return {"set": [], "skipped": [], "status": "column_not_ready"}

    set_, skipped = [], []
    for org_name, color in BRANDS.items():
        if not frappe.db.exists("RN Organization", org_name):
            skipped.append((org_name, "missing"))
            continue
        current = (frappe.db.get_value("RN Organization", org_name, "brand_color") or "").strip()
        if current:
            skipped.append((org_name, "already_set"))
            continue
        frappe.db.set_value("RN Organization", org_name, "brand_color", color,
                            update_modified=False)
        set_.append(org_name)

    if set_:
        frappe.db.commit()
    return {"set": set_, "skipped": skipped, "status": "ok"}
