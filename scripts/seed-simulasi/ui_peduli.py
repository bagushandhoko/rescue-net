"""Program simulasi "UI Peduli — Sekolah Darurat Krakatau" dibuat realistis (owner 24 Nov 2026: "ui peduli gambar dan rab dan
lain buat yang realistis juga progress nya, qris belum keliatan"). SEMUA DATA SIMULASI, semua gambar bercap SIMULASI.
Aset (gambar kerja, RAB, ilustrasi, QRIS, rekening koran) dibangkitkan oleh scripts/seed-simulasi/ui_peduli/gen_*.py.
Jalankan di kontainer backend: salin folder ui_peduli ke /tmp/ui-sim lalu `bench --site <site> console < ui_peduli.py`.
Idempoten: tiap bagian dicek dulu (penanda "SIM/UIP")."""
import base64, json, os
import frappe
from frappe.utils import flt

A = "/tmp/ui-sim"
PROG = "rn-donor-ddc38efbfaf6"
TENDER, BID = "pur8kre3or", "b0cfdsjou8"
PIC = "sim-ui-peduli@example.org"
TOTAL, FISIK, KONTRAK = 756_805_000, 610_006_000, 598_500_000
done, found = [], []
b64 = lambda f: base64.b64encode(open(os.path.join(A, f), "rb").read()).decode()


def as_user(email, fn, *a, **kw):
    frappe.set_user(email)
    try:
        r = fn(*a, **kw); frappe.db.commit(); return r
    except Exception as e:
        frappe.db.rollback(); found.append("%s @%s: %s: %s" % (getattr(fn, "__name__", fn), email.split("@")[0], type(e).__name__, str(e)[:200])); return None
    finally:
        frappe.set_user("Administrator")


from rescue_net import api_donor_program as dp
from rescue_net.donor_program import plan
row = frappe.get_doc("RN Donor Program", PROG)
ev = row.disaster_event

# 1) info dasar
if "SIM/UIP" not in (row.notes or ""):
    as_user(PIC, dp.update_program_info, PROG, {
        "description": ("Erupsi Anak Krakatau (simulasi) merusak gedung SDN 1 Way Urang, Kalianda: atap runtuh tertimpa abu dan 160 siswa SD/SMP "
                        "pengungsi belajar di tenda. UI Peduli membangun sekolah darurat semi-permanen di lahan sekolah (pinjam pakai): 4 ruang kelas "
                        "7x8 m, 1 ruang guru, toilet 4 bilik, sumur bor & tandon, tempat cuci tangan, lengkap dengan 160 set meja-kursi. Konstruksi "
                        "kolom baja hollow + rangka atap baja ringan agar cepat dibangun dan bisa dibongkar-pindah setelah gedung permanen selesai. "
                        "Pekerjaan fisik ditenderkan (pemenang CV Bangun Cepat, 35 hari kerja), diawasi tim teknik pendamping. Laporan dana & foto "
                        "progres diunggah tiap tahap. SIMULASI: lembaga, angka dan gambar adalah contoh."),
        "target_description": "4 ruang kelas + 1 ruang guru + toilet 4 bilik siap dipakai 160 siswa sebelum semester genap (Jan 2027)",
        "location": "SDN 1 Way Urang, Kalianda, Lampung Selatan", "target_beneficiaries": "160 siswa SD/SMP pengungsi + 6 guru",
        "budget_target": TOTAL, "start_date": "2026-11-03", "end_date": "2027-01-15",
        "officer_in_charge_name": "[SIM] Koordinator Program UI Peduli", "officer_in_charge_phone": "021-7867222",
        "contact_person": "[SIM] Sekretariat UI Peduli Bencana", "contact_phone": "021-7867222"})
    frappe.db.set_value("RN Donor Program", PROG, {"partners": "SDN 1 Way Urang (pemilik lahan), Tim Teknik Pendamping (simulasi), BPBD Lampung Selatan (simulasi)",
                                                   "output_target": 4, "output_verified": 0, "output_verification_status": "dalam_proses",
                                                   "output_estimated_done": "2027-01-10", "target_amount": 4,
                                                   "notes": "SIM/UIP: diisi ulang realistis 24 Nov 2026 (scripts/seed-simulasi/ui_peduli.py)"})
    frappe.db.commit(); done.append("info dasar + target Rp %s" % TOTAL)

