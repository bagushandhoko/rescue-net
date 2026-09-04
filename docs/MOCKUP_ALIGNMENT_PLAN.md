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

### 4.6 ✅ Manajemen Alat Kerja — `pages/alat-kerja.html` + `assets/js/alat-kerja.js` — DONE 2026-09-02
Mockup: `manajemen alat kerja.png`
- **PERTAHANKAN:** form "Buat Request Alat Kerja" + "Daftar Request Alat Kerja"
  (dipindah ke `<details class="rn-input-drawer">`, tetap fungsional).
- **TAMBAH (semua real data, bukan dekorasi):** 6 KPI (Alat Tersedia / Kebutuhan
  Alat / Operator Aktif / Dispatch Berjalan / BBM Kritis / Alat Rusak) dengan
  drill modal; **Inventari Alat per Kategori** (6 tile: Ekskavator / Genset /
  Pompa Air / Forklift / Chainsaw / Perahu Karet + legend Ready/Assigned/
  Maintenance/Critical dari `RN Resource Profile.availability_status`);
  **Operator & Tenaga Teknis** dari `RN Work Tool Deployment.operator_name`;
  **Matching Kebutuhan Alat** ranked by priority dengan kandidat alat available;
  **Jadwal Dispatch Alat**; **Lokasi Kerja & Produktivitas** (completion-rate
  bar per `destination_location`); **BBM & Support Operasional** (Solar/Bensin/
  Oli via keyword match ke `RN Stock Observation`, sama pola dengan Dapur
  Umum's `gas_bbm`); **QR / Asset Tracking** (honest static: tiap Resource
  Profile record punya Kode Aset (`name`), tabel lookup manual — TIDAK ada
  scanner kamera beneran, dicatat sebagai keterbatasan); **Hambatan Alat
  Kerja** (request critical/urgent belum matched + BBM kritis + alat rusak) +
  **Ringkasan Hari Ini** (Penggunaan % / Jam Operasional / Dispatch Selesai /
  Kerusakan Baru — semua derived dari deployment/resource timestamps hari ini).
- **BACKEND:** `api_resource_tools.tools_board(disaster_event)` guest →
  `{totals, kpi_items, categories, operators, matches, dispatch, sites, fuel,
  blockers, summary, asset_registry}`. Legacy `dashboard()` diperbaiki jadi
  `allow_guest=True` + `rn_actor(required=False)` (konsisten dengan fix di
  kitchen/shelter/logistics/volunteer) — PIC tetap disembunyikan dari guest.
- **SEED:** data event-sim-001 sebelumnya kosong (0 Resource Profile bertag
  event, 0 Request, 0 Deployment) — diseed 30 Resource Profile (5 per kategori
  × 6 kategori, status tersebar Ready/Assigned/Maintenance/Critical), 9 Work
  Tool Request (mix priority/status), 5 Work Tool Deployment (operator +
  jadwal hari ini), 3 Stock Observation BBM/Oli di Posko BNPB Meulaboh.
- **TAMBAHAN 2026-09-02 (owner directive, sesi sama):** **Object Kerja &
  Prediksi Kebutuhan Alat** — halaman baru `RN Work Object` (longsoran/
  jembatan putus/puing berat/pohon tumbang/akses terendam/lainnya) dengan
  ukuran (m³/m/m²/pohon), diprediksi jadi kebutuhan alat via heuristik
  sederhana yang didokumentasikan (bukan rumus rekayasa resmi), dicocokkan
  ke ketersediaan alat real (`ready_available`/`gap`). Endpoint guest
  `work_objects_board` + write `create_work_object`/
  `update_work_object_status`. **Kelompok Alat (Normalisasi AI Lintas
  Posko)** — panel baru di `tools_board.groups`: alat sejenis dari SEMUA
  owner/posko dikelompokkan otomatis pakai `canonical_category/group/item`
  (field baru di `RN Resource Profile`, pola sama dgn `RN Stock
  Observation`/`RN Community Need`) + `classify_text()` (rule-based, sudah
  ada di `rescue_net.intelligence.normalization`, diperluas dgn 6 rule alat
  kerja baru: Ekskavator/Genset/Pompa Air/Forklift/Chainsaw/Perahu Karet).
  Alat dengan satuan berbeda antar posko ditampilkan terpisah per satuan
  (tidak dijumlahkan langsung) — normalization_source jujur berlabel
  manual/rule/ai, tidak pernah mengklaim panggilan AI black-box padahal
  aturan kata kunci deterministik.

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

