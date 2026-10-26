"""Konversi satuan untuk stok (owner 2026-10-26, dari simulasi: dapur mencatat
beras dalam kg, LD2 mengirim dalam karung → penerimaan tertahan).

Reads the editable RN Unit Conversion table (already used by the item
normalisation in intelligence/packaging.py). Lookup order for one unit:
a row for the exact item name → the AI canonical item → its canonical group →
global. Two units convert when both reach the same base unit (karung → kg ←
kg). Returns None when no conversion is known; callers then keep refusing."""

import frappe
from frappe.utils import flt

from rescue_net.intelligence.normalization import normalize_unit


def _canon(unit):
    return normalize_unit(unit or "") or (unit or "").strip().lower()


def _rows():
    from rescue_net.intelligence.packaging import _enabled_conversions
    return _enabled_conversions()


def _classify(item_name):
    try:
        from rescue_net.intelligence.normalization_registry import classify_text
        r = classify_text(item_name or "") or {}
        return r.get("canonical_item"), r.get("canonical_group")
    except Exception:
        return None, None


def _to_base(item_name, unit, citem, cgroup):
    """(factor, base_unit, certainty) for one unit of `unit`, or None."""
    u = _canon(unit)
    name = (item_name or "").strip().lower()
    tiers = ([], [], [], [])
    for r in _rows():
        if _canon(r.get("from_unit")) != u or not flt(r.get("factor")):
            continue
        st = r.get("scope_type") or "canonical_item"
        ci = (r.get("canonical_item") or "").strip()
        if st == "canonical_item" and ci.lower() == name:
            tiers[0].append(r)
        elif st == "canonical_item" and citem and ci == citem:
            tiers[1].append(r)
        elif st == "canonical_group" and cgroup and r.get("canonical_group") == cgroup:
            tiers[2].append(r)
        elif st == "global":
            tiers[3].append(r)
    for t in tiers:
        if t:
            r = t[0]
            return flt(r["factor"]), _canon(r.get("to_base_unit")), r.get("certainty") or "perkiraan"
    return None


def convert(item_name, quantity, from_unit, to_unit):
    """Quantity in `to_unit`, plus a human note. None when not convertible."""
    q = flt(quantity)
    fu, tu = _canon(from_unit), _canon(to_unit)
    if not fu or not tu:
        return None
    if fu == tu:
        return {"quantity": q, "note": None, "certainty": "standar"}
    citem, cgroup = _classify(item_name)
    a = _to_base(item_name, from_unit, citem, cgroup) or ((1.0, fu, "standar") if fu else None)
    b = _to_base(item_name, to_unit, citem, cgroup) or ((1.0, tu, "standar") if tu else None)
    if not a or not b or a[1] != b[1] or not b[0]:
        return None
    out = round(q * a[0] / b[0], 3)
    cert = "perkiraan" if "perkiraan" in (a[2], b[2]) else "standar"
    note = "%g %s = %g %s (tabel konversi%s)" % (q, from_unit, out, to_unit, ", perkiraan" if cert == "perkiraan" else "")
    return {"quantity": out, "note": note, "certainty": cert}


def stock_unit(posko, item_name):
    """Unit of the latest stock observation of `item_name` at `posko` (or None)."""
    r = frappe.db.sql("""SELECT unit FROM `tabRN Stock Observation` WHERE posko=%s AND item_name=%s
                         ORDER BY observed_at DESC, creation DESC LIMIT 1""", (posko, item_name))
    return (r[0][0] or "").strip() if r else None
