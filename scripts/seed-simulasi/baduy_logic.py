"""Simulasi lengkap kebakaran Kampung Baduy Luar (owner 24 Nov 2026: "buat simulasi program lengkap ... dari berita
pandeglangnews 21 Nov 2026: 21 rumah warga Baduy Luar hangus, akan dibangun kembali"; "untuk Baduy ada laporan
bencana, dan ada program khusus pembangunan rumah"). SEMUA DATA SIMULASI. Pemrakarsa DISAMARKAN (bukan nama tokoh
asli): program donasi palsu atas nama orang sungguhan bisa menyesatkan. Angka RAB = perkiraan contoh.
Dibuat lewat API RN sebagai akun demo sesuai perannya; idempoten (dicari dulu). Gambar = ilustrasi bertanda SIMULASI.
Dipakai lewat scripts/seed-simulasi/baduy.py (gabungan gambar base64 + berkas ini)."""
import base64, json
import frappe
from frappe.utils import add_days, nowdate, now_datetime, getdate

found, done = [], []
TITLE = "[SIMULASI] Kebakaran Kampung Baduy Luar — Lebak 2026"
LAT, LNG = -6.6176, 106.2295
LOC = "Kampung Baduy Luar, Desa Kanekes, Kec. Leuwidamar, Kab. Lebak, Banten (SIMULASI)"
U = lambda n: n + ".demo@rescue-net.local"
B64 = lambda k: IMAGES[k]


def as_user(email, fn, *a, **kw):
    frappe.set_user(email)
    try:
        r = fn(*a, **kw); frappe.db.commit(); return r
    except Exception as e:
        frappe.db.rollback(); found.append("%s @%s: %s: %s" % (getattr(fn, "__name__", fn), email.split("@")[0], type(e).__name__, str(e)[:180])); return None
    finally:
        frappe.set_user("Administrator")


def pdf(title, lines):
    esc = lambda s: s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    body = ["BT /F1 16 Tf 50 800 Td (" + esc(title) + ") Tj ET", "BT /F1 9 Tf 50 784 Td (SIMULASI - bukan dokumen asli; angka perkiraan contoh) Tj ET"]
    y = 760
    for ln in lines:
        body.append("BT /F1 10 Tf 50 %d Td (%s) Tj ET" % (y, esc(ln))); y -= 15
    stream = "\n".join(body).encode("latin-1", "replace")
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
            b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream", b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>"]
    import io
    out = io.BytesIO(); out.write(b"%PDF-1.4\n"); offs = []
    for i, o in enumerate(objs, 1):
        offs.append(out.tell()); out.write(b"%d 0 obj\n" % i + o + b"\nendobj\n")
    x = out.tell(); out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1))
    for o in offs: out.write(b"%010d 00000 n \n" % o)
    out.write(b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, x))
    return base64.b64encode(out.getvalue()).decode()


rp = lambda v: "Rp " + "{:,.0f}".format(v).replace(",", ".")
# ---- RAB per rumah (perkiraan contoh) ----
PER_HOUSE = [("Kayu tiang & balok (rasamala/albasia)", 6_500_000), ("Bambu lantai, dinding anyaman (bilik) & rangka", 4_200_000),
             ("Atap daun kiray / ijuk", 3_800_000), ("Tali rotan, ijuk & pasak kayu (tanpa paku, aturan adat)", 600_000),
             ("Upah tukang adat & konsumsi gotong royong", 5_500_000), ("Angkut bahan (dipikul, tanpa kendaraan)", 1_400_000),
             ("Perabot dasar: tungku beralas tanah liat, tikar, alat dapur", 1_500_000)]
house = sum(v for _, v in PER_HOUSE)
lumbung = 2 * 6_000_000
sub = 21 * house + lumbung
adm = round(sub * 0.02, -3)
cad = round(sub * 0.05, -3)
TOTAL = sub + adm + cad
RAB_LINES = ["A. Per rumah (x 21 rumah):"] + ["   %-58s %15s" % (n[:58], rp(v)) for n, v in PER_HOUSE] + [
    "   %-58s %15s" % ("Subtotal per rumah", rp(house)), "",
    "   21 rumah x %s %32s" % (rp(house), rp(21 * house)),
    "B. 2 lumbung padi (leuit) x Rp 6.000.000 %26s" % rp(lumbung),
    "C. Administrasi, dokumentasi & laporan (2%%) %23s" % rp(adm),
    "D. Cadangan harga bahan (5%%) %38s" % rp(cad), "",
    "TOTAL ANGGARAN %52s" % rp(TOTAL), "",
    "Catatan: bahan & tata cara mengikuti aturan adat, disepakati dengan lembaga adat (asumsi simulasi).",
    "Sumber skenario: berita pandeglangnews.co.id 21 Nov 2026 (21 rumah warga Baduy Luar hangus)."]

