"""Lengkapi PROFIL posko SIMULASI (owner 24 Nov 2026: "lengkapi data simulasi di semua hal supaya kelihatan
kurang-kurangnya"). Hanya posko di event simulasi (drill.simulation_event_names); hanya mengisi kolom yang KOSONG
(aman diulang). Disimpan lewat doc.save() supaya validasi asli ikut teruji; galat dicatat sebagai temuan.
Jalankan di bench console: exec(open(path).read(), {"__name__": "rn"})."""
import math, random
import frappe
from frappe.utils import now_datetime, add_days, getdate
from rescue_net.services import drill

rnd = random.Random(20261124)
SIMS = list(drill.simulation_event_names())
found, changed = [], {}

FN = {  # posko_type -> (logistik, shelter, dapur, peran logistik)
    "logistics": (1, 0, 0, "collector"), "collection_hub": (1, 0, 0, "collector"), "transport": (1, 0, 0, "collector"),
    "shelter": (1, 1, 0, "receiver"), "kitchen": (1, 0, 1, "receiver"), "medical": (1, 0, 0, "receiver"),
    "field_assessment": (0, 0, 0, ""), "volunteer": (0, 0, 0, ""), "sar": (0, 0, 0, ""),
    "org_admin": (0, 0, 0, ""), "posko_operator": (1, 0, 0, "receiver"),
}
FAC = {
    "logistics": "Gudang 200 m2, 2 truk 4 t, forklift manual, genset 10 kVA, timbangan",
    "collection_hub": "Titik kumpul donasi, gudang 120 m2, meja registrasi, CCTV",
    "transport": "2 truk, 1 pikap, area parkir, pos BBM cadangan 200 L",
    "shelter": "Tenda pleton 6 unit, 12 MCK portabel, air bersih 5.000 L, ruang laktasi, pos ramah anak",
    "kitchen": "Dapur umum 4 tungku, kapasitas 1.500 porsi/hari, gudang bahan, air bersih",
    "medical": "Tenda medis 2 unit, 6 tempat tidur lipat, kulkas vaksin, ambulans 1 unit",
    "field_assessment": "Tim kaji cepat 6 orang, drone, motor trail 2 unit",
    "volunteer": "Ruang briefing, tenda istirahat relawan, dapur relawan",
    "sar": "Perahu karet 2 unit, alat ekstrikasi, tandu, radio HT 10 unit",
    "org_admin": "Ruang rapat, internet satelit, printer, genset 5 kVA",
    "posko_operator": "Meja layanan, gudang kecil, genset 3 kVA",
}
BEN = {"shelter": (300, 1500, "jiwa mengungsi di posko"), "kitchen": (800, 3000, "porsi/hari untuk pengungsi sekitar"),
       "medical": (50, 300, "pasien dilayani per hari"), "logistics": (1000, 6000, "jiwa terlayani distribusi"),
       "collection_hub": (1000, 5000, "jiwa terlayani distribusi"), "posko_operator": (200, 900, "jiwa di wilayah layanan")}
RADIUS = {"shelter": 1500, "kitchen": 3000, "medical": 5000, "logistics": 15000, "collection_hub": 25000,
          "transport": 40000, "field_assessment": 10000, "sar": 10000, "volunteer": 5000, "org_admin": 30000,
          "posko_operator": 3000}

areas = frappe.get_all("RN Admin Area", filters={"center_lat": ["is", "set"], "level": "district"},
                       fields=["code", "area_name", "parent_code", "center_lat", "center_lng"], limit_page_length=0)
names = {a.code: a.area_name for a in frappe.get_all("RN Admin Area", filters={"level": ["in", ["city", "province"]]},
                                                       fields=["code", "area_name"], limit_page_length=0)}


def nearest(lat, lng):
    best, bd = None, 9e9
    for a in areas:
        d = (a.center_lat - lat) ** 2 + ((a.center_lng - lng) * math.cos(math.radians(lat))) ** 2
        if d < bd: best, bd = a, d
    return best if best and bd < 0.25 else None   # <~55 km


def empty(v):
    return v in (None, "", 0, "[]", "{}")


rows = frappe.get_all("RN Posko", filters={"disaster_event": ["in", SIMS]}, pluck="name")
for name in rows:
    doc = frappe.get_doc("RN Posko", name)
    t = doc.posko_type or "posko_operator"
    ev_start = frappe.db.get_value("RN Disaster Event", doc.disaster_event, "started_at")
    vals = {}
    def put(k, v):
        if doc.meta.has_field(k) and empty(doc.get(k)) and not empty(v): vals[k] = v
    lg, sh, kt, role = FN.get(t, (0, 0, 0, ""))
    put("rn_fn_logistics", lg); put("rn_fn_shelter", sh); put("rn_fn_kitchen", kt); put("rn_logistics_role", role)
    put("active_from", getdate(ev_start) if ev_start else add_days(getdate(), -14))
    put("facilities", FAC.get(t))
    if t in BEN:
        lo, hi, unit = BEN[t]; n = rnd.randrange(lo, hi, 10)
        put("rn_beneficiary_count", n); put("rn_beneficiary_note", "%s %s (SIMULASI)" % (format(n, ",").replace(",", "."), unit))
        put("rn_beneficiary_updated_at", now_datetime())
    put("coverage_radius_meters", RADIUS.get(t, 3000))
    put("officer_in_charge_role", "Koordinator Posko")
    if not empty(doc.officer_in_charge_phone):
        put("officer_in_charge_whatsapp", doc.officer_in_charge_phone); put("emergency_contact", doc.officer_in_charge_phone)
    put("rn_comms_status", rnd.choice(["connected", "connected", "connected", "weak", "disconnected"]))
    put("rn_comms_last_contact", now_datetime())
    put("comms_support_needed", "Radio HT 2 unit, baterai cadangan" if t in ("shelter", "medical", "field_assessment") else None)
    put("comms_support_offered", "Relay radio VHF, internet satelit (jam 06-22)" if t in ("org_admin", "logistics", "transport") else None)
    for k in ("public_participation", "accept_volunteers", "accept_donations", "accept_partners", "public_service_access"):
        put(k, 1)
    put("accept_goods", 1 if lg else 0)
    if lg or sh or kt:
        put("public_not_needed", "Pakaian bekas, mi instan berlebih, obat tanpa label (SIMULASI)")
        put("public_not_accepted_packaging", "Kemasan kaca, karung terbuka, makanan tanpa tanggal kedaluwarsa")
        put("public_notes_updated", now_datetime())
    put("notes", "Data contoh SIMULASI - bukan posko sungguhan.")
    if empty(doc.admin_area_id) and doc.latitude and doc.longitude:
        a = nearest(doc.latitude, doc.longitude)
        if a:
            city = a.parent_code; prov = city.split(".")[0]
            vals.update({"admin_area_id": a.code, "district_name": a.area_name, "city_name": names.get(city),
                         "province_name": names.get(prov), "area_level": "district"})
        else:
            found.append("%s: tidak ada kecamatan dalam 55 km dari titik %s,%s" % (name, doc.latitude, doc.longitude))
    if not vals: continue
    doc.update(vals); doc.flags.ignore_permissions = True
    try:
        doc.save(); frappe.db.commit(); changed[name] = sorted(vals)
    except Exception as e:
        frappe.db.rollback(); found.append("%s: save gagal %s: %s" % (name, type(e).__name__, str(e)[:200]))
frappe.db.commit()
print(); print("POSKO_DIUBAH", len(changed), "dari", len(rows))
from collections import Counter
print("KOLOM", dict(Counter(k for v in changed.values() for k in v)))
for f in found: print("TEMUAN", f)
