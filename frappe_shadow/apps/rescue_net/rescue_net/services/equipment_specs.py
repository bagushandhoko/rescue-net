"""Spesifikasi alat per kategori (owner 2026-11-03: "posko alat kerja/support semacam logistik tapi lebih ke
data lebih detail secara speks: dari alat berat, tenda, perahu karet, genset dll").

One catalog drives the forms (posko alat kerja, tawarkan alat) and the detail pages. Specs are stored as a JSON
object in RN Resource Profile.specs ({key: value}); clean_specs() keeps only the keys of the chosen category,
numbers as numbers, text trimmed. Category keys reuse services.tool_needs where they exist (ekskavator, genset,
pompa_air, perahu_karet, ...), so the field-condition estimates and the boards keep matching.
"""

import json

import frappe

FUEL = ["solar", "bensin", "campur (2 tak)", "listrik / baterai", "tanpa BBM"]

# shared spec blocks
_ENGINE = [("engine_power_hp", "Daya mesin", "number", "HP"), ("fuel_type", "Jenis BBM", "select", FUEL),
           ("fuel_use_lph", "Konsumsi BBM", "number", "liter/jam")]
_HEAVY = [("operating_weight_t", "Berat operasi", "number", "ton"), *_ENGINE,
          ("transport_need", "Kebutuhan angkut", "select", ["lowbed / trailer", "jalan sendiri", "truk biasa"]),
          ("attachments", "Attachment tersedia", "text", "mis. breaker, ripper, grapple")]