# ---- 1) Bencana ----
ev = frappe.db.get_value("RN Disaster Event", {"title": TITLE})
if not ev:
    from rescue_net import api_disaster_admin
    r = as_user(U("baduy"), api_disaster_admin.create_event, title=TITLE, event_type="kebakaran", location_summary=LOC,
                latitude=LAT, longitude=LNG, started_at="2026-11-19 16:30:00", severity="high", force=1)
    ev = r and r.get("name")
    done.append("bencana %s (%s)" % (ev, r and r.get("event_status")))
if ev and frappe.db.get_value("RN Disaster Event", ev, "event_status") != "active":
    frappe.db.set_value("RN Disaster Event", ev, "event_status", "active"); frappe.db.commit()   # = disetujui super admin
    done.append("bencana diaktifkan (persetujuan super admin)")
from rescue_net.services import drill
if ev and not drill.is_simulation_event(ev):
    found.append("bencana %s TIDAK terdeteksi simulasi" % ev)

# ---- 2) Kelompok relawan pemrakarsa (perorangan belum bisa memulai program sendiri) ----
ORG_T = "[SIMULASI] Gerakan Bangun Rumah Baduy (relawan perorangan)"
org = frappe.db.get_value("RN Organization", {"title": ORG_T})
if not org:
    from rescue_net import api_community_cluster as cc
    r = as_user(U("baduy"), cc.create_organization, ORG_T, organization_type="community",
                contact_person="[SIMULASI] Relawan pemrakarsa", notes="Kelompok contoh SIMULASI untuk program rumah Baduy")
    org = frappe.db.get_value("RN Organization", {"title": ORG_T})
    done.append("kelompok %s" % org)
if org and frappe.db.get_value("RN Organization", org, "verification_status") not in ("verified", "official_verified", "community_verified"):
    frappe.db.set_value("RN Organization", org, "verification_status", "verified"); frappe.db.commit()
    done.append("kelompok diverifikasi (antrean verifikasi, simulasi)")

# ---- 3) Posko darurat ----
PK_T = "[SIMULASI] Posko Darurat Kebakaran Kanekes"
pk = frappe.db.get_value("RN Posko", {"title": PK_T})
if not pk and ev and org:
    from rescue_net import api_community_cluster as cc
    as_user(U("baduy"), cc.create_posko, PK_T, "shelter", "Balai warga Kampung Kaduketug, Desa Kanekes (SIMULASI)",
            organization=org, disaster_event=ev, latitude=LAT + 0.004, longitude=LNG - 0.003,
            officer_in_charge_name="[SIMULASI] Koordinator Posko", officer_in_charge_phone="081200009007",
            facilities="Tenda keluarga 10 unit, dapur umum 2 tungku, air bersih 3.000 L, pos kesehatan", rn_beneficiary_count=84)
    pk = frappe.db.get_value("RN Posko", {"title": PK_T})
    if pk:
        frappe.db.set_value("RN Posko", pk, {"rn_fn_shelter": 1, "rn_fn_kitchen": 1, "rn_fn_logistics": 1, "rn_logistics_role": "receiver",
                                            "verification_status": "verified", "accept_goods": 1, "accept_donations": 1,
                                            "accept_volunteers": 1, "public_participation": 1}); frappe.db.commit()
        done.append("posko %s" % pk)

