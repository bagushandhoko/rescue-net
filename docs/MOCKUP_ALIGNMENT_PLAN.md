# Rescue-Net — Mockup Alignment Plan

> Rencana menyamakan setiap `pages/*.html` dengan mockup di `assets/img/mockup/*.png`
> **dan** spec `blueprint/DISASTER MANAGEMENT SYSTEM.docx.pdf`.
> Dibuat 2026-09-01. Sumber kebenaran status pengerjaan tetap `HANDOVER.md`.
> Doc ini = peta pekerjaan; centang item saat selesai.

---

## 1. Temuan perbandingan (semua halaman)

Pola **seragam** di semua halaman yang belum dikerjakan:

| | Existing (sekarang) | Mockup (target) |
|---|---|---|
| Judul panel | Bahasa Inggris (`Add Missing Report`, `Record Meal Production`, `Stock Observations`) | Bahasa Indonesia, berorientasi operasi |
| Isi | 2–5 panel: **form input + tabel hasil kosong**; sering butuh login; sebagian endpoint belum `allow_guest` / belum ada (`api_kitchen.dashboard is not whitelisted`) | **Dashboard**: 4–6 KPI tile (+ delta "dari kemarin"), lalu 4–10 panel data kaya (tabel, donut, matching board, kartu peringatan, strip evidence), + rail kanan detail item terpilih |
| Data | 0 / kosong | angka realistis, per-wilayah / per-item |
| Sidebar | grup "Posko" + "Modul" hasil `rn-navigation-v2.js` | menu modul kiri (Ringkasan, Peta Situasi, Laporan & Insiden, Organisasi & Posko, Permintaan Bantuan, Sumber Daya, Relawan, Komunikasi, Verifikasi, Pengaturan) |

**Sudah selesai** (tidak masuk rencana ini): Welcome (`index.html`), Login & Registrasi
(`auth.html`), Bencana Aktif (`bencana-aktif.html`), Control Centre (`war-room.html`),
Posko Logistik (`posko-logistik.html`).

---

## 2. Aturan global (WAJIB dipatuhi — permintaan owner)