### 4.10 ✅ Program Khusus — `pages/program-khusus.html` + `assets/js/program-khusus.js` — DONE 2026-09-02
Mockup: `program khusus.png`
- **PERTAHANKAN:** "Daftar Program", form "Buat Program", form "Update Progress
  Program" — moved into `<details class="rn-input-drawer">`, kept fully working.
- **TAMBAH (real data):** 6 KPI (Program Aktif / Critical / Selesai / Milestone
  Terlambat / Lokasi Belum Terlayani / Butuh Support) with drill modal; kiri
  **Daftar Program** kartu (nama + kategori + lokasi + progress bar) + tab
  Semua/Aktif/Critical/Selesai; kanan **detail program terpilih** (header +
  Overall Progress + Target/Tercapai + tab **Ringkasan** (deskripsi, PJ,
  periode, sasaran, Evidence Program strip, 4 kartu Support dengan deep-link
  ke modul terkait) / **Anggaran** (target/diterima/terpakai) / **Riwayat**
  (real `RN Donor Program Update` timeline)).
- **Deviasi jujur dari mock-up:** "Rencana Kerja"/"Dokumen"/"Catatan" sebagai
  tab terpisah, "Lokasi Implementasi" mini-map, dan "Verifikasi Output" TIDAK
  dibangun — tidak ada data rinci per-baris (rencana kerja/dokumen) atau
  koordinat per-program di model data; Anggaran + Riwayat Update sudah jadi
  sumber kebenaran progres yang jujur. 4 kartu Support (Logistik/Distribusi/
  Relawan/Alat Kerja) adalah deep-link nyata ke modul terkait, BUKAN status
  "Butuh Support"/kuantitas fabrikasi — tidak ada field relasional yang
  menghubungkan program ke kebutuhan spesifik modul lain di data model saat
  ini.
- **BACKEND:** `api_donor_program.program_board(disaster_event)` +
  `program_detail(program)`, keduanya guest. Sumber: `RN Donor Program` (field
  `program_type` dipakai sebagai label kategori — bukan filter, "special_program"
  ternyata cuma default form lama, bukan flag scoping nyata) + `RN Donor
  Program Update`. Evidence Program pakai `event_evidence()` yang sama
  (dicocokkan by nama program/lokasi ke `location_text`, pola sama dengan
  Dapur Umum/Posko Logistik).

### 4.11 ✅ Profil Sumber Daya — `pages/resource-profile.html` + `assets/js/resource-profile.js` — DONE 2026-09-02
Mockup: `Profil Sumber Daya.png` — turned out to be a **personal volunteer/
member profile** (not the multi-category directory the old page was), same
kind of concept-mismatch as Shelter/Verification earlier in this pass.
- **PERTAHANKAN:** old "Organizations"/"Posko & Nodes"/"Volunteers"/
  "Tools / Shared Resources" 4-panel directory kept working inside a
  `<details class="rn-input-drawer">`.
