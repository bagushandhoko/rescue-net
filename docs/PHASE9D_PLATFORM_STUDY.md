# Fase 9d — Kajian platform sejenis: Sahana Eden, Ushahidi, KoboToolbox/ODK

Tanggal: 2026-10-08. Status: kajian saja (tanpa kode, tanpa deploy). Terkait: ADR-0002, ADR-0004, ADR-0005, NEXT_STEPS 9d.
**Tujuan: mengambil pelajaran dan peluang integrasi. Bukan mengganti Rescue-Net** — ketiganya tidak punya model
posko/logistik/organisasi + approval silang yang menjadi inti Rescue-Net.

Tanda `[belum diverifikasi]` = klaim dari ingatan atau sumber sekunder/usang; cek ke repo/dokumen resmi sebelum jadi keputusan.
Pencarian web (mode standard, 2026-10-08) hanya memberi hasil sebagian; banyak hasil adalah arsip lama.

## 1. Ringkasan satu halaman

| | Sahana Eden | Ushahidi | KoboToolbox / ODK |
|---|---|---|---|
| Fungsi | Manajemen bencana penuh (orang hilang, shelter, logistik, relawan, organisasi) | Pengumpulan + kurasi laporan krisis (crowdsourcing, peta) | Pengumpulan data lapangan berbasis form XLSForm, offline-first |
| Mirip bagian Rescue-Net | Domain (posko, logistik, organisasi), sinkron antar-instance | Laporan Masyarakat + review | Form lapangan, asesmen cepat |
| Lisensi | MIT (sumber arsip OSGeo; fork Eden ASP juga MIT) | AGPL-3.0 (LICENSE repo + DPG) | KPI: AGPL-3.0 (staf komunitas Kobo); registri DPG mencatat BSD-2-Clause + AGPL-3.0 (komponen beda). ODK: Apache-2.0 (Wikipedia/DPG; file LICENSE `getodk/central` [belum diverifikasi]) |
| Pemeliharaan | **Tidak jelas** — halaman Launchpad "Obsolete", pindah ke GitHub; tidak ditemukan rilis resmi; aktivitas terkini [belum diverifikasi] | v5 API sedang menggantikan v3 (v3 ditandai deprecated di dokumen Mzima); versi terbaru [belum diverifikasi] | Aktif (paket R menyebut perubahan KPI 2.026.03 → batas halaman 1.000 submission; sumber sekunder) |
| Stack | Python 3.6+ di atas web2py | PHP (Lumen → Laravel) + klien baru "Mzima" | Kobo: Django (KPI) + Enketo; ODK Central: Node.js [belum diverifikasi] |

## 2. Sahana Eden

### 2.1 Arsitektur & model data singkat
- Framework web2py (Python); modul domain: organisasi (`org`), orang/relawan (`hrm`/`pr`), shelter (`cr`), inventori/pasokan
  (`inv`/`supply`), permintaan (`req`), kebutuhan/asesmen, peta (`gis`), laporan insiden (`irs`). Nama modul [belum diverifikasi]
  terhadap versi sekarang.
- Resource-based: satu definisi tabel menghasilkan CRUD, REST/CSV/XML/JSON, dan filter. Impor/ekspor berbasis *stylesheet XSLT*
  per resource.
- Hierarki wilayah (`gis_location` L0–L4) dan **organisasi + site** (fasilitas) sebagai sumbu: stok, kebutuhan, dan orang
  melekat pada organisasi/site — mirip organisasi + posko di Rescue-Net.
- Dokumentasi menyebut framework **sinkronisasi antar-instance** (kantor lapangan ↔ pusat, termasuk instalasi di flash drive).

### 2.2 Pelajaran relevan
- **Federasi/sinkron:** model "sync lewat repositori + job + kebijakan per resource" membuktikan bahwa sinkron selektif per
  tabel itu perlu dan bisa dilakukan. Rincian detail (konflik, resolusi, pemilik data) [belum diverifikasi] — baca kode
  `s3sync` sebelum menyalin gagasan apa pun. Klaim yang aman: konsepnya sejalan dengan ADR-0004 (kebijakan per DocType/field,
  bukan replikasi DB).