0. **Layout & tampilan semirip mungkin dengan mockup** (bukan sekadar "mirip
   struktur"): urutan panel, judul, kolom tabel, chip status, warna, ikon, rail
   kanan — semua ditiru. Deviasi hanya yang tercatat di poin 5.
0b. **Semua fungsional & terhubung database.** Tidak ada angka/tabel/kartu dummy.
   Tiap panel membaca record nyata (Frappe/MariaDB) lewat endpoint guest. Kalau
   datanya memang kosong → tampilkan empty-state jujur ("Belum ada …"), jangan
   diisi contoh.
0c. **KPI WAJIB bisa diklik.** Tiap KPI tile = tombol → buka **daftar item
   underlying** (modal drill-down) + tiap baris **link ke data relevan**
   (halaman modul / posko-detail / drawer aksi). Pola acuan: `bencana-aktif.js`
   `openDrill()` + `kebutuhan_items`/`distribusi_items`/`posko_kritis_items` yang
   dikembalikan endpoint, dan pola lama Control Centre `openDrill`/`kpi_drilldown`.
   Item "Isu/Alert/Peringatan" juga harus jadi link.
1. **Additive saja.** Jangan hapus menu / fitur / form / tabel yang ada di existing
   walau tidak ada di mockup. Yang ada di mockup tapi belum ada di existing →
   **ditambahkan**. Yang ada di existing tapi tidak di mockup → **dipertahankan**
   (dipindah ke bawah / ke dalam `<details>`, bukan dihapus).
2. **Sidebar dev tetap** (keputusan pass 2026-09-01). "Match mockup" = area konten,
   bukan chrome. Menu modul mockup ditambahkan sebagai link baru di `<nav>` bila
   belum ada; `rn-navigation-v2.js` yang mengelompokkan.
3. **Form input existing dipertahankan** — bungkus dalam
   `<details class="panel create-panel rn-input-drawer">` (pola Posko Logistik),
   di bawah dashboard. Aksi operator (Penuhi / OTW / Approve) tetap.
4. **Endpoint guest.** Tiap modul butuh 1 endpoint `@frappe.whitelist(allow_guest=True)`
   gaya `active_disasters_board` / `logistik_board` yang mengembalikan `totals` +
   panel-panel dalam satu payload. Audit `api_<modul>.py` dulu; kalau sudah ada
   fungsi dashboard tapi tidak guest → tambah wrapper guest read-only.
5. **Deviasi yang diterima** (sama seperti Welcome/Bencana Aktif): KPI tanpa
   sparkline & tanpa delta "N dari kemarin" bila belum ada snapshot harian; glyph
   ikon KPI opsional (ikut pola `.kpi-card`). Data tipis untuk event nyata = jujur.
6. **Per halaman:** backup ke `_archive/mockup-align-<ts>/`, cache-buster
   `?v=<slug>-<tgl>` di `<link>`/`<script>`, verifikasi Playwright via
   `http://host.docker.internal/rescue-net/…` (`--add-host=host.docker.internal:host-gateway`,
   tunggu ≥ 15 s worker dingin), update `HANDOVER.md` di commit yang sama.
7. Deploy backend: pipe file via `docker exec -i` ke `osiun-frappe-backend`,
   backup dulu, restart, cek md5 host == container (lihat `HANDOVER.md`).

---

## 3. Komponen dipakai ulang (bikin sekali, di `style.css`)

- `.kpi-grid` / `.kpi-card` (+ `.danger` / `.warning`) — sudah ada.
- `.rn-table` / `.rn-table-wrap` / `.rn-table-foot` + pager — sudah ada.
- **Baru:** `.rn-donut` (SVG ring + legend) untuk "Kapasitas & Okupansi",
  "Produksi Makanan", "Status Identifikasi", "Trust/Risk Score".
- **Baru:** `.rn-matchboard` (kolom-kolom alur: Kebutuhan → Bantuan → Pickup →
  Transport) untuk Distribusi & Search-Found.
- **Baru:** `.rn-alert-card` (kartu peringatan ikon + judul + waktu + level) untuk
  "Peringatan & Hambatan", "Peringatan Keselamatan", "Peringatan Konektivitas".
- **Baru:** `.rn-evidence-strip` (thumbnail + Unggah Foto) — generalisasi dari
  `logistik.js` `renderEvidence` / CC bukti.
- **Baru:** `.rn-detail-rail` (rail kanan: item terpilih + tab + stat box + checklist)
  — generalisasi dari `bencana-aktif.js` right rail.
- **Baru:** `.rn-checklist` (verifikasi: ikon centang + label) untuk Trust Level /
  Status Verifikasi.

---

## 4. Rencana per halaman

Format: **PERTAHANKAN** = yang sudah ada, jangan diutak-atik selain dipindah ·
**TAMBAH** = dari mockup · **BACKEND** = endpoint yang dibutuhkan.

### 4.1 Organisasi & Posko — `pages/organisasi-posko.html` + `assets/js/org-posko.js`
Mockup: `organisasi & posko.png`
- **PERTAHANKAN:** form "Tambah Kelompok" + "Daftar Kelompok", form "Tambah Posko /
  Node" + "Daftar Posko" (+ `.rn-fn-picker` fieldset fungsi posko yang baru
  ditambah), badge koordinasi detail/ringkasan, `event_poskos` fallback.
- **TAMBAH:** 4 KPI (Organisasi Aktif / Posko Aktif / Pending Verifikasi / Anggota
  Terdaftar); panel kiri **Struktur Organisasi** (toggle Pohon Hierarki / Daftar —
  tree: event → organisasi → posko, tiap node status + jumlah anggota, tombol
  "+ Tambah Organisasi"); rail kanan **detail organisasi terpilih** (nama +
  Terverifikasi, tab Ringkasan / Posko (n) / Anggota (n) / Program (n), Status
  Verifikasi, Ringkasan Sumber Daya, **Trust Level** grade + skor + checklist,
  "Terakhir diperbarui").
- **BACKEND:** `api_control_centre.org_posko_board(disaster_event)` guest →
  `{totals, tree:[org→posko], orgs:[{...trust, resource_summary, counts}]}`.
  Sumber: `RN Organization`, `RN Posko`, `RN Org Membership`, `RN Verification*`.

