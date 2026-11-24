"""Data fiktif untuk Gempa Simulasi Aceh Barat, 24 November 2026."""
EVENT = "disaster_events:event-sim-001"
PLANS = {
    "24ea13d2e0a8": (
        "psychosocial", "Dukungan psikososial anak",
        "96 anak dalam kelompok kecil", "Sesi bermain dan menggambar terbimbing, tanpa publikasi identitas anak.",
        "Pemetaan kebutuhan anak", "Penyiapan kit bermain", "Sesi bermain kelompok", "Evaluasi fasilitator",
        35_000_000, 12_000_000, 35_000_000, 0, 4_800_000, "733822", None,
        [
            ("Fasilitator kegiatan anak", 48, "sesi", 300000),
            ("Pendamping kelompok", 48, "sesi", 150000),
            ("Kit bermain dan alat gambar", 24, "set", 275000),
            ("Alas duduk lipat dan kotak simpan", 12, "set", 250000),
            ("Snack dan air peserta", 240, "porsi", 12500),
            ("Transport kit dan relawan", 8, "rit", 100000),
        ],
    ),
    "2e3020faa479": (
        "energy_support", "PLTS posko",
        "1 posko dengan beban prioritas", "Panel → pengaman DC → inverter dan baterai → jalur lampu, radio, dan pengisian perangkat.",
        "Audit beban dan atap", "Pengadaan PLTS", "Pemasangan dan pengujian beban", "Serah terima dan pelatihan",
        30_000_000, 5_000_000, 50_000_000, 8_000_000, 15_000_000, "211666", None,
        [
            ("Panel surya 550 Wp", 6, "unit", 2300000),
            ("Baterai LiFePO4 48 V 100 Ah", 1, "unit", 15300000),
            ("Inverter hibrida 3 kW", 1, "unit", 7500000),
            ("Rangka dan pengikat panel", 6, "set", 600000),
            ("Proteksi DC/AC, kabel dan pentanahan", 1, "paket", 4800000),
            ("Pemasangan, pengujian dan pelatihan", 2, "hari tim", 2500000),
        ],
    ),
    "6e945dc35c1e": (
        "nutrition", "Pemberian makanan tambahan",
        "120 anak × 10 hari layanan", "Rotasi menu nasi, telur/tempe, sayur labu dan pisang. Verifikasi porsi serta alergi oleh petugas.",
        "Pendataan anak dan alergi", "Siapkan bahan dan dapur", "Masak dan bagikan PMT", "Rekap porsi dan evaluasi",
        42_000_000, 21_000_000, 60_000_000, 6_000_000, 8_400_000, "275296", None,
        [
            ("Beras", 120, "kg", 17000),
            ("Telur", 840, "butir", 2700),
            ("Tempe", 120, "kg", 24000),
            ("Labu dan sayur hijau", 210, "kg", 20000),
            ("Buah dan susu UHT", 1200, "porsi", 10500),
            ("Minyak, bumbu dan air matang", 1200, "porsi", 3500),
            ("Kemasan makanan", 1200, "set", 3000),
            ("Tim dapur", 40, "orang-hari", 400000),
            ("Antar makanan", 20, "rit", 350000),
            ("Gas dan sanitasi dapur", 8, "set", 625000),
            ("Termometer makanan", 2, "unit", 106000),
        ],
    ),
    "83d25e5a39f5": (
        "special_program", "Paket kebersihan keluarga",
        "100 paket keluarga", "Isi per keluarga: sabun, sikat dan pasta gigi, pembalut, deterjen serta ember bertutup.",
        "Pendataan kebutuhan keluarga", "Siapkan isi paket kebersihan", "Rakit dan distribusikan paket", "Rekap tanda terima",
        250_000, 128_000, 15_000_000, 6_250_000, 2_872_000, "793332", "sim-ui-peduli@example.org",
        [
            ("Sabun mandi", 400, "batang", 6000),
            ("Sikat gigi", 400, "buah", 5000),
            ("Pasta gigi", 200, "tube", 12000),
            ("Pembalut", 200, "pak", 12000),
            ("Deterjen", 100, "pak", 10000),
            ("Ember bertutup", 100, "buah", 38000),
            ("Pengemasan dan distribusi", 100, "paket", 10000),
        ],
    ),
    "d346ff392f8e": (
        "special_program", "Paket logistik posko",
        "140 paket keluarga", "Penerimaan → timbang dan periksa → rakit paket → muat sesuai daftar penerima.",
        "Pemetaan kebutuhan logistik", "Siapkan stok dan kemasan", "Rakit dan salurkan paket", "Cocokkan stok dan tanda terima",
        250_000, 134_000, 30_000_000, 10_750_000, 4_866_000, "575447", "sim-kompastv@example.org",
        [
            ("Beras (5 kg per paket)", 700, "kg", 16000),
            ("Minyak (1 L per paket)", 140, "liter", 20000),
            ("Ikan kaleng (2 per paket)", 280, "kaleng", 21000),
            ("Mi kering (4 per paket)", 560, "bungkus", 4500),
            ("Karton, pelabelan dan pengemasan", 140, "paket", 10000),
            ("Kendaraan distribusi", 8, "rit", 650000),
            ("Timbang dan alat kebersihan posko", 2, "set", 500000),
        ],
    ),
    "d743d5d52ba8": (
        "water_sanitation", "Air bersih posko",
        "3 titik layanan air", "Pasokan air → toren tertutup → filter sedimen dan karbon → titik isi. Uji kualitas sebelum penyaluran.",
        "Cek lokasi dan pasokan air", "Pengadaan toren dan filter", "Pasang dan uji jaringan air", "Serah terima titik air",
        40_000_000, 18_000_000, 40_000_000, 0, 8_400_000, "436667", None,
        [
            ("Toren 2.000 liter", 3, "unit", 4600000),
            ("Dudukan toren dan alas rata", 3, "set", 2300000),
            ("Pipa PVC dan sambungan", 100, "meter", 40000),
            ("Filter sedimen dan karbon", 3, "set", 1700000),
            ("Keran dan katup", 6, "set", 400000),
            ("Uji mutu air dan sanitasi", 6, "uji", 500000),
            ("Instalasi dan pengiriman", 3, "titik", 1600000),
        ],
    ),
    "e065907513c7": (
        "health", "Layanan kesehatan keliling",
        "8 kunjungan klinik bergerak", "Registrasi → skrining dasar → konsultasi petugas → obat sesuai keputusan klinis atau rujukan.",
        "Susun jadwal kunjungan", "Siapkan stok klinik", "Kunjungan dan rujukan", "Rekap layanan tanpa identitas pasien",
        25_000_000, 24_500_000, 25_000_000, 10_000_000, 5_500_000, "159252", None,
        [
            ("Dokter layanan keliling", 8, "hari", 850000),
            ("Perawat dan petugas registrasi", 16, "hari", 425000),
            ("Obat dan bahan medis habis pakai", 8, "paket sesi", 1650000),
            ("BBM", 240, "liter", 14500),
            ("Kendaraan dan pengemudi", 8, "hari", 650000),
            ("Pengelolaan limbah medis", 8, "sesi", 315000),
        ],
    ),
    "eb590551280a": (
        "education", "Kelas pemulihan belajar",
        "4 kelompok belajar, 120 siswa", "Belajar bergilir, masing-masing 30 siswa. Isi kit: buku tulis, alat tulis, map dan bahan latihan.",
        "Asesmen ketertinggalan belajar", "Siapkan ruang dan kit siswa", "Kelas bergilir dan peminjaman buku", "Evaluasi dan serah terima alat",
        90_000_000, 60_000_000, 150_000_000, 12_000_000, 13_200_000, "409069", None,
        [
            ("Kit alat tulis dan buku latihan", 120, "set", 200000),
            ("Meja belajar dan bangku", 60, "set", 1050000),
            ("Buku bacaan berjenjang", 240, "buku", 65000),
            ("Papan tulis dan rak", 4, "set", 2250000),
            ("Tutor kelas pemulihan", 96, "sesi", 300000),
            ("Bahan kegiatan dan kebersihan", 48, "sesi", 125000),
            ("Angkutan perabot dan kit", 6, "rit", 600000),
        ],
    ),
    "ed5431a4c682": (
        "general_relief", "Paket sembako dan bantuan keluarga",
        "4.000 keluarga dalam beberapa gelombang", "Paket pangan dan kebersihan dirakit per KK. Bantuan hunian diprioritaskan bagi 800 KK berdasarkan asesmen simulasi.",
        "Pemetaan keluarga penerima", "Siapkan stok gelombang pertama", "Distribusi pangan dan hunian", "Rekap distribusi dan audit stok",
        5_500_000, 2_056_000, 1_500_000_000, 44_500_000, 12_944_000, "445175", "sim-kompastv@example.org",
        [
            ("Beras 10 kg per keluarga", 40000, "kg", 16000),
            ("Minyak 2 liter per keluarga", 8000, "liter", 20000),
            ("Lauk awet 3 kaleng per keluarga", 12000, "kaleng", 22000),
            ("Paket sabun dan perlengkapan cuci", 4000, "paket", 44000),
            ("Terpal keluarga untuk hunian sementara", 800, "buah", 160000),
            ("Gudang, sortir dan angkutan gelombang", 80, "rit", 1250000),
            ("Karton, label dan pengemasan", 4000, "paket", 8000),
        ],
    ),
}

