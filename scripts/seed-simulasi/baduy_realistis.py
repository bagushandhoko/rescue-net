"""Perbarui program Baduy pada site uji terisolasi. Lihat baduy_realistis/README.md."""
import base64
import json
import os
import re
from pathlib import Path
from runpy import run_path

import frappe
from rescue_net import api_donor_program as dp
from rescue_net.donor_program import plan
from rescue_net.services.money import lock

PROGRAM_TYPE = "RN Donor Program"
UPDATE_TYPE = "RN Donor Program Update"
LEGACY = re.compile(
    r"^(?:(?:sampul|kondisi|rumah-jadi|denah|rab|koran|qris)-sim-baduy|progres-.*-sim-baduy)"
)
DOCUMENTS = [
    ("rab", "baduy-rab.pdf", "RAB lengkap · 21 rumah panggung dan 2 leuit"),
    ("rab", "baduy-rab-1.png", "RAB halaman 1/2 · Biaya satu rumah adat"),
    ("rab", "baduy-rab-2.png", "RAB halaman 2/2 · Leuit dan rekapitulasi"),
    ("gambar", "baduy-gk01.png", "GK-01 · Denah tapak kampung (simulasi)"),
    ("gambar", "baduy-gk02.png", "GK-02 · Tampak dan potongan rumah (simulasi)"),
    ("qris", "baduy-qris.png", "QRIS contoh · Jangan transfer"),
    ("koran", "baduy-koran.pdf", "Rekening koran contoh · 22 November–12 Desember 2026"),
]


def legacy_file(value):
    return bool(LEGACY.match(str(value or "").rsplit("/", 1)[-1]))


def reconcile(program, received, spent, pending):
    donations = frappe.get_all(
        "RN Cash Donation", filters={"donor_program": program}, fields=["status", "amount"],
    )
    updates = frappe.get_all(UPDATE_TYPE, filters={"program": program}, pluck="amount_spent")
    status_amounts = {
        status: sorted(int(d.amount) for d in donations if d.status == status)
        for status in ("received", "pending")
    }
    if (status_amounts["received"] != sorted(received)
            or status_amounts["pending"] != sorted(pending)
            or sum(updates) != spent
            or tuple(frappe.db.get_value(PROGRAM_TYPE, program, ["budget_received", "budget_spent"]))
            != (sum(received), spent)):
        raise RuntimeError("Donasi atau belanja berbeda dari skenario rekening koran. Transaksi dibatalkan.")


def seed():
    site = str(frappe.local.site or "")
    # Ming Ming 24 Nov: produksi hanya dengan RN_BADUY_PROD=1 (moderator, setelah backup DB)
    prod_ok = os.environ.get("RN_BADUY_PROD") == "1" and site == "osiun.localhost"
    if (site != os.environ.get("RN_BADUY_SITE") or not (prod_ok or site == "rescuenet-test.localhost" or site.startswith(("test-", "test.")))):
        raise RuntimeError("RN_BADUY_SITE harus sama dengan nama site uji (rescuenet-test.localhost atau awalan test-/test.)")
    assets = Path(os.environ.get("RN_BADUY_ASSETS", "/tmp/baduy-realistis")).resolve()
    data = run_path(str(assets / "baduy_data.py"))
    program = data["PROGRAM"]
    previous_user = frappe.session.user
    try:
        lock(PROGRAM_TYPE, program)
        row = frappe.get_doc(PROGRAM_TYPE, program)
        if (row.disaster_event != data["EVENT"] or row.owner_id != data["ORG"]
                or row.owner_type != "organization"
                or row.program_name != "[SIMULASI] Bangun Kembali 21 Rumah Warga Baduy Luar"):
            raise RuntimeError("Identitas program Baduy tidak cocok.")
        if data["MARKER"] in (row.notes or "").splitlines():
            frappe.db.rollback()
            print(f"{program} sudah diisi.")
            return
        opening = [v for _, _, v in data["OPENING"] if v > 0]
        pending = [data["OPENING_PENDING"]]
        reconcile(program, opening, data["OPENING_SPENT"], pending)
        files = {name: base64.b64encode((assets / name).read_bytes()).decode("ascii")
                 for _, name, _ in DOCUMENTS}

        frappe.set_user(data["PIC"])
        update_info(row, data)
        seed_plan(program)
        seed_transactions(program, data)
        reconcile(
            program,
            opening + [d[2] for d in data["DONATIONS"] if d[4]],
            data["SPENT"],
            pending + [d[2] for d in data["DONATIONS"] if not d[4]],
        )
        for kind, name, label in DOCUMENTS:
            dp.upload_program_file(program, kind, name, files[name], label=label, redacted=int(kind == "koran"))
        frappe.db.set_value(PROGRAM_TYPE, program, "notes", "\n".join(filter(None, (row.notes, data["MARKER"]))))
        frappe.db.commit()
        print(f"{program} · target {data['TOTAL']} · masuk {data['RECEIVED']} · terpakai {data['SPENT']}")
    except Exception:
        frappe.db.rollback()
        raise
    finally:
        frappe.set_user(previous_user)


