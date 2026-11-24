# Program donasi simulasi kelompok A

Sembilan program Gempa Simulasi, Meulaboh, Aceh Barat, dengan saldo pembuka sesuai TSV 24 November 2026. Data RAB, transaksi tambahan, output, dan kabar lapangan adalah skenario latihan. Pemrakarsa dan nama program yang sudah tersimpan tetap digunakan.

## Aset

- `<id>/rab.pdf` dan `rab-*.png` memuat volume, harga satuan, dan total. Harga adalah asumsi simulasi untuk wilayah Meulaboh tahun 2026. [SSH Aceh Barat TA 2026](https://acehbaratkab.go.id/berita/ssh-standar-satuan-harga-tahun-anggaran-2026) memberi konteks perencanaan.
- `panduan.png` memuat rincian dan titik layanan fiktif. Titik dicek terhadap jaringan darat OpenStreetMap. Titik pertama sekitar 6 m dari [jalan OSM 307037242](https://www.openstreetmap.org/way/307037242), titik kedua pada [jalan 472260872](https://www.openstreetmap.org/way/472260872), dan titik ketiga pada [jalan 197668795](https://www.openstreetmap.org/way/197668795).
- `rekening.pdf` merekap total masuk dan keluar sebelum seed sebagai agregat, kemudian menampilkan mutasi fiktif tambahan dan saldo akhir.
- `qris.png` berisi QR teks peringatan. `contact-sheet.png` menunjukkan ketersediaan foto menurut program. Foto yang tersedia dicap dan diberi keterangan.
- TSV tidak memuat nama program. Skenario `83d25e5a39f5` memakai paket kebersihan dan `d346ff392f8e` memakai paket logistik posko sebagai asumsi untuk tipe `special_program`. Cocokkan dengan judul tersimpan di site uji sebelum dipakai.

Buat ulang dokumen dengan Python 3, paket `playwright`, `pillow`, `qrcode`, font DejaVu Sans, dan Chromium Playwright.

```sh
python -m playwright install chromium
python gen_assets.py
```

Untuk foto yang sudah diperiksa, simpan JPG bernama `<id>-0.jpg` dan `<id>-1.jpg` dalam direktori pilihan. Jalankan `python cap_foto.py <direktori>`, lalu `python gen_assets.py --contact-only`.

## Seed di site uji terisolasi

Salin direktori aset beserta subdirektorinya ke backend. Site uji memerlukan salinan sembilan program dan data awal yang cocok dengan TSV. Jalankan skrip dari direktori bench untuk site itu saja.

```sh
RN_PROG_SITE=rn-uji RN_PROG_ASSETS=/tmp/program_lain_A bench --site rn-uji console
```

Di konsol jalankan `exec(open("/tmp/program_lain_A.py").read())`. Skrip mengambil kunci program, memeriksa tipe/event, rekening, dana, jumlah item awal, dan penanda di catatan. Satu transaksi per program. Perubahan dalam transaksi program yang gagal di-rollback dan dicetak sebagai `TEMUAN`. Klik publikasi, status verifikasi pemrakarsa, dan data kontak lama mengikuti data site uji.