# 2) dokumen: buang yang lama (contoh asal-asalan), unggah set baru
row = frappe.get_doc("RN Donor Program", PROG)
if "rab-sekolah-darurat-kalianda" not in (row.work_drawings or ""):
    as_user(PIC, dp.remove_program_file, PROG, "rab")
    for d in json.loads(frappe.db.get_value("RN Donor Program", PROG, "work_drawings") or "[]"):
        if not d.get("kind"):
            as_user(PIC, dp.remove_program_file, PROG, "gambar", d["url"])
    UP = [("rab", "rab-sekolah-darurat-kalianda.pdf", "RAB lengkap 11 pekerjaan + rekap — Rp 756.805.000 (PDF, simulasi)"),
          ("rab", "rab-full.png", "RAB (gambar satu halaman) — simulasi"),
          ("gambar", "denah.png", "GK-01 Denah: 4 ruang kelas, ruang guru, toilet, tandon (simulasi)"),
          ("gambar", "tampak.png", "GK-02 Tampak depan & potongan A-A (simulasi)"),
          ("gambar", "il-cover.png", "Ilustrasi rencana sekolah jadi (simulasi)"),
          ("gambar", "il-kondisi.png", "Kondisi awal: gedung tertutup abu, siswa di tenda (ilustrasi simulasi)"),
          ("gambar", "il-p1.png", "Progres: pondasi & sloof selesai 18 Nov (ilustrasi simulasi)"),
          ("gambar", "il-p2.png", "Progres: kolom & rangka atap 24 Nov (ilustrasi simulasi)"),
          ("qris", "qris.png", None),
          ("koran", "koran-nov-2026.pdf", "Rekening koran 1–24 Nov 2026 (simulasi)")]
    for kind, fn, label in UP:
        if as_user(PIC, dp.upload_program_file, PROG, kind, fn, b64(fn), label=label, redacted=1 if kind == "koran" else 0) is not None:
            done.append("dokumen %s %s" % (kind, fn))
if not frappe.db.get_value("RN Donor Program", PROG, "bank_account_number"):
    if as_user(PIC, dp.set_program_bank, PROG, bank_name="Bank Simulasi", account_number="9001-2026-0711", account_holder="[SIM] UI Peduli Bencana") is not None:
        done.append("rekening")
cov = frappe.db.get_value("RN Donor Program", PROG, "cover_image_url")
if not cov:
    from frappe.utils.file_manager import save_file
    f = save_file("sampul-ui-sekolah-darurat.png", open(os.path.join(A, "il-cover.png"), "rb").read(), "RN Donor Program", PROG, is_private=0)
    frappe.db.set_value("RN Donor Program", PROG, "cover_image_url", f.file_url); frappe.db.commit(); done.append("sampul")

# 3) rencana
if not frappe.db.count("RN Program Milestone", {"program": PROG}):
    for i, (t, due, st, pct) in enumerate([
            ("Asesmen kerusakan, izin pinjam pakai lahan & desain", "2026-11-04", "selesai", 100),
            ("Tender pekerjaan fisik & penandatanganan SPK", "2026-11-11", "selesai", 100),
            ("Pembersihan abu, pondasi umpak & sloof", "2026-11-18", "selesai", 100),
            ("Kolom baja, rangka & penutup atap", "2026-12-01", "berjalan", 70),
            ("Dinding, lantai, kusen, listrik & sanitasi", "2026-12-20", "belum_mulai", 0),
            ("Mebel 160 set, pengecatan & uji kelayakan", "2027-01-08", "belum_mulai", 0),
            ("Serah terima ke sekolah & mulai belajar semester genap", "2027-01-15", "belum_mulai", 0)], 1):
        as_user(PIC, plan.save_plan_item, PROG, "milestone", values={"title": t, "sort_order": i, "due_date": due, "milestone_status": st, "progress_percent": pct})
    done.append("7 milestone")
if not frappe.db.count("RN Program Location", {"program": PROG}):
    for t, la, lo, st in [("Lokasi bangun: SDN 1 Way Urang, Kalianda", -5.7258577, 105.5874507, "belum_terlayani"),
                          ("Kelas tenda sementara: shelter GOR Kalianda", -5.7248498, 105.5905894, "terlayani")]:
        as_user(PIC, plan.save_plan_item, PROG, "location", values={"title": t, "latitude": la, "longitude": lo, "location_status": st})
    done.append("2 lokasi")
