"""Packaging + quantity-conversion layer for Rescue-Net item normalisation.

Turns the many ways a lay reporter writes a quantity —
  "mie instan dalam dus isi 24 bh"   -> 24 bungkus per dus  (EXPLICIT)
  "air mineral 2 dus"                 -> 2 x factor via RN Unit Conversion
  "aqua gelas 100 bh"                 -> 100 gelas (direct count)
  "5 botol air"                       -> 5 botol -> liter via table
  "mie instan 2 karung kecil"        -> UNMEASURABLE (kemasan tidak baku)
  "beras seadanya"                    -> UNMEASURABLE
— into a measurable base quantity plus an honest certainty flag.

Deterministic: regex + an editable conversion table. No LLM call.
`parse_packaging()` never touches the DB; `resolve_base_quantity()` reads
RN Unit Conversion (memoised per request on frappe.local)."""

import re

from rescue_net.intelligence.normalization import normalize_unit

# --- constants -------------------------------------------------------------

# Pack words with an unambiguous count regardless of the item.
_PACK_CONSTANTS = {
    "lusin": 12, "losin": 12, "dozen": 12,
    "kodi": 20,
    "gross": 144, "gros": 144,
    "rim": 500, "ream": 500,
}

# Outer packaging whose content count depends on the item -> needs a
# RN Unit Conversion row (or an explicit "isi N" in the text).
_OUTER_UNITS = {
    "dus", "karton", "karung", "sak", "bal", "ball", "pallet", "palet",
    "peti", "krat", "crate", "jerigen", "drum", "galon", "pak", "paket",
    "renceng", "renteng", "ikat", "koli",
}

# Units that are already a countable base measure on their own.
_BASE_UNITS = {
    "pcs", "buah", "butir", "bungkus", "gelas", "botol", "sachet", "kaleng",
    "porsi", "lembar", "pasang", "tablet", "ampul", "kapsul", "strip",
    "keping", "batang", "kg", "gram", "liter", "ml", "meter", "orang",
    "pouch", "roll", "tube",
}

# Product-form / container words that name the real unit even when a generic
# counter ("bh", "pcs") sits next to the number: "aqua gelas 100 bh" -> gelas.
_FORM_UNITS = {
    "gelas", "botol", "galon", "jerigen", "kaleng", "sachet", "saset",
    "pouch", "tube", "dus", "karton", "karung", "sak", "pak", "renceng",
    "renteng", "drum", "ember", "kotak", "bal", "ball", "peti", "krat",
}
# Generic counting words that are NOT the meaningful unit on their own.
_GENERIC_COUNTERS = {"bh", "buah", "pcs", "pc", "butir", "biji", "keping", "unit"}

# Base-unit vocabulary is deliberately kept separate from normalize_unit()'s
# packaging space (which folds "bungkus" -> "sachet"). Base units stay
# human-friendly for the coordinator panel.
_BASE_ALIAS = {
    "bh": "pcs", "buah": "pcs", "butir": "pcs", "biji": "pcs", "pc": "pcs",
    "pieces": "pcs", "piece": "pcs", "unit": "pcs", "units": "pcs", "buc": "pcs",
    "saset": "sachet", "bgks": "bungkus", "bks": "bungkus",
    "ltr": "liter", "l": "liter", "lt": "liter", "litre": "liter",
    "kgs": "kg", "kilo": "kg", "kilos": "kg", "kilogram": "kg",
    "gr": "gram", "grm": "gram",
    "btl": "botol", "klg": "kaleng", "pkt": "paket", "tab": "tablet",
    "kaplet": "tablet", "kapsul": "tablet",
}


def _canon_base(u):
    """Light canonicalisation for base units — lower/trim + a tiny alias map,
    WITHOUT the packaging-space folding of normalize_unit()."""
    if not u:
        return u
    u = str(u).strip().lower()
    return _BASE_ALIAS.get(u, u)

# The single base unit each canonical item rolls up to.
_ITEM_BASE_UNIT = {
    "Air Minum Kemasan": "liter",
    "Mie Instan": "bungkus",
    "Beras": "kg",
    "Minyak Goreng": "liter",
    "Paracetamol": "tablet",
}

