"""Hitungan analisis Nala: Python murni, tanpa site, AI, atau perubahan data."""
import math
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from statistics import median


def angka(value):
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (ValueError, TypeError):
        return None


def waktu(value):
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
    return dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo else dt


def normal(value):
    return " ".join(re.findall(r"\w+", unicodedata.normalize("NFKC", str(value or "")).casefold()))


def ukuran(row):
    """Jangan mencampur satuan. Nol base_quantity adalah nilai sah."""
    if row.get("base_unit") and angka(row.get("base_quantity")) is not None and row.get("conversion_status") == "ok":
        return angka(row["base_quantity"]), normal(row["base_unit"]), True
    return angka(row.get("quantity")), normal(row.get("unit")), False


def kelompok_stok(rows):
    groups = defaultdict(list)
    for row in rows:
        if row.get("stock_state") not in (None, "", "available") or row.get("quantity_mode") in ("unknown", "range"):
            continue
        qty, unit, base = ukuran(row)
        stamp = waktu(row.get("observed_at"))
        item = normal(row.get("canonical_item") or row.get("item_name"))
        if row.get("posko") and item and unit and qty is not None and qty >= 0 and stamp:
            groups[(row["posko"], item, unit)].append((stamp, str(row.get("name") or ""), qty, base, row))
    return groups


def hitung_stok(rows, now=None):
    """Laju eksplisit di unit asli/hari; jika dikonversi, skalakan ke unit dasar.

    Tren = penurunan bersih observasi pertama-terakhir / selang hari. Ini
    perkiraan, bukan ledger: pengisian ulang dapat menutupi pemakaian aktual.
    """
    result = []
    now = waktu(now) if now else None
    for (posko, item, unit), values in sorted(kelompok_stok(rows).items()):
        values.sort(key=lambda v: (v[0], v[1]))
        first, last = values[0], values[-1]
        stamp, _, stock, base, row = last
        daily = angka(row.get("rn_daily_consumption"))
        source = "rn_daily_consumption"
        if daily is not None and daily > 0 and base:
            original = angka(row.get("quantity"))
            if original and original > 0:
                daily *= stock / original
            elif normal(row.get("unit")) != unit:
                daily = None  # faktor konversi tidak diketahui pada stok nol
        if daily is None or daily <= 0:
            elapsed = (stamp - first[0]).total_seconds() / 86400
            daily = (first[2] - stock) / elapsed if elapsed > 0 and first[2] > stock else None
            source = "tren_bersih" if daily else "tidak_diketahui"
        days = stock / daily if daily and daily > 0 else None
        result.append({"posko": posko, "item": item, "unit": unit, "stok": stock,
                       "pemakaian_per_hari": daily, "sumber_laju": source, "sisa_hari": days,
                       "status": "kritis" if days is not None and days <= 3 else "waspada" if days is not None and days <= 7 else "cukup" if days is not None else "data_kurang",
                       "observasi": len(values), "observed_at": stamp.isoformat(sep=" "),
                       "umur_hari": max(0, (now-stamp).total_seconds()/86400) if now else None,
                       "calon_surplus": False})
    for row in result:
        peers = [r["stok"] for r in result if r["item"] == row["item"] and r["unit"] == row["unit"] and r["posko"] != row["posko"]]
        # 'besar': >=100 unit dan >=2x median stok posko LAIN yang sebanding.
        threshold = max(100, 2 * median(peers)) if peers else 100
        row["calon_surplus"] = bool((row["sisa_hari"] is not None and row["sisa_hari"] > 30) or
            (row["pemakaian_per_hari"] is None and row["stok"] >= threshold))
    for row in result:
        row["sumber_realokasi"] = [r["posko"] for r in result if r["posko"] != row["posko"] and
            r["item"] == row["item"] and r["unit"] == row["unit"] and r["calon_surplus"]] if row["status"] in ("kritis", "waspada") else []
    return result


def koordinat(lat, lon):
    lat, lon = angka(lat), angka(lon)
    if lat is None or lon is None or not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise ValueError("Koordinat tidak sah")
    return lat, lon


def haversine(lat1, lon1, lat2, lon2):
    lat1, lon1 = koordinat(lat1, lon1)
    lat2, lon2 = koordinat(lat2, lon2)
    a, b, c, d = map(math.radians, (lat1, lon1, lat2, lon2))
    h = math.sin((c-a)/2)**2 + math.cos(a)*math.cos(c)*math.sin((d-b)/2)**2
    return 6371.0088 * 2 * math.asin(math.sqrt(min(1, max(0, h))))


