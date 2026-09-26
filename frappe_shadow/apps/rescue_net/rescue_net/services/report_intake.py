"""Turn a citizen's free narrative into the community-report form.

Two parsers, same output shape:

* `rules_extract(text)` — deterministic Indonesian keyword/number rules;
  always available, no key, no cost.
* `ai_extract(text, ...)` — the platform AI key (api_ai.save_platform_key)
  via services/llm.py. Its answer is clamped to the same fields/value sets;
  any failure falls back to the rules.

The result is a *suggestion*: the reporter sees it in the form and can fix
it before sending (ADR-0001: AI suggests, a person accepts).
"""

import re

REPORT_TYPES = {
    "affected_need_help": "Warga terdampak butuh bantuan",
    "location_needs_help": "Lokasi butuh bantuan",
    "medical_case": "Korban sakit / medis",
    "missing_or_found": "Orang hilang / ditemukan",
    "shelter_need": "Kebutuhan shelter / pengungsian",
    "blocked_access": "Jalan terputus / akses terganggu",
    "water_shortage": "Kekeringan / krisis air bersih",
    "available_stock": "Stok atau bantuan tersedia",
    "new_hazard": "Risiko bahaya baru",
}
PRIORITIES = ("normal", "urgent", "critical")

# report_type -> keywords (lower-case substrings); most hits wins
_TYPE_WORDS = {
    "medical_case": ("luka", "sakit", "demam", "diare", "pingsan", "patah tulang", "medis", "dokter",
                     "obat", "ambulans", "meninggal", "tewas", "jenazah", "sesak"),
    "missing_or_found": ("hilang", "belum ditemukan", "terseret", "mencari keluarga", "ditemukan selamat"),
    "shelter_need": ("mengungsi", "pengungsi", "pengungsian", "tenda", "rumah rusak", "kehilangan rumah",
                     "tempat tinggal", "hunian", "rumah roboh"),
    "blocked_access": ("jalan putus", "jalan tertutup", "akses terputus", "jembatan putus", "menutup jalan",
                       "tidak bisa dilewati", "tertutup longsor", "jalan rusak", "akses jalan"),
    "water_shortage": ("kekeringan", "krisis air", "air bersih habis", "sumur kering", "kekurangan air",
                       "gagal panen", "tidak ada air", "sungai kering", "kemarau"),
    "new_hazard": ("retakan", "potensi longsor", "air naik", "tanggul", "asap", "kebakaran", "erupsi",
                   "awan panas", "api"),
    "available_stock": ("tersedia", "bisa menyumbang", "siap kirim", "stok kami"),
}
_CRITICAL = ("meninggal", "tewas", "tertimbun", "terjebak", "kritis", "darurat", "tenggelam", "sesak napas",
             "tidak sadar")
_URGENT = ("segera", "mendesak", "tolong", "bayi", "lansia", "belum makan", "cepat", "urgent")

_NEED_ITEMS = ("air bersih", "air minum", "beras", "makanan", "mie instan", "selimut", "tenda", "terpal",
               "obat", "ambulans", "perahu karet", "perahu", "popok", "susu", "pakaian", "tikar", "masker",
               "genset", "senter", "kantong jenazah", "excavator", "ekskavator", "buldoser", "alat berat",
               "tangki air", "jerigen", "toren", "pompa air", "sembako", "hygiene kit", "tenaga medis")

_PEOPLE = re.compile(r"(\d[\d.]*)\s*(orang|jiwa|warga|penduduk|korban|anak|lansia|balita)\b", re.I)
_FAMILIES = re.compile(r"(\d[\d.]*)\s*(kk|kepala keluarga|keluarga)\b", re.I)
_SCALE = re.compile(r"(\d[\d.,]*)\s*(m3|m³|meter kubik|kubik|km|kilometer|meter|ha|hektar|hektare|m)\b", re.I)
_PLACE = re.compile(r"\b(?:di\s+)?((?i:desa|dusun|kampung|kelurahan|kecamatan|kec\.|kabupaten|kab\.|kota)"
                    r"\s+[A-Z][\w'-]*(?:\s+[A-Z][\w'-]*)*)")
_UNITS = {"m3": "m3", "m³": "m3", "meter kubik": "m3", "kubik": "m3", "km": "km", "kilometer": "km",
          "meter": "meter", "m": "meter", "ha": "ha", "hektar": "ha", "hektare": "ha"}
PEOPLE_PER_FAMILY = 4