# Fallback base unit per canonical group.
_GROUP_BASE_UNIT = {
    "Air Minum": "liter",
    "Air Bersih": "liter",
    "Bahan Pangan": "kg",
    "Makanan Siap Saji": "porsi",
    "Hygiene": "paket",
    "Bahan Bakar": "liter",
}

# Vague quantity words -> unmeasurable.
_VAGUE_WORDS = {
    "seadanya", "secukupnya", "beberapa", "banyak", "sedikit", "sebagian",
    "sisa", "seperlunya", "sebanyaknya", "nya",
}
# Non-standard containers -> unmeasurable even with a number.
_VAGUE_CONTAINERS = {
    "kresek", "tas", "kantong", "kantung", "plastik", "ember", "bak",
    "baskom", "kotak", "dus bekas", "kardus bekas",
}
_VAGUE_MODIFIERS = {"kecil", "besar", "sedang", "mini", "jumbo", "gede"}

_NUM = r"(\d+(?:[.,]\d+)?)"

_CONTENT_UNIT_RE = (
    r"(bh|butir|buah|pcs|pc|bungkus|sachet|saset|kaleng|botol|gelas|pouch|"
    r"keping|lembar|pasang|porsi|tablet|kapsul|strip|batang|tube|roll)"
)


def _num(raw):
    """Parse an id-ID number token. '1.500' -> 1500, '2,5' -> 2.5, '24' -> 24."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    else:
        # dots are thousand separators in id-ID quantity writing
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


def parse_packaging(text):
    """Extract packaging hints from free item text. Pure, no DB.

    Keys: outer_quantity (count before an outer package unit, "2 dus" -> 2),
    content_quantity (count before a content unit, "100 bh" -> 100),
    form_unit (product-form word naming the real unit), pack_unit,
    pack_size (isi per kemasan), pack_base_unit, pack_certainty
    (explicit|constant|unmeasurable), unmeasurable_reason.
    parsed_quantity is kept as a convenience = outer_quantity or content_quantity."""
    out = {
        "outer_quantity": None,
        "content_quantity": None,
        "form_unit": None,
        "pack_unit": None,
        "pack_size": None,
        "pack_base_unit": None,
        "pack_certainty": None,
        "unmeasurable_reason": None,
        "parsed_quantity": None,
    }
    t = (text or "").casefold()
    t = re.sub(r"[^\w,./@±-]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    if not t:
        return out
    tokens = t.split(" ")

    # 1. unmeasurable: vague words, or a vague container (with/without a number),
    #    or "<container> <modifier>".
    for w in _VAGUE_WORDS:
        if w in tokens:
            out["pack_certainty"] = "unmeasurable"
            out["unmeasurable_reason"] = f"jumlah tidak pasti: \"{w}\""
            return out
    m = re.search(
        r"\b(karung|kantong|kantung|ember|kotak|tas|dus|kardus|box)\s+"
        r"(kecil|besar|sedang|mini|jumbo|gede)\b", t)
    if m:
        out["pack_certainty"] = "unmeasurable"
        out["unmeasurable_reason"] = f"kemasan tidak baku: \"{m.group(0)}\""
        return out
    for c in _VAGUE_CONTAINERS:
        if re.search(rf"\b{re.escape(c)}\b", t):
            out["pack_certainty"] = "unmeasurable"
            out["unmeasurable_reason"] = f"kemasan tidak baku: \"{c}\""
            return out

    # 2. explicit contents: "isi 24", "@24", "dus isi 24", "24 bh / dus"
    m = re.search(rf"(?:isi|@)\s*@?\s*{_NUM}\s*{_CONTENT_UNIT_RE}?", t)
    if m:
        out["pack_size"] = _num(m.group(1))
        if m.group(2):
            out["pack_base_unit"] = _canon_base(m.group(2))
        out["pack_certainty"] = "explicit"
    if out["pack_size"] is None:
        m = re.search(
            rf"{_NUM}\s*{_CONTENT_UNIT_RE}\s*(?:/|per)\s*"
            r"(dus|karton|karung|box|pak|pack|renceng|renteng|bal|ikat)", t)
        if m:
            out["pack_size"] = _num(m.group(1))
            out["pack_base_unit"] = _canon_base(m.group(2))
            out["pack_unit"] = normalize_unit(m.group(3))
            out["pack_certainty"] = "explicit"

    # 3. constant packs: "2 lusin", "1 kodi"
    if out["pack_size"] is None:
        for word, const in _PACK_CONSTANTS.items():
            if re.search(rf"\b{word}\b", t):
                out["pack_size"] = float(const)
                out["pack_certainty"] = "constant"
                break

    # 4. product-form word anywhere -> the real unit ("aqua gelas 100 bh")
    for w in tokens:
        if w in _FORM_UNITS:
            out["form_unit"] = normalize_unit(w)
            if w in _OUTER_UNITS and not out["pack_unit"]:
                out["pack_unit"] = normalize_unit(w)
            break

    # 5. "<n> <outer unit>"  e.g. "2 dus", "3 karung", "5 jerigen"
    for mm in re.finditer(rf"{_NUM}\s*([a-z]+)", t):
        word = mm.group(2)
        cand = normalize_unit(word)
        if word in _OUTER_UNITS or cand in _OUTER_UNITS:
            out["outer_quantity"] = _num(mm.group(1))
            if not out["pack_unit"]:
                out["pack_unit"] = cand
            break

    # 6. "<n> <content / base unit>"  e.g. "100 bh", "5 botol", "10 kg"
    for mm in re.finditer(rf"{_NUM}\s*([a-z]+)", t):
        word = mm.group(2)
        cand = normalize_unit(word)
        if word in _OUTER_UNITS or cand in _OUTER_UNITS:
            continue
        if (word in _BASE_UNITS or cand in _BASE_UNITS
                or re.fullmatch(_CONTENT_UNIT_RE, word)):
            out["content_quantity"] = _num(mm.group(1))
            if not out["pack_base_unit"] and word not in _GENERIC_COUNTERS:
                out["pack_base_unit"] = _canon_base(word)
            break

    out["parsed_quantity"] = out["outer_quantity"] or out["content_quantity"]
    return out


# --- conversion table (RN Unit Conversion) -------------------------------

def _enabled_conversions():
    """Enabled RN Unit Conversion rows, memoised per request."""
    import frappe

    cached = getattr(frappe.local, "_rn_unit_conversions", None)
    if cached is not None:
        return cached
    if not frappe.db.exists("DocType", "RN Unit Conversion"):
        frappe.local._rn_unit_conversions = []
        return []
    rows = frappe.get_all(
        "RN Unit Conversion",
        filters={"enabled": 1},
        fields=[
            "name", "scope_type", "canonical_item", "canonical_group",
            "from_unit", "to_base_unit", "factor", "certainty", "priority",
        ],
        order_by="priority desc, modified desc",
        limit_page_length=5000,
    )
    frappe.local._rn_unit_conversions = rows
    return rows


def _lookup_conversion(canonical_item, canonical_group, from_unit):
    if not from_unit:
        return None
    fu = normalize_unit(from_unit)
    tiers = {"canonical_item": [], "canonical_group": [], "global": []}
    for r in _enabled_conversions():
        if normalize_unit(r.get("from_unit")) != fu:
            continue
        st = r.get("scope_type") or "canonical_item"
        if st == "canonical_item" and r.get("canonical_item") == canonical_item:
            tiers["canonical_item"].append(r)
        elif st == "canonical_group" and r.get("canonical_group") == canonical_group:
            tiers["canonical_group"].append(r)
        elif st == "global":
            tiers["global"].append(r)
    for key in ("canonical_item", "canonical_group", "global"):
        if tiers[key]:
            return tiers[key][0]
    return None


def _base_unit_for(canonical_item, canonical_group):
    return (
        _ITEM_BASE_UNIT.get(canonical_item)
        or _GROUP_BASE_UNIT.get(canonical_group)
        or "pcs"
    )


def resolve_base_quantity(canonical_item, canonical_group, quantity, unit,
                          quantity_mode=None, raw_text="", parsed=None):
    """Return {base_quantity, base_unit, pack_size, conversion_source,
    conversion_status}. conversion_source: explicit|table|direct|heuristic|none.
    conversion_status: ok|needs_review|unmeasurable."""
    parsed = parsed if parsed is not None else parse_packaging(raw_text)
    out = {
        "base_quantity": None,
        "base_unit": None,
        "pack_size": None,
        "conversion_source": "none",
        "conversion_status": "ok",
    }

    if parsed["pack_certainty"] == "unmeasurable":
        out["conversion_status"] = "unmeasurable"
        return out

    try:
        q_struct = float(quantity) if quantity not in (None, "", 0, 0.0) else None
    except (TypeError, ValueError):
        q_struct = None

    item_base = _base_unit_for(canonical_item, canonical_group)
    generic = {"pcs", "buah", "butir", "biji", "keping", "unit"}

    # 1. explicit "isi N" (or a constant pack like lusin/kodi) in the text
    if parsed["pack_size"]:
        mult = q_struct or parsed["outer_quantity"] or 1
        pbu = parsed["pack_base_unit"]
        base_unit = item_base if (not pbu or pbu in generic) else pbu
        out["pack_size"] = parsed["pack_size"]
        out["base_quantity"] = round(mult * parsed["pack_size"], 3)
        out["base_unit"] = base_unit
        out["conversion_source"] = (
            "explicit" if parsed["pack_certainty"] == "explicit" else "table"
        )
        return out

    # effective quantity + unit for the non-pack paths
    q = q_struct or parsed["outer_quantity"] or parsed["content_quantity"]
    if q in (None, ""):
        return out
    q = float(q)
    raw_u = (unit or parsed["form_unit"] or parsed["pack_unit"]
             or parsed["pack_base_unit"] or "")
    u = normalize_unit(raw_u) if raw_u else ""

    # 2. unit already equals this item's canonical base unit -> exact
    if raw_u and _canon_base(raw_u) == item_base:
        out["base_quantity"] = round(q, 3)
        out["base_unit"] = item_base
        out["conversion_source"] = "direct"
        return out

    # 3. RN Unit Conversion table
    row = _lookup_conversion(canonical_item, canonical_group, u)
    if row and row.get("factor"):
        out["pack_size"] = row["factor"]
        out["base_quantity"] = round(q * float(row["factor"]), 3)
        out["base_unit"] = _canon_base(row.get("to_base_unit")) or item_base
        out["conversion_source"] = "table"
        out["conversion_status"] = (
            "ok" if (row.get("certainty") or "standar") == "standar"
            else "needs_review"
        )
        return out

    # 4. a recognised base unit but no table row -> direct count
    if u and u in _BASE_UNITS and u not in generic:
        out["base_quantity"] = round(q, 3)
        out["base_unit"] = _canon_base(u)
        out["conversion_source"] = "direct"
        return out

    # 4b. a generic counter ("unit", "pcs", "buah") with no packaging signal.
    #     If the item does not roll up to a *different* base unit (liter, kg…),
    #     a bare count of discrete things IS reliable — e.g. "5 ekskavator",
    #     "3 genset". Only treat it as fuzzy when the item wants another base
    #     unit (e.g. "100 bh" of Air Minum, which should be litres).
    if u and u in generic and not parsed["pack_size"]:
        if item_base in generic or item_base == "pcs":
            out["base_quantity"] = round(q, 3)
            out["base_unit"] = "pcs"
            out["conversion_source"] = "direct"
            return out

    # 5. an outer package with no factor -> cannot measure yet
    if u and u in _OUTER_UNITS:
        out["conversion_status"] = "needs_review"
        return out

    # 6. a bare number with only a generic/unknown counter -> tentative
    out["base_quantity"] = round(q, 3)
    out["base_unit"] = _canon_base(u) if (u and u not in generic) else item_base
    out["conversion_source"] = "heuristic"
    out["conversion_status"] = "needs_review"
    return out


# conversion_source values trusted enough to call a quantity "measured"
_TRUSTED_SOURCES = {"explicit", "table", "direct", "manual"}


def _raw_split(quantity, quantity_mode, quantity_min, quantity_max):
    """(raw_exact, raw_est_mid, is_estimate) in the row's own unit."""
    def _f(v):
        try:
            return float(v) if v not in (None, "") else None
        except (TypeError, ValueError):
            return None

    q = _f(quantity) or 0.0
    lo, hi = _f(quantity_min), _f(quantity_max)
    mode = str(quantity_mode or "").lower()
    if mode == "range" and (lo is not None or hi is not None):
        lo = lo if lo is not None else (hi or 0.0)
        hi = hi if hi is not None else lo
        return 0.0, round((lo + hi) / 2.0, 3), True
    if mode in ("estimated", "estimate", "perkiraan"):
        base = q or (round(((lo or 0) + (hi or 0)) / 2.0, 3) if (lo or hi) else 0.0)
        return 0.0, base, True
    return q, 0.0, False