# ---- 4) Laporan masyarakat ----
from rescue_net import api_reports
REPORTS = [
    ("pelapor", "Kebakaran permukiman Kampung Baduy Luar, 21 rumah hangus", "Api diduga dari tungku dapur, cepat menjalar karena "
     "rumah berdinding bambu & beratap daun. 21 rumah dan 2 lumbung padi habis. Warga mengungsi ke balai & rumah kerabat. (SIMULASI)",
     "affected_need_help", "critical", 84, "Tenda, terpal, selimut, alat masak, beras"),
    ("masyarakat", "Pengungsi kebakaran Kanekes butuh terpal & alat masak", "Sekitar 21 KK tidur di balai warga dan rumah kerabat. "
     "Perlu terpal, tikar, panci, dan air bersih. Anak-anak dan lansia mulai batuk. (SIMULASI)", "shelter_need", "urgent", 84,
     "Terpal, tikar, panci, air bersih, masker"),
    ("relawan", "Lumbung padi ikut terbakar, cadangan pangan warga habis", "Dua leuit (lumbung padi) terbakar sehingga cadangan "
     "pangan beberapa bulan hilang. Perlu bantuan beras sementara sampai panen. (SIMULASI)", "logistics", "high", 84, "Beras, minyak, garam"),
]
have = set(frappe.get_all("RN Community Report", filters={"disaster_event": ev}, pluck="title")) if ev else set()
for who, t, d, rt, pr, n, needs in REPORTS:
    if ev and t not in have:
        r = as_user(U(who), api_reports.submit_community_report, title=t, description=d, report_type=rt, priority=pr,
                    affected_people_count=n, urgent_needs=needs, location_text=LOC, latitude=LAT, longitude=LNG,
                    consent_to_contact=1, disaster_event=ev)
        if r: done.append("laporan: " + t[:40])

# ---- 5) Program khusus ----
PG_T = "[SIMULASI] Bangun Kembali 21 Rumah Warga Baduy Luar"
prog = frappe.db.get_value("RN Donor Program", {"program_name": PG_T})
from rescue_net import api_donor_program as dp
if not prog and ev and org:
    desc = ("Kebakaran di Kampung Baduy Luar (Desa Kanekes, Lebak) menghanguskan 21 rumah dan 2 lumbung padi. Program ini "
            "membangun kembali 21 rumah panggung bambu sesuai aturan adat bersama warga (gotong royong) dan tukang adat, "
            "ditambah 2 lumbung padi. Bahan dibeli dari sekitar kampung, diangkut dengan dipikul. Jarak antar rumah dibuat "
            "lebih lega sebagai sekat api dan tungku diberi alas tanah liat. Laporan pemakaian dana dan foto progres "
            "diunggah tiap tahap. SIMULASI: skenario dari berita 21 Nov 2026; pemrakarsa disamarkan; angka perkiraan contoh.")
    r = as_user(U("baduy"), dp.create_special_program, ev, PG_T, owner_type="organization", owner_id=org,
                target_location="Desa Kanekes, Leuwidamar, Lebak", target_beneficiaries="21 KK (± 84 jiwa)",
                budget_target=TOTAL, status="active", priority="high", start_date="2026-11-23", end_date="2027-02-28",
                description=desc, officer_in_charge_name="[SIMULASI] Relawan Pemrakarsa", officer_in_charge_phone="081200009007")
    prog = r and (r.get("program") or r.get("name"))
    done.append("program %s" % prog)