if not frappe.db.count("RN Program Need", {"program": PROG}):
    for item, kind, need, avail, unit, by in [("Spandek pasir 0,35 + foil", "material", 410, 160, "m2", "2026-11-28"),
                                               ("Papan GRC 9 mm (120x240)", "material", 110, 0, "lembar", "2026-12-05"),
                                               ("Meja + kursi siswa", "material", 160, 0, "set", "2027-01-05"),
                                               ("Buku bacaan anak", "material", 600, 140, "buku", "2027-01-05"),
                                               ("Relawan pengecatan & bersih-bersih", "relawan", 30, 12, "orang", "2027-01-03"),
                                               ("Relawan pendamping belajar (trauma healing)", "relawan", 12, 5, "orang", "2026-12-15")]:
        as_user(PIC, plan.save_plan_item, PROG, "need", values={"item": item, "kind": kind, "qty_needed": need, "qty_available": avail, "unit": unit, "needed_by": by})
    done.append("6 kebutuhan")

# 4) donasi masuk (simulasi) supaya progres masuk akal; tanggal disetel sesuai rekening koran
DON = [("2026-11-03 09:12", "Ikatan Alumni Teknik (simulasi)", 100_000_000, 0, "Untuk adik-adik di Kalianda"),
       ("2026-11-05 14:40", "PT Sinar Nusantara Abadi — CSR (simulasi)", 75_000_000, 0, "Dukungan CSR pendidikan"),
       ("2026-11-06 20:05", "Gerakan Koin Kampus (simulasi)", 18_750_000, 0, "Hasil penggalangan 4 fakultas"),
       ("2026-11-08 07:30", "Donatur", 25_000_000, 1, None),
       ("2026-11-10 16:22", "Paguyuban Warga Lampung di Depok (simulasi)", 7_500_000, 0, "Semoga cepat selesai"),
       ("2026-11-14 12:01", "Rina A. (simulasi)", 1_000_000, 0, None),
       ("2026-11-20 19:45", "Budi S. (simulasi)", 500_000, 0, "Semangat belajar!"),
       ("2026-11-22 06:50", "Komunitas Lari Pagi (simulasi)", 3_250_000, 0, "Hasil fun run amal"),
       ("2026-11-23 21:10", "Hamba Allah (simulasi)", 2_000_000, 1, None),
       ("2026-11-24 08:15", None, 250_000, 0, "Untuk sekolah darurat")]
if not frappe.db.exists("RN Cash Donation", {"donor_program": PROG, "donor_name": DON[0][1]}):
    n = 0
    for i, (ts, name, amt, anon, msg) in enumerate(DON):
        who = "masyarakat.demo@rescue-net.local" if name is None else ("relawan.demo@rescue-net.local" if i % 2 else "pelapor.demo@rescue-net.local")
        r = as_user(who, dp.create_cash_donation, PROG, amt, is_anonymous=anon, message=msg, donor_name=name)
        if not r: continue
        d = r.get("donation") or r.get("name")
        if i < 8:
            as_user(PIC, dp.decide_cash_donation, d, "confirm")
        frappe.db.sql("update `tabRN Cash Donation` set creation=%s, modified=%s where name=%s", (ts, ts, d))
        if i < 8:
            frappe.db.sql("update `tabRN Cash Donation` set confirmed_at=%s where name=%s", (ts, d))
        n += 1
    frappe.db.commit(); done.append("%d donasi (8 dikonfirmasi, 2 menunggu)" % n)

# 5) kabar lapangan + penggunaan dana (budget_spent bertambah lewat API)
UPD = [("2026-11-05 17:00", "Pembersihan abu & pengukuran lahan selesai", "spending", 8, 21_500_000,
        "Abu vulkanik 620 m2 diangkut, bouwplank 110 m' terpasang, papan nama & APD tersedia. Kuitansi 001-003. (SIMULASI)"),
       ("2026-11-12 10:00", "SPK kontraktor ditandatangani, uang muka 20%", "spending", 12, 119_700_000,
        "Pemenang tender CV Bangun Cepat (Rp 598.500.000, 35 hari kerja). Uang muka 20% dibayar dengan jaminan uang muka. (SIMULASI)"),
       ("2026-11-18 16:30", "Pondasi umpak 30 titik & sloof 138 m' selesai", "progress", 26, 0,
        "Uji slump beton & pemeriksaan tulangan oleh pengawas. Foto: lihat Gambar Rencana > Progres. (SIMULASI)"),
       ("2026-11-20 11:00", "DP 30% mebel 160 set meja-kursi", "spending", 28, 30_333_000,
        "Pesanan ke pengrajin lokal Kalianda agar uang berputar di daerah terdampak; kirim awal Januari. (SIMULASI)"),
       ("2026-11-24 15:00", "Kolom baja & rangka atap baja ringan terpasang", "progress", 38, 0,
        "24 kolom hollow berdiri, kuda-kuda 70% terpasang. Berikut: penutup atap spandek (stok 160 dari 410 m2). (SIMULASI)")]
