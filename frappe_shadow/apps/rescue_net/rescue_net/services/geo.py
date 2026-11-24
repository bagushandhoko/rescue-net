"""Hitungan lokasi bersama (owner 24 Nov 2026, langkah 1 menuju PostGIS).

Prinsip: database menyaring dulu dengan KOTAK lintang/bujur (memakai indeks rn_lat_lng), baru Python menghitung
jarak bulat (haversine) untuk sisa baris yang sedikit. Hasilnya sama dengan menghitung semua baris, tetapi tidak
lagi mengambil ribuan posko/laporan setiap kali. Bila kelak pindah ke PostGIS, cukup modul ini yang diganti."""

import math

import frappe
from frappe.utils import flt

EARTH_KM = 6371.0088


def km(lat1, lng1, lat2, lng2):
    """Jarak garis lurus (km) di permukaan bumi; None bila salah satu titik tidak lengkap."""
    if None in (lat1, lng1, lat2, lng2):
        return None
    p1, p2 = math.radians(flt(lat1)), math.radians(flt(lat2))
    h = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(flt(lng2) - flt(lng1)) / 2) ** 2)
    return 2 * EARTH_KM * math.asin(min(1.0, math.sqrt(h)))


def bbox(lat, lng, radius_km):
    """(lat_min, lat_max, lng_min, lng_max) yang PASTI memuat lingkaran radius_km di sekitar titik."""
    lat, lng, r = flt(lat), flt(lng), max(0.0, flt(radius_km))
    dlat = math.degrees(r / EARTH_KM)
    la0, la1 = max(-90.0, lat - dlat), min(90.0, lat + dlat)
    # lebar 1 derajat bujur menyempit ke arah kutub: pakai lintang terjauh dari khatulistiwa di dalam kotak
    c = math.cos(math.radians(max(abs(la0), abs(la1))))
    dlng = 180.0 if c < 1e-6 else min(180.0, math.degrees(r / (EARTH_KM * c)))
    return la0, la1, lng - dlng, lng + dlng


def bbox_filters(lat, lng, radius_km, lat_field="latitude", lng_field="longitude"):
    """Penyaring Frappe (daftar [kolom, op, nilai]) untuk kotak lokasi. ``between`` Frappe hanya untuk tanggal."""
    la0, la1, lo0, lo1 = bbox(lat, lng, radius_km)
    f = [[lat_field, ">=", la0], [lat_field, "<=", la1]]
    if lo0 >= -180.0 and lo1 <= 180.0:   # kotak menyeberang garis tanggal: saring lintang saja (Indonesia tak kena)
        f += [[lng_field, ">=", lo0], [lng_field, "<=", lo1]]
    return f


def near(doctype, lat, lng, radius_km, fields=None, filters=None, limit=None,
         lat_field="latitude", lng_field="longitude"):
    """Baris ``doctype`` dalam radius_km dari titik, terurut dari yang terdekat; tiap baris diberi kunci ``km``.
    Titik 0,0 (koordinat belum diisi) tidak pernah ikut."""
    if isinstance(filters, dict):
        f = [[k] + (list(v) if isinstance(v, (list, tuple)) else ["=", v]) for k, v in filters.items()]
    else:
        f = [list(x) for x in (filters or [])]
    f += bbox_filters(lat, lng, radius_km, lat_field, lng_field)
    want = list(dict.fromkeys(["name", lat_field, lng_field] + list(fields or [])))
    out = []
    for r in frappe.get_all(doctype, filters=f, fields=want, limit_page_length=0):
        la, lo = flt(r.get(lat_field)), flt(r.get(lng_field))
        if not (la or lo):
            continue
        d = km(lat, lng, la, lo)
        if d is not None and d <= radius_km:
            r["km"] = d
            out.append(r)
    out.sort(key=lambda x: x["km"])
    return out[:limit] if limit else out
