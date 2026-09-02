import re


RULES = [
    {
        "kind": "barang",
        "category": "Sanitasi & Hygiene",
        "group": "Air Bersih Non-Konsumsi",
        "item": "Air Bersih Non-Konsumsi",
        "terms": [
            "air untuk mandi", "air mandi", "air untuk cuci",
            "air cuci", "air sanitasi"
        ],
    },
    {
        "kind": "barang",
        "category": "Pangan & Air",
        "group": "Air Minum",
        "item": "Air Minum Kemasan",
        "terms": [
            "air mineral", "air minum", "aqua",
            "air kemasan", "air botol"
        ],
    },
    {
        "kind": "barang",
        "category": "Pangan & Air",
        "group": "Makanan Siap Saji",
        "item": "Makanan Siap Saji",
        "terms": [
            "nasi bungkus", "makanan siap saji",
            "makanan matang", "makanan siap makan"
        ],
    },
    {
        "kind": "barang",
        "category": "Pangan & Air",
        "group": "Bahan Pangan",
        "item": "Bahan Pangan",
        "terms": [
            "beras", "mie instan", "mi instan",
            "sembako", "bahan pangan"
        ],
    },
    {
        "kind": "barang",
        "category": "Medis & Kesehatan",
        "group": "Obat & Perbekalan Medis",
        "item": "Perbekalan Medis",
        "terms": [
            "obat", "perban", "infus", "masker medis",
            "alat kesehatan", "alkes"
        ],
    },
    {
        "kind": "barang",
        "category": "Shelter & Hunian",
        "group": "Perlengkapan Pengungsian",
        "item": "Perlengkapan Shelter",
        "terms": [
            "tenda", "selimut", "matras",
            "terpal", "shelter"
        ],
    },
    {
        "kind": "barang",
        "category": "Sanitasi & Hygiene",
        "group": "Hygiene",
        "item": "Hygiene Kit",
        "terms": [
            "hygiene", "sabun", "pembalut",
            "popok", "toiletries"
        ],
    },
    {
        "kind": "barang",
        "category": "Energi & Bahan Bakar",
        "group": "Bahan Bakar",
        "item": "BBM",
        "terms": [
            "solar", "bensin", "bbm",
            "bahan bakar"
        ],
    },
    {
        "kind": "jasa",
        "category": "Transportasi",
        "group": "Evakuasi",
        "item": "Transportasi Evakuasi",
        "terms": [
            "evakuasi", "kendaraan evakuasi",
            "transport korban"
        ],
    },
    {
        "kind": "jasa",
        "category": "Medis & Kesehatan",
        "group": "Transportasi Medis",
        "item": "Ambulans",
        "terms": [
            "ambulans", "ambulance",
            "transport pasien"
        ],
    },
    {
        "kind": "jasa",
        "category": "Tenaga & Relawan",
        "group": "Relawan",
        "item": "Tenaga Relawan",
        "terms": [
            "relawan", "tenaga bantuan",
            "tenaga lapangan"
        ],
    },
    {
        "kind": "jasa",
        "category": "Peralatan Operasional",
        "group": "Ekskavator",
        "item": "Ekskavator",
        "terms": [
            "excavator", "ekskavator", "bulldozer",
        ],
    },
    {
        "kind": "jasa",
        "category": "Peralatan Operasional",
        "group": "Genset",
        "item": "Genset",
        "terms": [
            "genset", "generator", "generator set",
        ],
    },
    {
        "kind": "jasa",
        "category": "Peralatan Operasional",
        "group": "Pompa Air",
        "item": "Pompa Air",
        "terms": [
            "pompa air", "pompa lumpur", "water pump", "pompa",
        ],
    },
    {
        "kind": "jasa",
        "category": "Peralatan Operasional",
        "group": "Forklift",
        "item": "Forklift",
        "terms": [
            "forklift",
        ],
    },
    {
        "kind": "jasa",
        "category": "Peralatan Operasional",
        "group": "Chainsaw",
        "item": "Chainsaw",
        "terms": [
            "chainsaw", "gergaji mesin", "gergaji chainsaw",
        ],
    },
    {
        "kind": "jasa",
        "category": "Peralatan Operasional",
        "group": "Perahu Karet",
        "item": "Perahu Karet",
        "terms": [
            "perahu karet", "rubber boat", "perahu evakuasi",
        ],
    },
    {
        "kind": "jasa",
        "category": "Peralatan Operasional",
        "group": "Alat Berat",
        "item": "Layanan Alat Berat",
        "terms": [
            "alat berat",
        ],
    },
    {
        "kind": "barang",
        "category": "Komunikasi & IT",
        "group": "Peralatan Komunikasi",
        "item": "Peralatan Komunikasi",
        "terms": [
            "radio komunikasi", "ht", "handy talky",
            "starlink", "internet darurat"
        ],
    },
]


ESTIMATE_TERMS = [
    "sekitar", "kira-kira", "kira kira",
    "kurang lebih", "lebih kurang", "±",
    "perkiraan", "estimasi"
]


def classify_text(text):
    raw = (text or "").strip()
    normalized = raw.lower()

    result = {
        "raw_need_text": raw,
        "item_kind": "tidak_diketahui",
        "canonical_category": None,
        "canonical_group": None,
        "canonical_item": None,
        "normalization_source": "rule",
        "normalization_confidence": 35,
        "normalization_status": "suggested",
        "quantity_mode": "unknown",
        "quantity_min": None,
        "quantity_max": None,
        "estimate_text": None,
    }

    for rule in RULES:
        if any(term in normalized for term in rule["terms"]):
            result.update({
                "item_kind": rule["kind"],
                "canonical_category": rule["category"],
                "canonical_group": rule["group"],
                "canonical_item": rule["item"],
                "normalization_confidence": 80,
            })
            break

    range_match = re.search(
        r"(?<!\d)(\d+(?:[.,]\d+)?)\s*[-–]\s*(\d+(?:[.,]\d+)?)",
        normalized,
    )

    if range_match:
        result["quantity_mode"] = "range"
        result["quantity_min"] = float(
            range_match.group(1).replace(",", ".")
        )
        result["quantity_max"] = float(
            range_match.group(2).replace(",", ".")
        )
        result["estimate_text"] = raw
    elif any(term in normalized for term in ESTIMATE_TERMS):
        result["quantity_mode"] = "estimated"
        result["estimate_text"] = raw

    return result