def _num(raw):
    raw = (raw or "").replace(".", "").replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def rules_extract(text):
    text = (text or "").strip()
    low = text.lower()
    notes = []

    hits = {t: sum(1 for w in words if w in low) for t, words in _TYPE_WORDS.items()}
    best = max(hits, key=lambda t: hits[t])
    report_type = best if hits[best] else "affected_need_help"

    if any(w in low for w in _CRITICAL):
        priority = "critical"
    elif any(w in low for w in _URGENT):
        priority = "urgent"
    else:
        priority = "normal"

    people = sum(int(_num(m.group(1)) or 0) for m in _PEOPLE.finditer(text))
    if not people:
        families = sum(int(_num(m.group(1)) or 0) for m in _FAMILIES.finditer(text))
        if families:
            people = families * PEOPLE_PER_FAMILY
            notes.append(f"{families} KK dihitung ≈ {people} jiwa ({PEOPLE_PER_FAMILY} jiwa/KK).")

    scale_value = scale_unit = None
    for m in _SCALE.finditer(text):
        # "200 orang" is people, not a scale; the unit regex already excludes it
        scale_value, scale_unit = _num(m.group(1)), _UNITS.get(m.group(2).lower(), m.group(2).lower())
        break

    needs = [item for item in _NEED_ITEMS if item in low]
    # a longer item already covers the shorter one ("perahu karet" ⊃ "perahu")
    needs = [n for n in needs if not any(n != o and n in o for o in needs)]

    places = [m.group(1).strip() for m in _PLACE.finditer(text)]
    location_text = ", ".join(dict.fromkeys(places)) or None

    first = re.split(r"(?<=[.!?])\s+|\n", text, maxsplit=1)[0].strip()
    title = first[:90] if len(first) >= 12 else REPORT_TYPES[report_type]
    if location_text and len(first) < 12:
        title = f"{REPORT_TYPES[report_type]} di {location_text}"[:90]

    return {
        "title": title,
        "report_type": report_type,
        "priority": priority,
        "affected_people_count": people,
        "urgent_needs": ", ".join(needs) or None,
        "damage_scale_value": scale_value,
        "damage_scale_unit": scale_unit,
        "location_text": location_text,
        "notes": notes,
    }


AI_SYSTEM_PROMPT = """
Kamu membantu warga Indonesia melaporkan kondisi bencana ke Rescue-Net.
Ubah uraian warga menjadi satu objek JSON dengan kunci persis:
title (judul singkat <= 90 karakter),
report_type (salah satu: {types}),
priority (normal | urgent | critical),
affected_people_count (bilangan bulat jiwa; KK x 4 bila hanya KK; 0 bila tidak disebut),
urgent_needs (daftar kebutuhan dipisah koma, dengan jumlah bila disebut; null bila tidak ada),
damage_scale_value (angka skala kerusakan: panjang jalan, volume longsor, luas genangan; null bila tidak ada),
damage_scale_unit (meter | km | m3 | ha; null bila tidak ada),
location_text (nama desa/kecamatan/kabupaten yang disebut; null bila tidak ada),
notes (daftar string: asumsi yang kamu buat).
Jangan mengarang angka atau tempat yang tidak ada di uraian. Jawab hanya JSON.
"""


def _clamp(parsed, fallback):
    out = dict(fallback)
    if not isinstance(parsed, dict):
        return out
    if parsed.get("report_type") in REPORT_TYPES:
        out["report_type"] = parsed["report_type"]
    if parsed.get("priority") in PRIORITIES:
        out["priority"] = parsed["priority"]
    for key, limit in (("title", 90), ("urgent_needs", 500), ("location_text", 200)):
        v = parsed.get(key)
        if isinstance(v, list):
            v = ", ".join(str(x) for x in v)
        if isinstance(v, str) and v.strip():
            out[key] = v.strip()[:limit]
    try:
        n = int(parsed.get("affected_people_count") or 0)
        if 0 <= n <= 10_000_000:
            out["affected_people_count"] = n
    except (TypeError, ValueError):
        pass
    try:
        v = parsed.get("damage_scale_value")
        if v not in (None, "") and float(v) >= 0:
            out["damage_scale_value"] = float(v)
            unit = str(parsed.get("damage_scale_unit") or "").lower()
            out["damage_scale_unit"] = _UNITS.get(unit, unit or None)
    except (TypeError, ValueError):
        pass
    if isinstance(parsed.get("notes"), list):
        out["notes"] = [str(x)[:200] for x in parsed["notes"][:5]]
    return out


def ai_extract(text, api_key, model, provider):
    from rescue_net.services import llm

    fallback = rules_extract(text)
    system = AI_SYSTEM_PROMPT.format(types=" | ".join(REPORT_TYPES))
    answer, usage = llm.chat(provider, api_key, model, system, [text], temperature=0, json_mode=True,
                             max_tokens=2000)
    return _clamp(llm.parse_json(answer), fallback), usage


def extract(text):
    """Best available parser: the platform AI key if one is set, else rules.
    Returns (fields, parser) — parser is 'rules' or 'ai:<provider>'."""
    import frappe

    from rescue_net import api_ai
    from rescue_net.services import llm

    key, model, provider = api_ai.resolve_platform_key()
    if key:
        log = dict(owner_type="platform", owner_id=api_ai.PLATFORM_OWNER, user_id=frappe.session.user,
                   key_source="platform", provider=provider, model_name=model, disaster_event=None,
                   q_chars=len(text or ""))
        try:
            fields, usage = ai_extract(text, key, model, provider)
            api_ai._log_ai_usage(**log, usage=usage, outcome="ok")
            return fields, f"ai:{provider}"
        except llm.LLMError as e:
            api_ai._log_ai_usage(**log, outcome="error", error_note=f"{e.kind} {e.note}")
    return rules_extract(text), "rules"
