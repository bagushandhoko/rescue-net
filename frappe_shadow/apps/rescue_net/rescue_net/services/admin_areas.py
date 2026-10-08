"""Wilayah administratif berkode: impor aman, crosswalk kode eksternal, pencocokan nama → kode (ADR-0005).

Aturan impor (ADR-0005 A.4):
  * dry-run adalah bawaan; tidak ada baris ditulis sebelum laporan kualitas `ok` (kode salah, ganda bernama beda,
    level/induk tidak cocok, induk tidak ada = berhenti);
  * idempoten: menjalankan berkas yang sama dua kali tidak mengubah apa pun; nama yang berubah diperbarui,
    wilayah yang tidak ada di berkas TIDAK dihapus/dinonaktifkan (pemekaran → `valid_to`, bukan hapus);
  * jalankan dulu di test stack, bandingkan jumlah per tingkat, baru produksi dengan persetujuan owner.
"""

import csv
import json
from pathlib import Path

import frappe
from frappe.utils import now

from rescue_net.services import admin_area_codes as codes

DOCTYPE = "RN Admin Area"
_INSERT_FIELDS = ("name", "creation", "modified", "modified_by", "owner", "docstatus", "idx",
                  "code", "area_name", "level", "parent_code", "source", "source_reference", "enabled")


# ---------- reading a file ----------
def load_file(path):
    """CSV (delimiter sniffed) or JSON (array / {data|results|items|records: [...]}) -> (rows, unusable_count)."""
    path = Path(path)
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if isinstance(data, dict):
            for key in ("data", "results", "items", "records"):
                if isinstance(data.get(key), list):
                    data = data[key]
                    break
        if not isinstance(data, list):
            raise ValueError("JSON harus berupa array atau punya key data/results/items/records.")
        raw = data
    else:
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            sample = f.read(8192)
            f.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
            except csv.Error:
                dialect = csv.excel
            raw = list(csv.DictReader(f, dialect=dialect))
    rows, unusable = [], 0
    for r in raw:
        item = codes.normalize_row(r)
        if item:
            rows.append(item)
        else:
            unusable += 1
    return rows, unusable


def existing_codes():
    return set(frappe.get_all(DOCTYPE, pluck="name", limit_page_length=0))


# ---------- import ----------
def import_rows(rows, source, source_reference=None, dry_run=True, batch=2000):
    """Plan, validate and (unless dry_run) write. Returns a report; `applied` is True only when rows were written."""
    rows = codes.sort_rows(rows)
    have = existing_codes()
    report = codes.validate_rows(rows, known_codes=have)
    current = {r.name: r for r in frappe.get_all(
        DOCTYPE, fields=["name", "area_name", "level", "parent_code"], limit_page_length=0)} if have else {}

    new, changed, same = [], [], 0
    seen = set()
    for r in rows:
        if r["code"] in seen:
            continue
        seen.add(r["code"])
        cur = current.get(r["code"])
        if not cur:
            new.append(r)
        elif (cur.area_name, cur.level, cur.parent_code or "") != (r["area_name"], r["level"], r["parent_code"] or ""):
            changed.append((cur, r))
        else:
            same += 1

    plan = {"new": len(new), "changed": len(changed), "unchanged": same, "not_in_file_left_untouched": len(have - seen)}
    out = {"validation": report, "plan": plan, "dry_run": bool(dry_run), "applied": False, "samples": {
        "new": [r["code"] + " " + r["area_name"] for r in new[:5]],
        "changed": [f"{c.name}: {c.area_name} → {r['area_name']}" for c, r in changed[:5]]}}
    if dry_run or not report["ok"]:
        return out

    stamp, user = now(), frappe.session.user or "Administrator"
    for i in range(0, len(new), batch):
        chunk = new[i:i + batch]
        frappe.db.bulk_insert(
            DOCTYPE, fields=list(_INSERT_FIELDS),
            values=[(r["code"], stamp, stamp, user, user, 0, 0, r["code"], r["area_name"], r["level"],
                     r["parent_code"] or None, source, source_reference, 1) for r in chunk],
            ignore_duplicates=True)
    for cur, r in changed:
        frappe.db.set_value(DOCTYPE, cur.name, {"area_name": r["area_name"], "level": r["level"],
                                                "parent_code": r["parent_code"] or None, "source": source,
                                                "source_reference": source_reference}, update_modified=True)
    out["applied"] = True
    return out