if prog:
    as_user(U("baduy"), dp.update_program_info, prog, {"target_description": "21 rumah panggung + 2 lumbung padi, layak huni sebelum musim hujan puncak",
            "location": "Desa Kanekes, Leuwidamar, Lebak", "contact_person": "[SIMULASI] Relawan Pemrakarsa", "contact_phone": "081200009007"})
    row = frappe.db.get_value("RN Donor Program", prog, ["cover_image_url", "work_drawings", "bank_account_number"], as_dict=True)
    if not row.cover_image_url:
        from frappe.utils.file_manager import save_file
        f = save_file("sampul-sim-baduy.png", base64.b64decode(B64("cover")), "RN Donor Program", prog, is_private=0)
        frappe.db.set_value("RN Donor Program", prog, "cover_image_url", f.file_url); frappe.db.commit(); done.append("sampul")
    if not row.bank_account_number:
        if as_user(U("baduy"), dp.set_program_bank, prog, bank_name="Bank Simulasi", account_number="9002100210021",
                   account_holder="[SIM] Gerakan Bangun Rumah Baduy") is not None:
            done.append("rekening")
    wd = row.work_drawings or ""
    UP = [("rab", "rab-sim-baduy.pdf", pdf("RAB - Bangun Kembali 21 Rumah Baduy Luar", RAB_LINES), "RAB lengkap (simulasi)"),
          ("gambar", "denah-sim-baduy.png", B64("plan"), "Denah 21 rumah + 2 lumbung (simulasi)"),
          ("gambar", "rumah-jadi-sim-baduy.png", B64("done"), "Rencana bentuk rumah jadi (ilustrasi simulasi)"),
          ("gambar", "kondisi-sim-baduy.png", B64("burnt"), "Kondisi pasca-kebakaran (ilustrasi simulasi)"),
          ("gambar", "progres-rangka-sim-baduy.png", B64("frame"), "Progres: rangka R1-R4 (ilustrasi simulasi)"),
          ("gambar", "progres-atap-sim-baduy.png", B64("roof"), "Progres: pemasangan atap (ilustrasi simulasi)"),
          ("qris", "qris-sim-baduy.png", B64("qris"), None),
          ("koran", "koran-sim-baduy.pdf", pdf("Rekening koran Nov 2026 - [SIM] Gerakan Bangun Rumah Baduy",
                                              ["21/11  Saldo awal                      Rp 0", "22/11  Donasi masuk (3 transaksi)     Rp 2.750.000",
                                               "23/11  Belanja bambu tahap 1          -Rp 1.200.000"]), "Rekening koran Nov 2026 (simulasi)")]
    for kind, fn, b, label in UP:
        if fn.rsplit(".", 1)[0] in wd:
            continue
        if as_user(U("baduy"), dp.upload_program_file, prog, kind, fn, b, label=label, redacted=1 if kind == "koran" else 0) is not None:
            done.append("dokumen " + kind)
    # rencana: milestone, lokasi, kebutuhan
    from rescue_net.donor_program import plan
    if not frappe.db.count("RN Program Milestone", {"program": prog}):
        for i, (t, due, st, pct) in enumerate([
                ("Asesmen kerusakan & musyawarah dengan lembaga adat", "2026-11-25", "selesai", 100),
                ("Pengadaan bahan adat (kayu, bambu, kiray, ijuk, rotan)", "2026-12-05", "berjalan", 60),
                ("Pembangunan tahap 1: rumah R1-R7", "2026-12-20", "berjalan", 35),
                ("Pembangunan tahap 2: rumah R8-R14", "2027-01-15", "belum_mulai", 0),
                ("Pembangunan tahap 3: rumah R15-R21 + 2 lumbung", "2027-02-10", "belum_mulai", 0),
                ("Serah terima & syukuran adat", "2027-02-28", "belum_mulai", 0)], 1):
            as_user(U("baduy"), plan.save_plan_item, prog, "milestone", values={"title": t, "sort_order": i, "due_date": due,
                                                                               "milestone_status": st, "progress_percent": pct})
        done.append("6 milestone")
    if not frappe.db.count("RN Program Location", {"program": prog}):
        for t, dl, dg, st in [("Klaster A (R1-R8)", 0.001, -0.001, "terlayani"), ("Klaster B (R9-R16)", 0.0, 0.0012, "belum_terlayani"),
                              ("Klaster C (R17-R21) + 2 lumbung", -0.0012, 0.002, "belum_terlayani")]:
            as_user(U("baduy"), plan.save_plan_item, prog, "location", values={"title": t, "latitude": LAT + dl, "longitude": LNG + dg,
                                                                              "location_status": st})
        done.append("3 lokasi")
    if not frappe.db.count("RN Program Need", {"program": prog}):
        for item, kind, need, avail, unit in [("Kayu tiang & balok", "material", 420, 150, "batang"), ("Bambu", "material", 2100, 900, "batang"),
                                               ("Daun kiray / ijuk (ikat)", "material", 3150, 600, "ikat"), ("Tali rotan", "material", 210, 80, "gulung"),
                                               ("Tukang adat", "relawan", 21, 9, "orang"), ("Relawan gotong royong", "relawan", 60, 34, "orang")]:
            as_user(U("baduy"), plan.save_plan_item, prog, "need", values={"item": item, "kind": kind, "qty_needed": need,
                                                                          "qty_available": avail, "unit": unit, "needed_by": "2026-12-20"})
        done.append("6 kebutuhan")
    # kabar lapangan
    if not frappe.db.count("RN Donor Program Update", {"program": prog}) and hasattr(dp, "create_special_program_update"):
        for t, ty, pct, spent, note in [
                ("Asesmen selesai, warga & lembaga adat sepakat tata letak baru", "progress", 10, 0,
                 "Denah 21 rumah disepakati; jarak antar rumah dilebarkan sebagai sekat api. (SIMULASI)"),
                ("Belanja bambu & kayu tahap 1", "spending", 25, 1_200_000, "Bambu 900 batang & kayu 150 batang tiba, dipikul warga. (SIMULASI)"),
                ("Rangka R1-R4 berdiri, atap R1 mulai dipasang", "progress", 35, 0, "Gotong royong 34 warga + 9 tukang adat. (SIMULASI)")]:
            as_user(U("baduy"), dp.create_special_program_update, prog, t, update_type=ty, progress_percent=pct, amount_spent=spent, update_notes=note)
        done.append("3 kabar lapangan")
    # donasi
    if not frappe.db.count("RN Cash Donation", {"donor_program": prog}):
        ids = []
        for who, amt, msg in [("sim-mu-donatur1@example.org", 1_000_000, "Semoga cepat berdiri lagi"), (U("masyarakat"), 250_000, "Untuk warga Baduy"),
                              (U("relawan"), 1_500_000, "Titip untuk bahan atap"), (U("pelapor"), 500_000, None)]:
            r = as_user(who, dp.create_cash_donation, prog, amt, message=msg)
            if r: ids.append(r["donation"])
        for d in ids[:3]:
            as_user(U("baduy"), dp.decide_cash_donation, d, "confirm")
        done.append("%d donasi (3 dikonfirmasi, 1 menunggu)" % len(ids))

