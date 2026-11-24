"""Seed untuk site uji terisolasi. Lihat ui_rekonstruksi/README.md."""
import base64
import json
import os
import sys
from pathlib import Path

import frappe
from rescue_net import api_donor_program as dp
from rescue_net.donor_program import plan
from rescue_net.services.money import lock


def seed():
    site = str(frappe.local.site)
    if (not site or site != os.environ.get("RN_UI_REK_TEST_SITE")
            or "rescue-net.online" in site.lower() or site == "192.168.100.3"):
        raise RuntimeError("Seed dibatalkan. RN_UI_REK_TEST_SITE harus persis nama site uji terisolasi.")
    assets = Path(os.environ.get("RN_UI_REK_ASSETS", "/tmp/ui-rekonstruksi")).resolve()
    sys.path.insert(0, str(assets))
    try:
        from rek_data import ACCOUNT, DONATIONS, EVENT, HOLDER, LOCATION, PIC, PROGRAM, TOTAL, UPDATES
        from gen_docs import rp, statement_html
    finally:
        sys.path.remove(str(assets))

    documents = [
        ("rab", "rek-rab.pdf", f"RAB lengkap 2 halaman · Rp {rp(TOTAL)} (simulasi)"),
        ("rab", "rek-rab-1.png", "RAB halaman 1/2 · Persiapan, struktur dan atap"),
        ("rab", "rek-rab-2.png", "RAB halaman 2/2 · Arsitektur, perabot dan rekap"),
        ("gambar", "rek-gk01.png", "GK-01 · Denah kelas dan perpustakaan (simulasi)"),
        ("gambar", "rek-gk02.png", "GK-02 · Tampak depan dan potongan A–A (simulasi)"),
        ("qris", "rek-qris.png", "QRIS contoh · Jangan transfer"),
        ("koran", "rek-koran.pdf", "Rekening koran simulasi · 4–24 November 2026"),
    ]
    content = {filename: (assets / filename).read_bytes() for _, filename, _ in documents}

    previous_user = frappe.session.user
    try:
        lock("RN Donor Program", PROGRAM)
        row = frappe.get_doc("RN Donor Program", PROGRAM)
        if row.disaster_event != EVENT or "Rekonstruksi Fasilitas Belajar" not in row.program_name:
            raise RuntimeError("Program atau event simulasi tidak cocok.")
        marker = "SIM/UIP/REB/02"
        if marker in (row.notes or "").splitlines():
            print(f"{PROGRAM} sudah diisi. Tidak ada perubahan.")
            frappe.db.rollback()
            return

        frappe.set_user(PIC)
        dp.update_program_info(PROGRAM, {
            "description": ("[SIMULASI] Gempa di Aceh Barat merusak berat dua ruang kelas dan perpustakaan "
                            "SD Tunas Pesisir (fiktif). Rehabilitasi memakai fondasi yang dinilai masih layak, "
                            "perkuatan rangka beton bertulang, penggantian atap dan dinding, serta pemulihan listrik, "
                            "akses dan perabot. Siswa belajar bergiliran di blok aman. Ruang hasil rehabilitasi "
                            "dibuka setelah pemeriksaan dan serah terima."),
            "target_description": "Dua kelas 7 × 8 m dan satu perpustakaan 7 × 8 m siap pakai setelah uji kelayakan.",
            "location": LOCATION, "target_beneficiaries": "64 siswa dan 6 guru (simulasi)",
            "start_date": "2026-11-04", "end_date": "2027-01-29",
            "budget_target": TOTAL, "target_amount": 3,
            "officer_in_charge_name": "[SIM] Koordinator UI Peduli",
            "contact_person": "[SIM] Sekretariat UI Peduli",
        })
        fields = {
            "target_location": LOCATION,
            "partners": "[SIM] Komite SD Tunas Pesisir, Tim Teknik Sipil, BPBD Aceh Barat",
            "notes": "\n".join(filter(None, (row.notes, marker))),
        }
        if (row.cover_image_url or "").rsplit("/", 1)[-1].startswith("sampul-sim-7a9c62"):
            fields["cover_image_url"] = None
        frappe.db.set_value("RN Donor Program", PROGRAM, fields)
        plan.set_output_verification(PROGRAM, status="dalam_proses", output_target=3, output_verified=0,
                                     verifier="[SIM] Tim pemeriksa teknis", estimated_done="2027-01-29")
        dp.set_program_bank(PROGRAM, bank_name="Bank Simulasi", account_number=ACCOUNT,
                            account_holder=HOLDER)

        placeholders = {
            "rab-sim-7a9c62.pdf", "gambar-sim-7a9c62-1.png", "gambar-sim-7a9c62-2.png",
            "koran-sim-7a9c62.pdf",
        }
        # Ming Ming 24 Nov: nama di DB berakhiran acak (mis. gambar-sim-7a9c62-1dd7c68.png) -> cocokkan awalan
        prefixes = ("rab-sim-7a9c62", "gambar-sim-7a9c62", "koran-sim-7a9c62")
        for entry in json.loads(row.work_drawings or "[]"):
            if entry.get("name") in placeholders or str(entry.get("name") or "").startswith(prefixes):
                dp.remove_program_file(PROGRAM, entry.get("kind") or "gambar", entry["url"])
        if (row.rab_file_url or "").rsplit("/", 1)[-1].startswith("rab-sim-7a9c62"):
            current = frappe.db.get_value("RN Donor Program", PROGRAM, "rab_file_url")
            if current == row.rab_file_url:
                dp.remove_program_file(PROGRAM, "rab", current)

        opening_received = int(row.budget_received or 0)
        opening_spent = int(row.budget_spent or 0)
        if opening_received or opening_spent:
            from frappe.utils.pdf import get_pdf

            content["rek-koran.pdf"] = get_pdf(
                statement_html(opening_received, opening_spent), {"page-size": "A4"})
        for kind, filename, label in documents:
            dp.upload_program_file(PROGRAM, kind, filename, base64.b64encode(content[filename]).decode("ascii"),
                                   label=label, redacted=int(kind == "koran"))

        seed_plan(PROGRAM)
        # Simpan kabar generik dari seed lama sebagai arsip internal.
        for name in frappe.get_all("RN Donor Program Update", {
            "program": PROGRAM, "update_notes": "Kabar simulasi untuk uji tampilan.",
        }, pluck="name"):
            frappe.db.set_value("RN Donor Program Update", name, "public_visibility", "internal")

        for timestamp, donor, amount, anonymous, received in DONATIONS:
            # Donatur fiktif tanpa akun/kontak agar seed tidak memicu notifikasi.
            donation = frappe.get_doc({
                "doctype": "RN Cash Donation", "disaster_event": EVENT, "donor_program": PROGRAM,
                "amount": amount, "currency": "IDR", "is_anonymous": anonymous, "donor_name": donor,
                "message": "[SIM/REB] Dukungan rehabilitasi sekolah", "status": "pending",
            }).insert(ignore_permissions=True)
            if received:
                dp.decide_cash_donation(donation.name, "confirm")
            fields = {"creation": timestamp}
            if received:
                fields["confirmed_at"] = timestamp
            frappe.db.set_value(donation.doctype, donation.name, fields, update_modified=False)

        for timestamp, title, percent, spent, note in UPDATES:
            result = dp.create_special_program_update(
                PROGRAM, "[SIM] " + title, update_type="spending" if spent else "progress",
                progress_percent=percent, amount_spent=spent, update_notes=note,
                officer_in_charge_name="[SIM] Koordinator UI Peduli",
            )
            frappe.db.set_value("RN Donor Program Update", result["update"],
                                {"creation": timestamp, "observed_at": timestamp}, update_modified=False)
        expected = (opening_received + sum(x[2] for x in DONATIONS if x[4]),
                    opening_spent + sum(x[3] for x in UPDATES))
        totals = frappe.db.get_value("RN Donor Program", PROGRAM, ["budget_received", "budget_spent"])
        if tuple(totals) != expected:
            raise RuntimeError(f"Rekonsiliasi dana gagal. Total {totals}, seharusnya {expected}.")
        frappe.db.commit()
        print(f"{PROGRAM}: target Rp {rp(TOTAL)}, masuk Rp {rp(expected[0])}, terpakai Rp {rp(expected[1])}")
    except Exception:
        frappe.db.rollback()
        raise
    finally:
        frappe.set_user(previous_user)


