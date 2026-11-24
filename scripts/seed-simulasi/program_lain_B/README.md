# Seed donasi simulasi Kelompok B

Aset dan skenario untuk tujuh program Karhutla Kalbar, Peduli Asap di Riau, dan Krakatau. Dokumen, donatur, transaksi, dan lokasi kegiatan adalah bagian dari skenario latihan. Titik peta memakai area permukiman darat sebagai referensi. Data OpenStreetMap © kontributor.

| Area | Referensi peta |
| --- | --- |
| Sungai Raya | [OSM node 13076749093](https://www.openstreetmap.org/node/13076749093) · [Rincian koordinat OSM](https://mapcarta.com/34365408) |
| Siak Sri Indrapura | [OSM node 3478404969](https://www.openstreetmap.org/node/3478404969) · [Rincian koordinat OSM](https://mapcarta.com/Siak_Sri_Indrapura) |
| Pangkalan Kerinci | [OSM way 1050454729](https://www.openstreetmap.org/way/1050454729) · [Rincian koordinat OSM](https://mapcarta.com/W1050454729) |
| Way Urang | [OSM node 1308644580](https://www.openstreetmap.org/node/1308644580) · [Rincian koordinat OSM](https://mapcarta.com/27676688) |

## Render aset

Dari folder ini jalankan `python generate.py` dengan Playwright Chromium, Pillow, dan qrcode. Gunakan `--photos <folder>` untuk memberi cap foto dari Pollinations yang telah diperiksa. Nama sumber memakai pola `<id>-foto-1.jpg` dan `<id>-foto-2.jpg`. Untuk memproses foto saja gunakan juga `--photos-only`. PNG lembar kontak menunjukkan slot kosong.

## Jalankan pada site uji

Pastikan site terisolasi berisi tujuh ID program dan event sesuai `data_b.py`, dengan saldo awal dan rekening sesuai TSV serta akun PIC yang berhak mengelola. Salin folder aset ke `/tmp/program_lain_B` atau isi `RN_PROG_ASSETS` dengan lokasi lain. Salin `program_lain_B.py` ke `/tmp`.

```sh
RN_PROG_SITE=rescuenet-test.localhost bench --site rescuenet-test.localhost console
```

```python
exec(compile(open("/tmp/program_lain_B.py").read(), "/tmp/program_lain_B.py", "exec"))
```

Tiap program memegang lock selama mutasi, memeriksa angka awal, lalu menyimpan penanda di notes setelah cek dana akhir. Jalankan dari sesi bench yang bersih karena setiap program memakai commit atau rollback tersendiri. Bila muncul TEMUAN periksa perbedaan sebelum mencoba ulang. Foto yang sudah tersedia saat seed dijalankan ikut terpasang. Lembar kontak untuk pemeriksaan moderator.
