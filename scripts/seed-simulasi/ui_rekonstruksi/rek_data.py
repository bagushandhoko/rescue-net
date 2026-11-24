"""Angka dan tanggal bersama untuk dokumen dan seed. Seluruh data fiktif."""
PROGRAM = "rn-donor-f5fa707a9c62"
EVENT = "disaster_events:event-sim-001"
PIC = "sim-ui-peduli@example.org"
LOCATION = "SD Tunas Pesisir (fiktif), Johan Pahlawan, Aceh Barat"
ACCOUNT = "9002026112402"
HOLDER = "[SIMULASI] UI Peduli Rekonstruksi"
QR_TEXT = "SIMULASI RESCUE-NET — QR CONTOH UI PEDULI. JANGAN TRANSFER. QR INI TIDAK UNTUK PEMBAYARAN."
# Tiga ruang 7 x 8 m = 168 m². Selasar 21 x 2 m = 42 m².
RAB = [
    ("A", "Asesmen, pengamanan dan pembongkaran", [
        ("Asesmen struktur, uji mutu beton dan pemetaan retak", 1, "paket", 14_000_000),
        ("Pagar kerja, penyangga sementara dan K3", 1, "paket", 13_500_000),
        ("Bongkar dinding dan pilah puing", 160, "m²", 85_000),
        ("Bongkar atap dan plafon rusak", 210, "m²", 53_000),
        ("Angkut dan buang puing", 36, "m³", 265_000),
    ]),
    ("B", "Perbaikan fondasi dan rangka beton bertulang", [
        ("Galian lokal dan uruk kembali fondasi", 24, "m³", 245_000),
        ("Beton struktur untuk jaket kolom, balok dan sloof", 12, "m³", 2_050_000),
        ("Baja tulangan, potong, tekuk dan pasang", 1750, "kg", 23_500),
        ("Bekisting dan perancah", 135, "m²", 265_000),
        ("Angkur terpasang pada beton eksisting", 108, "titik", 189_000),
        ("Injeksi retak pada balok yang dipertahankan", 36, "m", 385_000),
    ]),
    ("C", "Atap, penutup dan plafon", [
        ("Kuda-kuda baja galvanis dan pengaku", 256, "m²", 180_000),
        ("Penutup metal berinsulasi, nok dan sekrup", 256, "m²", 225_000),
        ("Talang dan pipa turun", 48, "m", 165_000),
        ("Plafon papan semen dan rangka", 168, "m²", 165_000),
    ]),
    ("D", "Arsitektur dan akses", [
        ("Dinding bata ringan dan pengikat ke rangka", 160, "m²", 193_000),
        ("Plester dan aci dua muka", 320, "m²", 78_000),
        ("Perbaikan alas dan keramik ruang", 168, "m²", 220_000),
        ("Perbaikan lantai selasar antiselip", 42, "m²", 221_000),
        ("Pintu 1,0 × 2,1 m dengan perangkat", 3, "set", 4_200_000),
        ("Jendela 1,5 × 1,2 m dengan ventilasi", 12, "set", 2_500_000),
        ("Cat dinding dan plafon", 488, "m²", 36_000),
        ("Ramp masuk dan pegangan", 1, "paket", 8_500_000),
    ]),
    ("E", "Listrik, keselamatan dan perabot", [
        ("Titik lampu LED terpasang", 18, "titik", 390_000),
        ("Stopkontak terpasang", 12, "titik", 310_000),
        ("Panel, pembumian dan uji instalasi", 1, "paket", 9_500_000),
        ("APAR dan tanda jalur keluar", 3, "set", 1_220_000),
        ("Meja-kursi siswa pengganti; 32 set lama dipakai", 32, "set", 935_000),
        ("Rak buku dengan angkur dan meja baca", 1, "paket", 13_600_000),
    ]),
    ("F", "Pengawasan, verifikasi dan cadangan", [
        ("Pengawasan teknis dan uji mutu pekerjaan", 1, "paket", 15_000_000),
        ("Uji akhir, bersih akhir dan dokumen serah terima", 1, "paket", 6_000_000),
        ("Cadangan pekerjaan tersembunyi", 1, "alokasi", 10_000_000),
    ]),
]
TOTAL = sum(qty * rate for _, _, items in RAB for _, qty, _, rate in items)

# Tanggal, nama fiktif, rupiah, anonim, diterima.
DONATIONS = [
    ("2026-11-04 09:00", "Ikatan Alumni Sipil (SIM)", 80_000_000, 0, True),
    ("2026-11-06 10:00", "Dana CSR Lentera Pesisir (SIM)", 65_000_000, 0, True),
    ("2026-11-09 14:00", "Komunitas Baca Meulaboh (SIM)", 12_500_000, 0, True),
    ("2026-11-13 08:30", "Donatur perorangan (SIM)", 25_000_000, 1, True),
    ("2026-11-17 16:30", "Forum Wali Murid Tunas Pesisir (SIM)", 7_500_000, 0, True),
    ("2026-11-23 13:30", "Bazar Buku Kampus (SIM)", 4_750_000, 0, True),
    ("2026-11-24 09:15", "Sahabat Perpustakaan (SIM)", 2_000_000, 0, False),
]
# Tanggal, judul, progres fisik, pengeluaran inkremental, catatan.
UPDATES = [
    ("2026-11-05 16:00", "Asesmen kerusakan selesai", 0, 14_000_000,
     "Retak berat pada dua kelas dan perpustakaan. Fondasi dipertahankan setelah pemeriksaan. Siswa belajar bergiliran di blok yang aman."),
    ("2026-11-12 16:00", "Area kerja aman dan puing diangkut", 8, 47_770_000,
     "Penyangga, pagar dan K3 dibayar bersama bongkar 160 m² dinding dan 210 m² atap serta angkut 36 m³ puing."),
    ("2026-11-20 16:00", "Termin pertama perkuatan beton", 19, 59_000_000,
     "Pembayaran progres angkur, baja tulangan, bekisting dan pengecoran awal. Lorong kerja masih ditutup untuk siswa."),
    ("2026-11-24 14:00", "Perkuatan beton masih berlangsung", 23, 0,
     "Empat dari delapan kolom sudah dijaket. Pekerjaan balok dan sloof berlanjut. Atap dan pekerjaan ruang dimulai setelah rangka diperiksa."),
]
