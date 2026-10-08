"""Kode wilayah Kemendagri (Permendagri 72/2019) — normalisasi, tingkat, induk, validasi. Tanpa Frappe.

ADR-0005 A.1: kunci kanonik wilayah = kode Kemendagri bertitik. Modul ini murni (tidak menyentuh database) supaya
bisa dites cepat, dipakai skrip impor di luar Frappe, dan memvalidasi berkas sebelum satu baris pun masuk.

    provinsi        11
    kabupaten/kota  11.71
    kecamatan       11.71.02
    desa/kelurahan  11.71.02.1001
"""

import re

LEVELS = ("province", "city", "district", "village")
# digits in the code -> level
_DIGITS_TO_LEVEL = {2: "province", 4: "city", 6: "district", 10: "village"}
_LEVEL_TO_DIGITS = {v: k for k, v in _DIGITS_TO_LEVEL.items()}
CODE_RE = re.compile(r"^\d{2}(\.\d{2}(\.\d{2}(\.\d{4})?)?)?$")

_LEVEL_ALIAS = {
    "provinsi": "province", "province": "province", "prov": "province", "adm1": "province",
    "kabupaten": "city", "kota": "city", "kabupaten/kota": "city", "kab/kota": "city", "regency": "city",
    "city": "city", "adm2": "city",
    "kecamatan": "district", "district": "district", "adm3": "district",
    "desa": "village", "kelurahan": "village", "desa/kelurahan": "village", "village": "village", "adm4": "village",
}


def clean(value):
    return "" if value is None else str(value).strip()


def normalize_code(raw):
    """11 / 1171 / 117102 / 1171021001 / 11.71.02.1001 -> bertitik. Kode yang bukan kode wilayah dikembalikan
    apa adanya (jangan mengarang); `validate_code` yang menolaknya."""
    raw = clean(raw)
    if not raw:
        return ""
    if CODE_RE.match(raw):
        return raw
    digits = "".join(ch for ch in raw if ch.isdigit())
    if digits != raw.replace(".", "").replace(" ", ""):
        return raw                       # mixed letters etc.: leave it for validation to reject
    if len(digits) == 2:
        return digits
    if len(digits) == 4:
        return f"{digits[:2]}.{digits[2:]}"
    if len(digits) == 6:
        return f"{digits[:2]}.{digits[2:4]}.{digits[4:]}"
    if len(digits) == 10:
        return f"{digits[:2]}.{digits[2:4]}.{digits[4:6]}.{digits[6:]}"
    return raw


def validate_code(code):
    return bool(CODE_RE.match(clean(code)))


def level_of(code):
    digits = clean(code).replace(".", "")
    return _DIGITS_TO_LEVEL.get(len(digits), "") if validate_code(code) else ""


def parent_of(code):
    """11.71.02.1001 -> 11.71.02 ; a province has no parent."""
    code = clean(code)
    if not validate_code(code) or "." not in code:
        return ""
    return code.rsplit(".", 1)[0]


def normalize_level(raw, code=""):
    raw = clean(raw).lower()
    return _LEVEL_ALIAS.get(raw) or (raw if raw in LEVELS else "") or level_of(code)


def normalize_row(row, source=None):
    """A free-form dict (CSV/JSON row) -> {code, parent_code, area_name, level} or None when unusable."""
    low = {str(k).strip().lower(): v for k, v in row.items()}

    def first(*names):
        for n in names:
            v = clean(low.get(n))
            if v:
                return v
        return ""

    code = normalize_code(first("code", "kode", "kode_wilayah", "wilayah_code", "id", "kemendagri"))
    name = first("area_name", "name", "nama", "nama_wilayah", "wilayah_name")
    if not code or not name:
        return None
    level = normalize_level(first("level", "tingkat", "jenis_level", "admin_level"), code)
    parent = normalize_code(first("parent_code", "parent", "kode_parent", "parent_kode", "kode_induk")) or parent_of(code)
    return {"code": code, "parent_code": parent, "area_name": re.sub(r"\s+", " ", name), "level": level}


