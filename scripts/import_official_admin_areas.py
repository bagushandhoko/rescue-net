#!/usr/bin/env python3

import csv
import json
import sys
from pathlib import Path


def clean(v):
    return "" if v is None else str(v).strip()


def normalize_code(raw):
    """
    Menerima:
      11
      1106
      110610
      1106102001
      11.06
      11.06.10
      11.06.10.2001
    lalu mengubah ke format Rescue-Net bertitik.
    """
    raw = clean(raw)
    if not raw:
        return ""

    digits = "".join(ch for ch in raw if ch.isdigit())

    if len(digits) == 2:
        return digits
    if len(digits) == 4:
        return f"{digits[:2]}.{digits[2:4]}"
    if len(digits) == 6:
        return f"{digits[:2]}.{digits[2:4]}.{digits[4:6]}"
    if len(digits) == 10:
        return f"{digits[:2]}.{digits[2:4]}.{digits[4:6]}.{digits[6:10]}"

    # Bila dataset memang sudah memakai format kode lain,
    # pertahankan nilai aslinya daripada mengarang.
    return raw


def infer_level(code):
    digits = "".join(ch for ch in code if ch.isdigit())
    return {
        2: "province",
        4: "city",
        6: "district",
        10: "village",
    }.get(len(digits), "")


def infer_parent(code, level):
    digits = "".join(ch for ch in code if ch.isdigit())

    if level == "province":
        return ""
    if level == "city" and len(digits) >= 4:
        return normalize_code(digits[:2])
    if level == "district" and len(digits) >= 6:
        return normalize_code(digits[:4])
    if level == "village" and len(digits) >= 10:
        return normalize_code(digits[:6])

    return ""


def first(row, *names):
    lowered = {str(k).lower(): v for k, v in row.items()}
    for name in names:
        if name.lower() in lowered and clean(lowered[name.lower()]):
            return clean(lowered[name.lower()])
    return ""


def normalize_row(row):
    code = normalize_code(first(
        row,
        "code", "kode", "kode_wilayah", "wilayah_code", "id"
    ))

    name = first(
        row,
        "name", "nama", "nama_wilayah", "wilayah_name"
    )

    level = first(
        row,
        "level", "tingkat", "jenis_level", "admin_level"
    ).lower()

    level_alias = {
        "provinsi": "province",
        "province": "province",
        "kabupaten": "city",
        "kota": "city",
        "kabupaten/kota": "city",
        "regency": "city",
        "city": "city",
        "kecamatan": "district",
        "district": "district",
        "desa": "village",
        "kelurahan": "village",
        "desa/kelurahan": "village",
        "village": "village",
    }

    level = level_alias.get(level, level)

    if not level:
        level = infer_level(code)

    parent = normalize_code(first(
        row,
        "parent_code", "parent", "kode_parent",
        "parent_kode", "kode_induk"
    ))

    if not parent:
        parent = infer_parent(code, level)

    if not code or not name or level not in {
        "province", "city", "district", "village"
    }:
        return None

    return {
        "code": code,
        "parent_code": parent,
        "name": name,
        "level": level,
    }


def load_rows(path):
    path = Path(path)

    if not path.exists():
        raise SystemExit(f"File tidak ditemukan: {path}")

    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8-sig"))

        if isinstance(data, dict):
            for key in ("data", "results", "items", "records"):
                if isinstance(data.get(key), list):
                    data = data[key]
                    break

        if not isinstance(data, list):
            raise SystemExit("JSON harus berupa array atau mempunyai key data/results/items/records.")

        raw_rows = data

    else:
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            sample = f.read(8192)
            f.seek(0)

            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
            except csv.Error:
                dialect = csv.excel

            raw_rows = list(csv.DictReader(f, dialect=dialect))

    normalized = {}
    invalid = 0

    for row in raw_rows:
        item = normalize_row(row)
        if not item:
            invalid += 1
            continue
        normalized[item["code"]] = item

    rows = list(normalized.values())

    level_order = {
        "province": 1,
        "city": 2,
        "district": 3,
        "village": 4,
    }

    rows.sort(key=lambda x: (level_order[x["level"]], x["code"]))

    return rows, invalid


def sql_quote(v):
    return "'" + clean(v).replace("'", "''") + "'"


def main():
    if len(sys.argv) < 2:
        print(
            "Usage: import_official_admin_areas.py FILE [SOURCE_NAME] [SOURCE_URL]",
            file=sys.stderr
        )
        raise SystemExit(2)

    source_file = sys.argv[1]
    source_name = (
        sys.argv[2]
        if len(sys.argv) > 2
        else "Official Indonesian Government Administrative Area Dataset"
    )
    source_url = sys.argv[3] if len(sys.argv) > 3 else ""

    rows, invalid = load_rows(source_file)

    counts = {
        "province": 0,
        "city": 0,
        "district": 0,
        "village": 0,
    }

    for row in rows:
        counts[row["level"]] += 1

    print("BEGIN;")
    print("""
CREATE TEMP TABLE rn_admin_import (
    code TEXT PRIMARY KEY,
    parent_code TEXT,
    name TEXT NOT NULL,
    level TEXT NOT NULL
) ON COMMIT DROP;
""")

    for row in rows:
        parent = (
            "NULL"
            if not row["parent_code"]
            else sql_quote(row["parent_code"])
        )

        print(
            "INSERT INTO rn_admin_import "
            "(code,parent_code,name,level) VALUES "
            f"({sql_quote(row['code'])},{parent},"
            f"{sql_quote(row['name'])},{sql_quote(row['level'])}) "
            "ON CONFLICT (code) DO UPDATE SET "
            "parent_code=EXCLUDED.parent_code,"
            "name=EXCLUDED.name,"
            "level=EXCLUDED.level;"
        )

    print(f"""
INSERT INTO official_admin_areas
(code, parent_code, name, level, source_name, source_url, is_active, updated_at)
SELECT
    code,
    NULLIF(parent_code,''),
    name,
    level,
    {sql_quote(source_name)},
    {sql_quote(source_url)},
    TRUE,
    NOW()
FROM rn_admin_import
ON CONFLICT (code) DO UPDATE SET
    parent_code = EXCLUDED.parent_code,
    name        = EXCLUDED.name,
    level       = EXCLUDED.level,
    source_name = EXCLUDED.source_name,
    source_url  = EXCLUDED.source_url,
    is_active   = TRUE,
    updated_at  = NOW();

COMMIT;
""")

    print(
        "-- IMPORT SUMMARY: "
        f"province={counts['province']} "
        f"city={counts['city']} "
        f"district={counts['district']} "
        f"village={counts['village']} "
        f"invalid_skipped={invalid}",
        file=sys.stderr
    )


if __name__ == "__main__":
    main()
