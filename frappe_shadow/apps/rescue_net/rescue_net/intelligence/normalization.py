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
            "air mineral", "air minum", "aqua", "amdk",
            "air kemasan", "air botol", "air galon", "le minerale"
        ],
    },
    {
        "kind": "barang",
        "category": "Pangan & Air",
        "group": "Makanan Siap Saji",
        "item": "Makanan Siap Saji",
        "terms": [
            "nasi bungkus", "nasi kotak", "nasi box", "makanan siap saji",
            "makanan matang", "makanan siap makan", "lauk pauk", "rendang kaleng"
        ],
    },
    {
        "kind": "barang",
        "category": "Pangan & Air",
        "group": "Bahan Pangan",
        "item": "Bahan Pangan",
        "terms": [
            "beras", "mie instan", "mi instan", "indomie", "mie", "sarden",
            "sarden kaleng", "kornet", "susu", "susu bubuk", "gula", "minyak goreng",
            "sembako", "bahan pangan", "biskuit", "abon"
        ],
    },
    {
        "kind": "barang",
        "category": "Medis & Kesehatan",
        "group": "Obat & Perbekalan Medis",
        "item": "Perbekalan Medis",
        "terms": [
            "obat", "obat-obatan", "paracetamol", "parasetamol", "antibiotik",
            "perban", "kasa", "infus", "cairan infus", "masker medis", "masker bedah",
            "alat kesehatan", "alkes", "vitamin", "oralit", "antiseptik", "betadine"
        ],
    },
    {
        "kind": "barang",
        "category": "Shelter & Hunian",
        "group": "Perlengkapan Pengungsian",
        "item": "Perlengkapan Shelter",
        "terms": [
            "tenda", "selimut", "matras", "tikar", "sleeping bag", "kasur lipat",
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


# --- unit normalisation ------------------------------------------------------
# Fold the many raw ways people write a unit into one canonical token, so
# "dus" / "Dus" / "kardus" / "box" / "karton" all roll up together in a
# group's unit breakdown. Deterministic keyword map — no black-box AI.
_UNIT_SYNONYMS = {
    "pcs": ["pcs", "pc", "piece", "pieces", "buah", "bh", "unit", "units",
            "biji", "keping"],
    "dus": ["dus", "dos", "box", "boxes", "kardus", "karton", "carton",
            "kartun", "ctn"],
    "kg": ["kg", "kgs", "kilogram", "kilo", "kilos", "kg."],
    "gram": ["gram", "gr", "grm", "g"],
    "ton": ["ton", "tonne", "tonnes", "mt"],
    "liter": ["liter", "litre", "litres", "ltr", "lt", "l", "ltrs"],
    "ml": ["ml", "mililiter", "milliliter", "cc"],
    "karung": ["karung", "sak", "zak", "sack", "goni"],
    "sachet": ["sachet", "saset", "bungkus", "kantong", "kantung", "pouch"],
    "paket": ["paket", "pak", "pack", "packs", "package", "bundel", "bundle"],
    "botol": ["botol", "btl", "bottle", "bottles"],
    "galon": ["galon", "gallon", "gln"],
    "jerigen": ["jerigen", "jerrycan", "jrgn"],
    "tablet": ["tablet", "tab", "tabs", "kaplet", "kapsul", "pil", "strip",
               "blister"],
    "ampul": ["ampul", "ampoule", "vial", "flakon"],
    "roll": ["roll", "rol", "gulung", "rll"],
    "lembar": ["lembar", "lbr", "sheet", "sheets", "helai"],
    "pasang": ["pasang", "psg", "pair", "pairs"],
    "set": ["set", "sets", "rangkaian"],
    "orang": ["orang", "org", "jiwa", "pax", "personil", "personel"],
    "rit": ["rit", "trip", "ritase"],
    "drum": ["drum", "drm"],
    "tabung": ["tabung", "tbg", "cylinder"],
    "meter": ["meter", "m", "mtr", "metre"],
    "m3": ["m3", "m³", "meter kubik", "kubik", "cbm"],
    "porsi": ["porsi", "portion", "serving", "servings"],
}
_UNIT_LOOKUP = {}
for _canon, _alts in _UNIT_SYNONYMS.items():
    for _a in _alts:
        _UNIT_LOOKUP[_a] = _canon


def normalize_unit(unit):
    """Canonical form of a raw unit string ('Kardus' -> 'dus', 'KG' -> 'kg').
    Unknown units are lower-cased + trimmed but kept as-is."""
    if not unit:
        return "unit"
    u = re.sub(r"[^\w²³]+", " ", str(unit).strip().lower())
    u = re.sub(r"\s+", " ", u).strip()
    if not u:
        return "unit"
    if u in _UNIT_LOOKUP:
        return _UNIT_LOOKUP[u]
    if u.endswith("s") and u[:-1] in _UNIT_LOOKUP:
        return _UNIT_LOOKUP[u[:-1]]
    first = u.split(" ")[0]
    return _UNIT_LOOKUP.get(first, u)


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
