# ADR-0005: Standar data kemanusiaan — P-code wilayah, HXL, CAP

Status: **Accepted** (owner 2026-10-08). Jawaban owner 2026-10-08: pertanyaan 1-4 diterima sesuai rekomendasi (kode Kemendagri = kunci; HXL ekspor dulu; CAP hanya masuk, tampil saja). Mulai dari langkah D.1-D.2 (wilayah berkode) di test stack; sumber berkas wilayah dipilih saat implementasi dan hasil impor dilaporkan ke owner sebelum produksi.
Tanggal: 2026-10-08
Terkait: ADR-0004 (federasi), NEXT_STEPS Fase 9c

## Konteks (fakta kode saat ini, diaudit 2026-10-08)
- `RN Admin Area` (`rn_core`): `code`, `area_name`, `level` (province/city/district/village), `parent_code`, `source`,
  `source_reference`, `enabled`. **Produksi hanya berisi 14 baris demo** (2 provinsi, 3 kota, 3 kecamatan, 6 desa; sumber
  "demo cache"). Kodenya berpola Kemendagri bertitik (`11`, `11.71`, `11.71.02`, `11.71.02.1001`).
- `api_admin_areas` hanya `get_children` / `get_provinces` (guest, rate-limited). Tidak ada impor, pencarian, atau pemetaan kode.
- `RN Posko` dan `RN Community Report` menyimpan `admin_area_id` (teks bebas, tanpa validasi/link) **dan** nama
  `province_name`/`city_name`/`district_name`/`village_name` (teks bebas). Routing laporan (`services/report_routing.py`)
  mencocokkan nama (bukan kode) dan memakai `admin_area_id` hanya bila sama persis dan ≥ 10 karakter.
- Tidak ada kode HXL, CAP, P-code, atau BPS di repo.
- Akibat: dua server federasi (ADR-0004) atau BNPB/OCHA tidak punya kunci wilayah yang pasti; "Kampung Baru" salah eja = beda wilayah.

## Keputusan yang diusulkan

### A. P-code wilayah (9c-1)
1. **Kunci kanonik = kode Kemendagri** (Permendagri 72/2019, bentuk bertitik) — sudah dipakai `RN Admin Area`. Alasan: sumber resmi,
   BNPB/pemda memakainya, hierarkinya terbaca dari kodenya.
2. Tambah di `RN Admin Area` (tanpa mengubah `code`): `pcode_ocha` (P-code COD-AB OCHA/HDX, mis. bentuk `ID1171`),
   `bps_code`, `valid_from`/`valid_to` (pemekaran/penggabungan), `replaced_by`, `lat`/`lng` pusat wilayah.
   Format P-code OCHA dan versi COD-AB yang berlaku **harus diverifikasi dari berkas HDX Indonesia saat implementasi** —
   ADR ini tidak mengasumsikannya.
3. Tabel pemetaan terpisah **RN Admin Area Crosswalk** (`code_system`, `external_code`, `area`, `confidence`, `source`) agar satu
   wilayah bisa punya banyak sistem kode tanpa menambah kolom tiap kali.
4. **Impor** lewat satu skrip bertahap (provinsi → desa) dari berkas resmi (data.go.id / BPS / HDX COD-AB), dijalankan dulu di
   test stack; hasilnya diperiksa (jumlah per level, anak tanpa induk, kode ganda) sebelum menyentuh produksi.
   Wilayah yang sudah tidak berlaku diberi `valid_to`, tidak dihapus.
5. `RN Posko.admin_area_id` dan `RN Community Report.admin_area_id` menjadi **Link ke RN Admin Area** (nama tetap disimpan sebagai
   teks tampilan). Patch pra-sinkron memetakan baris lama dari nama → kode; yang tidak cocok ditandai `area_unmatched`
   untuk diperbaiki manusia (tidak ditebak diam-diam).
6. Routing laporan: cocok kode lebih dulu (desa/kecamatan/kota/provinsi lewat awalan kode), nama hanya cadangan.
7. Federasi (ADR-0004): event membawa `admin_area_code` (Kemendagri) + `pcode_ocha` bila ada; node penerima yang tidak mengenal
   kodenya menandai `area_unmatched`, bukan membuat wilayah baru.