LOCATIONS = [
    ("Desa Suak Indrapuri", "Titik layanan utama", 4.1437, 96.1274),
    ("Desa Ujong Baroh", "Titik penjangkauan", 4.1440513, 96.1288997),
    ("Desa Padang Seurahet", "Titik penerimaan perlengkapan", 4.1432691, 96.127481),
]

# Kemajuan dihitung sebagai bagian dari target pelayanan, bukan rasio kas.
PROGRESS = dict(zip(PLANS, (40, 20, 50, 20, 15, 33, 63, 46, 2)))


COUNTS = {
    "24ea13d2e0a8": (4, 3, 5, 3, 6),
    "2e3020faa479": (4, 3, 5, 2, 6),
    "6e945dc35c1e": (4, 3, 5, 3, 6),
    "83d25e5a39f5": (4, 3, 5, 2, 1),
    "d346ff392f8e": (4, 3, 5, 2, 1),
    "d743d5d52ba8": (4, 3, 5, 3, 6),
    "e065907513c7": (4, 3, 5, 3, 6),
    "eb590551280a": (4, 3, 5, 3, 6),
    "ed5431a4c682": (4, 3, 5, 2, 3),
}

# Stok yang telah disiapkan untuk lima kebutuhan yang terlihat di papan program.
AVAILABLE = {
    "24ea13d2e0a8": (20, 20, 12, 12, 96),
    "2e3020faa479": (4, 0, 0, 4, 0),
    "6e945dc35c1e": (65, 420, 60, 105, 600),
    "83d25e5a39f5": (160, 120, 60, 60, 20),
    "d346ff392f8e": (150, 25, 50, 100, 30),
    "d743d5d52ba8": (2, 1, 60, 1, 3),
    "e065907513c7": (5, 10, 6, 150, 5),
    "eb590551280a": (80, 32, 144, 2, 44),
    "ed5431a4c682": (1000, 200, 300, 100, 20),
}
OUTPUTS = dict(zip(PLANS, ((48, 19), (1, 0), (1200, 600), (100, 20), (140, 21),
                           (3, 1), (8, 5), (96, 44), (4000, 80))))
