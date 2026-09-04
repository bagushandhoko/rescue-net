import frappe
from frappe.utils import now_datetime

# Seed data for the Rehabilitation "Perencanaan Pengungsi" module
# (RN Displacement Plan) + "Masukan Masyarakat" forum (RN Community Feedback).
# Idempotent: skip if a row with the same natural key already exists.
# Simulation content only ([SIMULASI] disaster events).

EVENT = "event-sim-001"


def _resolved_event():
    for cand in (EVENT, "disaster_events:" + EVENT):
        if frappe.db.exists("RN Disaster Event", cand):
            return cand
    try:
        from rescue_net.reference_resolver import resolve_disaster_event
        r = resolve_disaster_event(EVENT)
        if r and frappe.db.exists("RN Disaster Event", r):
            return r
    except Exception:
        pass
    return None

PLANS = [
    {"household_code": "KK-SMT-001", "origin_area": "Desa Suak Ribee, Johan Pahlawan",
     "current_location": "Shelter Samatiga", "in_camp": 1, "people_count": 5,
     "vulnerable_count": 2, "health_status": "mixed", "plan_type": "return_home",
     "est_return_cost": 1500000, "est_rebuild_support": 7500000,
     "support_needed": "Perbaikan atap rumah, akses air bersih desa", "status": "proposed"},
    {"household_code": "KK-SMT-002", "origin_area": "Dusun Pasi, Arongan Lambalek",
     "current_location": "Numpang di rumah kerabat", "in_camp": 0, "people_count": 4,
     "vulnerable_count": 1, "health_status": "healthy", "plan_type": "relocate",
     "est_return_cost": 0, "est_rebuild_support": 20000000,
     "support_needed": "Lahan relokasi, rumah tumbuh, modal usaha (nelayan)", "status": "proposed"},
    {"household_code": "KK-SMT-003", "origin_area": "Gampong Rundeng",
     "current_location": "Shelter Samatiga", "in_camp": 1, "people_count": 3,
     "vulnerable_count": 3, "health_status": "orphan", "plan_type": "undecided",
     "est_return_cost": 500000, "est_rebuild_support": 12000000,
     "support_needed": "Pendampingan psikososial, biaya sekolah 2 anak, wali", "status": "draft"},
    {"household_code": "KK-SMT-004", "origin_area": "Desa Cot Seulamat",
     "current_location": "Tenda mandiri pinggir jalan", "in_camp": 0, "people_count": 6,
     "vulnerable_count": 2, "health_status": "needs_care", "plan_type": "return_home",
     "est_return_cost": 2000000, "est_rebuild_support": 9000000,
     "support_needed": "Rujukan medis lansia, perbaikan jembatan akses desa", "status": "approved"},
]

FEEDBACK = [
    {"topic": "Distribusi air bersih belum merata di RW 04",
     "category": "keluhan", "author_name": "Warga RW 04",
     "wilayah": "Johan Pahlawan, Aceh Barat",
     "body": "Sudah 2 hari tangki air tidak sampai ke RW 04. Mohon dijadwalkan.",
     "official_response": "Terima kasih. Armada tangki dijadwalkan ke RW 04 besok pagi lewat Posko Distribusi. Titik ambil di depan meunasah.",
     "responded_by": "Koordinator Logistik", "status": "noted"},
    {"topic": "Usul: dapur umum tambahan di sisi barat",
     "category": "usul", "author_name": "Pemuda Gampong",
     "wilayah": "Samatiga, Aceh Barat",
     "body": "Pengungsi di sisi barat jauh dari dapur umum. Usul buka satu titik masak lagi di sekolah SD 3.",
     "status": "open"},
    {"topic": "Kapan sekolah anak-anak mulai lagi?",
     "category": "pertanyaan", "author_name": "Orang tua murid",
     "body": "Anak-anak sudah 10 hari tidak sekolah. Ada rencana sekolah darurat?",
     "status": "open"},
]


def _mk_plan(cfg):
    if frappe.db.exists("RN Displacement Plan",
                        {"household_code": cfg["household_code"]}):
        return "skip"
    doc = frappe.new_doc("RN Displacement Plan")
    ev = _resolved_event()
    if ev:
        doc.disaster_event = ev
    else:
        doc.disaster_event_legacy_id = EVENT
    for k, v in cfg.items():
        doc.set(k, v)
    doc.title = cfg["household_code"] + " · " + cfg["plan_type"]
    doc.insert(ignore_permissions=True)
    return doc.name


def _mk_feedback(cfg):
    if frappe.db.exists("RN Community Feedback", {"topic": cfg["topic"]}):
        return "skip"
    doc = frappe.new_doc("RN Community Feedback")
    ev = _resolved_event()
    if ev:
        doc.disaster_event = ev
    else:
        doc.disaster_event_legacy_id = EVENT
    for k, v in cfg.items():
        doc.set(k, v)
    if cfg.get("official_response"):
        doc.responded_at = now_datetime()
    doc.insert(ignore_permissions=True)
    return doc.name


def install_defaults():
    made = skipped = 0
    if frappe.db.exists("DocType", "RN Displacement Plan"):
        for c in PLANS:
            r = _mk_plan(c)
            made += 1 if r not in ("skip", None) else 0
            skipped += 1 if r == "skip" else 0
    if frappe.db.exists("DocType", "RN Community Feedback"):
        for c in FEEDBACK:
            r = _mk_feedback(c)
            made += 1 if r not in ("skip", None) else 0
            skipped += 1 if r == "skip" else 0
    frappe.db.commit()
    print(f"[rehab_forum_defaults] created {made}, skipped {skipped}")
    return {"created": made, "skipped": skipped}
