import frappe

RULES = [
    {
        "rule_name": "Air Minum Kemasan",
        "priority": 200,
        "canonical_category": "Pangan & Air",
        "canonical_group": "Air Minum",
        "canonical_item": "Air Minum Kemasan",
        "match_mode": "contains",
        "aliases": "\n".join([
            "air mineral",
            "aqua",
            "aqua kecil",
            "air botol",
            "air kemasan",
            "mineral water",
            "bottled water",
        ]),
        "confidence": 95,
    },
    {
        "rule_name": "Air Bersih",
        "priority": 200,
        "canonical_category": "Pangan & Air",
        "canonical_group": "Air Bersih",
        "canonical_item": "Air Bersih",
        "match_mode": "contains",
        "aliases": "\n".join([
            "air bersih",
            "air bersih siap distribusi",
            "air mandi",
            "air untuk mandi",
            "air sanitasi",
            "air layak pakai",
            "tandon air",
            "tangki air",
            "air tangki",
            "water tank",
        ]),
        "confidence": 95,
    },
    {
        "rule_name": "Beras",
        "priority": 200,
        "canonical_category": "Pangan & Air",
        "canonical_group": "Bahan Pangan",
        "canonical_item": "Beras",
        "match_mode": "contains",
        "aliases": "\n".join([
            "beras",
            "beras medium",
            "beras premium",
        ]),
        "confidence": 95,
    },
    {
        "rule_name": "Mie Instan",
        "priority": 210,
        "canonical_category": "Pangan & Air",
        "canonical_group": "Bahan Pangan",
        "canonical_item": "Mie Instan",
        "match_mode": "contains",
        "aliases": "\n".join([
            "mie instan",
            "mi instan",
            "indomie",
            "supermi",
            "sarimi",
            "mie telur",
            "mie",
        ]),
        "confidence": 95,
    },
    {
        "rule_name": "Minyak Goreng",
        "priority": 210,
        "canonical_category": "Pangan & Air",
        "canonical_group": "Bahan Pangan",
        "canonical_item": "Minyak Goreng",
        "match_mode": "contains",
        "aliases": "\n".join([
            "minyak goreng",
            "minyak sayur",
            "migor",
        ]),
        "confidence": 95,
    },
    {
        "rule_name": "Makanan Siap Saji",
        "priority": 200,
        "canonical_category": "Pangan & Air",
        "canonical_group": "Makanan Siap Saji",
        "canonical_item": "Makanan Siap Saji",
        "match_mode": "contains",
        "aliases": "\n".join([
            "makanan siap saji",
            "nasi bungkus",
            "nasi kotak",
            "makanan matang",
            "ready meal",
        ]),
        "confidence": 95,
    },
    {
        "rule_name": "Obat Umum",
        "priority": 100,
        "canonical_category": "Medis & Kesehatan",
        "canonical_group": "Obat & Perbekalan Medis",
        "canonical_item": "Perbekalan Medis",
        "match_mode": "exact",
        "aliases": "\n".join([
            "obat",
            "obat-obatan",
            "obat obatan",
            "perbekalan medis",
        ]),
        "confidence": 90,
    },
    {
        "rule_name": "Paracetamol",
        "priority": 250,
        "canonical_category": "Medis & Kesehatan",
        "canonical_group": "Obat & Perbekalan Medis",
        "canonical_item": "Paracetamol",
        "match_mode": "contains",
        "aliases": "\n".join([
            "paracetamol",
            "parasetamol",
        ]),
        "confidence": 98,
    },
    {
        "rule_name": "Masker",
        "priority": 200,
        "canonical_category": "Medis & Kesehatan",
        "canonical_group": "APD & Perlindungan",
        "canonical_item": "Masker",
        "match_mode": "contains",
        "aliases": "\n".join([
            "masker",
            "masker medis",
            "masker bedah",
            "surgical mask",
            "n95",
        ]),
        "confidence": 95,
    },
    {
        "rule_name": "Hygiene Kit",
        "priority": 150,
        "canonical_category": "Sanitasi & Hygiene",
        "canonical_group": "Hygiene",
        "canonical_item": "Hygiene Kit",
        "match_mode": "contains",
        "aliases": "\n".join([
            "sabun",
            "pembalut",
            "sikat gigi",
            "pasta gigi",
            "hygiene kit",
            "paket kebersihan",
        ]),
        "confidence": 92,
    },
    {
        "rule_name": "Perlengkapan Shelter",
        "priority": 150,
        "canonical_category": "Shelter & Hunian",
        "canonical_group": "Perlengkapan Pengungsian",
        "canonical_item": "Perlengkapan Shelter",
        "match_mode": "contains",
        "aliases": "\n".join([
            "tenda",
            "selimut",
            "matras",
            "terpal",
            "sleeping bag",
        ]),
        "confidence": 92,
    },
    {
        "rule_name": "BBM",
        "priority": 200,
        "canonical_category": "Energi & Bahan Bakar",
        "canonical_group": "Bahan Bakar",
        "canonical_item": "BBM",
        "match_mode": "contains",
        "aliases": "\n".join([
            "bbm",
            "bensin",
            "solar",
            "pertalite",
            "pertamax",
            "biosolar",
            "dexlite",
        ]),
        "confidence": 95,
    },
    {
        "rule_name": "Genset",
        "priority": 200,
        "canonical_category": "Energi & Bahan Bakar",
        "canonical_group": "Peralatan Energi",
        "canonical_item": "Genset",
        "match_mode": "contains",
        "aliases": "\n".join([
            "genset",
            "generator listrik",
            "generator",
        ]),
        "confidence": 95,
    },
]

def install_defaults():
    created = []
    existing = []

    if not frappe.db.exists(
        "DocType",
        "RN Normalization Rule",
    ):
        return {
            "created": [],
            "existing": [],
            "status": "doctype_not_ready",
        }

    for row in RULES:
        name = row["rule_name"]

        if frappe.db.exists(
            "RN Normalization Rule",
            name,
        ):
            existing.append(name)
            continue

        frappe.get_doc({
            "doctype": "RN Normalization Rule",
            "enabled": 1,
            **row,
        }).insert(ignore_permissions=True)

        created.append(name)

    return {
        "created": created,
        "existing": existing,
        "total_defaults": len(RULES),
        "status": "PASS",
    }