FIELD_REPORTS = {
    "24ea13d2e0a8": "Sebanyak 19 dari 48 sesi bermain sudah berlangsung. Dana tahap ini menutup fasilitator, pendamping dan pengisian ulang kit.",
    "2e3020faa479": "Empat panel sudah diterima. Rangka masih disiapkan dan posko belum dialiri PLTS. Dana tahap ini mencakup panel dan rangka.",
    "6e945dc35c1e": "Dapur telah menyalurkan 600 dari 1.200 porsi. Dana tahap ini digunakan untuk bahan segar, dapur dan pengantaran.",
    "83d25e5a39f5": "Paket pertama diterima 20 keluarga. Dana tahap ini mencakup isi paket, ember bertutup dan distribusi awal.",
    "d346ff392f8e": "Sebanyak 21 dari 140 paket sudah keluar dari posko. Dana tahap ini mencakup stok beras dan lauk serta pengantaran.",
    "d743d5d52ba8": "Satu dari tiga titik sudah melayani pengisian. Dua toren tersedia. Dana tahap ini mencakup pemasangan dan uji mutu titik pertama.",
    "e065907513c7": "Tim menuntaskan lima dari delapan kunjungan. Dana tahap ini meliputi tenaga, isi ulang stok klinik, BBM dan pengelolaan limbah.",
    "eb590551280a": "Sebanyak 44 dari 96 sesi tutor sudah berlangsung. Dana tahap ini mencakup honor tutor, buku latihan dan angkutan meja.",
    "ed5431a4c682": "Penyaluran dimulai untuk 80 dari 4.000 keluarga. Dana tahap ini mencakup paket pangan gelombang pertama dan angkutan.",
}


def programs():
    for key, fields in PLANS.items():
        (kind, title, target, guide, *tail) = fields
        (survey, procure, operate, close, opening_in, opening_out, old_target, added, spent, bank, pic, lines) = tail
        total = sum(qty * price for _, qty, _, price in lines)
        donations = [("22 Nov 2026", "[SIM] Lingkar Warga Pesisir Fiktif", added * 4 // 5),
                     ("23 Nov 2026", "[SIM] Nara Rimba Fiktif", added - added * 4 // 5)] if added else []
        yield dict(key=key, id="rn-donor-" + key, kind=kind, title=title, target=target, guide=guide,
                   steps=(survey, procure, operate, close), initial=(opening_in, opening_out, old_target),
                   terminal=(opening_in + added, opening_out + spent), spent=spent, bank="900-SIM-" + bank,
                   pic=pic or "Administrator", lines=lines, total=total, donations=donations,
                   progress=PROGRESS[key], counts=COUNTS[key], outputs=OUTPUTS[key], available=AVAILABLE[key], report=FIELD_REPORTS[key])