CATALOG = {
    # --- Alat berat
    "ekskavator": ("Ekskavator", "Alat Berat", "unit", [
        ("bucket_m3", "Kapasitas bucket", "number", "m³"), ("dig_depth_m", "Kedalaman gali maks", "number", "m"),
        ("track", "Penggerak", "select", ["crawler (rantai)", "wheel (roda)", "mini / amphibi"]), *_HEAVY]),
    "buldoser": ("Buldoser", "Alat Berat", "unit", [
        ("blade_width_m", "Lebar blade", "number", "m"), ("blade_type", "Tipe blade", "text", "mis. straight, U, semi-U"),
        *_HEAVY]),
    "wheel_loader": ("Wheel Loader", "Alat Berat", "unit", [
        ("bucket_m3", "Kapasitas bucket", "number", "m³"), *_HEAVY]),
    "dump_truck": ("Dump Truck", "Alat Berat", "unit", [
        ("payload_t", "Muatan maks", "number", "ton"), ("bed_m3", "Volume bak", "number", "m³"),
        ("plate", "Nomor polisi", "text", ""), *_ENGINE]),
    "crane": ("Crane", "Alat Berat", "unit", [
        ("lift_capacity_t", "Kapasitas angkat", "number", "ton"), ("boom_length_m", "Panjang boom", "number", "m"),
        ("crane_type", "Tipe", "select", ["mobile crane", "truck crane", "crawler crane", "lorry loader"]), *_HEAVY]),
    "forklift": ("Forklift", "Alat Berat", "unit", [
        ("lift_capacity_t", "Kapasitas angkat", "number", "ton"), ("lift_height_m", "Tinggi angkat", "number", "m"),
        *_ENGINE]),
    # --- Shelter & tenda
    "tenda": ("Tenda", "Shelter & Tenda", "unit", [
        ("tent_type", "Tipe tenda", "select", ["peleton", "regu", "keluarga", "pengungsi (UNHCR)", "dome", "posko / komando",
                                                "kesehatan / medis", "gudang"]),
        ("length_m", "Panjang", "number", "m"), ("width_m", "Lebar", "number", "m"),
        ("capacity_people", "Kapasitas orang", "number", "orang"), ("material", "Bahan", "text", "mis. terpal PVC, kanvas"),
        ("weight_kg", "Berat per unit", "number", "kg"),
        ("includes", "Kelengkapan", "text", "mis. tiang, pasak, alas, jendela kasa"),
        ("setup_people", "Orang untuk memasang", "number", "orang"), ("setup_minutes", "Waktu pasang", "number", "menit")]),
    # --- Air & SAR
    "perahu_karet": ("Perahu Karet", "Air & SAR", "unit", [
        ("length_m", "Panjang", "number", "m"), ("capacity_people", "Kapasitas orang", "number", "orang"),
        ("max_load_kg", "Muatan maks", "number", "kg"),
        ("engine", "Mesin tempel", "text", "mis. Yamaha 15 PK / tanpa mesin"), ("fuel_type", "Jenis BBM", "select", FUEL),
        ("life_jackets", "Pelampung tersedia", "number", "buah"), ("paddles", "Dayung", "number", "buah")]),
    "perahu_fiber": ("Perahu Fiber / LCR", "Air & SAR", "unit", [
        ("length_m", "Panjang", "number", "m"), ("capacity_people", "Kapasitas orang", "number", "orang"),
        ("max_load_kg", "Muatan maks", "number", "kg"), ("engine", "Mesin", "text", ""),
        ("fuel_type", "Jenis BBM", "select", FUEL)]),
    "alat_sar": ("Peralatan SAR", "Air & SAR", "set", [
        ("sar_type", "Jenis", "text", "mis. hydraulic cutter, airbag, tandu, tali rescue"),
        ("capacity", "Kapasitas / ukuran", "text", ""), ("power", "Sumber tenaga", "text", "")]),
    # --- Listrik & penerangan
    "genset": ("Genset", "Listrik & Penerangan", "unit", [
        ("power_kva", "Kapasitas", "number", "kVA"), ("phase", "Fase", "select", ["1 fase", "3 fase"]),
        ("voltage", "Tegangan", "text", "mis. 220 V / 380 V"), ("fuel_type", "Jenis BBM", "select", FUEL),
        ("fuel_use_lph", "Konsumsi BBM", "number", "liter/jam"), ("tank_l", "Kapasitas tangki", "number", "liter"),
        ("runtime_h", "Lama nyala per tangki", "number", "jam"),
        ("form", "Bentuk", "select", ["portable", "silent / kanopi", "open frame", "trailer"]),
        ("weight_kg", "Berat", "number", "kg")]),
    "light_tower": ("Lampu Sorot / Light Tower", "Listrik & Penerangan", "unit", [
        ("lamp_w", "Daya lampu total", "number", "watt"), ("mast_m", "Tinggi tiang", "number", "m"),
        ("fuel_type", "Jenis BBM", "select", FUEL), ("runtime_h", "Lama nyala per tangki", "number", "jam")]),
    # --- Air bersih & sanitasi
    "pompa_air": ("Pompa Air", "Air Bersih & Sanitasi", "unit", [
        ("flow_lpm", "Debit", "number", "liter/menit"), ("head_m", "Head (tinggi dorong)", "number", "m"),
        ("hose_inch", "Diameter selang", "number", "inch"),
        ("pump_type", "Tipe", "select", ["pompa celup", "pompa alkon / engine", "pompa lumpur", "pompa listrik"]),
        ("fuel_type", "Jenis BBM", "select", FUEL), ("fuel_use_lph", "Konsumsi BBM", "number", "liter/jam")]),
    "tangki_air": ("Tangki / Truk Air", "Air Bersih & Sanitasi", "unit", [
        ("volume_l", "Kapasitas", "number", "liter"), ("mobile", "Jenis", "select", ["truk tangki", "tandon / tangki tetap",
                                                                                       "bladder / tangki lipat"]),
        ("plate", "Nomor polisi (truk)", "text", "")]),
    "water_purifier": ("Penjernih Air", "Air Bersih & Sanitasi", "unit", [
        ("output_lph", "Kapasitas olah", "number", "liter/jam"), ("method", "Metode", "text", "mis. RO, UF, klorinasi"),
        ("power", "Sumber tenaga", "text", "")]),
    "toilet_portabel": ("Toilet Portabel / MCK", "Air Bersih & Sanitasi", "unit", [
        ("rooms", "Jumlah bilik", "number", "bilik"), ("tank_l", "Tangki limbah", "number", "liter"),
        ("needs_water", "Butuh air bersih", "select", ["ya", "tidak"])]),
    # --- Kendaraan
    "truk": ("Truk Angkut", "Kendaraan", "unit", [
        ("payload_t", "Muatan maks", "number", "ton"), ("box", "Bak", "select", ["bak terbuka", "box tertutup", "wing box",
                                                                                  "flatbed"]),
        ("plate", "Nomor polisi", "text", ""), ("four_wd", "Gardan", "select", ["4x2", "4x4", "6x4"]), *_ENGINE]),
    "kendaraan_4x4": ("Kendaraan 4x4 / Double Cabin", "Kendaraan", "unit", [
        ("seats", "Kursi", "number", "orang"), ("payload_kg", "Muatan", "number", "kg"), ("plate", "Nomor polisi", "text", ""),
        ("winch", "Winch", "select", ["ada", "tidak"]), ("fuel_type", "Jenis BBM", "select", FUEL)]),
    "ambulans": ("Ambulans", "Kendaraan", "unit", [
        ("ambulance_type", "Tipe", "select", ["transport", "gawat darurat (ALS/BLS)", "jenazah"]),
        ("plate", "Nomor polisi", "text", ""), ("equipment", "Perlengkapan", "text", "mis. oksigen, AED, tandu")]),
    "motor_trail": ("Motor Trail", "Kendaraan", "unit", [
        ("cc", "Mesin", "number", "cc"), ("plate", "Nomor polisi", "text", "")]),
    # --- Perkakas
    "chainsaw": ("Chainsaw", "Perkakas", "unit", [
        ("bar_inch", "Panjang bar", "number", "inch"), ("engine_cc", "Mesin", "number", "cc"),
        ("fuel_type", "Jenis BBM", "select", FUEL), ("spare_chain", "Rantai cadangan", "number", "buah")]),
    "alat_pertukangan": ("Alat Pertukangan", "Perkakas", "set", [
        ("tools", "Isi set", "text", "mis. palu, gergaji, bor, gerinda, meteran"),
        ("power", "Sumber tenaga", "select", ["manual", "listrik", "baterai", "BBM"])]),
    "jack_hammer": ("Jack Hammer / Breaker", "Perkakas", "unit", [
        ("impact", "Kekuatan / berat", "text", "mis. 30 kg"), ("power", "Sumber tenaga", "select", ["kompresor", "listrik", "BBM"])]),
    # --- Lainnya
    "kantong_jenazah": ("Kantong Jenazah", "Lainnya", "pcs", [
        ("size", "Ukuran", "select", ["dewasa", "anak"]), ("material", "Bahan", "text", "")]),
    "alat_berat_lain": ("Alat berat lain", "Alat Berat", "unit", [("tool_type", "Jenis alat", "text", ""), *_HEAVY]),
    "kendaraan_angkut": ("Kendaraan angkut lain", "Kendaraan", "unit", [
        ("payload_t", "Muatan maks", "number", "ton"), ("plate", "Nomor polisi", "text", "")]),
    "lainnya": ("Lainnya", "Lainnya", "unit", [("spec", "Spesifikasi", "text", "")]),
}