### B. HXL (9c-2)
1. **Hanya ekspor dulu** (aman, tanpa risiko data masuk): endpoint CSV/JSON dengan baris tagar HXL di bawah header untuk
   - posko publik (`#loc +name`, `#adm1/2/3/4 +code`, `#geo +lat/+lon`, `#capacity`),
   - kebutuhan/stok logistik agregat per wilayah (`#item`, `#meta +unit`, `#affected`/`#indicator` sesuai kamus HXL),
   - kejadian bencana (`#event`, `#date`).
2. Pemetaan field → tagar disimpan di satu registri kode (`standards/hxl_map.py`), diuji terhadap kamus HXL standar
   (validasi tagar/atribut) — bukan dikarang per endpoint.
3. **Hanya data berklasifikasi "boleh keluar"** (ADR-0004 bagian C). Nomor HP, identitas korban, rekam medis tidak pernah
   masuk ekspor; test kebocoran wajib (seperti BUG-1..6). Ekspor penuh perlu peran org admin dan tercatat di log audit.
4. Impor HXL ditunda: perlu aturan validasi + karantina (data masuk lewat antrian review manusia, ADR-0002 prinsip yang sama).

### C. CAP — Common Alerting Protocol (9c-3)
1. Arah **masuk** lebih dulu: baca feed CAP 1.2 (OASIS) dari sumber resmi (mis. BMKG) → DocType **RN Early Warning**
   (`identifier`, `sender`, `sent`, `status`, `msgType`, `severity`, `urgency`, `certainty`, `event`, `area_desc`, `polygon`,
   `expires`, `raw_xml`, `source_url`, `admin_areas` hasil pencocokan). URL/format feed yang aktif **diverifikasi saat
   implementasi**; ADR ini tidak mengasumsikan endpoint tertentu.
2. Peringatan **tidak otomatis** membuat tindakan: tampil di Bencana Aktif / Control Centre sebagai banner "peringatan resmi",
   dengan wilayah terdampak (cocok polygon/kode → posko di dalamnya). Pengiriman WA ke posko hanya lewat `api_notify`
   yang sudah ada dan atas keputusan manusia/aturan yang disetujui org admin.
3. Arah **keluar** (Rescue-Net menerbitkan CAP) tidak diusulkan sekarang: menerbitkan peringatan publik adalah wewenang
   lembaga resmi; risikonya tinggi. Hanya dibahas lagi bila owner minta, dengan persetujuan lembaga.
4. Fase 10 "peringatan dini BMKG" memakai komponen ini.

### D. Urutan implementasi (setelah Accepted; satu langkah per persetujuan)
1. Skema + crosswalk + impor di test stack (+ test kualitas data).
2. Link `admin_area_id` + patch pemetaan + routing berbasis kode.
3. Ekspor HXL + test kebocoran.
4. Penerima CAP + banner.

## Alternatif yang ditimbang
- Mengganti kode Kemendagri dengan P-code OCHA sebagai kunci utama: hubungan ke data pemda/BNPB jadi tidak langsung. Ditolak; crosswalk cukup.
- Tetap memakai nama wilayah sebagai kunci: salah eja/pemekaran memecah data. Ditolak.
- Mengimpor seluruh desa Indonesia ke produksi langsung: tidak bisa dipulihkan bila berkas salah. Ditolak; test stack dulu.

## Konsekuensi
- `admin_area_id` yang tervalidasi mengubah perilaku simpan Posko/Laporan (kode tidak dikenal ditolak atau ditandai) — perlu
  uji agar tidak memblokir laporan warga di lapangan: laporan **selalu diterima**, wilayah yang tak cocok ditandai.
- Impor wilayah penuh ± 80 ribu desa: perlu paginasi di `get_children` dan indeks pada `parent_code`.
- Data eksternal (BNPB/OCHA/BMKG) hanya dibaca lewat kebijakan klasifikasi ADR-0004; AI tidak memetakan wilayah tanpa review (ADR-0002).

## Pertanyaan untuk owner
1. Kode Kemendagri sebagai kunci kanonik diterima?
2. Ekspor HXL dulu (tanpa impor) — diterima? Apakah ada mitra (OCHA/BNPB/NGO) yang sudah meminta format tertentu?
3. CAP: hanya masuk (BMKG) dulu — diterima? Apakah perlu peringatan WA otomatis ke posko, atau tampil saja?
4. Sumber berkas wilayah resmi mana yang boleh dipakai (data.go.id, BPS, HDX), dan siapa yang memverifikasi hasil impor?