### 4.2 Registrasi & Verifikasi Posko — **HALAMAN BARU** `pages/registrasi-posko.html`
Mockup: `registrasi & verifikasi Posko.png` · dilink dari Organisasi & Posko.
- **PERTAHANKAN:** logika `create_posko` + `set_posko_functions` yang sudah ada di
  `org-posko.js` (dipakai ulang / dipindah).
- **TAMBAH:** 4 KPI (Posko Aktif / Pending Verification / Official Verified /
  Community Verified); **Form Registrasi/Edit Posko** lengkap (Nama, Jenis, Event,
  Lokasi GPS, Alamat, PIC nama/jabatan/kontak/email, Afiliasi Org, Kontak Darurat,
  Fasilitas chips, Kapasitas, Visibility, Upload Foto); rail **Status Verifikasi
  Posko** (checklist Email / No HP / Identitas PIC / Lokasi / Trusted Verifier +
  tombol Ajukan Verifikasi / Simpan Draft / Hapus); bawah **Daftar Posko** tabel
  (Nama / Jenis / Lokasi / PIC / Kapasitas / Status Verifikasi / Terakhir
  Diperbarui) + filter + pagination.
- **BACKEND:** perluas `event_poskos` → sertakan PIC, kapasitas, verification_status,
  checklist; endpoint `posko_verification_checklist(posko)` guest.

### 4.3 Verification & Approval — `pages/verification-approval.html` + `assets/js/verification-approval.js`
Mockup: `verification & Approval.png`
- **PERTAHANKAN:** "Verifier Requests", "Endorsements", "Verifier Registry",
  "Revoked & Suspicious Activity", form "Respons Permintaan Verifikasi".
- **TAMBAH:** 6 KPI (User / Organisasi / Posko / Needs / Expense / Evidence Pending);
  kolom kiri **Antrian Verifikasi** (tab Semua/User/Organisasi/Posko/Needs + tabel
  Jenis / Nama / Dibuat Oleh / Evidence / Risk / Status); kolom tengah **Detail
  Item** (kartu item + Ringkasan + Evidence thumbnails + **Trust/Risk donut** +
  checklist); kolom kanan **Alur Persetujuan** (step tracker + **Jejak Audit**
  timeline); bar bawah **Tindakan** (Approve / Reject / Request Revision / Merge /
  Escalate).
- **BACKEND:** `api_verification.approval_queue(disaster_event)` guest →
  `{totals, queue:[...], }` + `approval_item_detail(kind, id)` +
  reuse `api_operator_approval` untuk aksi (butuh login).

### 4.4 Manajemen Distribusi — `pages/management-distribusi.html` + `assets/js/distribusi.js`
Mockup: `manajemen distribusi.png`
- **PERTAHANKAN:** "Bantuan Perlu Pickup", "Donatur Antar Sendiri", form "Tambah
  Transport Space" + "Transport Space Tersedia", form "Buat Distribution Flow" +
  tabel "Distribution Flow".
- **TAMBAH:** 6 KPI (Transport Space % / Kapasitas Darat / Laut / Udara /
  Kebutuhan Belum Match / Distribusi Terhambat); **Papan Pencocokan** 4 kolom
  (Kebutuhan → Bantuan → Relawan Pickup → Transportasi) + "Otomatis Cocokkan";
  rail **Ruang Transportasi real-time** (tab Darat/Laut/Udara + donut + Unit Aktif);
  **Alur Distribusi (Live Shipment)** tabel (ID / Kebutuhan / Bantuan / Pickup /
  Transportasi / Rute / ETA / Status / Trace); **Peringatan & Hambatan**
  (`.rn-alert-card`); footer reference (Pedoman Kemasan / Berat & Volume / Trace &
  Barcode).
- **BACKEND:** `api_control_centre.distribusi_board(disaster_event)` guest → gabung
  `RN Distribution Flow` + `RN Transport Space` + `RN Logistic Need` + `RN Aid Offer`.
  (Sebagian sudah ada di `_drill_flows` / `logistik_incoming` — bungkus.)