def validate_rows(rows, known_codes=None, sample=5):
    """Quality report for a batch of normalised rows BEFORE anything is written.

    `known_codes`: codes already in the database (a parent may live there instead of in the file).
    Returns {counts, issues:{kind:{count, samples}}, ok}. `ok` = no blocking issue."""
    known = set(known_codes or ())
    seen, issues = {}, {}

    def flag(kind, detail):
        bucket = issues.setdefault(kind, {"count": 0, "samples": []})
        bucket["count"] += 1
        if len(bucket["samples"]) < sample:
            bucket["samples"].append(detail)

    for r in rows:
        code = r.get("code", "")
        if not validate_code(code):
            flag("bad_code_format", code)
            continue
        if code in seen:
            flag("duplicate_code", code)
            if seen[code]["area_name"] != r.get("area_name"):
                flag("duplicate_code_conflicting_name", f"{code}: {seen[code]['area_name']} / {r.get('area_name')}")
            continue
        seen[code] = r
        if r.get("level") != level_of(code):
            flag("level_mismatch", f"{code}: level={r.get('level')} kode menunjukkan {level_of(code)}")
        if (r.get("parent_code") or "") != parent_of(code):
            flag("parent_mismatch", f"{code}: parent={r.get('parent_code')} seharusnya {parent_of(code)}")
        if not clean(r.get("area_name")):
            flag("empty_name", code)

    for code, r in seen.items():
        parent = parent_of(code)
        if parent and parent not in seen and parent not in known:
            flag("orphan", f"{code} ({r.get('area_name')}) → induk {parent} tidak ada")

    counts = {lv: 0 for lv in LEVELS}
    for code in seen:
        counts[level_of(code)] = counts.get(level_of(code), 0) + 1
    blocking = {"bad_code_format", "duplicate_code_conflicting_name", "level_mismatch", "parent_mismatch", "empty_name", "orphan"}
    return {"counts": counts, "total": len(seen), "issues": issues, "ok": not (blocking & set(issues))}


def sort_rows(rows):
    order = {lv: i for i, lv in enumerate(LEVELS)}
    return sorted(rows, key=lambda r: (order.get(r.get("level"), 9), r.get("code", "")))


# How people actually write provinces vs the official (Kepmendagri) spelling. Keys/values are normalize_name() output.
PROVINCE_ALIASES = {
    "dki jakarta": "daerah khusus ibukota jakarta", "dki": "daerah khusus ibukota jakarta",
    "jakarta": "daerah khusus ibukota jakarta", "daerah khusus jakarta": "daerah khusus ibukota jakarta",
    "di yogyakarta": "daerah istimewa yogyakarta", "d i yogyakarta": "daerah istimewa yogyakarta",
    "diy": "daerah istimewa yogyakarta", "yogyakarta": "daerah istimewa yogyakarta",
    "nad": "aceh", "nanggroe aceh darussalam": "aceh", "bangka belitung": "kepulauan bangka belitung",
    "babel": "kepulauan bangka belitung", "kepri": "kepulauan riau", "ntb": "nusa tenggara barat",
    "ntt": "nusa tenggara timur", "sumut": "sumatera utara", "sumbar": "sumatera barat", "sumsel": "sumatera selatan",
    "kalbar": "kalimantan barat", "kalteng": "kalimantan tengah", "kalsel": "kalimantan selatan",
    "kaltim": "kalimantan timur", "kaltara": "kalimantan utara", "sulut": "sulawesi utara",
    "sulteng": "sulawesi tengah", "sulsel": "sulawesi selatan", "sultra": "sulawesi tenggara",
    "sulbar": "sulawesi barat", "jabar": "jawa barat", "jateng": "jawa tengah", "jatim": "jawa timur",
}


def city_kind(name):
    """'Kota Bandung' -> 'kota', 'Kab. Bandung' -> 'kabupaten', 'Bandung' -> None."""
    s = clean(name).lower()
    if re.match(r"^\s*kota\b", s):
        return "kota"
    if re.match(r"^\s*(kabupaten|kab\b)", s):
        return "kabupaten"
    return None


def normalize_name(name, level=None):
    """For name matching only: lower-case, drop 'Kabupaten/Kota/Kecamatan/Desa/Kelurahan' prefixes, punctuation;
    provinces also go through PROVINCE_ALIASES (DKI Jakarta → Daerah Khusus Ibukota Jakarta, ...)."""
    s = clean(name).lower()
    s = re.sub(r"\b(kabupaten|kab\.?|kota adm\.?|kota administrasi|kota|kecamatan|kec\.?|kelurahan|kel\.?|desa|provinsi|prov\.?)\b", " ", s)
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if level == "province":
        s = PROVINCE_ALIASES.get(s, s)
    return s