def bucket_quantity(canonical_item, canonical_group, quantity, unit,
                    quantity_mode=None, quantity_min=None, quantity_max=None,
                    raw_text="", stored=None):
    """Classify one row's quantity for a consolidated view.

    Returns a dict: measurable / estimated (both in base_unit),
    unmeasurable (0/1), base_unit, base_quantity, conversion_source,
    conversion_status.

    `stored` = a mapping carrying already-persisted base_* fields
    (RN Aid Offer / Logistic Need / Stock Observation). When its
    conversion_source is set (not 'none'/empty) it is trusted as-is;
    otherwise a fresh resolve_base_quantity() runs (used for
    RN Community Need, which does not persist these fields)."""
    raw_exact, raw_mid, is_est = _raw_split(
        quantity, quantity_mode, quantity_min, quantity_max)

    csource = (stored or {}).get("conversion_source") if stored else None
    if csource and str(csource).lower() not in ("none", ""):
        bq = (stored or {}).get("base_quantity")
        try:
            bq = float(bq) if bq not in (None, "") else None
        except (TypeError, ValueError):
            bq = None
        base_unit = (stored or {}).get("base_unit")
        cstatus = str((stored or {}).get("conversion_status") or "ok").lower()
        csource = str(csource).lower()
    else:
        res = resolve_base_quantity(
            canonical_item, canonical_group, quantity, unit,
            quantity_mode, raw_text or "")
        bq = res["base_quantity"]
        base_unit = res["base_unit"]
        cstatus = res["conversion_status"]
        csource = res["conversion_source"]

    if not base_unit:
        base_unit = (_canon_base(normalize_unit(unit)) if unit
                     else _base_unit_for(canonical_item, canonical_group))

    out = {
        "measurable": 0.0, "estimated": 0.0, "unmeasurable": 0,
        "base_unit": base_unit, "base_quantity": bq,
        "conversion_source": csource, "conversion_status": cstatus,
    }

    if cstatus == "unmeasurable":
        out["unmeasurable"] = 1
        return out
    if bq is not None and bq > 0:
        if cstatus == "ok" and csource in _TRUSTED_SOURCES and not is_est:
            out["measurable"] = bq
        else:
            out["estimated"] = bq
        return out
    # no converted base quantity
    if csource in ("none", "") and cstatus == "needs_review":
        val = raw_exact or raw_mid
        if val:
            out["estimated"] = val
        else:
            out["unmeasurable"] = 1
        return out
    if is_est:
        out["estimated"] = raw_mid
    elif raw_exact:
        out["estimated"] = raw_exact       # unconverted exact -> still fuzzy
    else:
        out["unmeasurable"] = 1
    return out


def enrich_document(doc):
    """Fill base_quantity / base_unit / pack_size / conversion_source /
    conversion_status on an RN Aid Offer / Logistic Need / Stock Observation
    before insert, without clobbering values a human already set."""
    if getattr(doc, "conversion_source", None) in ("manual",):
        return
    if getattr(doc, "base_quantity", None) not in (None, "", 0, 0.0):
        return
    res = resolve_base_quantity(
        getattr(doc, "canonical_item", None),
        getattr(doc, "canonical_group", None),
        getattr(doc, "quantity", None),
        getattr(doc, "unit", None),
        getattr(doc, "quantity_mode", None),
        getattr(doc, "raw_item_text", None) or getattr(doc, "item_name", "") or "",
    )
    if res["base_quantity"] is not None:
        doc.base_quantity = res["base_quantity"]
    if res["base_unit"]:
        doc.base_unit = res["base_unit"]
    if res["pack_size"] is not None:
        doc.pack_size = res["pack_size"]
    doc.conversion_source = res["conversion_source"]
    doc.conversion_status = res["conversion_status"]
