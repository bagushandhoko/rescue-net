# Simulasi rekonstruksi rumah Baduy Luar

Paket untuk program donor `rn-donor-fc5d3f8cd6c3` dan event `event-487311176a69`. Gunakan salinan data awal di Frappe uji terisolasi yang memuat program, organisasi dan akun pemrakarsa. Aset terbitan disertakan.

## Render dan jalankan

Dari direktori ini, gunakan Python dengan `playwright`, `qrcode[pil]` dan Chromium dari `python -m playwright install chromium`.

```sh
python gen_docs.py
```

Generator menulis dua PDF dan lima PNG. Salin direktori aset ke `/tmp/baduy-realistis` dan skrip **sefolder dengan induknya** (`../baduy_realistis.py`) ke `/tmp/baduy_realistis.py` di mesin atau kontainer bench uji. Dari direktori bench uji:

```sh
RN_BADUY_SITE=rescuenet-test.localhost RN_BADUY_ASSETS=/tmp/baduy-realistis \
  bench --site rescuenet-test.localhost console
```

Di konsol:

```python
exec(compile(open("/tmp/baduy_realistis.py").read(), "/tmp/baduy_realistis.py", "exec"))
```

Site uji harus cocok persis dengan env dan bernama `rescuenet-test.localhost` atau memakai awalan `test-` / `test.`. Seed mengunci program, mencocokkan mutasi pembuka sebelum mengubah data, dan mencatat `SIM/RN/BADUY/02` di notes setelah rekonsiliasi. Eksekusi ulang mengenali penanda tersebut. Lampiran kartun dilepas dari slot program berdasarkan awalan berkas. Foto dibiarkan kosong untuk paket moderator.

## Skenario per 12 Desember 2026

Mutasi setelah 24 November adalah proyeksi latihan agar waktu pengerjaan tahap pertama masuk akal.

| Angka | Nilai |
| --- | ---: |
| Biaya satu rumah | Rp35.470.000 |
| Biaya satu leuit | Rp10.190.000 |
| Target RAB | Rp812.662.500 |
| Delapan donasi dikonfirmasi | Rp284.000.000 |
| Dua donasi menunggu | Rp3.750.000 |
| Terpakai | Rp267.500.000 |
| Saldo | Rp16.500.000 |
| Progres fisik tertimbang | 35% |

Lokasi menggunakan titik permukiman darat hasil Nominatim. Peran tiap lokasi dan tata letak kampung adalah asumsi skenario. Rumah dan leuit di gambar belum disurvei atau disetujui lembaga adat.

- Acuan tapak [Cihulu](https://www.openstreetmap.org/node/13380795605), −6.6017207, 106.2259689.
- Bongkar bahan [Ciboleger](https://www.openstreetmap.org/node/13463083419), −6.5939378, 106.2257927.
- Koordinasi tukang [Kadujangkung](https://www.openstreetmap.org/node/13380785900), −6.5994270, 106.2318975.
- Klasifikasi Baduy Luar [Perbup Lebak 38/2023](https://peraturan.bpk.go.id/Download/327613/PerBup%20No%2038%20Tahun%202023.pdf).
- Rujukan konteks tingkat harga [Perbup Lebak 7/2025 untuk TA 2026](https://jdih.lebakkab.go.id/dokumen/1254). Tarif bahan adat, upah dan pikul pada RAB adalah asumsi simulasi yang perlu dicek dengan penawaran lokal.