def deteksi_kandidat(offers=(), stocks=(), needs=(), bids=(), reports=(), max_candidates=2000):
    """Kandidat untuk pemeriksaan, bukan bukti kesalahan/penipuan. Identitas tidak keluar."""
    out = []
    def add(jenis, ids, alasan, **facts):
        if len(out) >= max_candidates:
            return
        out.append({"id": "K%04d" % (len(out)+1), "jenis": jenis,
                    "rujukan": list(ids), "alasan": alasan, "fakta": facts})
    groups = defaultdict(list)
    for r in offers:
        donor = normal(r.get("donor_name"))
        qty = angka(r.get("quantity"))
        item = normal(r.get("item_name"))
        stamp = waktu(r.get("creation"))
        if donor and item and qty is not None and stamp:
            groups[(donor, item, qty, normal(r.get("unit")))].append((stamp, r["name"]))
    for values in groups.values():
        values.sort()
        for i, (stamp, name) in enumerate(values):
            for other_stamp, other_name in values[i+1:]:
                if (other_stamp-stamp).total_seconds() > 48*3600:
                    break
                add("bantuan_kembar", [name, other_name], "Donor, barang, jumlah dan satuan sama dalam 48 jam; perlu dicek.")
    for values in kelompok_stok(stocks).values():
        values.sort(key=lambda v: (v[0], v[1]))
        for prev, curr in zip(values, values[1:]):
            if prev[0] == curr[0]:
                continue
            low, high = sorted((prev[2], curr[2]))
            if high > 0 and (low == 0 or high > low * 5):
                add("perubahan_stok", [prev[1], curr[1]], "Stok berubah lebih dari 5 kali atau melintasi nol; perlu dicek.", sebelum=prev[2], sesudah=curr[2])
    groups = defaultdict(list)
    for r in needs:
        qty, unit, _ = ukuran(r)
        if r.get("canonical_item") and unit and qty is not None and qty >= 0:
            groups[(normal(r["canonical_item"]), unit)].append((qty, r["name"]))
    for values in groups.values():
        mid = median(q for q, _ in values)
        if len(values) >= 3 and mid > 0:
            for qty, name in values:
                if qty > mid * 10:
                    add("kebutuhan_outlier", [name], "Jumlah melebihi 10 kali median barang dan satuan sama; perlu dicek.", jumlah=qty, median=mid, sampel=len(values))
    groups = defaultdict(list)
    for r in bids:
        amount = angka(r.get("bid_amount"))
        if r.get("tender") and amount is not None and amount >= 0:
            groups[r["tender"]].append((amount, r["name"]))
    for tender, values in groups.items():
        mid = median(q for q, _ in values)
        if len(values) >= 3 and mid > 0:
            for amount, name in values:
                if amount < mid * .5 or amount > mid * 2:
                    add("penawaran_tender", [name, tender], "Nilai di luar 50–200% median tender; perlu dicek.", nilai=amount, median=mid, sampel=len(values))
    texts = [normal(r.get("description"))[:600] for r in reports]
    # Jaccard bigram kata: linear terhadap panjang teks, tanpa pencocokan
    # kuadratik karakter yang mahal pada teks berulang/adversarial.
    grams = [set(zip(t.split(), t.split()[1:])) for t in texts]
    for i, r in enumerate(reports):
        text = texts[i]
        if len(text) < 40:
            continue
        for j in range(i+1, len(reports)):
            s = reports[j]
            loc1, loc2 = normal(r.get("location_text")), normal(s.get("location_text"))
            different = bool(loc1 and loc2 and loc1 != loc2)
            try:
                different = different or haversine(r.get("latitude"), r.get("longitude"), s.get("latitude"), s.get("longitude")) > 1
            except ValueError:
                pass
            union = grams[i] | grams[j]
            similarity = 1.0 if text == texts[j] else len(grams[i] & grams[j]) / len(union) if union else 0
            if different and len(texts[j]) >= 40 and similarity >= .9:
                add("laporan_mirip", [r["name"], s["name"]], "Teks sangat mirip di lokasi berbeda; perlu dicek (bisa laporan ulang).", kemiripan=round(similarity, 3))
    return out
