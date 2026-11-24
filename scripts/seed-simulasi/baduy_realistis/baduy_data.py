"""Data skenario bersama untuk dokumen dan seed Frappe."""

PROGRAM = "rn-donor-fc5d3f8cd6c3"
EVENT = "event-487311176a69"
ORG = "rn-org-64ca7bff722ee216e254"
PIC = "baduy.demo@rescue-net.local"
COORDINATOR = "[SIMULASI] Relawan Pemrakarsa Baduy"
LOCATION = "Cihulu (Baduy Luar), Desa Kanekes, Leuwidamar, Lebak, Banten"
ACCOUNT = "9002100210021"
HOLDER = "[SIM] Gerakan Bangun Rumah Baduy"
QR_TEXT = "SIMULASI RESCUE-NET. QR INI BUKAN PEMBAYARAN. JANGAN TRANSFER."
MARKER = "SIM/RN/BADUY/02"

HOUSE = [
    ("Umpak batu setempat", 12, "buah", 85_000),
    ("Kayu tiang pilihan tukang adat", 12, "batang", 265_000),
    ("Kayu balok, gelagar dan tangga", 18, "batang", 240_000),
    ("Bambu rangka atap dan dinding", 55, "batang", 34_000),
    ("Lantai palupuh bambu", 36, "m²", 85_000),
    ("Dinding bilik bambu (luas bersih)", 48, "m²", 67_500),
    ("Panel penutup atap kiray (termasuk susut)", 76, "m²", 70_000),
    ("Ijuk untuk bubungan", 8, "m", 95_000),
    ("Rotan/serat pengikat", 10, "gulung", 78_000),
    ("Pasak kayu", 1, "paket", 440_000),
    ("Pintu bilik/kayu dan penutup bukaan", 2, "set", 450_000),
    ("Alas tungku tanah liat dan tikar", 1, "paket", 790_000),
    ("Tukang adat", 28, "OH", 180_000),
    ("Pembantu tukang", 18, "OH", 130_000),
    ("Angkut pikul dari titik bongkar", 32, "rit", 55_000),
    ("Persiapan dan pembersihan tapak", 1, "paket", 650_000),
]

LEUIT = [
    ("Umpak dan rangka kayu termasuk penghalang tikus", 1, "paket", 3_450_000),
    ("Bambu, palupuh, bilik, rotan dan pasak", 1, "paket", 2_400_000),
    ("Panel kiray dan bubungan ijuk", 15, "m²", 78_000),
    ("Tukang adat", 9, "OH", 180_000),
    ("Pembantu tukang dan angkut pikul", 1, "paket", 1_550_000),
]


def subtotal(items):
    return sum(qty * rate for _, qty, _, rate in items)


DIRECT_COST = 21 * subtotal(HOUSE) + 2 * subtotal(LEUIT)
SUPPORT = [
    ("Pendampingan adat dan pemeriksaan lapangan", 12, "kunjungan", 450_000),
    ("Administrasi dan laporan", 3, "paket", 1_250_000),
    ("Cadangan perubahan harga (5% biaya langsung)", 1, "alokasi", DIRECT_COST // 20),
]
TOTAL = DIRECT_COST + subtotal(SUPPORT)

# Mutasi pembuka dari catatan program lama.
OPENING = [
    ("22/11/2026", "Donatur Muhammadiyah 1 [SIMULASI]", 1_000_000),
    ("22/11/2026", "Masyarakat Demo", 250_000),
    ("22/11/2026", "Relawan Perorangan Demo [SIMULASI]", 1_500_000),
    ("23/11/2026", "Belanja bambu dan kayu tahap 1", -1_200_000),
]
OPENING_PENDING = 500_000
DONATIONS = [
    ("2026-11-25 08:15:00", "[SIM] Komunitas Rimbun Pangan", 104_000_000, 0, True),
    ("2026-11-26 08:30:00", "[SIM] Paguyuban Pijar Kanekes", 64_000_000, 0, True),
    ("2026-11-27 08:45:00", "", 53_000_000, 1, True),
    ("2026-11-28 09:00:00", "[SIM] Forum Lestari Cisawarna", 42_500_000, 0, True),
    ("2026-11-29 09:20:00", "", 17_750_000, 1, True),
    ("2026-11-30 09:40:00", "[SIM] Kelompok Sapa Ranting", 3_250_000, 0, False),
]
UPDATES = [
    ("2026-12-02 10:00:00", "Pengadaan kayu dan bambu untuk 21 rumah", 25, 119_800_000,
     "Pembayaran material stok bertahap untuk tiga tahap; perakitan awal di R01–R07. Belanja awal Rp1.200.000 dicatat terpisah."),
    ("2026-12-05 11:00:00", "Umpak, palupuh dan bilik", 29, 63_000_000,
     "Umpak, palupuh dan bilik dibeli bertahap untuk tiga tahap, sebagian sudah dipasang."),
    ("2026-12-08 12:00:00", "Upah tukang adat dan angkut pikul", 33, 35_000_000,
     "Upah tahap 1 dan pemikulan bahan lewat jalur setapak dari titik bongkar."),
    ("2026-12-10 13:00:00", "Pembayaran tahap pertama atap kiray dan ijuk", 35, 48_500_000,
     "Pembayaran tahap awal bahan atap dalam skenario. Nilai tender yang sudah tercatat tetap Rp79.800.000."),
    ("2026-12-12 14:00:00", "Kemajuan fisik tertimbang mencapai 35%", 35, 0,
     "R01–R04 mendekati tutup atap, R05–R07 masih perakitan rangka. Umpak R08–R14 disiapkan. "
     "Belum ada rumah yang diserahterimakan. Bobot yang tercapai: persiapan 5, umpak 9, rangka 14, "
     "lantai dan bilik 4, penutup atap 3 poin dari 100."),
]
OPENING_RECEIVED = sum(max(0, change) for _, _, change in OPENING)
OPENING_SPENT = sum(max(0, -change) for _, _, change in OPENING)
RECEIVED = OPENING_RECEIVED + sum(amount for _, _, amount, _, confirmed in DONATIONS if confirmed)
SPENT = OPENING_SPENT + sum(amount for _, _, _, amount, _ in UPDATES)
PENDING = OPENING_PENDING + sum(amount for _, _, amount, _, confirmed in DONATIONS if not confirmed)
