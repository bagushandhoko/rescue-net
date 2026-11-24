"""Isi modul SIMULASI yang masih kosong/tipis (owner 24 Nov 2026: "lengkapi data simulasi di semua hal supaya
kelihatan kurang-kurangnya"). Semua lewat API RN yang sama dengan layar, DIJALANKAN SEBAGAI akun demo masyarakat
(sekaligus menguji Simulasi Terbuka). Hanya event simulasi; idempoten (cek jumlah dulu). Galat = TEMUAN.
Jalankan di bench console: exec(open(path).read(), {"__name__": "rn"})."""
import random
import frappe
from frappe.utils import add_days, nowdate, now_datetime
from rescue_net.services import drill

rnd = random.Random(20261124)
SIMS = list(drill.simulation_event_names())
DEMO = frappe.db.get_value("RN User Account", {"frappe_user": ["like", "masyarakat.demo%"]}, "frappe_user")
done, found = {}, []


def step(label, fn, *a, **kw):
    try:
        r = fn(*a, **kw); frappe.db.commit(); done[label] = done.get(label, 0) + 1; return r
    except Exception as e:
        frappe.db.rollback(); found.append("%s: %s: %s" % (label, type(e).__name__, str(e)[:160])); return None


frappe.set_user(DEMO)
from rescue_net import api_shelter, api_aid_card, api_displacement, api_stock_expiry, api_recovery_support, api_medical

poskos = frappe.get_all("RN Posko", filters={"disaster_event": ["in", SIMS]},
                        fields=["name", "title", "posko_type", "rn_fn_shelter", "rn_fn_logistics", "disaster_event",
                                "district_name", "city_name"], limit_page_length=0)
shelters = [p for p in poskos if p.rn_fn_shelter or p.posko_type == "shelter"]

# 1) Shelter: keluarga (min 6), putaran distribusi, kartu keluarga, penerimaan bantuan
for p in shelters:
    have = frappe.db.count("RN Shelter Household", {"posko": p.name})
    for i in range(have, 6):
        m = rnd.randint(2, 7)
        step("keluarga", api_shelter.check_in_household, p.name, "SIM-KK-%s-%02d" % (p.name[-6:], i + 1), m,
             infants_count=rnd.randint(0, 1), children_count=rnd.randint(0, 3), elderly_count=rnd.randint(0, 1),
             pregnant_count=rnd.choice([0, 0, 0, 1]), disability_count=rnd.choice([0, 0, 0, 1]),
             notes="Keluarga contoh SIMULASI")
    if not frappe.db.exists("RN Distribution Round", {"posko": p.name}):
        step("putaran", api_aid_card.create_round, p.name, "Putaran 1 - Paket sembako & kebersihan",
             item_note="Beras 5 kg, minyak 1 L, sabun, pembalut, popok bayi (SIMULASI)")
    rnd_name = frappe.db.get_value("RN Distribution Round", {"posko": p.name, "round_status": "open"}, "name")
    hh = frappe.get_all("RN Shelter Household", filters={"posko": p.name, "household_status": "checked_in"}, pluck="name")
    for j, h in enumerate(hh):
        card = step("kartu", api_aid_card.issue_card, h)
        if card and rnd_name and j % 3 != 2 and not frappe.db.exists("RN Aid Receipt", {"round": rnd_name, "household": h}):
            r = step("penerimaan", api_aid_card.record_receipt, card["token"], rnd_name, items_note="Paket lengkap (SIMULASI)")
            if r and not r.get("ok"):
                found.append("penerimaan %s: state=%s" % (h, r.get("state")))

