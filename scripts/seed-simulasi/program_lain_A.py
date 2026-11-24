"""Seed sembilan program simulasi di site uji. Lihat program_lain_A/README.md."""
import base64
import json
import os
import sys
from pathlib import Path

import frappe
from rescue_net import api_donor_program as dp
from rescue_net.donor_program import plan
from rescue_net.services.money import lock

DOCTYPE = "RN Donor Program"
MARKER = "SIM/PROG-A/20261124/01"
PLACEHOLDERS = ("sampul-sim-", "rab-sim-", "gambar-sim-", "koran-sim-", "qris-sim-")
OLD_MILESTONES = ("Survei & pendataan penerima", "Pengadaan material",
                  "Pelaksanaan di lapangan", "Serah terima & laporan akhir")
OLD_NEEDS = ("Semen", "Truk angkut 3 ton", "Distribusi ke 3 desa", "Relawan tukang", "Genset 5 kVA")


def existing(doctype, program, key, old, new):
    for label in (new, old):
        name = frappe.db.exists(doctype, {"program": program, key: label})
        if name:
            return name
    return None


def save_plan(program, item_type, doctype, field, old, values):
    name = existing(doctype, program, field, old, values[field])
    return plan.save_plan_item(program, item_type, name=name, values=values)["name"]


def seed_plan(data, locations):
    program = data["id"]
    dates = ("2026-11-18", "2026-11-24", "2026-12-08", "2026-12-20")
    progress = data["progress"]
    portions = (100, max(30, progress), progress, 0)
    statuses = ("selesai", "berjalan", "berjalan", "belum_mulai")
    for index, (old, title, date, pct, status) in enumerate(
            zip(OLD_MILESTONES, data["steps"], dates, portions, statuses), 1):
        name = save_plan(program, "milestone", "RN Program Milestone", "title", old, {
            "title": title, "due_date": date, "milestone_status": status,
            "progress_percent": pct, "sort_order": index,
        })
        frappe.db.set_value("RN Program Milestone", name, "completed_at", date if status == "selesai" else None)

    for index, (old, role, lat, lon) in enumerate(locations):
        served = index == 0 and data["kind"] != "energy_support"
        name = save_plan(program, "location", "RN Program Location", "title", "[SIM] " + old, {
            "title": f"[SIM] {role} · Meulaboh", "latitude": lat, "longitude": lon,
            "location_status": "terlayani" if served else "belum_terlayani",
        })
        frappe.db.set_value("RN Program Location", name, "served_at", "2026-11-24" if served else None)

    for old, (item, qty, unit, _), available in zip(OLD_NEEDS, data["lines"], data["available"]):
        save_plan(program, "need", "RN Program Need", "item", "[SIM] " + old, {
            "item": "[SIM] " + item, "kind": "material", "qty_needed": qty,
            "qty_available": available,
            "unit": unit, "needed_by": "2026-12-08",
        })


def placeholder(value):
    return str(value or "").rsplit("/", 1)[-1].startswith(PLACEHOLDERS)