# ---- 6) Proyek pemulihan + kebutuhan relawan ----
if ev and org and not frappe.db.exists("RN Recovery Project", {"disaster_event": ev}):
    p = frappe.get_doc({"doctype": "RN Recovery Project", "disaster_event": ev, "project_name": "[SIMULASI] Rekonstruksi 21 rumah Baduy Luar",
                        "owner_type": "organization", "owner_id": org, "target_description": "21 rumah + 2 lumbung padi",
                        "location": "Desa Kanekes, Lebak", "priority": "high", "target_amount": TOTAL, "progress_percent": 35,
                        "status": "in_progress", "start_date": "2026-11-23", "target_finish_date": "2027-02-28",
                        "pic_name": "[SIMULASI] Relawan Pemrakarsa", "pic_phone": "081200009007", "notes": "SIMULASI"})
    try:
        p.insert(ignore_permissions=True); frappe.db.commit(); done.append("proyek pemulihan")
    except Exception as e:
        frappe.db.rollback(); found.append("proyek pemulihan: %s" % str(e)[:160]); p = None
    if p:
        from rescue_net import api_recovery_support as rs
        for role, n in [("Tukang adat (kayu & bambu)", 12), ("Relawan gotong royong angkut bahan", 40)]:
            as_user(U("baduy"), rs.create_volunteer_need, p.name, role, n, date_from=add_days(nowdate(), 3), date_to="2026-12-20",
                    location="Desa Kanekes, Lebak", task_description="Membantu pembangunan rumah tahap 1 (SIMULASI)",
                    requirements="Sehat, siap jalan kaki ± 1 jam, menghormati aturan adat", provisions="Makan 2x sehari")
        done.append("2 kebutuhan relawan")

# ---- 7) Tender bahan atap + penawaran vendor ----
if ev and org and prog and not frappe.db.exists("RN Procurement Tender", {"donor_program": prog}):
    from rescue_net import api_tender
    t = as_user(U("baduy"), api_tender.create_tender, ev, "[SIMULASI] Pengadaan daun kiray & ijuk untuk atap 21 rumah",
                rab_total=21 * 3_800_000, scope_description="3.150 ikat daun kiray/ijuk, diantar ke Kampung Kaduketug (dipikul dari batas kendaraan)",
                location="Desa Kanekes, Lebak", donor_program=prog, organization=org, contact_person="[SIMULASI] Relawan Pemrakarsa",
                contact_phone="081200009007", bidding_opens_at=now_datetime(), bidding_closes_at=add_days(now_datetime(), 10))
    tn = t and (t.get("tender") or t.get("name"))
    if tn:
        done.append("tender %s (%s)" % (tn, t.get("status")))
        b = as_user(U("vendor"), api_tender.submit_bid, tn, "[SIMULASI] CV Bangun Bersama", 76_500_000, bid_days=18,
                    bidder_org="CV Bangun Bersama (contoh)", bidder_contact="081200009006",
                    proposal_summary="Kiray & ijuk dari pengrajin sekitar Leuwidamar, diantar bertahap 3 kali. (SIMULASI)")
        if b: done.append("penawaran vendor")

frappe.db.commit()
print(); print("BADUY_EVENT", ev, "| ORG", org, "| POSKO", pk, "| PROGRAM", prog, "| TOTAL", rp(TOTAL))
for d in done: print("DONE", d)
for f in found: print("TEMUAN", f)