### 4.5 Manajemen Relawan — `pages/management-relawan.html` + `assets/js/relawan.js`
Mockup: `manajemen relawan.png`
- **PERTAHANKAN:** form "Tambah Relawan" + "Daftar Relawan", form "Assign Relawan" +
  tabel "Assignments".
- **TAMBAH:** 5 KPI (Terdaftar / Available Hari Ini / Sedang Bertugas / Butuh
  Penugasan / Fatigue Risk); **Daftar Relawan** tabel kaya (Nama / Organisasi /
  Skill / Lokasi / Tersedia / Durasi / Status) + filter lokasi/status + pagination;
  rail **Filter Keterampilan** (skill + jumlah + checkbox); **Papan Penugasan**
  (kartu prioritas + "N/M terisi" + Isi Penugasan); **Jenis Relawan** 4 tile;
  **Akomodasi & Keselamatan** (Akomodasi Tersedia / Menginap / Titik Aman /
  Briefing).
- **BACKEND:** `api_volunteer.volunteer_board(disaster_event)` guest →
  `{totals, volunteers, skills, assignments, accommodation}`. Sumber:
  `RN Volunteer`, `RN Volunteer Assignment`, `RN Volunteer Skill`.

### 4.6 Manajemen Alat Kerja — `pages/alat-kerja.html` + `assets/js/*` (baru `alat-kerja.js`)
Mockup: `manajemen alat kerja.png`
- **PERTAHANKAN:** form "Buat Request Alat Kerja" + "Daftar Request Alat Kerja".
- **TAMBAH:** 6 KPI (Alat Tersedia / Kebutuhan Alat / Operator Aktif / Dispatch
  Berjalan / BBM Kritis / Alat Rusak); **Inventari Alat per Kategori** (6 tile:
  Ekskavator / Genset / Pompa Air / Forklift / Chainsaw / Perahu Karet, N tersedia
  + legend Ready/Assigned/Maintenance/Critical); **Operator & Tenaga Teknis** list;
  **Matching Kebutuhan Alat** ranked; **Jadwal Dispatch Alat**; **Lokasi Kerja &
  Produktivitas** (progress bar); **BBM & Support Operasional** (Solar/Bensin/Oli);
  **QR / Asset Tracking**; **Hambatan Alat Kerja** + **Ringkasan** (Penggunaan 86%
  / Jam Operasional / Dispatch Selesai / Kerusakan Baru).
- **BACKEND:** `api_resource_tools.tools_board(disaster_event)` guest →
  `{totals, categories, operators, matches, dispatch, sites, fuel, blockers}`.

### 4.7 Dapur Umum — `pages/dapur-umum.html` + `assets/js/dapur-umum.js`
Mockup: `dapur umum.png` · (dashboard call `api_kitchen.dashboard` sekarang **error
`is not whitelisted`** — perbaiki dulu.)
- **PERTAHANKAN:** "Kitchen Stock", form "Record Meal Production", "Meal
  Productions", "Stock Movements".
- **TAMBAH:** 6 KPI (Jiwa Dilayani / Kapasitas Porsi Hari / Produksi Hari Ini % /
  Gap Porsi / Bahan Kritis / Distribusi Hari Ini); **Target Layanan** (Total Target
  / Target Jiwa / Rasio); **Produksi Makanan Hari Ini** (`.rn-donut` + breakdown);
  **Stok Bahan Dapur** tabel (Bahan / Stok / Satuan / Status); **Kebutuhan Bahan
  Kritis** kartu; **Jadwal Masak**; **Distribusi Makanan Hari Ini** tabel;
  **Relawan Dapur** list + Aktif/Istirahat; **Evidence Foto Dapur** strip; **Status
  Gas / BBM**.
- **BACKEND:** buat `api_kitchen.kitchen_board(posko, disaster_event)` guest
  (bukan `dashboard`) → satu payload. Reuse pola `logistik_board`.