def update_info(row, data):
    program = row.name
    dp.update_program_info(program, {
        "description": "[SIMULASI] Pemulihan 21 keluarga dengan pembangunan 21 rumah panggung dan dua leuit. "
                       "Bahan diangkut dengan dipikul. Sambungan memakai pasak dan pengikat. "
                       "Tapak simulasi mengikuti kontur dengan jarak bersih antartepi atap minimal 6 m.",
        "target_description": "21 rumah panggung layak huni dan 2 leuit siap pakai setelah pemeriksaan.",
        "location": data["LOCATION"], "target_beneficiaries": "21 KK (sekitar 84 jiwa)",
        "start_date": "2026-11-23", "end_date": "2027-02-28",
        "budget_target": data["TOTAL"], "target_amount": 23,
        "officer_in_charge_name": data["COORDINATOR"], "contact_person": data["COORDINATOR"],
        "contact_phone": None, "officer_in_charge_phone": None,
    })
    fields = {"target_location": data["LOCATION"]}
    if legacy_file(row.cover_image_url):
        fields["cover_image_url"] = None
    frappe.db.set_value(PROGRAM_TYPE, program, fields)
    for entry in json.loads(row.work_drawings or "[]"):
        if legacy_file(entry.get("name")) or legacy_file(entry.get("url")):
            dp.remove_program_file(program, entry.get("kind") or "gambar", entry["url"])
    rab = frappe.db.get_value(PROGRAM_TYPE, program, "rab_file_url")
    if legacy_file(rab):
        dp.remove_program_file(program, "rab", rab)
    dp.set_program_bank(program, bank_name="Bank Simulasi", account_number=data["ACCOUNT"],
                        account_holder=data["HOLDER"])
    plan.set_output_verification(program, status="dalam_proses", output_target=23, output_verified=0,
                                 verifier="[SIM] Tim pemeriksa adat dan warga", estimated_done="2027-02-28")


def save_item(program, kind, doctype, key, old, values):
    filters = {"program": program, key: ["in", [old, values[key]]]}
    name = frappe.db.get_value(doctype, filters, "name")
    return plan.save_plan_item(program, kind, name=name, values=values)["name"]


