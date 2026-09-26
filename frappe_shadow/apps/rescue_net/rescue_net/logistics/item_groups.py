"""Logistics — cross-posko item groups (normalisation) and corrections."""

from collections import defaultdict

import frappe
from frappe.rate_limiter import rate_limit
from rescue_net.reference_resolver import resolve_disaster_event, resolve_posko
from frappe.utils import cint, flt, now_datetime

from rescue_net.access_policy import (
    approved_member,
    can_manage_organization,
    can_manage_posko,
    is_system_manager,
    public_posko_allowed,
    rn_actor,
)
from rescue_net.intelligence.freshness import freshness
from rescue_net.rescue_net.doctype.rn_distribution_flow.rn_distribution_flow import TRANSITIONS
from rescue_net.intelligence.normalization import normalize_unit

from rescue_net.logistics.common import (  # noqa: F401
    _ITEM_GROUP_DOCTYPES,
    _can_contribute,
    _can_operate,
)


def _split_qty(row):
    """Return (exact, est_mid, est_min, est_max, is_estimate) for one row,
    in the row's OWN unit (pre-conversion)."""
    q = flt(row.get("quantity")) if row.get("quantity") not in (None, "") else 0.0
    lo = flt(row.get("quantity_min")) if row.get("quantity_min") not in (None, "") else None
    hi = flt(row.get("quantity_max")) if row.get("quantity_max") not in (None, "") else None
    mode = str(row.get("quantity_mode") or "").lower()

    if mode == "range" and (lo is not None or hi is not None):
        lo = lo if lo is not None else (hi or 0.0)
        hi = hi if hi is not None else lo
        return 0.0, round((lo + hi) / 2.0, 2), lo, hi, True
    if mode in ("estimated", "estimate", "perkiraan"):
        base = q if q else (round(((lo or 0) + (hi or 0)) / 2.0, 2) if (lo or hi) else 0.0)
        return 0.0, base, (lo if lo is not None else base), (hi if hi is not None else base), True
    # exact / unknown / blank -> treat the number as accurate
    return q, 0.0, q, q, False