- **Pemetaan wilayah:** hierarki lokasi dengan kode eksternal (P-code, GeoNames) sebagai atribut tambahan, bukan pengganti kunci —
  sejalan dengan ADR-0005 (kunci Kemendagri + crosswalk).
- **Permintaan ↔ penawaran ↔ pengiriman** sebagai tiga entitas terpisah (seperti `req`/`inv`/`send`) — Rescue-Net sudah punya
  Kebutuhan/Penawaran/Flow; tidak ada yang perlu diubah, hanya konfirmasi arah.
- **Peringatan keras:** proyek ini besar, monolitik, dan status pemeliharaannya tidak jelas. Jangan bergantung padanya sebagai
  runtime; hanya sumber ide dan (jika perlu) format tukar data.

### 2.3 Risiko
- Memakai kodenya langsung = utang pemeliharaan (web2py jauh lebih sepi dari Frappe) dan model data berbeda dari Rescue-Net.
- Dokumentasi di web berserakan antara fork dan arsip lama; mudah mengutip hal usang.

## 3. Ushahidi

### 3.1 Arsitektur & model data singkat
- **Survey** (form yang bisa dikonfigurasi, dengan *stage*/tahap dan field kustom) → **Post** (satu laporan) → nilai field.
  Sumber data: web, SMS (SMSSync, FrontlineSMS, Twilio, Nexmo/Vonage, Africa's Talking), email, Twitter — sesuai dokumen
  pengguna (halaman Data Sources; dokumen sendiri mengingatkan isinya bisa usang).
- **Alur kurasi:** post yang dikirim publik masuk antrian review admin sebelum terbit; *task* pada post bisa diwajibkan
  selesai sebelum post boleh dipublikasikan (dokumen pengguna). Nama persis status internal [belum diverifikasi].
- REST API v5 (post, survey; baru mencakup dasar-dasarnya saat diperkenalkan) menggantikan v3; backend pindah Lumen → Laravel
  (issue GitHub). Klien baru "Mzima".

### 3.2 Pelajaran relevan
- **Verifikasi laporan:** pemisahan tegas "diterima" vs "terbit/terverifikasi" dan *gerbang berbasis tugas* (mis. wajib
  geolokasi + cek privasi sebelum tayang). Deployment Uchaguzi memakai tim penerbit sebagai kontrol kualitas pertama:
  field wajib, geolokasi, terjemahan, privasi. Rescue-Net sudah punya status "belum dikonfirmasi" + antrian review AI/manusia
  (Fase 7); pelajarannya: **daftar periksa wajib per jenis laporan** sebelum publik, dan jejak siapa yang menyetujui.
- **Multi-kanal masuk** (SMS/email) memakai satu antrian — sejalan dengan antrian review Rescue-Net; kanal baru = sumber baru,
  bukan alur baru.
- **Form dapat dikonfigurasi** tanpa deploy kode — Rescue-Net sebaiknya tidak membangun form builder sendiri (lihat 4).

### 3.3 Risiko
- AGPL-3.0: bila kode Ushahidi disalin/dimodifikasi dan dilayankan lewat jaringan, kewajiban sumber terbuka berlaku. Cukup
  pakai API/ekspor-nya, jangan menyalin kode. Konsultasi hukum bila ragu.
- Transisi v3 → v5 dan klien baru: kontrak API bisa berubah; integrasi harus dibungkus adaptor tipis.
- Crowdsourcing terbuka rawan spam/hoaks; kontrolnya di sisi review, bukan di platform.

## 4. KoboToolbox / ODK

### 4.1 Arsitektur & model data singkat
- Form ditulis sebagai **XLSForm** (spreadsheet → XForm XML), diisi lewat aplikasi Android (Collect) atau web (Enketo) —
  offline, lalu dikirim saat ada koneksi. Submission = XML (OpenRosa) dengan `instanceID` dan `deprecatedID` untuk edit.
- **KoboToolbox** (KPI): aset (form) + submission; API v2 (`/api/v2/assets/{uid}/data/`) dengan token autentikasi; ekspor
  CSV/XLS/GeoJSON; **REST service** yang mendorong submission baru ke URL luar (webhook).
  Detail jalur persis `/data/` dan format respons [belum diverifikasi] terhadap dokumen resmi
  (support.kobotoolbox.org/api.html).
- **ODK Central:** antarmuka REST, OpenRosa, dan OData; dokumen menyebut REST paling cocok untuk JSON sederhana; submission
  dapat dibuat via REST dengan POST XML. Central patuh pada API pengiriman form OpenRosa tetapi tidak pada bagian
  autentikasinya. Status submission (mis. `approvalState`: approved/hasIssues/rejected) dan *review state* [belum diverifikasi].

### 4.2 Pelajaran relevan
- **Form lapangan offline:** mekanisme `instanceID` unik per submission memberi idempotensi alami saat kirim ulang — ini
  persis `event_id` di `RN Sync Log` (ADR-0004); pola terbukti.
- **Form sebagai data, bukan kode:** asesmen cepat pascabencana (RHA/MIRA-like, form posko, pemeriksaan stok) lebih murah
  dikelola sebagai XLSForm daripada layar HTML baru tiap kali. Rescue-Net tidak perlu form builder sendiri; cukup menerima
  hasilnya.
- **Review state** per submission (disetujui/bermasalah/ditolak) — pola sama dengan antrian review; bisa dipetakan.
- **Daftar pilihan berjenjang (cascading select)** untuk wilayah di form: sumber kebenarannya sebaiknya daftar P-code
  ADR-0005, diekspor ke lembar `choices` XLSForm.

### 4.3 Risiko
- AGPL-3.0 pada KPI: memanggil API dari luar umumnya tidak menularkan lisensi (pendapat informal di forum komunitas — bukan
  nasihat hukum), tetapi menyalin/memodifikasi kodenya iya.
- Server Kobo gratis publik (kobotoolbox.org) punya kuota; jangan membuat alur kritis bergantung padanya tanpa rencana
  (self-host atau ODK Central). Batas persisnya [belum diverifikasi].
- Data dari lapangan membawa PII (nama, HP, lokasi rumah). Impor ke Rescue-Net harus tunduk klasifikasi ADR-0004 bagian C.
- Skema submission bebas: field tidak terduga, lampiran besar (foto/audio), pengulangan (*repeat group*), jawaban kosong.

## 5. Pelajaran lintas-platform untuk Rescue-Net

### 5.1 Federasi / sinkron offline
1. Tiga platform sepakat: **sinkron selektif per jenis data**, bukan replikasi DB (ADR-0004 sudah memilih ini).
2. **ID unik dibuat di klien** (instanceID, UUID) → idempoten saat kirim ulang. ADR-0004 `uid` UUIDv7 + `event_id` sesuai.
3. Konflik jarang diselesaikan otomatis dengan baik; ODK menghindarinya dengan membuat submission **tak bisa diubah** (edit = versi
   baru yang menggantikan lewat `deprecatedID`). Padanan: event append-only + proposal ke pemilik (ADR-0004 B.3).
4. Uji "koneksi putus di tengah kirim" harus ada sejak awal (sudah diwajibkan di 9e).
5. [belum diverifikasi] Cara Eden menangani konflik — baca `s3sync` sebelum mengklaim apa pun.

### 5.2 Form lapangan
- Pertahankan form Rescue-Net untuk alur inti (kebutuhan, posko, laporan warga). Untuk asesmen khusus per bencana, **terima**
  form dari ODK/Kobo daripada membangun builder.
- Form lapangan harus bekerja dengan sinyal lemah: kirim ringkas, lampiran terpisah/ditunda (praktik ODK).

### 5.3 Verifikasi laporan
- Satu antrian, banyak sumber (Ushahidi): web, app, WA, ODK/Kobo masuk antrian yang sama, dengan label `source`.
- Gerbang wajib sebelum "terbit" (daftar periksa), pemisahan "diterima" vs "terverifikasi", jejak pemutus (Ushahidi/Uchaguzi).
- Konsisten dengan ADR-0002: AI hanya memberi saran, manusia memutuskan; impor eksternal **tidak pernah** langsung menjadi data
  terverifikasi.

### 5.4 Wilayah / P-code
- Eden dan Kobo (via cascading select) sama-sama bergantung pada daftar wilayah berkode; tanpa kode pasti, impor eksternal
  jatuh ke pencocokan nama (rapuh). **Prasyarat integrasi apa pun: ADR-0005 langkah 1–2 (RN Admin Area terisi + crosswalk).**

## 6. Peluang integrasi (diurutkan dari paling aman)

### 6.1 Impor submission ODK/Kobo → Laporan Masyarakat lewat antrian review (rekomendasi utama)
Arah **masuk saja**, read-only terhadap Kobo/ODK, dengan karantina:
1. **Konektor** (adaptor tipis, satu modul, mis. `integrations/odk_kobo.py`): tarik berkala (kursor `_submission_time`/id terakhir)
   atau terima webhook REST service Kobo. Kredensial token di pengaturan platform (bukan di kode; seperti kunci AI Fase 7).
2. **Peta field** per form: tabel `RN Import Form Mapping` (id form, field sumber → field RN, versi form). Form tanpa peta
   ditolak/ditandai — tidak ditebak.
3. **Penyimpanan karantina:** submission masuk sebagai `RN Community Report` berstatus `source=odk|kobo`, `belum dikonfirmasi`,
   tidak publik, dengan `external_id` (instanceID/`_uuid`) + `external_server` unik → **idempoten** (impor ulang tidak membuat
   duplikat).
4. **Antrian review** yang sudah ada (Fase 7): AI memberi saran duplikat/routing posko (ADR-0002), manusia memutuskan.
   Wilayah dicocokkan lewat kode (ADR-0005 D.2), bukan nama; tak cocok → `area_unmatched`.
5. **Data pribadi:** hanya field yang dipetakan yang diambil; nomor HP/nama pelapor mengikuti aturan "tidak keluar server"
   (ADR-0004 C) — impor tidak memperluasnya. Lampiran (foto) diunduh ke penyimpanan RN, bukan ditautkan ke server Kobo.
6. **Batas laju + ukuran** per tarikan; submission gagal masuk ke log galat dengan alasan, tidak menghentikan batch.
7. **Tes wajib:** idempotensi, form tak dipetakan, field asing, `repeat group`, lampiran besar, token salah/kedaluwarsa,
   kebocoran PII ke publik, dan koneksi putus di tengah tarikan.

### 6.2 Ekspor ke Kobo/ODK (opsional, nanti)
Daftar pilihan wilayah dan posko (publik saja) diekspor sebagai lembar `choices` XLSForm agar form lapangan memakai
kode yang sama. Sejalan dengan ekspor HXL ADR-0005 B. Risiko rendah (data klasifikasi "boleh keluar").

### 6.3 Ushahidi
Peluang kecil: bila suatu organisasi mitra sudah memakai Ushahidi, konektor serupa 6.1 dapat menarik post terbit lewat API v5
ke antrian review. **Tidak diusulkan membangun sekarang** — tidak ada kebutuhan owner yang tercatat; v3→v5 masih bergerak.

### 6.4 Sahana Eden
Tidak ada integrasi runtime yang diusulkan (pemeliharaan tidak jelas). Jika ada mitra yang memakainya, jalur tukar yang
paling realistis adalah ekspor CSV/XML/JSON kedua sisi + HXL (ADR-0005), diperiksa dulu terhadap versi yang mitra jalankan
[belum diverifikasi].

## 7. Risiko lintas-integrasi
| Risiko | Mitigasi |
|---|---|
| Data tak tepercaya masuk sebagai fakta | Karantina + antrian review; tidak pernah auto-publik (ADR-0002) |
| Kebocoran PII dari/ke server eksternal | Whitelist field per peta; klasifikasi ADR-0004 C; test kebocoran |
| Duplikat tiap tarikan ulang | `external_id` + `external_server` unik |
| Kontrak API berubah (Ushahidi v5, Kobo KPI) | Adaptor tipis + versi di peta; alarm bila respons tak sesuai skema |
| Lisensi AGPL menular | Hanya pakai API/ekspor, jangan salin kode; tinjau hukum bila perlu |
| Ketergantungan pada server gratis pihak ketiga | Self-host atau ODK Central bila kritis; konektor menyimpan salinan |
| Wilayah tidak cocok | Prasyarat ADR-0005; `area_unmatched` ditandai, laporan tetap diterima |
| Beban NAS (memori ketat, lihat Status) | Tarik berkala berbatas, bukan streaming; jalankan di test stack dulu |

## 8. Rekomendasi
1. **Rescue-Net tetap platform utama.** Tidak ada platform yang dikaji menggantikan posko + logistik + org + approval silang.
2. **Prioritas:** (a) selesaikan ADR-0005 langkah 1–2 (wilayah berkode) — prasyarat semua integrasi; (b) konektor ODK/Kobo →
   antrian review (6.1) sebagai satu-satunya integrasi yang layak dibangun, di test stack dulu (9e).
3. **Jangan bangun form builder** dan **jangan menyalin kode** AGPL (Ushahidi, KPI). Pakai API.
4. **Salin pola, bukan kode:** instanceID/idempotensi, review-state, gerbang verifikasi, sinkron selektif — semuanya sudah
   searah dengan ADR-0004/0005/Fase 7; tidak ada perubahan ADR yang diperlukan, hanya tambahan: kolom `source`,
   `external_id`, `external_server` pada Laporan Masyarakat.
5. **Eden/Ushahidi:** tidak ada integrasi sekarang; tinjau ulang bila mitra nyata memakainya.
6. **Verifikasi sebelum implementasi** (semua bertanda [belum diverifikasi]): lisensi file `getodk/central`, jalur + skema
   `/api/v2/assets/{uid}/data/` Kobo, kuota server publik Kobo, status terbaru repo `sahana/eden`, versi rilis Ushahidi.

## 9. Pertanyaan untuk owner
1. Apakah ada mitra/organisasi nyata yang sudah memakai Kobo/ODK, Ushahidi, atau Eden? (menentukan prioritas 6.1/6.3/6.4)
2. Server Kobo/ODK mana yang dipakai (kobotoolbox.org publik, self-host, ODK Central)? Menentukan kuota dan autentikasi.
3. Untuk impor 6.1: apakah laporan hasil impor boleh dilihat org admin saja sebelum direview, atau langsung di antrian posko?
4. Setuju impor ODK/Kobo dibangun **setelah** wilayah berkode (ADR-0005) tersedia?

## Sumber (pencarian 2026-10-08, sebagian arsip/sekunder)
- Sahana: Wikipedia "Sahana Software Foundation"; Launchpad sahana-eden trunk (Obsolete); OSGeo overview (MIT);
  sahana-eden.readthedocs.io; archive.flossmanuals.net/sahana-eden.
- Ushahidi: github.com/ushahidi/platform LICENSE (AGPL-3.0); digitalpublicgoods.net/r/ushahidi;
  docs.ushahidi.com (Data Sources, Adding Posts, Uchaguzi Publishing); github.com/ushahidi/platform/issues/4753.
- Kobo/ODK: digitalpublicgoods.net/r/kobotoolbox dan /r/odk; community.kobotoolbox.org (lisensi AGPL, klien API);
  docs.getodk.org (Central API, OpenRosa); dokumentasi paket robotoolbox/ruODK (sekunder).