def replace_files(row, data, folder):
    program = row.name
    rab_images = sorted(folder.glob("rab-*.png"))
    if len(rab_images) not in (1, 2):
        raise ValueError("RAB harus punya satu atau dua halaman PNG")
    files = [("rab", folder / "rab.pdf", "RAB lengkap · PDF · SIMULASI")]
    files.extend(("rab", path, f"RAB halaman {index} · SIMULASI") for index, path in enumerate(rab_images, 1))
    files += [
        ("gambar", folder / "panduan.png", "Spesifikasi dan alur pelaksanaan · SIMULASI"),
        ("qris", folder / "qris.png", "Contoh QRIS · Jangan transfer"),
        ("koran", folder / "rekening.pdf", "Rekening koran sampai 24 November 2026 · SIMULASI"),
    ]
    photos = [(i, folder / f"foto-{i}.jpg") for i in range(2)]
    labels = (f"Gambaran kegiatan {data['title']} · FOTO AI SIMULASI",
              f"Rincian kegiatan {data['title']} · FOTO AI SIMULASI")
    files.extend(("gambar", path, labels[i]) for i, path in photos if path.exists())
    content = [(kind, path, label, path.read_bytes()) for kind, path, label in files]

    old_files = json.loads(row.work_drawings or "[]")
    keep = [entry for entry in old_files if not (placeholder(entry.get("name")) or placeholder(entry.get("url")))]
    fields = {"work_drawings": json.dumps(keep, ensure_ascii=False)}
    if placeholder(row.rab_file_url):
        fields["rab_file_url"] = None
    if placeholder(row.cover_image_url):
        fields["cover_image_url"] = None
    frappe.db.set_value(DOCTYPE, program, fields)
    for evidence in frappe.get_all("RN Evidence File",
                                   {"linked_object_type": DOCTYPE, "linked_object_id": program},
                                   fields=["name", "filename", "file_path"]):
        if placeholder(evidence.filename) or placeholder(evidence.file_path):
            frappe.db.set_value("RN Evidence File", evidence.name, "visibility", "internal")

    for kind, path, label, raw in content:
        # Gunakan nama unik per program karena File Frappe dapat memberi akhiran acak.
        filename = f"prog-a-{data['key']}-{path.name}"
        dp.upload_program_file(program, kind, filename, base64.b64encode(raw).decode("ascii"),
                               label=label, redacted=int(kind == "koran"))
    entries = json.loads(frappe.db.get_value(DOCTYPE, program, "work_drawings") or "[]")
    urls = {entry["name"]: entry["url"] for entry in entries}
    count = 0
    for index, path in photos:
        if not path.exists():
            continue
        url = urls[f"prog-a-{data['key']}-{path.name}"]
        if count == 0:
            frappe.db.set_value(DOCTYPE, program, "cover_image_url", url)
        frappe.get_doc({
            "doctype": "RN Evidence File", "legacy_id": f"evidence-prog-a-{data['key']}-{index}",
            "legacy_source": "seed-simulasi", "title": labels[index], "disaster_event": row.disaster_event,
            "linked_object_type": DOCTYPE, "linked_object_id": program, "evidence_type": "photo",
            "filename": url.rsplit("/", 1)[-1], "file_path": url, "mime_type": "JPEG",
            "visibility": "public",
        }).insert(ignore_permissions=True)
        count += 1
    return count


def seed_finance_and_updates(row, data):
    program = row.name
    for stamp, donor, amount in data["donations"]:
        donation = frappe.get_doc({
            "doctype": "RN Cash Donation", "disaster_event": row.disaster_event, "donor_program": program,
            "amount": amount, "currency": "IDR", "is_anonymous": 0, "donor_name": donor,
            "message": "[SIM] Donasi latihan", "status": "pending",
        }).insert(ignore_permissions=True)
        dp.decide_cash_donation(donation.name, "confirm")
        when = f"2026-11-{stamp[:2]} 10:00:00"
        frappe.db.set_value(donation.doctype, donation.name, {"creation": when, "confirmed_at": when},
                            update_modified=False)

    update_type = "RN Donor Program Update"
    for name in frappe.get_all(update_type, {"program": program, "update_notes": "Kabar simulasi untuk uji tampilan."},
                               pluck="name"):
        frappe.db.set_value(update_type, name, "public_visibility", "internal")

    for day, title, pct, spend, notes in [
        (18, data["steps"][0], 5, 0, "Pendataan kebutuhan dan alur layanan latihan dicatat di tiga titik Meulaboh."),
        (24, data["steps"][2], data["progress"], data["spent"], data["report"]),
    ]:
        result = dp.create_special_program_update(
            program, "[SIM] " + title, update_type="spending" if spend else "progress",
            progress_percent=pct, amount_spent=spend, update_notes="[SIMULASI] " + notes,
            officer_in_charge_name="[SIM] Koordinator latihan",
        )
        stamp = f"2026-11-{day} 15:00:00"
        frappe.db.set_value(update_type, result["update"], {"creation": stamp, "observed_at": stamp},
                            update_modified=False)