def _row_base_split(row):
    """Bucket one row's quantity for the grouped view.

    Thin wrapper over rescue_net.intelligence.packaging.bucket_quantity — the
    same helper the Control Centre consolidation (api_intelligence._group_rows)
    and Kelompok Alat (api_resource_tools) use, so all consolidated views agree.
    Returns (measurable, estimated, unmeasurable_flag, base_unit)."""
    from rescue_net.intelligence.packaging import bucket_quantity

    b = bucket_quantity(
        row.get("canonical_item"), row.get("canonical_group"),
        row.get("quantity"), row.get("unit"),
        row.get("quantity_mode"), row.get("quantity_min"),
        row.get("quantity_max"),
        row.get("raw_item_text") or row.get("item_name") or "",
        stored=row,
    )
    return b["measurable"], b["estimated"], b["unmeasurable"], b["base_unit"]


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def item_groups(disaster_event=None, posko=None, kinds=None):
    """Canonical rollup of aid offers + needs + stock by
    (canonical_group, base_unit). Each group carries three honest numbers:
    kuantitas TERUKUR (trusted conversion), PERKIRAAN AI (fuzzy conversion or
    estimate input), and a count of rows that are BELUM TERUKUR (no usable
    number / kemasan tidak baku)."""
    from rescue_net.intelligence.normalization import normalize_unit

    event = resolve_disaster_event(disaster_event) if disaster_event else None
    posko = resolve_posko(posko) if posko else None
    want = {k.strip() for k in (kinds or "offer,need,stock").split(",") if k.strip()}

    _F = [
        "name", "item_name", "raw_item_text", "quantity", "unit",
        "quantity_mode", "quantity_min", "quantity_max", "estimate_text",
        "canonical_group", "canonical_item", "canonical_category",
        "normalization_source", "normalization_confidence",
        "normalization_status",
        "base_quantity", "base_unit", "pack_size",
        "conversion_source", "conversion_status",
    ]

    groups = {}
    for kind, (dt, posko_field, _name_field) in _ITEM_GROUP_DOCTYPES.items():
        if kind not in want:
            continue
        filt = {}
        if event:
            filt["disaster_event"] = event
        if posko:
            filt[posko_field] = posko
        rows = frappe.get_all(dt, filters=filt,
                              fields=_F + [posko_field], limit_page_length=5000)
        for r in rows:
            gkey = (r.get("canonical_group") or r.get("canonical_item")
                    or (r.get("item_name") or r.get("raw_item_text") or "Lainnya"))
            meas, est, unmeas, base_unit = _row_base_split(r)
            key = (gkey, base_unit)
            g = groups.setdefault(key, {
                "group": gkey, "unit": base_unit,
                "category": r.get("canonical_category"),
                "qty_measurable": 0.0, "qty_estimated": 0.0,
                "member_count": 0, "measurable_member_count": 0,
                "estimated_member_count": 0, "unmeasurable_count": 0,
                "needs_review": 0, "conversion_review": 0,
                "poskos": set(), "sources": set(), "conv_sources": set(),
                "kinds": set(), "estimate_notes": [],
                "classified": bool(r.get("canonical_group")),
            })
            g["qty_measurable"] += meas
            g["qty_estimated"] += est
            g["member_count"] += 1
            if unmeas:
                g["unmeasurable_count"] += 1
                if r.get("estimate_text") or r.get("raw_item_text"):
                    g["estimate_notes"].append(
                        str(r.get("estimate_text") or r.get("raw_item_text"))[:80])
            elif meas:
                g["measurable_member_count"] += 1
            elif est:
                g["estimated_member_count"] += 1
                if r.get("estimate_text"):
                    g["estimate_notes"].append(str(r["estimate_text"])[:80])
            if (r.get("normalization_status") or "suggested") == "suggested":
                g["needs_review"] += 1
            if str(r.get("conversion_status") or "ok").lower() == "needs_review":
                g["conversion_review"] += 1
            p = r.get(posko_field)
            if p:
                g["poskos"].add(p)
            g["sources"].add(r.get("normalization_source") or "rule")
            g["conv_sources"].add(r.get("conversion_source") or "none")
            g["kinds"].add(kind)
            if r.get("canonical_group"):
                g["classified"] = True

    out = []
    for g in groups.values():
        src = ("manual" if "manual" in g["sources"]
               else "ai" if "ai" in g["sources"]
               else "rule" if "rule" in g["sources"] else "tidak_diketahui")
        measurable = round(g["qty_measurable"], 2)
        estimated = round(g["qty_estimated"], 2)
        out.append({
            "group": g["group"],
            "unit": g["unit"],
            "base_unit": g["unit"],
            "category": g["category"],
            "qty_measurable": measurable,
            "qty_estimated": estimated,
            "qty_total": round(measurable + estimated, 2),
            "unmeasurable_count": g["unmeasurable_count"],
            "estimate_note": " · ".join(g["estimate_notes"][:3]),
            "member_count": g["member_count"],
            "measurable_member_count": g["measurable_member_count"],
            "estimated_member_count": g["estimated_member_count"],
            "needs_review": g["needs_review"],
            "conversion_review": g["conversion_review"],
            "posko_spread": len(g["poskos"]),
            "kinds": sorted(g["kinds"]),
            "source": src,
            "conversion_sources": sorted(s for s in g["conv_sources"] if s and s != "none"),
            "classified": g["classified"],
            # --- back-compat aliases for older cached frontend ---
            "qty_exact": measurable,
            "estimate_member_count": g["estimated_member_count"],
            "est_range": None,
        })
    out.sort(key=lambda x: (-x["member_count"], x["group"]))
    return {
        "disaster_event": event, "posko": posko,
        "generated_at": now_datetime(),
        "groups": out,
        "method_note": (
            "Pengelompokan + konversi pakai aturan deterministik "
            "(classify_text + RN Unit Conversion) — bukan AI black-box. "
            "'Terukur' = konversi tepat (isi eksplisit / tabel standar / satuan "
            "dasar). 'Perkiraan AI' = konversi perkiraan atau input estimasi. "
            "'Belum terukur' = tanpa angka jelas / kemasan tidak baku "
            "(mis. 'karung kecil', 'tas kresek'). Posko penerima bisa koreksi "
            "(ubah satuan/kemasan/isi per dus) via tombol Koreksi di detail."
        ),
    }


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def item_group_members(group, disaster_event=None, unit=None, posko=None,
                       kinds=None):
    from rescue_net.intelligence.normalization import normalize_unit

    event = resolve_disaster_event(disaster_event) if disaster_event else None
    posko = resolve_posko(posko) if posko else None
    want = {k.strip() for k in (kinds or "offer,need,stock").split(",") if k.strip()}
    unit_c = normalize_unit(unit) if unit else None

    _F = [
        "name", "item_name", "raw_item_text", "quantity", "unit",
        "quantity_mode", "quantity_min", "quantity_max", "estimate_text",
        "canonical_group", "canonical_item", "normalization_source",
        "normalization_confidence", "normalization_status", "observed_at",
        "base_quantity", "base_unit", "pack_size",
        "conversion_source", "conversion_status",
    ]
    members = []
    for kind, (dt, posko_field, _nf) in _ITEM_GROUP_DOCTYPES.items():
        if kind not in want:
            continue
        filt = {}
        if event:
            filt["disaster_event"] = event
        if posko:
            filt[posko_field] = posko
        for r in frappe.get_all(dt, filters=filt, fields=_F + [posko_field],
                                limit_page_length=5000):
            gkey = (r.get("canonical_group") or r.get("canonical_item")
                    or (r.get("item_name") or r.get("raw_item_text") or "Lainnya"))
            if gkey != group:
                continue
            row_base_unit = r.get("base_unit") or normalize_unit(r.get("unit"))
            if unit_c and row_base_unit != unit_c:
                continue
            ex, mid, lo, hi, is_est = _split_qty(r)
            meas, est, unmeas, _bu = _row_base_split(r)
            p = r.get(posko_field)
            members.append({
                "doctype": dt, "name": r["name"], "kind": kind,
                "posko": p,
                "posko_title": (frappe.db.get_value("RN Posko", p, "title") if p else "-"),
                "item_name": r.get("item_name") or r.get("raw_item_text") or "-",
                "raw_text": r.get("raw_item_text") or r.get("item_name") or "",
                "quantity": r.get("quantity"),
                "unit": r.get("unit") or "",
                "unit_canonical": normalize_unit(r.get("unit")),
                "quantity_mode": r.get("quantity_mode") or "unknown",
                "quantity_min": r.get("quantity_min"),
                "quantity_max": r.get("quantity_max"),
                "estimate_text": r.get("estimate_text") or "",
                "is_estimate": is_est,
                "qty_exact": round(ex, 2),
                "qty_estimated": round(mid, 2),
                "base_quantity": r.get("base_quantity"),
                "base_unit": row_base_unit,
                "pack_size": r.get("pack_size"),
                "conversion_source": r.get("conversion_source") or "none",
                "conversion_status": r.get("conversion_status") or "ok",
                "measured_bucket": ("belum_terukur" if unmeas
                                    else "terukur" if meas else "perkiraan"),
                "base_measurable": round(meas, 2),
                "base_estimated": round(est, 2),
                "canonical_group": r.get("canonical_group") or "",
                "canonical_item": r.get("canonical_item") or "",
                "normalization_source": r.get("normalization_source") or "rule",
                "normalization_confidence": r.get("normalization_confidence"),
                "normalization_status": r.get("normalization_status") or "suggested",
                "observed_at": r.get("observed_at"),
            })
    members.sort(key=lambda m: str(m["observed_at"] or ""), reverse=True)
    return {"group": group, "unit": unit_c, "members": members}


