"""Lengkapi data SIMULASI Program Donasi (owner 24 Nov 2026: "lengkapi data simulasi di semua hal supaya kelihatan
kurang-kurangnya"). Hanya event simulasi; hanya mengisi yang KOSONG (aman diulang); semua berkas bertanda SIMULASI.
Jalankan di bench console: exec(open(path).read(), {"__name__": "rn"})."""
import io, json, random, datetime
import frappe
from frappe.utils import add_days, nowdate, now_datetime
from frappe.utils.file_manager import save_file

EVENT = "disaster_events:event-sim-001"
BASE_LAT, BASE_LNG = 4.1363, 96.1285   # Meulaboh, Aceh Barat
rnd = random.Random(20261124)
log = []


def png(title, sub, w=960, h=600, bg=(232, 117, 90)):
    from PIL import Image, ImageDraw, ImageFont
    im = Image.new("RGB", (w, h), bg)
    d = ImageDraw.Draw(im)
    try:
        f1 = ImageFont.truetype("DejaVuSans-Bold.ttf", 44); f2 = ImageFont.truetype("DejaVuSans.ttf", 26)
    except Exception:
        f1 = f2 = ImageFont.load_default()
    for x in range(0, w, 60):
        d.line([(x, 0), (x, h)], fill=tuple(min(255, c + 18) for c in bg))
    for y in range(0, h, 60):
        d.line([(0, y), (w, y)], fill=tuple(min(255, c + 18) for c in bg))
    d.rectangle([40, h // 2 - 110, w - 40, h // 2 + 110], outline=(255, 255, 255), width=4)
    d.text((70, h // 2 - 80), title[:38], fill=(255, 255, 255), font=f1)
    d.text((70, h // 2 + 0), sub[:60], fill=(255, 255, 255), font=f2)
    d.text((70, h // 2 + 50), "SIMULASI - bukan dokumen asli", fill=(255, 240, 200), font=f2)
    out = io.BytesIO(); im.save(out, "PNG"); return out.getvalue()


def pdf(title, lines):
    """PDF teks sederhana satu halaman (tanpa pustaka tambahan)."""
    esc = lambda s: s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    body = ["BT /F1 18 Tf 50 790 Td (" + esc(title) + ") Tj ET",
            "BT /F1 10 Tf 50 770 Td (SIMULASI - bukan dokumen asli) Tj ET"]
    y = 740
    for ln in lines:
        body.append("BT /F1 11 Tf 50 %d Td (%s) Tj ET" % (y, esc(ln))); y -= 18
    stream = "\n".join(body).encode("latin-1", "replace")
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
            b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out = io.BytesIO(); out.write(b"%PDF-1.4\n"); offs = []
    for i, o in enumerate(objs, 1):
        offs.append(out.tell()); out.write(b"%d 0 obj\n" % i + o + b"\nendobj\n")
    xref = out.tell()
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1))
    for o in offs: out.write(b"%010d 00000 n \n" % o)
    out.write(b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref))
    return out.getvalue()


def attach(prog, fname, content):
    f = save_file(fname, content, "RN Donor Program", prog, is_private=0)
    return f.file_url


def rp(n):
    return "Rp " + format(int(n), ",").replace(",", ".")


progs = frappe.get_all("RN Donor Program", filters={"disaster_event": EVENT},
                       fields=["name", "program_name", "program_type", "budget_target", "budget_received", "budget_spent",
                               "status", "work_drawings", "cover_image_url", "description", "officer_in_charge_name",
                               "start_date", "bank_account_number", "output_verification_status", "location",
                               "target_location", "partners", "rab_file_url"])
for p in progs:
    name, title = p.name, p.program_name
    short = title.replace("[SIMULASI]", "").strip()
    done = p.status == "completed"
    upd = {}
    tgt = float(p.budget_target or 0) or 50000000.0
    if not p.cover_image_url:
        upd["cover_image_url"] = attach(name, "sampul-sim-%s.png" % name[-6:], png(short, "Sampul program", bg=(196, 68, 47)))
    if not p.description:
        upd["description"] = "[SIMULASI] %s untuk warga terdampak Gempa Simulasi Aceh Barat. Data contoh untuk menguji tampilan." % short
    if not p.officer_in_charge_name:
        upd.update(officer_in_charge_name="[SIM] Koordinator %s" % short[:20], officer_in_charge_phone="0811000%04d" % rnd.randint(0, 9999))
    if not p.start_date:
        upd.update(start_date=add_days(nowdate(), -25), end_date=add_days(nowdate(), 35 if not done else -2))
    if not p.partners:
        upd["partners"] = "[SIM] BPBD Aceh Barat, Relawan Kampus, Karang Taruna"
    if not (p.target_location or p.location):
        upd["target_location"] = "Kec. Johan Pahlawan, Meulaboh"
    if not p.target_location:
        upd["target_beneficiaries"] = "%d KK terdampak (simulasi)" % rnd.randint(40, 300)
    if not p.bank_account_number:
        upd.update(bank_name="Bank Simulasi", bank_account_number="900-SIM-%06d" % rnd.randint(0, 999999),
                   bank_account_holder="[SIM] %s" % short[:30])
    if not p.output_verification_status:
        ot = rnd.randint(50, 300)
        upd.update(output_target=ot, output_verified=ot if done else int(ot * rnd.uniform(.2, .7)),
                   output_verification_status="terverifikasi" if done else "dalam_proses",
                   output_verifier="[SIM] Tim Verifikasi BPBD", output_estimated_done=add_days(nowdate(), 30))
    if not p.budget_spent:
        upd["budget_spent"] = round(float(p.budget_received or 0) * (0.9 if done else rnd.uniform(.3, .6)), -3)
    # dokumen: RAB (PDF), 2 gambar rencana, 1 rekening koran
    entries = json.loads(p.work_drawings or "[]")
    kinds = {e.get("kind", "gambar") for e in entries}
    if "rab" not in kinds:
        items = [("Material utama", .45), ("Upah tenaga kerja", .25), ("Transportasi & distribusi", .15),
                 ("Peralatan", .1), ("Administrasi & dokumentasi", .05)]
        lines = ["Program: " + short[:70], "Target dana: " + rp(tgt), ""] + \
                ["%d. %-30s %s" % (i + 1, k, rp(tgt * v)) for i, (k, v) in enumerate(items)] + ["", "TOTAL  " + rp(tgt)]
        u = attach(name, "rab-sim-%s.pdf" % name[-6:], pdf("Rencana Anggaran Biaya (RAB)", lines))
        entries.append({"url": u, "name": u.rsplit("/", 1)[-1], "label": "RAB simulasi", "pdf": True, "kind": "rab"})
        upd["rab_file_url"] = p.rab_file_url or u
    if not any(e.get("kind") not in ("rab", "qris", "koran") for e in entries):
        for i, lab in enumerate(["Denah lokasi", "Tampak depan"]):
            u = attach(name, "gambar-sim-%s-%d.png" % (name[-6:], i + 1), png(short, lab, bg=(70, 110, 160) if i else (60, 130, 110)))
            entries.append({"url": u, "name": u.rsplit("/", 1)[-1], "label": lab + " (simulasi)", "pdf": False})
    if "koran" not in kinds:
        rec = float(p.budget_received or 0)
        lines = ["Periode: 1 - 24 Nov 2026", "Saldo awal: Rp 0", "Dana masuk: " + rp(rec),
                 "Dana keluar: " + rp(upd.get("budget_spent", p.budget_spent or 0)), "", "Nama & nomor rekening donatur disamarkan."]
        u = attach(name, "koran-sim-%s.pdf" % name[-6:], pdf("Rekening Koran (simulasi)", lines))
        entries.append({"url": u, "name": u.rsplit("/", 1)[-1], "label": "Rekening koran Nov 2026 (simulasi)", "pdf": True,
                        "kind": "koran", "redacted": 1})
    if json.dumps(entries) != (p.work_drawings or "[]"):
        upd["work_drawings"] = json.dumps(entries, ensure_ascii=False)
    if upd:
        frappe.db.set_value("RN Donor Program", name, upd, update_modified=False)
    # milestone
    if not frappe.db.count("RN Program Milestone", {"program": name}):
        ms = [("Survei & pendataan penerima", "selesai", 100, -20), ("Pengadaan material", "selesai" if done else "berjalan", 100 if done else 60, -5),
              ("Pelaksanaan di lapangan", "selesai" if done else "berjalan", 100 if done else 30, 10),
              ("Serah terima & laporan akhir", "selesai" if done else "belum_mulai", 100 if done else 0, 30)]
        for i, (t, st, pc, dd) in enumerate(ms):
            frappe.get_doc({"doctype": "RN Program Milestone", "program": name, "title": t, "sort_order": i + 1,
                            "due_date": add_days(nowdate(), dd), "milestone_status": st, "progress_percent": pc,
                            "completed_at": add_days(nowdate(), dd) if st == "selesai" else None}).insert(ignore_permissions=True)
    # lokasi
    if not frappe.db.count("RN Program Location", {"program": name}):
        for i, t in enumerate(["Desa Suak Indrapuri", "Desa Ujong Baroh", "Desa Padang Seurahet"]):
            served = done or i == 0
            frappe.get_doc({"doctype": "RN Program Location", "program": name, "title": "[SIM] " + t,
                            "latitude": BASE_LAT + rnd.uniform(-.03, .03), "longitude": BASE_LNG + rnd.uniform(-.03, .03),
                            "location_status": "terlayani" if served else "belum_terlayani",
                            "served_at": add_days(nowdate(), -3) if served else None}).insert(ignore_permissions=True)
    # kebutuhan
    if not frappe.db.count("RN Program Need", {"program": name}):
        for item, kind, need, have, unit in [("Semen", "material", 120, 80, "sak"), ("Truk angkut 3 ton", "logistik", 2, 1, "unit"),
                                             ("Distribusi ke 3 desa", "distribusi", 3, 1, "rit"), ("Relawan tukang", "relawan", 15, 9, "orang"),
                                             ("Genset 5 kVA", "alat_kerja", 2, 0, "unit")]:
            frappe.get_doc({"doctype": "RN Program Need", "program": name, "item": "[SIM] " + item, "kind": kind,
                            "qty_needed": need, "qty_available": need if done else have, "unit": unit,
                            "needed_by": add_days(nowdate(), 7)}).insert(ignore_permissions=True)
    # kabar terbaru
    if frappe.db.count("RN Donor Program Update", {"program": name}) < 2:
        for ut, t, pc, amt, dd in [("progress", "Survei selesai, %d KK terdata" % rnd.randint(40, 200), 25, 0, -18),
                                   ("spending", "Pembelian material tahap 1", 45, round(tgt * .2, -3), -8)]:
            frappe.get_doc({"doctype": "RN Donor Program Update", "program": name, "disaster_event": EVENT, "update_type": ut,
                            "update_title": "[SIM] " + t, "update_notes": "Kabar simulasi untuk uji tampilan.",
                            "progress_percent": pc, "amount_spent": amt, "amount_unit": "IDR", "evidence_status": "not_required",
                            "public_visibility": "summary_public", "officer_in_charge_name": "[SIM] Koordinator",
                            "observed_at": add_days(now_datetime(), dd)}).insert(ignore_permissions=True)
    # penyumbang: catatan donasi = dana masuk yang sudah tercatat (total program TIDAK diubah)
    have = sum(float(x or 0) for x in frappe.get_all("RN Cash Donation", filters={"donor_program": name, "status": "received"}, pluck="amount"))
    gap = float(p.budget_received or 0) - have
    names = ["[SIM] Hamba Allah", "[SIM] Keluarga Besar Teuku", "[SIM] Alumni SMA 1 Meulaboh", "[SIM] PT Contoh Sejahtera",
             "[SIM] Ibu Nurhayati", "[SIM] Komunitas Pesepeda Aceh"]
    k = 0
    while gap >= 1000 and k < 6:
        amt = gap if k == 5 or gap < 200000 else round(gap * rnd.uniform(.2, .5), -3)
        anon = k % 3 == 0
        frappe.get_doc({"doctype": "RN Cash Donation", "disaster_event": EVENT, "donor_program": name,
                        "donor_name": "Donatur Anonim" if anon else names[k], "is_anonymous": 1 if anon else 0,
                        "amount": amt, "currency": "IDR", "status": "pending", "message": "Semoga bermanfaat (simulasi)"}).insert(ignore_permissions=True)
        # langsung "received" tanpa menambah total program (dana masuk sudah tercatat di budget_received)
        d = frappe.get_last_doc("RN Cash Donation", filters={"donor_program": name})
        frappe.db.set_value("RN Cash Donation", d.name, {"status": "received", "confirmed_by": "seed-simulasi",
                            "confirmed_at": add_days(now_datetime(), -rnd.randint(1, 20))}, update_modified=False)
        gap -= amt; k += 1
    log.append("%s: %d kolom, ms %d, lok %d, keb %d, kabar %d, donasi %d" % (
        short[:28], len(upd), frappe.db.count("RN Program Milestone", {"program": name}), frappe.db.count("RN Program Location", {"program": name}),
        frappe.db.count("RN Program Need", {"program": name}), frappe.db.count("RN Donor Program Update", {"program": name}),
        frappe.db.count("RN Cash Donation", {"donor_program": name})))

frappe.db.commit()
print("SEED-PROGRAM SELESAI")
for l in log: print("  " + l)