def seed_plan(program):
    milestones = [
        ("Survei & pendataan penerima", "Asesmen struktur, pemisahan area belajar dan desain", "2026-11-06", "selesai", 100),
        ("Pengadaan material", "Penyanggaan, bongkar dan pengangkutan puing", "2026-11-12", "selesai", 100),
        ("Pelaksanaan di lapangan", "Jaket kolom, balok dan sloof beton bertulang", "2026-12-04", "berjalan", 45),
        (None, "Atap metal, dinding, kusen dan lantai", "2026-12-30", "belum_mulai", 0),
        (None, "Listrik, akses ramp, perabot dan uji fungsi", "2027-01-20", "belum_mulai", 0),
        ("Serah terima & laporan akhir", "Pemeriksaan kelayakan dan serah terima sekolah", "2027-01-29", "belum_mulai", 0),
    ]
    for position, (old, title, due, status, progress) in enumerate(milestones, 1):
        name = existing("RN Program Milestone", program, "title", old, title)
        result = plan.save_plan_item(program, "milestone", name=name, values={
            "title": title, "due_date": due, "milestone_status": status,
            "progress_percent": progress, "sort_order": position,
        })
        frappe.db.set_value("RN Program Milestone", result["name"], "completed_at",
                            due if status == "selesai" else None)
    locations = [
        ("[SIM] Desa Suak Indrapuri", "[SIM] Blok kelas dan perpustakaan Tunas Pesisir", 4.1436, 96.1275, "belum_terlayani"),
        ("[SIM] Desa Ujong Baroh", "[SIM] Blok belajar bergilir sementara", 4.1440, 96.1285, "terlayani"),
        ("[SIM] Desa Padang Seurahet", "[SIM] Titik penerimaan bahan di luar pagar siswa", 4.1434, 96.1281, "terlayani"),
    ]
    for old, title, lat, lon, status in locations:
        name = existing("RN Program Location", program, "title", old, title)
        result = plan.save_plan_item(program, "location", name=name, values={
            "title": title, "latitude": lat, "longitude": lon, "location_status": status,
        })
        frappe.db.set_value("RN Program Location", result["name"], "served_at",
                            "2026-11-12" if status == "terlayani" else None)
    needs = [
        ("Semen", "Baja tulangan potong dan tekuk", "material", 1750, 1100, "kg", "2026-12-02"),
        ("Truk angkut 3 ton", "Penutup atap metal berinsulasi", "material", 256, 0, "m²", "2026-12-08"),
        ("Distribusi ke 3 desa", "Jendela kelas dan ruang baca", "material", 12, 0, "set", "2026-12-16"),
        ("Relawan tukang", "Relawan inventaris buku", "relawan", 8, 3, "orang", "2027-01-15"),
        ("Genset 5 kVA", "Meja-kursi pengganti", "material", 32, 0, "set", "2027-01-18"),
    ]
    for old, item, kind, needed, available, unit, due in needs:
        name = existing("RN Program Need", program, "item", "[SIM] " + old, item)
        plan.save_plan_item(program, "need", name=name, values={
            "item": item, "kind": kind, "qty_needed": needed, "qty_available": available,
            "unit": unit, "needed_by": due,
        })


def existing(doctype, program, key, old, new):
    current = frappe.db.exists(doctype, {"program": program, key: new})
    if not current and old:
        current = frappe.db.exists(doctype, {"program": program, key: old})
    return current


seed()
