"""Kebutuhan alat kerja, starting from the physical condition in the field.

A work object (RN Work Object) is what is physically there — a landslide of
200 m³, 5 ha of flooded settlement, 200 dead — plus a target number of
working days. From that the rules below estimate which tools, how many and
for how long:

    longsoran 200 m³, 2 hari  -> 2 ekskavator + 1 buldoser, 2 hari kerja
    banjir pemukiman 5 ha     -> 5 perahu karet
    korban jiwa 200 orang     -> 250 kantong jenazah

Only then does the page turn estimates into tool requests (kebutuhan) and
manage them (matching, dispatch). Every rate is a documented field
heuristic — a planning starting point, not an engineering calculation —
and is shown next to the number it produced.

Rule kinds:
  throughput  qty = ceil(size / (rate_per_day * days))   tool clears `rate` per day
  per_size    qty = ceil(size / per)                     one tool per `per` of size
  multiplier  qty = ceil(size * factor)                  consumables per person
  ratio       qty = ceil(qty_of(ref) * factor)           a support tool per main tool
"""

import math

CONDITIONS = {
    "longsoran": {
        "label": "Longsoran / material menutup",
        "unit": "m3",
        "measure": "volume material",
        "default_days": 2,
        "tools": [
            {"category": "ekskavator", "kind": "throughput", "rate": 50,
             "basis": "1 ekskavator membersihkan ±50 m³ material longsor per hari kerja "
                      "(lumpur, batu, kayu, akses terbatas)"},
            {"category": "buldoser", "kind": "ratio", "ref": "ekskavator", "factor": 0.5,
             "basis": "1 buldoser mendampingi setiap 2 ekskavator untuk mendorong dan meratakan material"},
        ],
    },
    "banjir_pemukiman": {
        "label": "Banjir di permukiman",
        "unit": "ha",
        "measure": "luas genangan",
        "default_days": None,
        "tools": [
            {"category": "perahu_karet", "kind": "per_size", "per": 1,
             "basis": "1 perahu karet per ±1 ha permukiman tergenang untuk evakuasi dan distribusi"},
        ],
    },
    "korban_jiwa": {
        "label": "Korban meninggal (penanganan jenazah)",
        "unit": "orang",
        "measure": "jumlah korban",
        "default_days": None,
        "tools": [
            {"category": "kantong_jenazah", "kind": "multiplier", "factor": 1.25,
             "basis": "1 kantong per korban + cadangan 25% untuk korban yang belum ditemukan"},
        ],
    },
    "jembatan_putus": {
        "label": "Jembatan putus",
        "unit": "m",
        "measure": "panjang bentang",
        "default_days": None,
        "tools": [
            {"category": "perahu_karet", "kind": "per_size", "per": 25,
             "basis": "1 perahu karet per ±25 m bentang sebagai jalur alternatif"},
            {"category": "genset", "kind": "per_size", "per": 50,
             "basis": "1 genset per ±50 m bentang untuk penerangan area kerja malam"},
        ],
    },
    "puing_berat": {
        "label": "Puing berat",
        "unit": "m2",
        "measure": "luas puing",
        "default_days": None,
        "tools": [
            {"category": "chainsaw", "kind": "per_size", "per": 100,
             "basis": "1 chainsaw per ±100 m² puing berpohon/berkayu"},
            {"category": "forklift", "kind": "per_size", "per": 300,
             "basis": "1 forklift per ±300 m² puing untuk angkut material berat"},
        ],
    },
    "pohon_tumbang": {
        "label": "Pohon tumbang",
        "unit": "pohon",
        "measure": "jumlah pohon",
        "default_days": None,
        "tools": [
            {"category": "chainsaw", "kind": "per_size", "per": 5, "basis": "1 chainsaw per ±5 pohon tumbang"},
        ],
    },
    "akses_terendam": {
        "label": "Akses terendam",
        "unit": "m2",
        "measure": "luas genangan akses",
        "default_days": None,
        "tools": [
            {"category": "pompa_air", "kind": "per_size", "per": 200,
             "basis": "1 pompa air per ±200 m² area tergenang"},
        ],
    },
    "lainnya": {"label": "Lainnya", "unit": None, "measure": "ukuran", "default_days": None, "tools": []},
}

CATEGORY_LABELS = {
    "ekskavator": "Ekskavator",
    "buldoser": "Buldoser",
    "genset": "Genset",
    "pompa_air": "Pompa Air",
    "forklift": "Forklift",
    "chainsaw": "Chainsaw",
    "perahu_karet": "Perahu Karet",
    "kantong_jenazah": "Kantong Jenazah",
}

# consumables are counted in pcs, everything else in unit
CATEGORY_UNITS = {"kantong_jenazah": "pcs"}


def condition_catalog():
    return [
        {"object_type": k, "label": v["label"], "unit": v["unit"], "measure": v["measure"],
         "default_days": v["default_days"], "time_based": any(t["kind"] == "throughput" for t in v["tools"])}
        for k, v in CONDITIONS.items()
    ]


def estimate(object_type, size_value, work_days=None):
    """[{category, label, predicted_qty, unit, work_days, basis}] for one condition."""
    spec = CONDITIONS.get(object_type) or CONDITIONS["lainnya"]
    size = float(size_value or 0)
    days = int(work_days or 0) or spec["default_days"] or 1
    out, qty_of = [], {}
    for rule in spec["tools"]:
        kind = rule["kind"]
        if size <= 0:
            qty = 1 if kind != "ratio" else max(1, math.ceil(qty_of.get(rule["ref"], 1) * rule["factor"]))
        elif kind == "throughput":
            qty = math.ceil(size / (rule["rate"] * days))
        elif kind == "per_size":
            qty = math.ceil(size / rule["per"])
        elif kind == "multiplier":
            qty = math.ceil(size * rule["factor"])
        else:  # ratio
            qty = math.ceil(qty_of.get(rule["ref"], 0) * rule["factor"])
        qty = max(1, qty)
        qty_of[rule["category"]] = qty
        timed = kind == "throughput" or (kind == "ratio" and any(
            r["category"] == rule["ref"] and r["kind"] == "throughput" for r in spec["tools"]))
        out.append({
            "category": rule["category"],
            "label": CATEGORY_LABELS.get(rule["category"], rule["category"]),
            "predicted_qty": qty,
            "unit": CATEGORY_UNITS.get(rule["category"], "unit"),
            "work_days": days if timed else None,
            "basis": rule["basis"],
        })
    return out
