# Impor wilayah berkode (ADR-0005 D.1)

Status: **dibangun dan diuji di test stack; BELUM di produksi** (gerbang review owner, ADR-0005). Kunci kanonik =
kode Kemendagri bertitik (`11`, `11.71`, `11.71.02`, `11.71.02.1001`).

## Yang sudah ada
- `rescue_net/services/admin_area_codes.py` — normalisasi/validasi kode, tingkat, induk, laporan kualitas, alias provinsi,
  pembeda Kota/Kabupaten. Murni (tanpa Frappe).
- `rescue_net/services/admin_areas.py` — `import_rows` (dry-run bawaan, idempoten, tidak menghapus), `import_crosswalk`,
  `resolve_external`, `match_by_names` (nama → kode, berhenti bila ambigu/tak ada, tidak menebak), `ancestors`.
- DocType `RN Admin Area` (+`pcode_ocha`, `bps_code`, `center_lat/lng`, `valid_from/to`, `replaced_by`, indeks) dan
  `RN Admin Area Crosswalk` (kode OCHA/BPS/lama → wilayah; satu kode eksternal = satu wilayah). **Butuh `bench migrate`.**
- API tamu `api_admin_areas.search_areas` (cari + paginasi) dan `get_area` (induk + kode eksternal).
- `scripts/rn-wilayah-convert.py` — dump SQL → CSV + laporan kualitas.

## Prosedur (test stack dulu)
1. Unduh ke folder kosong sendiri (berkas unduhan tidak tepercaya):
   `curl -L -o wilayah.sql https://raw.githubusercontent.com/cahyadsn/wilayah/master/db/wilayah.sql`
   (sumber komunitas, lisensi MIT, mencantumkan "Kepmendagri No 300.2.2-2138 Tahun 2025"; **owner memverifikasi terhadap berkas resmi** sebelum produksi).
2. `python3 -I scripts/rn-wilayah-convert.py wilayah.sql wilayah.csv <path admin_area_codes.py>` → laporan kualitas.
3. Di Frappe: `svc.load_file(csv)` → `svc.import_rows(rows, sumber, url, dry_run=True)` → periksa `validation.ok` & `plan` → `dry_run=False`.
4. Bandingkan jumlah per tingkat dengan laporan langkah 2.

## Hasil ukur (2026-10-08, test stack di NAS ini, dalam transaksi yang di-rollback)
| | |
|---|---|
| Baris | 91.599 = 38 provinsi, 514 kab/kota, 7.285 kecamatan, 83.762 desa/kelurahan |
| Kualitas | 0 kode salah, 0 ganda, 0 yatim, 0 level/induk tidak cocok |
| Waktu | baca 5 dtk, dry-run 4 dtk, tulis 89 dtk, ulang (idempoten) 15 dtk → 0 baru/0 berubah |
| Cari | `search_areas('Kampung Baru')` 0,28 dtk; anak 31.71 instan |

Pemetaan nama → kode atas data produksi (78 baris posko + laporan, 14 kombinasi nama): 27 terpetakan, 47 tanpa nama wilayah,
4 tidak ditemukan karena datanya janggal ("Desa A", kecamatan ditulis sebagai kabupaten). Tidak ada tebakan.

Catatan nama resmi: dataset memakai "Daerah Khusus Ibukota Jakarta", "Daerah Istimewa Yogyakarta", "Kota Administrasi Jakarta Pusat" →
alias provinsi dan pembeda Kota/Kabupaten sudah ditangani; tanpa pembeda "Bandung" dinyatakan ambigu (32.04 / 32.73).

## Belum dikerjakan (menunggu review owner)
- P-code OCHA/BPS: berkas HDX COD-AB belum diunduh/diverifikasi (format P-code tidak diasumsikan; ADR-0005 A.2).
- D.2: `admin_area_id` jadi Link + patch pemetaan nama→kode + routing berbasis kode; produksi: migrate + impor 91.599 baris.