def seed_plan(program):
    milestones = [
        ("Asesmen kerusakan & musyawarah dengan lembaga adat", "Asesmen dan musyawarah tata letak",
         "2026-11-24", "selesai", 100),
        ("Pengadaan bahan adat (kayu, bambu, kiray, ijuk, rotan)", "Pengadaan bahan adat bertahap",
         "2026-12-18", "berjalan", 60),
        ("Pembangunan tahap 1: rumah R1-R7", "Tahap 1 · Rumah R01–R07",
         "2026-12-20", "berjalan", 75),
        ("Pembangunan tahap 2: rumah R8-R14", "Tahap 2 · Rumah R08–R14",
         "2027-01-15", "berjalan", 15),
        ("Pembangunan tahap 3: rumah R15-R21 + 2 lumbung", "Tahap 3 · Rumah R15–R21 dan dua leuit",
         "2027-02-10", "belum_mulai", 0),
        ("Serah terima & syukuran adat", "Pemeriksaan dan serah terima",
         "2027-02-28", "belum_mulai", 0),
    ]
    for i, (old, title, due, status, percent) in enumerate(milestones, 1):
        name = save_item(program, "milestone", "RN Program Milestone", "title", old, {
            "title": title, "sort_order": i, "due_date": due, "milestone_status": status,
            "progress_percent": percent,
        })
        frappe.db.set_value("RN Program Milestone", name, "completed_at", due if status == "selesai" else None)
    locations = [
        ("Klaster A (R1-R8)", "[SIM] Cihulu · Acuan tapak 21 rumah", -6.6017207, 106.2259689, "belum_terlayani"),
        ("Klaster B (R9-R16)", "[SIM] Ciboleger · Titik bongkar bahan", -6.5939378, 106.2257927, "terlayani"),
        ("Klaster C (R17-R21) + 2 lumbung", "[SIM] Kadujangkung · Titik koordinasi tukang",
         -6.5994270, 106.2318975, "terlayani"),
    ]
    for old, title, lat, lon, status in locations:
        name = save_item(program, "location", "RN Program Location", "title", old, {
            "title": title, "latitude": lat, "longitude": lon, "location_status": status,
        })
        frappe.db.set_value("RN Program Location", name, "served_at",
                            "2026-11-24" if status == "terlayani" else None)
    needs = [
        ("Kayu tiang & balok", "Kayu tiang, balok dan gelagar", "material", 630, 315, "batang", "2026-12-20"),
        ("Bambu", "Bambu rangka atap dan dinding", "material", 1155, 560, "batang", "2026-12-20"),
        ("Daun kiray / ijuk (ikat)", "Panel penutup atap kiray", "material", 1596, 300, "m²", "2027-01-15"),
        ("Tali rotan", "Rotan atau serat pengikat", "material", 210, 80, "gulung", "2026-12-20"),
        ("Tukang adat", "Tukang adat", "relawan", 21, 9, "orang", "2026-12-20"),
        ("Relawan gotong royong", "Relawan angkut pikul", "relawan", 60, 34, "orang", "2026-12-20"),
        ("Bubungan ijuk", "Bubungan ijuk", "material", 168, 32, "m", "2027-01-15"),
    ]
    for old, title, kind, needed, available, unit, due in needs:
        save_item(program, "need", "RN Program Need", "item", old, {
            "item": title, "kind": kind, "qty_needed": needed, "qty_available": available,
            "unit": unit, "needed_by": due,
        })


def seed_transactions(program, data):
    old_notes = {
        "Asesmen selesai, warga & lembaga adat sepakat tata letak baru":
            "Asesmen simulasi dan musyawarah tata letak. Peta tapak menggambarkan jarak bersih minimal 6 m.",
        "Belanja bambu & kayu tahap 1":
            "Belanja awal Rp1.200.000 untuk sebagian kayu dan bambu. Pengadaan lanjutan dicatat terpisah.",
        "Rangka R1-R4 berdiri, atap R1 mulai dipasang":
            "Kemajuan tahap awal R01–R04. Angka kabar lama diperbarui agar sebanding dengan progres program.",
    }
    for title, note in old_notes.items():
        existing = frappe.db.get_value(UPDATE_TYPE, {"program": program, "update_title": title}, "name")
        if existing:
            frappe.db.set_value(UPDATE_TYPE, existing, {
                "update_notes": note, "officer_in_charge_name": data["COORDINATOR"],
                "progress_percent": 20 if title.startswith("Rangka") else 10,
            })
    for timestamp, donor, amount, anonymous, confirmed in data["DONATIONS"]:
        donation = frappe.get_doc({
            "doctype": "RN Cash Donation", "disaster_event": data["EVENT"], "donor_program": program,
            "amount": amount, "currency": "IDR", "is_anonymous": anonymous,
            "donor_name": donor or "[SIM] Anonim", "message": data["MARKER"], "status": "pending",
        }).insert(ignore_permissions=True)
        fields = {"creation": timestamp}
        if confirmed:
            dp.decide_cash_donation(donation.name, "confirm")
            fields["confirmed_at"] = timestamp
        frappe.db.set_value(donation.doctype, donation.name, fields, update_modified=False)
    for timestamp, title, percent, spent, note in data["UPDATES"]:
        result = dp.create_special_program_update(
            program, "[SIM] " + title, update_type="spending" if spent else "progress",
            progress_percent=percent, amount_spent=spent, update_notes=note,
            officer_in_charge_name=data["COORDINATOR"],
        )
        frappe.db.set_value(UPDATE_TYPE, result["update"],
                            {"creation": timestamp, "observed_at": timestamp}, update_modified=False)


seed()