GROUP_ORDER = ["Alat Berat", "Shelter & Tenda", "Air & SAR", "Listrik & Penerangan", "Air Bersih & Sanitasi", "Kendaraan",
               "Perkakas", "Lainnya"]

CONDITIONS = {"baik": "Baik / siap pakai", "perlu_servis": "Perlu servis", "rusak_ringan": "Rusak ringan",
              "rusak_berat": "Rusak berat"}


def labels():
    return {k: v[0] for k, v in CATALOG.items()}


def catalog():
    """For the forms: [{group, categories: [{value, label, unit, fields: [{key, label, type, unit|options}]}]}]."""
    groups = {g: [] for g in GROUP_ORDER}
    for key, (label, group, unit, fields) in CATALOG.items():
        groups.setdefault(group, []).append({
            "value": key, "label": label, "unit": unit,
            "fields": [{"key": f[0], "label": f[1], "type": f[2],
                        **({"options": f[3]} if f[2] == "select" else {"unit": f[3]} if f[2] == "number" else
                           {"placeholder": f[3]})} for f in fields],
        })
    return [{"group": g, "categories": groups[g]} for g in groups if groups[g]]


def clean_specs(category, specs):
    """Keep the category's keys only; numbers ≥ 0; select values from the list; text ≤ 300 chars."""
    if specs in (None, ""):
        return None
    if isinstance(specs, str):
        try:
            specs = json.loads(specs)
        except ValueError:
            frappe.throw("Spesifikasi alat tidak valid.")
    if not isinstance(specs, dict):
        frappe.throw("Spesifikasi alat tidak valid.")
    fields = {f[0]: f for f in CATALOG.get(category, CATALOG["lainnya"])[3]}
    out = {}
    for k, v in specs.items():
        f = fields.get(k)
        if not f or v in (None, ""):
            continue
        if f[2] == "number":
            try:
                n = float(v)
            except (TypeError, ValueError):
                frappe.throw(f"{f[1]} harus angka.")
            if n < 0 or n > 1e9:
                frappe.throw(f"{f[1]} tidak boleh negatif.")
            out[k] = int(n) if n == int(n) else n
        elif f[2] == "select":
            if v not in f[3]:
                frappe.throw(f"Pilihan '{f[1]}' tidak dikenal.")
            out[k] = v
        else:
            out[k] = str(v).strip()[:300]
    return json.dumps(out, ensure_ascii=False) if out else None


def spec_rows(category, raw):
    """[{label, value}] in catalog order, numbers with their unit — for detail pages."""
    try:
        specs = json.loads(raw or "{}")
    except ValueError:
        return []
    out = []
    for f in CATALOG.get(category, CATALOG["lainnya"])[3]:
        v = specs.get(f[0]) if isinstance(specs, dict) else None
        if v in (None, ""):
            continue
        if f[2] == "number":
            out.append({"label": f[1], "value": f"{v:g} {f[3]}".strip() if isinstance(v, (int, float)) else str(v)})
        else:
            out.append({"label": f[1], "value": str(v)})
    return out