# 2) Rencana pengungsian per event simulasi yang punya shelter (min 4)
for ev in sorted({p.disaster_event for p in shelters}):
    have = frappe.db.count("RN Displacement Plan", {"disaster_event": ev})
    sh = [p for p in shelters if p.disaster_event == ev]
    for i in range(have, 4):
        p = sh[i % len(sh)]
        step("rencana_pengungsian", api_displacement.create_displacement_plan, ev, p.district_name or p.city_name or "Desa terdampak",
             rnd.randint(3, 8), household_code="SIM-KK-RP-%02d" % (i + 1), current_location=p.title, in_camp=1, posko=p.name,
             vulnerable_count=rnd.randint(0, 2), health_status=rnd.choice(["healthy", "needs_care", "mixed"]),
             plan_type=rnd.choice(["undecided", "return_home", "relocate"]), est_return_cost=rnd.randrange(2, 15) * 1_000_000,
             est_rebuild_support=rnd.randrange(10, 60) * 1_000_000, support_needed="Bahan bangunan, air bersih (SIMULASI)",
             notes="Rencana contoh SIMULASI")

# 3) Lot kedaluwarsa untuk stok yang ada di posko logistik simulasi
for p in [x for x in poskos if x.rn_fn_logistics]:
    if frappe.db.exists("RN Stock Batch", {"posko": p.name}):
        continue
    items = frappe.get_all("RN Stock Observation", filters={"posko": p.name, "quantity": [">", 0]},
                           fields=["item_name", "unit", "quantity"], order_by="observed_at desc", limit_page_length=4)
    for k, it in enumerate(items):
        if not (it.item_name and it.unit):
            continue
        days = [-3, 12, 45, 180][k % 4]   # satu sudah lewat, satu segera, dua aman -> peringatan terlihat
        step("lot_kedaluwarsa", api_stock_expiry.add_lot, p.name, it.item_name, it.unit, max(1, int(it.quantity // 2)),
             add_days(nowdate(), days), batch_no="SIM-LOT-%03d" % rnd.randint(1, 999))

# 4) Kebutuhan relawan pemulihan per proyek pemulihan simulasi (min 2)
for pr in frappe.get_all("RN Recovery Project", filters={"disaster_event": ["in", SIMS]}, pluck="name"):
    have = frappe.db.count("RN Recovery Volunteer Need", {"recovery_project": pr})
    roles = [("Tukang bangunan", 6), ("Relawan bersih-bersih", 15), ("Tenaga psikososial", 3)]
    for role, n in roles[have:2]:
        step("relawan_pemulihan", api_recovery_support.create_volunteer_need, pr, role, n,
             date_from=add_days(nowdate(), 2), date_to=add_days(nowdate(), 16), location="Lokasi proyek (SIMULASI)",
             task_description="Tugas contoh SIMULASI", requirements="Sehat, membawa APD sendiri",
             provisions="Makan 2x, transport lokal")

# 5) Kasus medis di posko medis simulasi (min 3 per posko)
CASES = [("Luka robek kaki", "moderate", "yellow", "dewasa"), ("Demam & batuk", "mild", "green", "anak"),
         ("Diare dehidrasi", "moderate", "yellow", "balita"), ("Patah tulang lengan", "severe", "red", "dewasa"),
         ("Hipertensi kontrol", "mild", "green", "lansia")]
AGE = {"dewasa": "adult", "anak": "child", "balita": "child", "lansia": "elderly"}
for p in [x for x in poskos if x.posko_type == "medical"]:
    have = frappe.db.count("RN Medical Case", {"posko": p.name})
    for i in range(have, 3):
        c = CASES[(i + len(p.name)) % len(CASES)]
        step("kasus_medis", api_medical.create_case, p.name, "SIM-PX-%s-%02d" % (p.name[-5:], i + 1), c[0] + " (SIMULASI)",
             age_group=AGE[c[3]], gender=rnd.choice(["male", "female"]), severity=c[1], triage_status=c[2],
             treatment_notes="Penanganan contoh SIMULASI")

frappe.set_user("Administrator")
print(); print("AKUN", DEMO); print("DIBUAT", done)
from collections import Counter
for f, n in Counter(found).most_common(): print("TEMUAN", n, "x", f)