### 4.8 Shelter & Akomodasi — `pages/shelter-detail.html` + `assets/js/shelter-detail.js`
Mockup: `shelter & akomodasi.png` (mockup = **overview lintas shelter**, existing =
detail 1 shelter).
- **PERTAHANKAN:** "Registrasi Pengungsi" + form, "Shelter Occupancy" + "Record
  Occupancy", "Shelter Needs" + "Add Shelter Need", "Shelter Stock" (semua per-shelter).
- **TAMBAH (mode overview bila tanpa `?id=`):** 6 KPI (Total Penghuni / Kapasitas
  Maksimal / Overcapacity / Kelompok Rentan / Air Bersih Kritis / Sanitasi Kritis);
  **Daftar Shelter** tabel (Nama / Lokasi / Penghuni / Kapasitas / Okupansi /
  Status) + Lihat Peta + pagination; **Kapasitas & Okupansi** `.rn-donut`;
  **Kebutuhan Dasar** list + status; **Akomodasi Relawan / Petugas** tabel;
  **Sanitasi & Air** (Toilet/MCK + Titik Air, rasio); **Check-in / Check-out**;
  **Kelompok Rentan** tabel; **Peringatan Keselamatan** `.rn-alert-card`;
  **Dokumentasi & Bukti** strip.
- **BACKEND:** `api_shelter.shelter_board(disaster_event)` guest (agregat) +
  pertahankan `api_shelter` per-shelter yang dipakai `?id=`.

### 4.9 Search & Found — `pages/search-found.html` + `assets/js/search-found.js`
Mockup: `search & found.png`
- **PERTAHANKAN:** "Missing Person Reports" + "Add Missing Report", "Found Person
  Reports" + "Add Found Report", "Create Manual Match" + "Matches". Footer catatan
  data sensitif.
- **TAMBAH:** 6 KPI (Orang Hilang / Korban Ditemukan / Belum Teridentifikasi /
  Sudah Reunifikasi / Aset Hilang / Barang Ditemukan); tab (Orang Hilang / Korban
  Ditemukan / Aset / Barang / Hewan Peliharaan / Ternak); **Papan Pencocokan
  (Possible Matches)** kartu foto + % match + Tinjau Detail / Buat Kasus
  Reunifikasi; **Reunifikasi Keluarga (Aktif)** list; **Status Identifikasi**
  `.rn-donut`; **Klaim & Serah Terima (Barang/Aset)** tabel; **Foto Bukti** strip;
  rail **Aksi Verifikasi** (Verifikasi Identitas / Pencocokan Data / Validasi Bukti
  / Serah Terima).
- **BACKEND:** `api_search_found.search_board(disaster_event)` guest →
  `{totals, matches, reunifications, identification_stats, claims, evidence}`.

### 4.10 Program Khusus — `pages/program-khusus.html` + `assets/js/*` (baru `program-khusus.js`)
Mockup: `program khusus.png`
- **PERTAHANKAN:** "Daftar Program", form "Buat Program", form "Update Progress
  Program".
- **TAMBAH:** 6 KPI (Program Aktif / Critical / Selesai / Milestone Terlambat /
  Lokasi Belum Terlayani / Butuh Support Distribusi); kiri **Daftar Program** kartu
  (image + nama + kategori + lokasi + progress) + tab Semua/Aktif/Critical/Selesai;
  tengah **detail program terpilih** (header + Overall Progress + Target/Tercapai +
  tab Ringkasan / Rencana Kerja / Anggaran / Dokumen / Catatan / Riwayat →
  Target & Milestone, Lokasi Implementasi mini-map, Kebutuhan Program, 4 kartu
  Support (Logistik/Distribusi/Relawan/Alat Kerja) + Ajukan Support, Progress
  Lapangan, Evidence Program, Verifikasi Output).
- **BACKEND:** `api_control_centre` / `api_recovery` → `program_board(disaster_event)`
  + `program_detail(program)` guest. Sumber: `RN Donor Program`, `RN Action Plan`,
  `RN Recovery Project`.

### 4.11 Profil Sumber Daya — `pages/resource-profile.html` + `assets/js/*` (baru `resource-profile.js`)
Mockup: `Profil Sumber Daya.png`
- **PERTAHANKAN:** section "Organizations", "Posko & Nodes", "Volunteers",
  "Tools / Shared Resources" (jadikan tab/detail bila perlu, jangan hapus).
