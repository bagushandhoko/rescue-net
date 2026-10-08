#!/usr/bin/env python3
"""Ubah dump SQL kode wilayah (format `INSERT INTO wilayah (kode, nama) VALUES ('11','Aceh'), ...`) menjadi CSV dan
jalankan laporan kualitas. TIDAK menyentuh database. Jalankan terhadap berkas unduhan yang tidak tepercaya dengan:

    python3 -I scripts/rn-wilayah-convert.py <wilayah.sql> <keluaran.csv> \
        frappe_shadow/apps/rescue_net/rescue_net/services/admin_area_codes.py

Lihat docs/WILAYAH_IMPORT.md untuk prosedur lengkap."""
import csv, re, sys, importlib.util
src, dst, mod = sys.argv[1], sys.argv[2], sys.argv[3]
spec = importlib.util.spec_from_file_location("c", mod); c = importlib.util.module_from_spec(spec); spec.loader.exec_module(c)
pat = re.compile(r"^\('((?:[^']|'')*)','((?:[^']|'')*)'\)[,;]?\s*$")
rows, skipped = [], 0
for line in open(src, encoding="utf-8"):
    m = pat.match(line)
    if not m:
        if line.startswith("('"): skipped += 1
        continue
    rows.append({"kode": m.group(1).replace("''", "'"), "nama": m.group(2).replace("''", "'")})
with open(dst, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["kode", "nama"]); w.writeheader(); w.writerows(rows)
norm = [c.normalize_row(r) for r in rows]
bad = sum(1 for n in norm if n is None)
norm = [n for n in norm if n]
rep = c.validate_rows(norm)
print("lines parsed:", len(rows), "| unparsed '(' lines:", skipped, "| unusable rows:", bad)
print("counts:", rep["counts"], "| total:", rep["total"], "| ok:", rep["ok"])
for k, v in rep["issues"].items(): print(" issue", k, v["count"], v["samples"][:3])
import collections
print("longest names:", sorted((len(r["area_name"]), r["area_name"]) for r in norm)[-2:])
