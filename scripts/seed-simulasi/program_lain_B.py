"""Seed Kelompok B untuk site uji. Petunjuk ada di program_lain_B/README.md."""
import base64
import json
import os
import sys
import traceback
from functools import partial
from pathlib import Path
from urllib.parse import unquote, urlsplit

import frappe
from rescue_net import api_donor_program as dp
from rescue_net.donor_program import plan
from rescue_net.services.money import lock

DOCTYPE = "RN Donor Program"
PREFIXES = ("sampul-sim-", "rab-sim-", "gambar-sim-", "koran-sim-", "qris-sim-")


def existing(doctype, program, key, old, new):
    found = frappe.db.exists(doctype, {"program": program, key: new})
    return found or (old and frappe.db.exists(doctype, {"program": program, key: old}))


def placeholder(value):
    filename = unquote(urlsplit(value or "").path).rsplit("/", 1)[-1]
    return filename.lower().startswith(PREFIXES)


def detach_placeholders(row):
    entries = json.loads(row.work_drawings or "[]")
    keep = [entry for entry in entries
            if not any(placeholder(entry.get(field)) for field in ("name", "url"))]
    rab = row.rab_file_url
    if placeholder(rab) or any(entry.get("url") == rab and entry not in keep for entry in entries):
        rab = next((entry["url"] for entry in keep if entry.get("kind") == "rab"), None)
    fields = {"work_drawings": json.dumps(keep, ensure_ascii=False), "rab_file_url": rab}
    if placeholder(row.cover_image_url):
        fields["cover_image_url"] = None
    frappe.db.set_value(DOCTYPE, row.name, fields)


def upload(name, assets, kind, filename, label):
    encoded = base64.b64encode((assets / filename).read_bytes()).decode("ascii")
    dp.upload_program_file(name, kind, filename, encoded, label=label, redacted=int(kind == "koran"))
    if kind == "gambar":
        entries = json.loads(frappe.db.get_value(DOCTYPE, name, "work_drawings") or "[]")
        return next(entry["url"] for entry in reversed(entries) if entry["name"] == filename)


def attach_photos(row, key, program, assets):
    files = {}
    for index, label in enumerate(program.photos, 1):
        filename = f"{key}-foto-{index}.jpg"
        if not (assets / filename).is_file():
            continue
        title = "FOTO AI · SIMULASI — " + label
        url = upload(row.name, assets, "gambar", filename, title)
        if not url.startswith("/files/"):
            raise RuntimeError(f"Foto tidak tersimpan sebagai berkas publik: {filename}.")
        legacy = f"evidence-sim-progb-{key}-{index}"
        evidence = frappe.db.exists("RN Evidence File", {"legacy_id": legacy})
        if not evidence:
            evidence = frappe.get_doc({
                "doctype": "RN Evidence File", "legacy_id": legacy, "legacy_source": "seed-simulasi",
                "title": title, "disaster_event": row.disaster_event, "linked_object_type": DOCTYPE,
                "linked_object_id": row.name, "evidence_type": "photo", "filename": url.rsplit("/", 1)[-1],
                "file_path": url, "mime_type": "JPG", "verification_status": "verified", "visibility": "public",
            }).insert(ignore_permissions=True).name
        files[index] = (url, evidence)
    if files:
        frappe.db.set_value(DOCTYPE, row.name, "cover_image_url", next(iter(files.values()))[0])
    return files


def save_plan(name, program, locations):
    legacy = ("Survei & pendataan penerima", "Pengadaan material", "Pelaksanaan di lapangan",
              "Serah terima & laporan akhir")
    dates = ("2026-11-16", "2026-11-30", "2026-12-18", "2027-01-15")
    status = ("selesai", "berjalan", "belum_mulai", "belum_mulai")
    advances = (100, min(95, program.progress * 2), 0, 0)
    for index, (old, title, due, state, progress) in enumerate(zip(legacy, program.stages, dates, status, advances), 1):
        item = existing("RN Program Milestone", name, "title", old, title)
        result = plan.save_plan_item(name, "milestone", name=item, values={
            "title": title, "due_date": due, "milestone_status": state, "progress_percent": progress,
            "sort_order": index,
        })
        if state == "selesai":
            frappe.db.set_value("RN Program Milestone", result["name"], "completed_at", due)
    for place, lat, lon, _ in locations:
        title = "[SIMULASI] " + place
        item = existing("RN Program Location", name, "title", f"[SIM] {place}", title)
        plan.save_plan_item(name, "location", name=item, values={
            "title": title, "latitude": lat, "longitude": lon, "location_status": "belum_terlayani",
        })
    for label, qty, unit, _ in program.rows[:5]:
        item = existing("RN Program Need", name, "item", f"[SIM] {label}", label)
        values = {"item": label, "kind": "material", "qty_needed": qty,
                  "unit": unit, "needed_by": "2026-12-02"}
        if unit in {"orang-hari", "orang-sesi", "sesi", "kunjungan kasus"}:
            continue
        if not item:
            values["qty_available"] = 0
        plan.save_plan_item(name, "need", name=item, values=values)


