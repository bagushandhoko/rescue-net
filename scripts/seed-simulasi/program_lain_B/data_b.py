"""Asumsi skenario 24 November 2026. Nilai awal disalin dari program-lain.tsv."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Program:
    title: str
    kind: str
    area: str
    opening: tuple
    initial_target: int
    account: str
    pic: str
    receipts: tuple
    spending: tuple
    progress: int
    scope: str
    stages: tuple
    stories: tuple
    photos: tuple
    rows: tuple

    @property
    def target(self):
        return sum(qty * price for _, qty, _, price in self.rows)

    @property
    def final(self):
        return self.opening[0] + sum(self.receipts), self.opening[1] + sum(self.spending)


AREAS = {
    "Kalbar": ("event-karhutla-kalbar-2026", (
        ("Sungai Raya, Kubu Raya", -0.07712, 109.38219, "https://www.openstreetmap.org/node/13076749093"),
    )),
    "Riau": ("event-839db8a5e43f", (
        ("Siak Sri Indrapura, Siak", 0.7939, 102.0484, "https://www.openstreetmap.org/node/3478404969"),
        ("Pangkalan Kerinci, Pelalawan", 0.39809, 101.85364, "https://www.openstreetmap.org/way/1050454729"),
    )),
    "Krakatau": ("event-krakatau-2026", (
        ("Way Urang, Kalianda", -5.70951, 105.57749, "https://www.openstreetmap.org/node/1308644580"),
    )),
}

YUSUF = "sim-yusuf@example.org"
PROGRAMS = {
    "a5f8c8c24b92": Program(
        "Perawatan Satwa Terdampak Asap", "wildlife", "Kalbar", (0, 0), 0, "", "",
        (12_500_000, 19_000_000, 9_750_000), (5_400_000, 12_600_000), 28,
        "Dukungan 30 hari untuk hingga 12 satwa dalam perawatan. Penanganan oleh tenaga berwenang dalam skenario.",
        ("Asesmen dan persiapan ruang", "Pemeriksaan awal dan karantina", "Perawatan harian dan evaluasi", "Serah terima catatan perawatan"),
        ("Ruang perawatan dipisah menurut kebutuhan karantina. Pengeluaran awal membiayai asesmen klinis dan sewa kendaraan angkut.",
         "Pakan awal, bahan sanitasi dan perlengkapan kandang diterima. Pemeriksaan lanjutan dijadwalkan per kasus."),
        ("Rencana klinik dengan peti angkut berventilasi", "Progres perlengkapan kandang karantina"),
        (("Pakan spesifik satwa, rata-rata", 360, "satwa-hari", 95_000), ("Pemeriksaan dokter hewan", 24, "kunjungan kasus", 400_000),
         ("Obat dan bahan habis pakai klinik", 12, "paket kasus", 850_000), ("Kandang perawatan berventilasi", 6, "unit", 5_500_000),
         ("Peti angkut berventilasi", 6, "unit", 1_250_000), ("Transport evakuasi dan rujukan", 10, "perjalanan", 1_100_000),
         ("Petugas perawatan", 60, "orang-hari", 250_000), ("Sanitasi kandang", 30, "hari", 160_000))),
    "f1c101763add": Program(
        "Kelas Sementara Saat Asap", "education", "Kalbar", (0, 0), 0, "", "",
        (9_500_000, 14_000_000, 8_300_000), (6_600_000, 9_400_000), 32,
        "Dua kelompok masing-masing 30 siswa, 12 pertemuan per kelompok di ruang aman saat kualitas udara memenuhi syarat.",
        ("Pendataan siswa dan seleksi ruang", "Pengadaan alat belajar dan persiapan ruang", "Kelas kelompok bergilir", "Evaluasi dan penutupan"),
        ("Dua kelompok belajar dipetakan. Sewa ruang awal dan pembelian tikar serta papan tulis dicatat.",
         "Kit tahap pertama disusun. Sesi awal memakai materi literasi dan berhitung, dengan jadwal cadangan bila asap memburuk."),
        ("Rencana ruang belajar sementara", "Progres penyiapan alat tulis dan bahan bacaan"),
        (("Kit siswa: buku tulis, pensil dan map", 60, "set", 145_000), ("Bahan literasi dan numerasi", 60, "set", 95_000),
         ("Fasilitator, dua per pertemuan", 48, "orang-sesi", 250_000), ("Ruang belajar tertutup", 12, "hari", 550_000),
         ("Papan tulis dan perlengkapan", 2, "set", 1_200_000), ("Tikar kelas", 12, "lembar", 240_000),
         ("Sewa pemurni HEPA", 24, "unit-hari", 300_000), ("Transport bahan dan logistik", 12, "hari", 300_000))),
    "fc21b9e567d1": Program(
        "Layanan Kesehatan Keliling Saat Asap", "health", "Kalbar", (0, 0), 0, "", "",
        (10_000_000, 17_500_000, 12_500_000), (6_400_000, 11_600_000), 29,
        "Sepuluh putaran layanan kesehatan keliling untuk hingga 400 skrining keluhan asap dan rujukan bila diperlukan.",
        ("Pemetaan rute dan persediaan", "Putaran skrining awal", "Putaran lanjutan dan rujukan", "Rekap layanan"),
        ("Rute aman dan tempat berhenti ditentukan. Dana awal untuk sewa kendaraan, skrining dasar dan logistik.",
         "Putaran pertama menguji alur registrasi, pengukuran saturasi dan rujukan. Stok diperiksa sebelum keberangkatan berikutnya."),
        ("Rencana kendaraan layanan keliling", "Progres penyusunan perlengkapan skrining"),
        (("Dokter jaga", 10, "orang-hari", 1_000_000), ("Dua perawat per putaran", 20, "orang-hari", 450_000),
         ("Apoteker atau tenaga farmasi", 10, "orang-hari", 400_000), ("Obat dan bahan habis pakai sesuai asesmen", 400, "kunjungan", 45_000),
         ("Sewa kendaraan", 10, "hari", 850_000), ("BBM dan logistik rute", 10, "putaran", 350_000),
         ("Oksimeter dan alat tekanan darah", 4, "set", 850_000), ("Perlindungan petugas dan sanitasi", 10, "paket", 420_000),
         ("Dukungan perjalanan rujukan", 12, "perjalanan", 450_000))),
    "8861d9b89083": Program(
        "Peduli Asap — Ruang Udara Bersih", "special_program", "Riau", (31_100_000, 29_400_000),
        150_000_000, "7000987654", "sim-mu-lazismu@example.org",
        (16_000_000, 22_500_000, 11_500_000), (7_800_000, 13_600_000), 38,
        "Empat ruang aman asap dengan dua unit HEPA per ruang, sensor PM2.5 dan petugas bergilir selama 30 hari.",
        ("Pilih ruang tertutup dan ukur udara awal", "Pasang dan uji unit HEPA", "Operasikan empat ruang bergilir", "Rekap kualitas udara dan serah terima"),
        ("Satu ruang percontohan diuji dengan pencatatan PM2.5 sebelum dan sesudah penyaringan. Belanja meliputi sensor dan penyekat celah.",
         "Ruang kedua mulai disiapkan. Cadangan filter dan jadwal perawatan dicatat sebelum pembukaan ruang berikutnya."),
        ("Rencana ruang aman asap dengan pemurni HEPA", "Progres penyiapan alat pantau PM2.5"),
        (("Pemurni HEPA dengan CADR sesuai volume ruang", 8, "unit", 6_500_000), ("Filter pengganti", 16, "unit", 750_000),
         ("Sensor PM2.5", 8, "unit", 1_650_000), ("Penyekat celah dan perbaikan ringan", 4, "ruang", 3_500_000),
         ("Petugas ruang aman", 120, "orang-hari", 250_000), ("Kebersihan dan sanitasi", 120, "ruang-hari", 85_000),
         ("Listrik operasional", 120, "ruang-hari", 40_000), ("Pengiriman dan pemasangan", 4, "lokasi", 1_750_000),
         ("Pencatatan dan kalibrasi pembanding", 4, "paket", 1_700_000))),
    "51054addc87c": Program(
        "Pemulihan Jembatan Pejalan Kaki", "infrastructure", "Krakatau", (0, 0), 500_000_000, "", YUSUF,
        (35_000_000, 58_000_000, 32_000_000), (15_000_000, 43_000_000), 18,
        "Satu jembatan pejalan kaki konseptual, bentang 12 m dan lebar 2 m. Desain akhir mengikuti pemeriksaan tanah dan struktur.",
        ("Survei, kajian tanah dan desain", "Pesan baja dan siapkan akses", "Bangun tumpuan dan pasang rangka", "Uji beban dan serah terima"),
        ("Survei tepi saluran dan kajian tanah awal dicatat. Titik peta adalah area simulasi di darat.",
         "Uang muka fabrikasi dan pengamanan lokasi dicatat. Pemasangan menunggu verifikasi tumpuan."),
        ("Kondisi awal akses penyeberangan pejalan kaki", "Rencana fabrikasi rangka baja"),
        (("Survei, kajian tanah, gambar dan hitungan", 1, "paket", 24_000_000), ("Pengamanan dan akses sementara", 1, "paket", 18_000_000),
         ("Galian, pemadatan dan urugan", 60, "m³", 320_000), ("Beton tumpuan terpasang", 28, "m³", 1_850_000),
         ("Tulangan tumpuan terpasang", 2400, "kg", 22_000), ("Rangka baja galvanis fabrikasi", 4900, "kg", 39_000),
         ("Lantai antiselip dan sambungan", 24, "m²", 1_800_000), ("Pegangan dan pagar", 24, "m", 950_000),
         ("Dudukan dan angkur", 4, "set", 4_500_000), ("Mobilisasi dan angkat rangka", 1, "paket", 32_000_000),
         ("Uji beban dan inspeksi", 1, "paket", 27_100_000))),
    "55082529134c": Program(
        "Dukungan Psikososial Anak dan Keluarga", "psychosocial", "Krakatau", (60_000_000, 20_000_000),
        150_000_000, "", YUSUF, (10_000_000, 12_500_000, 8_500_000), (9_200_000, 11_400_000), 42,
        "24 sesi untuk hingga 120 anak dan 8 sesi untuk pengasuh, dengan fasilitator, kit bermain dan jalur rujukan.",
        ("Pemetaan kebutuhan dan pelatihan fasilitator", "Sesi awal dan distribusi kit", "Sesi terjadwal untuk anak dan pengasuh", "Evaluasi dan tindak lanjut"),
        ("Fasilitator menyiapkan ruang aman dengan alur kedatangan dan persetujuan pengasuh. Belanja mencakup materi dan kit awal.",
         "Kegiatan bermain kelompok dan pertemuan pengasuh mulai bergilir. Catatan program memakai rekap tanpa identitas anak."),
        ("Rencana ruang kegiatan psikososial", "Progres penyiapan kit bermain dan menggambar"),
        (("Fasilitator anak, tiga per sesi", 72, "orang-sesi", 530_000), ("Fasilitator pengasuh, dua per sesi", 16, "orang-sesi", 650_000),
         ("Supervisi klinis dan rujukan", 12, "sesi", 900_000), ("Kit anak: permainan, krayon dan buku", 120, "paket", 195_000),
         ("Bahan bermain dan sanitasi bersama", 24, "sesi", 450_000), ("Sewa ruang dan kebersihan", 32, "sesi", 650_000),
         ("Transport fasilitator dan perlengkapan", 32, "sesi", 430_000), ("Orientasi keselamatan anak", 2, "angkatan", 4_500_000),
         ("Rekap, umpan balik dan evaluasi", 1, "paket", 12_880_000))),
    "9577ecefacc5": Program(
        "Bantuan Paket Kebutuhan Dasar", "general_relief", "Krakatau", (9_250_000, 0),
        2_000_000_000, "", "sim-kompastv@example.org",
        (28_000_000, 46_500_000, 65_000_000), (22_400_000, 52_600_000), 4,
        "5.000 paket pangan untuk 2.500 rumah tangga dalam dua putaran. Paket berisi beras, minyak, lauk, mi dan gula.",
        ("Verifikasi daftar rumah tangga dan spesifikasi", "Pengadaan dan pilot 200 paket", "Distribusi susulan dalam dua putaran", "Rekonsiliasi dan penutupan"),
        ("Daftar penerima dan paket contoh diperiksa. Dana dipakai untuk uang muka bahan, kemasan dan persiapan gudang.",
         "Distribusi pilot 200 paket dicatat bersama bukti penerimaan simulasi. Belanja kedua mencakup pelunasan bahan pilot dan logistik."),
        ("Rencana gudang paket pangan Kalianda", "Progres pengemasan isi paket pangan"),
        (("Beras 10 kg per paket", 5000, "karung", 155_000), ("Minyak goreng 2 liter per paket", 5000, "set", 42_000),
         ("Ikan kaleng 4 kaleng per paket", 5000, "set", 72_000), ("Mi 10 bungkus per paket", 5000, "set", 33_000),
         ("Gula 1 kg per paket", 5000, "kg", 19_000), ("Kardus dan segel", 5000, "set", 9_000),
         ("Pengemasan dan pemeriksaan", 5000, "paket", 10_000), ("Angkut dan distribusi", 40, "perjalanan", 3_000_000),
         ("Sewa gudang transit", 2, "bulan", 18_000_000), ("Operasi titik serah dan rekap", 40, "hari-titik", 3_600_000))),
}

RECEIPT_DAYS = (9, 14, 19)
UPDATE_DAYS = (16, 24)
PENDING = 2_500_000
DONORS = ("Rinai Wira Lazuardi", "Harsa Nila Purnama", "Bayu Nadi Kencana", "Sora Arunika Pijar")
HOLDER = "[SIMULASI] Rekening Latihan Rescue-Net"


def account(key, program):
    return program.account or f"99006{list(PROGRAMS).index(key) + 1:05d}"