- **TAMBAH (real data, self-service editable by the profile's own owner):**
  5 status chips (Peran Utama / Tingkat Kepercayaan / Email / HP / ID
  Terverifikasi — all real field checks, no fabricated 0-100 trust score);
  profile card (initials avatar — no AI image-gen available, same
  placeholder policy as evidence photos — name, Aktif badge, role/org,
  location/email/phone, Tentang Saya, real "Bergabung sejak" from the
  account's own `creation` timestamp, Edit Profil); **Keahlian/Skill**
  (main_skill + skill_tags), **Kendaraan**/**Fasilitas**/**Bantuan Barang
  Tersedia** (all `RN Resource Profile`, `owner_type=individual`),
  **Wilayah Layanan**/**Waktu Ketersediaan** (2 new fields), **Kebutuhan
  Support** (`RN Work Tool Request`, `requested_by_type=other` — the
  doctype's own `validate()` only allows posko/organization/other, "other"
  is the closest fit for an individual requester) — every "+ Tambah"/"Atur
  Jadwal"/"Ajukan Kebutuhan" is a real write, login-gated.
- **BACKEND:** `api_resource_tools.resource_profile_board(user_account)`
  guest-read (defaults to the logged-in user, else a seeded demo profile —
  same "default when nothing specified" convention as every other board) +
  new self-service writes `add_personal_resource`/`add_personal_support_need`
  (deliberately NOT the existing manager-only `create_resource_profile`/
  `create_work_tool_request`, which require a MANAGER_ROLES operator role —
  wrong gate for "I manage my own profile"). Extended
  `api_volunteer.update_profile` with `skill_category`/`preferences`/
  `equipment_owned`/`service_areas`/`availability_schedule`. New
  `RN Volunteer Profile` fields: `service_areas`, `availability_schedule`.
  Extended `_can_manage_reference` with an `individual` case (a person can
  manage their own `owner_type=individual` resources). `RN Volunteer Skill`
  mentioned in the original plan line does not actually exist as a
  doctype — real skills come from `main_skill`/`skill_tags` instead.

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
3. ✅ **Manajemen Relawan** — DONE 2026-09-02 (`volunteer_board` guest endpoint +
   `api_volunteer.dashboard` guest-fix). Lihat `HANDOVER.md`.
4. ✅ **Manajemen Distribusi** — DONE 2026-09-02 (`distribusi_board` guest
   endpoint + real `auto_match_distribution` write action + 2 new RN
   Transport Space (laut/udara) filling a genuine data gap). Lihat `HANDOVER.md`.
5. ✅ **Evidence Center** — DONE 2026-09-02 (`evidence_board` guest endpoint,
   `event_evidence`/`_ev_norm` diperluas dengan module/visibility/mime; 2
   doctype evidence dapat field `visibility_scope` baru). Lihat `HANDOVER.md`.
6. ✅ **Verification & Approval** — DONE 2026-09-02 (`approval_queue` +
   `approval_item_detail` + real write `approval_action`; "Merge" intentionally
   not implemented). Lihat `HANDOVER.md`.
7. ✅ **Organisasi & Posko** + **Registrasi & Verifikasi Posko** (halaman
   baru) — DONE 2026-09-02, keduanya. Lihat `HANDOVER.md`.
8. ✅ **Manajemen Alat Kerja** — DONE 2026-09-02 (`tools_board` guest endpoint;
   6 kategori alat + 30 Resource Profile, 9 Work Tool Request, 5 Work Tool
   Deployment, 3 Stock Observation BBM diseed untuk event-sim-001; legacy
   `dashboard()` diperbaiki guest-access). Lihat `HANDOVER.md`.
9. ✅ **Profil Sumber Daya** — DONE 2026-09-02 (`resource_profile_board` guest
   endpoint; turned out to be a personal volunteer profile, not a directory —
   old directory kept in `<details>`; 2 new RN Volunteer Profile fields). Lihat
   `HANDOVER.md`.
10. ✅ **Program Khusus** — DONE 2026-09-02 (`api_donor_program.program_board`/
    `program_detail` guest; program_type dipakai sebagai kategori, bukan filter).
    Lihat `HANDOVER.md`.
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
- [x] `api_volunteer.volunteer_board(disaster_event)` — DONE 2026-09-02; `dashboard` juga dibuat `allow_guest`
- [x] `api_control_centre.distribusi_board(disaster_event)` — DONE 2026-09-02, + `auto_match_distribution` write action
- [x] `api_control_centre.evidence_board(disaster_event)` + perluas `event_evidence` — DONE 2026-09-02
- [x] `api_verification.approval_queue(disaster_event)` + `approval_item_detail` — DONE 2026-09-02, + real `approval_action` write endpoint
- [x] `api_control_centre.org_posko_board(disaster_event)` + `posko_verification_checklist` — DONE 2026-09-02
- [x] `api_resource_tools.tools_board(disaster_event)`
- [x] `api_resource_tools.resource_profile_board(user_account)`
- [x] `program_board(disaster_event)` + `program_detail(program)`
- [x] `comms_board(disaster_event)` (+ doctype/seed alat komunikasi) — DONE 2026-09-03 (Step 11/12; api_comms.py + 3 doctypes + seed_comms.py; pages/alat-komunikasi.html). Semua 12 langkah roadmap selesai.