if not frappe.db.exists("RN Donor Program Update", {"program": PROG, "update_title": UPD[0][1]}):
    for ts, t, ty, pct, spent, note in UPD:
        r = as_user(PIC, dp.create_special_program_update, PROG, t, update_type=ty, progress_percent=pct, amount_spent=spent, update_notes=note,
                    officer_in_charge_name="[SIM] Koordinator Program UI Peduli")
        if r:
            frappe.db.sql("update `tabRN Donor Program Update` set observed_at=%s, creation=%s where name=%s", (ts, ts, r["update"]))
    frappe.db.commit(); done.append("5 kabar lapangan")

# 6) bukti foto (RN Evidence File terhubung ke program)
for old in frappe.get_all("RN Evidence File", {"linked_object_id": PROG, "file_path": ["like", "/private/%"]}, pluck="name"):
    frappe.db.set_value("RN Evidence File", old, "visibility", "internal")   # berkas privat = gambar rusak di halaman publik
    done.append("bukti lama %s (berkas privat) disembunyikan" % old)
if not frappe.db.exists("RN Evidence File", {"linked_object_id": PROG, "title": ["like", "%ilustrasi SIMULASI%"]}):
    wd = json.loads(frappe.db.get_value("RN Donor Program", PROG, "work_drawings") or "[]")
    for key, title, ts in [("il-kondisi", "Kondisi awal sekolah & kelas tenda (ilustrasi SIMULASI)", "2026-11-03 08:00"),
                           ("il-p1", "Pondasi & sloof selesai (ilustrasi SIMULASI)", "2026-11-18 16:30"),
                           ("il-p2", "Kolom & rangka atap terpasang (ilustrasi SIMULASI)", "2026-11-24 15:00")]:
        url = next((d["url"] for d in wd if key in d["url"]), None)
        if not url: continue
        e = frappe.get_doc({"doctype": "RN Evidence File", "legacy_id": "evidence-sim-uip-" + key, "legacy_source": "seed-simulasi", "title": title, "disaster_event": ev, "linked_object_type": "RN Donor Program",
                            "linked_object_id": PROG, "evidence_type": "photo", "filename": url.rsplit("/", 1)[-1], "file_path": url,
                            "mime_type": "PNG", "verification_status": "verified", "visibility": "public"}).insert(ignore_permissions=True)
        frappe.db.sql("update `tabRN Evidence File` set creation=%s where name=%s", (ts, e.name))
    frappe.db.commit(); done.append("3 bukti foto")

# 7) tender & penawaran disamakan dengan RAB
wd = json.loads(frappe.db.get_value("RN Donor Program", PROG, "work_drawings") or "[]")
rab_pdf = next((d["url"] for d in wd if "rab-sekolah-darurat" in d["url"]), None)
tampak = next((d["url"] for d in wd if "tampak" in d["url"]), None)
if frappe.db.exists("RN Procurement Tender", TENDER) and rab_pdf:
    frappe.db.set_value("RN Procurement Tender", TENDER, {"rab_total": FISIK, "rab_document_url": rab_pdf, "design_image_url": tampak or "",
        "scope_description": "Pekerjaan fisik I–X RAB: sekolah darurat semi-permanen 4 ruang kelas 7x8 m + ruang guru 4x8 m + selasar 2 m + toilet 4 bilik, "
                             "sumur bor & tandon, listrik 3.500 VA. Kolom baja hollow, rangka atap baja ringan, dinding GRC. Waktu 35 hari kerja. (SIMULASI)"})
    if frappe.db.exists("RN Tender Bid", BID):
        frappe.db.set_value("RN Tender Bid", BID, {"bid_amount": KONTRAK, "bid_days": 35,
            "proposal_summary": "Penawaran Rp 598.500.000 (98% HPS), 35 hari kerja, tim 18 tukang + 2 mandor, garansi pemeliharaan 90 hari. (SIMULASI)"})
    frappe.db.commit(); done.append("tender & penawaran diselaraskan")

frappe.db.commit()
r = frappe.db.get_value("RN Donor Program", PROG, ["budget_target", "budget_received", "budget_spent"], as_dict=True)
print("\nUI_PEDULI target", r.budget_target, "terkumpul", r.budget_received, "terpakai", r.budget_spent)
for d in done: print("DONE", d)
for f in found: print("TEMUAN", f)