def save_activity(row, program, photos, data):
    amounts = (*program.receipts, data.PENDING)
    for day, donor, amount in zip((*data.RECEIPT_DAYS, 24), data.DONORS, amounts):
        ts = f"2026-11-{day:02d} 09:00:00"
        donation = frappe.get_doc({
            "doctype": "RN Cash Donation", "disaster_event": row.disaster_event,
            "donor_program": row.name, "amount": amount, "currency": "IDR", "is_anonymous": 0,
            "donor_name": f"[SIMULASI] {donor}", "message": "[SIMULASI] Dukungan kegiatan",
            "status": "pending",
        }).insert(ignore_permissions=True)
        dates = {"creation": ts}
        if day in data.RECEIPT_DAYS:
            dp.decide_cash_donation(donation.name, "confirm")
            dates["confirmed_at"] = ts
        frappe.db.set_value(donation.doctype, donation.name, dates, update_modified=False)

    for index, (day, amount, title, story) in enumerate(
            zip(data.UPDATE_DAYS, program.spending, program.stages, program.stories), 1):
        ts = f"2026-11-{day:02d} 15:00:00"
        result = dp.create_special_program_update(
            row.name, f"[SIMULASI] {title}", update_type="spending", amount_spent=amount,
            progress_percent=program.progress if index == 2 else program.progress // 3,
            update_notes=f"[SIMULASI] {story}",
            evidence_file_id=photos.get(index, (None, None))[1],
        )
        frappe.db.set_value("RN Donor Program Update", result["update"],
                            {"creation": ts, "observed_at": ts}, update_modified=False)


def seed_one(key, program, assets, data):
    name = f"rn-donor-{key}"
    marker = f"SIM/PROG-B/20261124/{key}"
    event, locations = data.AREAS[program.area]
    lock(DOCTYPE, name)
    row = frappe.get_doc(DOCTYPE, name)
    if row.disaster_event != event or row.program_type != program.kind:
        raise ValueError(f"program/event berbeda: {row.program_type}, {row.disaster_event}")
    if marker in (row.notes or "").splitlines():
        print(f"{name}: seed sudah tercatat.")
        return
    opening = (row.budget_received or 0, row.budget_spent or 0)
    if opening != program.opening:
        raise ValueError(f"dana awal DB {opening} berbeda dari TSV {program.opening}")
    if (row.budget_target or 0) != program.initial_target:
        raise ValueError(f"target awal DB {row.budget_target} berbeda dari TSV {program.initial_target}")
    if (row.bank_account_number or "") != program.account:
        raise ValueError("rekening awal berbeda dari TSV")
    if row.status == "cancelled":
        raise ValueError("program dibatalkan")

    frappe.set_user(program.pic or "Administrator")
    put = partial(upload, name, assets)
    location = " / ".join(place for place, *_ in locations)
    dp.update_program_info(name, {
        "description": "[SIMULASI] " + program.scope, "target_description": program.scope,
        "location": location, "budget_target": program.target,
        "start_date": row.start_date or "2026-11-09", "end_date": row.end_date or "2027-01-15",
    })
    frappe.db.set_value(DOCTYPE, name, "target_location", location)
    if not program.account:
        dp.set_program_bank(name, bank_name="Bank Simulasi", account_number=data.account(key, program),
                            account_holder=data.HOLDER)
    detach_placeholders(row)
    put("rab", f"{key}-rab.pdf", "RAB lengkap · SIMULASI")
    put("rab", f"{key}-rab-1.png", "RAB halaman 1 · SIMULASI")
    put("gambar", f"{key}-gambar.png", "Spesifikasi kegiatan · SIMULASI")
    put("qris", f"{key}-qris.png", "QRIS contoh · JANGAN TRANSFER")
    put("koran", f"{key}-koran.pdf", "Rekening koran · SIMULASI")
    photos = attach_photos(row, key, program, assets)
    save_plan(name, program, locations)
    save_activity(row, program, photos, data)

    actual = tuple(frappe.db.get_value(DOCTYPE, name, ["budget_received", "budget_spent"]))
    if actual != program.final:
        raise RuntimeError(f"dana akhir DB {actual} berbeda dari dokumen {program.final}")
    frappe.db.set_value(DOCTYPE, name, "notes", "\n".join(filter(None, (row.notes, marker))))
    frappe.db.commit()
    print(f"{name}: RAB Rp{program.target}, dana akhir {program.final}, {len(photos)} foto.")
    if len(photos) < len(program.photos):
        print(f"TEMUAN {name}: {len(program.photos) - len(photos)} foto belum tersedia.")


def seed():
    site = str(frappe.local.site or "")
    prod_ok = os.environ.get("RN_PROG_PROD") == "1" and site == "osiun.localhost"   # Ming Ming: produksi setelah backup
    if (not site or site != os.environ.get("RN_PROG_SITE")) or (not prod_ok and (site.lower() in {"osiun.localhost", "192.168.100.3"}
            or "rescue-net.online" in site.lower())):
        raise RuntimeError("RN_PROG_SITE harus sama dengan nama site uji terisolasi.")
    assets = Path(os.environ.get("RN_PROG_ASSETS", "/tmp/program_lain_B")).resolve()
    sys.path.insert(0, str(assets))
    try:
        import data_b as data
    finally:
        sys.path.pop(0)

    previous_user = frappe.session.user
    for key, program in data.PROGRAMS.items():
        try:
            seed_one(key, program, assets, data)
        except Exception as exc:
            print(f"TEMUAN rn-donor-{key}: {exc}")
            traceback.print_exc()
        finally:
            # Melepaskan lock ketika skip dan membatalkan perubahan parsial ketika gagal.
            frappe.db.rollback()
            frappe.set_user(previous_user)


seed()