@frappe.whitelist()
def correct_item_normalization(doctype, name, canonical_group=None,
                               canonical_item=None, unit=None, quantity=None,
                               quantity_mode=None, note=None, also_apply=None,
                               base_quantity=None, base_unit=None,
                               pack_size=None):
    """Posko-side correction of an item's normalisation: change the
    packaging/unit, move it to another group, mark the quantity accurate,
    fix the measured base quantity / isi-per-kemasan, or merge several rows
    into one group ("jadikan satu" via `also_apply`).
    Marks the row(s) normalization_status=accepted / source=manual.

    Base quantity handling on the primary row:
      - explicit `base_quantity` (+ optional `base_unit`)  -> stored as-is,
        conversion_source=manual, conversion_status=ok;
      - `pack_size` given (isi per kemasan)                -> base = qty * pack_size;
      - otherwise                                          -> recomputed from
        the (possibly updated) unit/quantity via the RN Unit Conversion table.
    `also_apply` = JSON list of {"doctype","name"} to receive the same
    canonical_group / canonical_item / unit in one approval."""
    import json as _json

    from rescue_net.intelligence.packaging import (
        parse_packaging,
        resolve_base_quantity,
        _base_unit_for,
    )

    if doctype not in {v[0] for v in _ITEM_GROUP_DOCTYPES.values()}:
        frappe.throw("Doctype tidak didukung untuk koreksi normalisasi.")

    actor = rn_actor()

    def _posko_of(dt, nm):
        pf = next(v[1] for v in _ITEM_GROUP_DOCTYPES.values() if v[0] == dt)
        return frappe.db.get_value(dt, nm, pf)

    def _recompute_base(d):
        """Refresh base_quantity/base_unit/pack_size/conversion_* on the primary
        row after a manual correction."""
        if base_quantity not in (None, ""):
            d.base_quantity = flt(base_quantity)
            d.base_unit = (base_unit or d.base_unit
                           or _base_unit_for(d.canonical_item, d.canonical_group))
            if pack_size not in (None, ""):
                d.pack_size = flt(pack_size)
            d.conversion_source = "manual"
            d.conversion_status = "ok"
            return
        if pack_size not in (None, ""):
            ps = flt(pack_size)
            qty = flt(d.quantity) or (parse_packaging(
                d.raw_item_text or d.item_name or "")["parsed_quantity"] or 0)
            d.pack_size = ps
            d.base_quantity = round(qty * ps, 3) if qty else None
            d.base_unit = (base_unit or d.base_unit
                           or _base_unit_for(d.canonical_item, d.canonical_group))
            d.conversion_source = "manual"
            d.conversion_status = "ok"
            return
        # no explicit base input -> recompute from the current unit/quantity
        res = resolve_base_quantity(
            d.canonical_item, d.canonical_group, d.quantity, d.unit,
            d.quantity_mode, d.raw_item_text or d.item_name or "",
        )
        d.base_quantity = res["base_quantity"]
        d.base_unit = res["base_unit"] or d.base_unit
        if res["pack_size"] is not None:
            d.pack_size = res["pack_size"]
        d.conversion_source = res["conversion_source"]
        d.conversion_status = res["conversion_status"]

    # L-23: regrouping is a contribution; changing a stock row's amount
    # (quantity / mode / unit / isi per kemasan) is a stock edit.
    rewrites_amount = any(v not in (None, "") for v in (
        quantity, quantity_mode, unit, base_quantity, pack_size))

    def _apply(dt, nm, is_primary):
        posko = _posko_of(dt, nm)
        if posko and not _can_contribute(actor, resolve_posko(posko)):
            frappe.throw(
                f"Anda tidak berhak mengoreksi item milik posko {posko}.",
                frappe.PermissionError,
            )
        if (is_primary and rewrites_amount and dt == "RN Stock Observation"
                and not (posko and _can_operate(actor, resolve_posko(posko)))):
            frappe.throw(
                "Jumlah/satuan stok hanya dapat diubah operator posko.",
                frappe.PermissionError,
            )
        d = frappe.get_doc(dt, nm)
        if canonical_group is not None:
            d.canonical_group = canonical_group or None
        if canonical_item is not None:
            d.canonical_item = canonical_item or None
        if is_primary:
            if unit is not None:
                d.unit = unit or None
            if quantity not in (None, ""):
                d.quantity = flt(quantity)
            if quantity_mode:
                d.quantity_mode = quantity_mode
            _recompute_base(d)
        d.normalization_source = "manual"
        d.normalization_status = "accepted"
        if note and hasattr(d, "notes"):
            d.notes = ((d.notes + " | ") if d.notes else "") + "Koreksi normalisasi: " + note
        d.save(ignore_permissions=True)
        return d.name

    changed = [_apply(doctype, name, True)]

    extras = also_apply
    if isinstance(extras, str):
        try:
            extras = _json.loads(extras)
        except Exception:
            extras = []
    for e in (extras or []):
        edt = (e or {}).get("doctype")
        enm = (e or {}).get("name")
        if edt in {v[0] for v in _ITEM_GROUP_DOCTYPES.values()} and enm:
            changed.append(_apply(edt, enm, False))

    return {
        "updated": changed,
        "count": len(changed),
        "canonical_group": canonical_group,
        "canonical_item": canonical_item,
    }