def seed(data, folder, event, locations):
    program = data["id"]
    lock(DOCTYPE, program)
    row = frappe.get_doc(DOCTYPE, program)
    if row.disaster_event != event or row.program_type != data["kind"]:
        raise ValueError("Event atau tipe program berbeda dari TSV simulasi")
    if MARKER in (row.notes or "").splitlines():
        frappe.db.rollback()
        print(f"LEWATI {program} · penanda sudah ada")
        return

    initial = (row.budget_received or 0, row.budget_spent or 0, row.budget_target or 0)
    counts = tuple(frappe.db.count(doctype, {field: program}) for doctype, field in (
        ("RN Program Milestone", "program"), ("RN Program Location", "program"),
        ("RN Program Need", "program"), ("RN Donor Program Update", "program"),
        ("RN Cash Donation", "donor_program"),
    ))
    if counts != data["counts"]:
        raise ValueError(f"Jumlah milestone/lokasi/kebutuhan/kabar/donasi berbeda: {counts}, TSV {data['counts']}")
    if initial != data["initial"] or row.bank_account_number not in (None, "", data["bank"]):
        raise ValueError(f"Snapshot berbeda: kas/target {initial}, TSV {data['initial']} atau rekening berubah")
    frappe.set_user(data["pic"])
    place = "Meulaboh, Johan Pahlawan, Aceh Barat"
    dp.update_program_info(program, {
        "description": f"[SIMULASI] {data['title']}. {data['guide']}",
        "target_description": data["target"], "target_beneficiaries": data["target"],
        "budget_target": data["total"], "location": place,
        "start_date": "2026-11-04", "end_date": "2026-12-20",
    })
    frappe.db.set_value(DOCTYPE, program, "target_location", place)
    output_target, completed = data["outputs"]
    plan.set_output_verification(program, status="dalam_proses", output_target=output_target,
                                 output_verified=completed, verifier="[SIM] Tim latihan Meulaboh",
                                 estimated_done="2026-12-20")
    if not row.bank_account_number:
        # Format jelas fiktif, sama dengan contoh nomor Bank Simulasi dari seed lama.
        frappe.db.set_value(DOCTYPE, program, {
            "bank_name": "Bank Simulasi", "bank_account_number": data["bank"],
            "bank_account_holder": "[SIM] Program latihan Meulaboh",
        })
    count = replace_files(row, data, folder)
    seed_plan(data, locations)
    seed_finance_and_updates(row, data)
    final = frappe.db.get_value(DOCTYPE, program, ["budget_received", "budget_spent", "budget_target"])
    expected = (*data["terminal"], data["total"])
    if tuple(final) != expected:
        raise ValueError(f"Rekonsiliasi gagal: {final}, semestinya {expected}")
    frappe.db.set_value(DOCTYPE, program, "notes", "\n".join(filter(None, (row.notes, MARKER))))
    frappe.db.commit()
    print(f"DONE {program} · RAB {final[2]} · masuk {final[0]} · terpakai {final[1]} · foto {count}")
    if count < 2:
        print(f"TEMUAN {program} · foto lolos pemeriksaan {count}/2")


def run():
    site = str(frappe.local.site or "")
    if (not site or site != os.environ.get("RN_PROG_SITE") or "rescue-net.online" in site.lower()
            or site.lower() in {"192.168.100.3", "osiun.localhost"}):
        raise RuntimeError("RN_PROG_SITE harus persis nama site uji terisolasi.")
    assets = Path(os.environ.get("RN_PROG_ASSETS", "/tmp/program_lain_A")).resolve()
    sys.path.insert(0, str(assets))
    try:
        from prog_a_data import EVENT, LOCATIONS, programs
    finally:
        sys.path.remove(str(assets))

    previous = frappe.session.user
    for data in programs():
        try:
            seed(data, assets / data["key"], EVENT, LOCATIONS)
        except Exception as error:
            frappe.db.rollback()
            print(f"TEMUAN {data['id']} · {type(error).__name__}: {error}")
        finally:
            frappe.set_user(previous)


run()