# ---------- crosswalk ----------
def import_crosswalk(rows, code_system, source=None, confidence="exact", dry_run=True, batch=2000):
    """rows: [{code (Kemendagri), external_code}] -> RN Admin Area Crosswalk. One external code → one area."""
    if code_system not in ("ocha_pcode", "bps", "kemendagri_legacy", "other"):
        raise ValueError("code_system tidak dikenal")
    have = existing_codes()
    existing = {(r.code_system, r.external_code): r.area for r in frappe.get_all(
        "RN Admin Area Crosswalk", filters={"code_system": code_system},
        fields=["code_system", "external_code", "area"], limit_page_length=0)}
    issues, add, seen = {}, [], {}

    def flag(kind, detail):
        b = issues.setdefault(kind, {"count": 0, "samples": []})
        b["count"] += 1
        if len(b["samples"]) < 5:
            b["samples"].append(detail)

    for r in rows:
        area = codes.normalize_code(r.get("code"))
        ext = str(r.get("external_code") or "").strip()
        if not ext or not area:
            flag("empty", f"{area!r} {ext!r}")
        elif area not in have:
            flag("unknown_area", f"{ext} → {area}")
        elif (code_system, ext) in existing and existing[(code_system, ext)] != area:
            flag("conflicts_with_existing", f"{ext}: {existing[(code_system, ext)]} ≠ {area}")
        elif ext in seen and seen[ext] != area:
            flag("one_code_two_areas", f"{ext}: {seen[ext]} / {area}")
        elif (code_system, ext) in existing or ext in seen:
            seen[ext] = area
        else:
            seen[ext] = area
            add.append((area, ext))
    ok = not issues
    out = {"issues": issues, "ok": ok, "new": len(add), "dry_run": bool(dry_run), "applied": False}
    if dry_run or not ok:
        return out
    stamp, user = now(), frappe.session.user or "Administrator"
    fields = ["name", "creation", "modified", "modified_by", "owner", "docstatus", "idx",
              "code_system", "external_code", "area", "confidence", "source"]
    for i in range(0, len(add), batch):
        frappe.db.bulk_insert(
            "RN Admin Area Crosswalk", fields=fields,
            values=[(frappe.generate_hash(length=10), stamp, stamp, user, user, 0, 0, code_system, ext, area,
                     confidence, source) for area, ext in add[i:i + batch]])
    out["applied"] = True
    return out


def resolve_external(code_system, external_code):
    """OCHA/BPS/older code -> RN Admin Area name (Kemendagri code), or None."""
    return frappe.db.get_value("RN Admin Area Crosswalk",
                               {"code_system": code_system, "external_code": str(external_code).strip()}, "area")


def external_codes(area):
    return frappe.get_all("RN Admin Area Crosswalk", filters={"area": area},
                          fields=["code_system", "external_code", "confidence", "source"], limit_page_length=50)


# ---------- names -> code (used to map existing poskos / reports, ADR-0005 A.5) ----------
def match_by_names(province=None, city=None, district=None, village=None):
    """Walk top-down by name. Returns {code, level, confidence, path} or {code: None, reason, candidates}.
    A level that is given but matches nothing, or matches several areas under the same parent, stops the walk —
    a wrong guess is worse than 'unmatched' (the reporter's area stays free text for a human to fix)."""
    parent, path, level_done = None, [], None
    for level, name in (("province", province), ("city", city), ("district", district), ("village", village)):
        want = codes.normalize_name(name, level)
        if not want:
            continue
        filters = {"level": level, "enabled": 1}
        if parent:
            filters["parent_code"] = parent
        rows = frappe.get_all(DOCTYPE, filters=filters, fields=["name", "area_name"], limit_page_length=0)
        exact = [r for r in rows if codes.normalize_name(r.area_name, level) == want]
        if len(exact) > 1 and level == "city" and codes.city_kind(name):
            kind = codes.city_kind(name)
            exact = [r for r in exact if codes.city_kind(r.area_name) == kind] or exact
        if len(exact) == 1:
            parent, level_done = exact[0].name, level
            path.append(exact[0].name)
            continue
        if not exact:
            return {"code": None, "reason": f"{level} '{name}' tidak ditemukan" + (f" di bawah {parent}" if parent else ""),
                    "candidates": [], "path": path}
        return {"code": None, "reason": f"{level} '{name}' ambigu", "candidates": [r.name for r in exact][:5], "path": path}
    if not parent:
        return {"code": None, "reason": "tidak ada nama wilayah", "candidates": [], "path": path}
    return {"code": parent, "level": level_done, "confidence": "exact", "path": path}


def ancestors(code):
    """[province, city, district, village] rows up to `code` (for breadcrumbs)."""
    out, cur = [], code
    while cur:
        row = frappe.db.get_value(DOCTYPE, cur, ["name", "area_name", "level", "parent_code"], as_dict=True)
        if not row:
            break
        out.append(row)
        cur = row.parent_code
    return list(reversed(out))