- **TAMBAH:** 5 status chip atas (Peran Utama / Tingkat Kepercayaan skor / Email /
  HP / ID Terverifikasi); **kartu profil** (foto, nama, Aktif, peran, lokasi,
  kontak, Tentang Saya, Bergabung sejak, Edit Profil); grid kartu:
  **Keahlian/Skill** (+ Tersertifikasi, + Tambah), **Kendaraan** (+ Tambah),
  **Fasilitas** (+ Tambah), **Bantuan Barang Tersedia** (+ Tambah), **Wilayah
  Layanan** (+ Tambah), **Waktu Ketersediaan** (+ Atur Jadwal), **Kebutuhan
  Support** (Dibutuhkan + Ajukan); tombol **Simpan Perubahan**.
- **BACKEND:** `api_resource_tools.resource_profile(actor|posko)` guest-read +
  setter login. Sumber: `RN User Account`, `RN Volunteer Skill`, `RN Resource*`.

### 4.12 Evidence Center — `pages/evidence.html` + `assets/js/*`
Mockup: `evidence centre.png`
- **PERTAHANKAN:** "Evidence List", form "Upload Evidence".
- **TAMBAH:** 6 KPI (Evidence Baru / Pending Verifikasi / Restricted / Geotagged /
  Dokumen Serah Terima / Video Evidence); **Filter Modul** chips (Semua / Logistik /
  Medis / Distribusi / Program / Search & Found) + cari + Filter Lainnya + **Ekspor**;
  tabel kaya (checkbox / thumbnail + filename + GPS / Modul chip / Lokasi / Waktu /
  Uploader avatar+role / Verifikasi / Visibilitas / Aksi ...) + pagination +
  "N / halaman".
- **BACKEND:** `api_control_centre.event_evidence` sudah ada dan unified — perluas
  return dengan `module`, `gps`, `visibility`, `uploader_role`, `mime`; tambah
  `evidence_board(disaster_event)` untuk `totals`.

### 4.13 Alat Komunikasi — **HALAMAN BARU** `pages/alat-komunikasi.html` + `assets/js/alat-komunikasi.js`
Mockup: `alat komunikasi.png` · tidak ada halaman existing (`contact-directory.html`
beda: itu direktori kontak, dipertahankan apa adanya). Tambah link "Alat Komunikasi"
/ "Komunikasi" di `<nav>`.
- **TAMBAH (semua):** 6 KPI (Alat Komunikasi Aktif / Posko Tidak Terhubung /
  Repeater Aktif / Internet Darurat Dibutuhkan / Operator Radio Dibutuhkan /
  Baterai Kritis); **Inventari Alat Komunikasi** tabel (Kategori / Total / Aktif /
  Cadangan / Tidak Aktif / Perlu Perhatian: HT / Repeater Radio / Telepon Satelit /
  Starlink / VSAT / Router 4G-5G / Antena-Mast); **Konektivitas Posko** map +
  Terhubung / Koneksi Lemah / Tidak Terhubung; **Operator Radio** list (+ channel,
  status, + Tambah Operator); **Status Daya & Baterai** list; **Status Frekuensi &
  Jaringan** (VHF/UHF/HF/Seluler/Starlink/VSAT); **Peringatan Konektivitas**
  `.rn-alert-card`.
- **BACKEND:** doctype `RN Comms Device` / `RN Comms Operator` mungkin belum ada —
  cek; kalau belum, mulai dengan Custom Fields di `RN Posko`
  (`rn_comms_status`) + endpoint `comms_board(disaster_event)` yang menyusun dari
  posko + `RN Resource` bertipe komunikasi. Seed contoh via script idempotent.

### 4.14 Kompilasi Tampilan HP — mockup `kompilasi tampilan HP.png`
Pass responsif akhir: pastikan tiap halaman di atas punya breakpoint mobile
(KPI grid → 2 kolom → 1, tabel → scroll `overflow-x`, rail → pindah ke bawah,
sidebar → drawer `rn-mobile-drawer.js`). Bukan halaman baru.

---

## 5. Halaman tanpa mockup — JANGAN diubah (selain wiring event/guest bila perlu)

`ai-analyst`, `ai-settings`, `sync-console`, `data-consolidation`, `map`,
`disaster-detail`, `contact-directory`, `kirim-bantuan`, `edit-bantuan`,
`laporan-masyarakat`, `recovery-reconstruction`, `donor-program`, `posko-detail`,
`posko-medis-detail`, `control-centre-v4`, `mockup`.

---

## 6. Urutan pengerjaan yang disarankan

Batch by kesiapan backend & kemiripan (pakai komponen bagian 3):

1. ✅ **Dapur Umum** — DONE 2026-09-02 (`kitchen_board` guest endpoint + `dashboard`
   guest-fix). Lihat `HANDOVER.md`.
2. ✅ **Shelter & Akomodasi** — DONE 2026-09-02 (`shelter_board` guest endpoint +
   `api_shelter.dashboard`/`api_logistics.dashboard` guest-fix). Lihat `HANDOVER.md`.
3. **Manajemen Relawan** — `api_volunteer` sudah ada (`volunteer_count` baru dipakai).
4. **Manajemen Distribusi** — banyak potongan sudah ada di `_drill_flows` /
   `logistik_incoming`.
5. **Evidence Center** — `event_evidence` sudah unified; tinggal perluas + KPI.
6. **Verification & Approval** — `api_verification` + `api_operator_approval` ada.
7. **Organisasi & Posko** + **Registrasi & Verifikasi Posko** (halaman baru) —
   sepasang, trust-level & tree.
8. **Manajemen Alat Kerja** — `api_resource_tools`.
9. **Profil Sumber Daya** — `api_resource_tools`.
10. **Program Khusus** — gabung `api_recovery` / `api_donor_program`.
11. **Alat Komunikasi** (halaman baru) — perlu doctype/seed, paling banyak kerja baru.
12. **Pass responsif HP** — setelah semua halaman di atas jadi.

Tiap item: 1 endpoint guest + 1 rebuild HTML (dashboard di atas, form existing
masuk `<details>`) + 1 JS (IIFE, `RN_FRAPPE.call`) + CSS `.rn-<slug>-*` +
Playwright verify + update `HANDOVER.md`.

---

### Bentuk payload endpoint (agar KPI klik-able)

Tiap endpoint dashboard mengembalikan, selain `totals` + data panel:
- `<kpi>_items` untuk **setiap** KPI — list record underlying, tiap elemen
  `{label/title, sub, badge, href}` di mana `href` = deep link ke data relevan.
- Contoh sudah jalan (`active_disasters_board`): `kebutuhan_items[].href =
  posko-logistik.html?id=<posko>&event=<ev>&penuhi=<item>`,
  `posko_kritis_items[].href = posko-detail.html?id=<posko>&event=<ev>`.
- Frontend: KPI tile = `<button class="kpi-card rn-kpi-btn" data-kpi="...">`,
  handler → modal (`.rn-ba-modal` reusable) yang me-render `<kpi>_items`.

## 7. Checklist backend endpoint (guest, read-only, satu payload `{totals, <kpi>_items, ...panel}`)

- [x] `api_kitchen.kitchen_board(posko, disaster_event)` — DONE 2026-09-02; `dashboard` juga dibuat `allow_guest`
- [x] `api_shelter.shelter_board(disaster_event)` — DONE 2026-09-02; `dashboard`/`api_logistics.dashboard` juga dibuat `allow_guest`
- [ ] `api_volunteer.volunteer_board(disaster_event)`
- [ ] `api_control_centre.distribusi_board(disaster_event)`
- [ ] `api_control_centre.evidence_board(disaster_event)` + perluas `event_evidence`
- [ ] `api_verification.approval_queue(disaster_event)` + `approval_item_detail`
- [ ] `api_control_centre.org_posko_board(disaster_event)` + `posko_verification_checklist`
- [ ] `api_resource_tools.tools_board(disaster_event)`
- [ ] `api_resource_tools.resource_profile(target)`
- [ ] `program_board(disaster_event)` + `program_detail(program)`
- [ ] `comms_board(disaster_event)` (+ doctype/seed alat komunikasi)
