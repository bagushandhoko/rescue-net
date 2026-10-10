# Fase 10 — audit + desain singkat (10b, 10f, 10a)

Dibuat 2026-10-08. Aturan Fase 10: cek dulu yang sudah ada, tulis desain singkat, **minta persetujuan owner sebelum membangun**.
Prioritas owner: 10b, 10f, 10a. Federasi (Fase 9a/9b/9e–9g) ditunda ke belakang atas perintah owner; 9c D.1 (wilayah berkode) sudah selesai di test stack.
Prinsip yang berlaku di semua: data pribadi baru wajib punya sentinel di sapuan tamu (`test_public_endpoints`); AI hanya saran (ADR-0002).

---
## 10b — QR paket bantuan + kartu pengungsi

### Yang sudah ada (fakta kode)
- Pelacakan per kiriman: `control_centre/distribusi.py::flow_trace` (tamu, hanya subset aman: barang, jumlah, nama dua posko, status, lini masa) →
  `pages/lacak-logistik.html`. Label QR cetak per kiriman di `management-distribusi.html` (`assets/js/distribusi.js`, pustaka `assets/vendor/qrcode`).
- Kode lacak = `RN-` + 8 karakter terakhir nama Flow (`_distribusi_trace`). `_resolve_flow_by_trace` memindai sampai 5.000 flow tiap panggilan
  (lambat dan, secara teori, bisa bentrok di 8 karakter).
- Rantai status Flow sudah dijaga controller (planned → … → received) dan menambah stok hanya lewat `receive_flow_and_update_stock`.
- `RN Shelter Household` punya `household_code`; belum ada kartu/QR dan belum ada catatan penerimaan per keluarga.

### Celah
1. QR hanya **dibaca publik**; tidak ada **scan** yang mencatat serah-terima (kirim / transit / terima) → belum ada rantai bukti (chain of custody).
2. Tidak ada QR per batch, tidak ada kartu QR keluarga, tidak ada pencegahan penerimaan ganda.
3. Tidak ada pemindai (kamera) maupun antrean scan offline.
4. Token lacak dapat ditebak sebagian (potongan nama) dan pencariannya O(n).

### Rancangan singkat (usulan, bertahap)
- **Langkah 1 — Rantai bukti per kiriman.** DocType baru `RN Custody Scan` (append-only): `flow`, `scan_type` (dispatch/transit/handover/receive), `actor`, `posko`,
  `scanned_at`, lat/lng, `offline_id` (kunci idempotensi), `evidence` (opsional), `note`. Endpoint `api_custody.record_scan` yang masuk lewat graf status Flow yang sudah ada
  (scan `receive` = jalur `receive_flow_and_update_stock`, bukan jalan pintas). Token QR baru: field `trace_token` acak per Flow (kode lama tetap berlaku).
- **Langkah 2 — Pemindai.** `pages/scan.html` (PWA; `BarcodeDetector` bila ada, cadangan pustaka JS yang di-vendor), antrean offline memakai `rn-sync-engine` yang sudah ada.
- **Langkah 3 — Kartu keluarga.** `RN Household Card` (token acak, tanpa nama di QR) + `RN Aid Receipt` (keluarga, putaran distribusi, barang, jumlah, posko, waktu);
  aturan: satu penerimaan per keluarga per putaran distribusi; hasil scan ke petugas hanya "boleh / sudah menerima pada …", tanpa data pribadi.
- Privasi: QR hanya memuat token buram; semua keputusan di server; nama anggota keluarga tidak pernah keluar lewat endpoint tamu.

### Pertanyaan owner
1. Mulai dari langkah 1 (rantai bukti kiriman), atau dari kartu keluarga (langkah 3)?
2. "Putaran distribusi" untuk satu-penerimaan-per-keluarga: harian, per jenis bantuan, atau ditetapkan koordinator?
3. Pemindai lewat kamera ponsel (PWA) cukup, atau perlu pemindai fisik?

---
## 10f — papan kebutuhan publik untuk donatur

### Yang sudah ada
- Papan Bencana Aktif (`api_control_centre.active_disasters_board`) memuat `kebutuhan_items`, tapi **hanya yang kritis** (contoh Krakatau: 7 butir, tiap butir: barang, urgensi,
  posko, tautan). Tanpa daftar lengkap per wilayah, tanpa jumlah, tanpa umur data, tanpa "jangan dikirim".
- Halaman donatur `pages/kirim-bantuan.html` (form bantuan cepat) dan aturan tujuan bantuan (offer → posko target) sudah ada; tidak ada daftar kebutuhan publik khusus.
- Visibilitas posko ke publik sudah diatur (`public_detail`, `control_centre_share`, `access_policy.public_posko_allowed`).

### Celah
Donatur tidak bisa melihat apa yang benar-benar dibutuhkan (jumlah, wilayah, kapan diperbarui) dan apa yang **tidak** dibutuhkan lagi → risiko donasi salah sasaran.

### Rancangan singkat
- Halaman `pages/kebutuhan-publik.html` + endpoint tamu `api_public_needs.board(event, wilayah?)`.
- Sumber deterministik (prinsip konsistensi KPI): kebutuhan terbuka (`RN Logistic Need` status terbuka) dikelompokkan per `canonical_item`+satuan per posko publik;
  jumlah kurang = kebutuhan − bantuan dalam perjalanan − stok efektif. **"Sudah cukup / jangan kirim"** = turunan yang sama (kurang ≤ 0) — tanpa kolom baru di tahap 1.
- Tiap baris: barang, jumlah kurang, satuan, posko/wilayah (kode wilayah bila ADR-0005 D.2 jalan), "diperbarui N jam lalu", tombol "Kirim ke posko ini" → form donatur dengan tujuan terisi.
- Tahap 2 (butuh persetujuan migrate): catatan eksplisit posko "barang yang tidak dibutuhkan / kemasan yang tidak diterima".
- Tanpa data sensitif: hanya posko yang publik; tanpa kontak pribadi; sapuan tamu menjaga ini.

### Pertanyaan owner
1. Tahap 1 turunan-saja dulu (tanpa kolom baru) disetujui?
2. Posko mana yang tampil: hanya `public_detail=public`, atau juga ringkasan wilayah dari posko yang tertutup?
3. Tampilkan jumlah persisnya, atau rentang/tingkat urgensi saja?

---
## 10a — peringatan dini & data resmi (BMKG)

### Yang sudah ada
Belum ada integrasi BMKG/inaRISK sama sekali (hanya `RN Disaster Event`). ADR-0005 bagian C (disetujui) sudah menetapkan: CAP **masuk saja**, tampil sebagai banner, tidak membuat tindakan otomatis.

### Fakta sumber (dicek langsung dari NAS, 2026-10-08)
- `https://data.bmkg.go.id/DataMKG/TEWS/autogempa.json` (gempa terbaru: Tanggal, Jam, DateTime UTC, Coordinates, Magnitude, Kedalaman, Wilayah, Potensi, Dirasakan, Shakemap), `gempaterkini.json` (daftar M5+), `gempadirasakan.json` — JSON, HTTP 200.
- `https://www.bmkg.go.id/alerts/nowcast/id/rss.xml` — RSS peringatan dini cuaca (CAP), HTTP 200.
- Syarat penggunaan/atribusi data BMKG **belum saya verifikasi**; tampilkan "Sumber: BMKG" dan konfirmasi ketentuan sebelum rilis.

### Rancangan singkat
- DocType `RN Early Warning` (ADR-0005 C): `source`, `identifier` (kunci dedupe), `kind` (earthquake/weather), `severity`, `title`, `area_desc`, lat/lng, `magnitude`, `depth_km`,
  `issued_at`, `expires_at`, `admin_areas`, `raw` (terpotong), `status` (new/acknowledged/dismissed), `draft_event` (Link).
- Pengambil terjadwal (scheduler Frappe, tiap 5–10 mnt, batas ukuran respons, timeout, tanpa mengikuti pengalihan ke host lain; XML dibaca dengan penolakan DOCTYPE/entitas).
- Aturan ambang (pengaturan, mis. M ≥ 5,0 dan kedalaman ≤ 100 km di wilayah Indonesia) → membuat **DRAFT** `RN Disaster Event`, menandai posko/organisasi dalam radius (menurut magnitudo)
  dan menampilkan banner di Bencana Aktif + Control Centre. **Aktivasi event tetap oleh manusia.** Notifikasi WA lewat `api_notify` ke admin organisasi di radius, berbatas laju, bertuliskan "belum diverifikasi".
- Tanpa AI. Dedupe idempoten; kegagalan sumber tidak mengganggu apa pun (dicatat, banner "data BMKG tidak terjangkau").

### Pertanyaan owner
1. Tahap 1 hanya gempa (JSON) dulu, cuaca CAP menyusul?
2. Ambang awal M ≥ 5,0 / kedalaman ≤ 100 km, radius posko 100 km (M5) – 300 km (M7)? Boleh disesuaikan nanti di pengaturan.
3. Notifikasi WA ke admin organisasi langsung, atau banner saja dulu dan WA setelah Anda lihat hasilnya seminggu?

---
## 10c — notifikasi SMS (cadangan saat WA/internet tak ada)

### Yang sudah ada (fakta kode)
- `api_notify.py`: pengiriman WhatsApp lewat penyedia `fonnte` / `wablas` / `twilio` / `meta_cloud` / `simulasi`, konfigurasi per skop (global/organisasi/posko) di `RN Notification Setting`, log di `RN Notification Log`.
  Tidak ada kata "SMS" di kode mana pun. Adaptor Twilio saat ini hanya mengirim ke `whatsapp:+nomor`.
- Nomor kontak tersimpan di posko (`emergency_contact`, kontak PIC), pelapor (`RN Community Report` telepon), relawan (`contact`), dan kini no HP verifikasi.

### Celah
1. Di lokasi bencana internet/data sering mati tetapi sinyal seluler dasar masih ada: WA tidak sampai, SMS bisa.
2. Tidak ada saluran cadangan (WA gagal → SMS), tidak ada kuota/biaya per pesan, tidak ada templat peringatan yang muat 160 karakter.

### Rancangan singkat (usulan)
- Tambah `channel` (`whatsapp`/`sms`) di `RN Notification Setting` dan `RN Notification Log`; adaptor SMS: Twilio (`From` nomor/alfanumerik, `To` biasa) dan satu penyedia lokal berbasis token (mis. Zenziva/Vonage — **dipilih owner**, tidak dikarang).
- Aturan cadangan: kirim WA dulu; bila status `failed` setelah N menit → SMS ke nomor yang sama, hanya untuk jenis pesan `peringatan`/`penugasan` (bukan promosi/ringkasan).
- Templat ringkas (≤160 karakter, tanpa emoji) dan batas harian per skop agar tagihan terkendali; log mencatat biaya bila penyedia mengembalikannya.
- Privasi: isi SMS tidak memuat data sensitif (nama korban, kondisi medis); hanya "ada pesan baru di Rescue-Net" + kode.

### Pertanyaan owner
1. Penyedia SMS mana (punya akun/token)? Tanpa itu tahap 1 hanya kerangka + mode simulasi.
2. Pesan apa yang boleh jatuh ke SMS (peringatan BMKG, penugasan relawan, status laporan)?
3. Batas biaya harian/bulanan?

---
## 10d — gudang & kedaluwarsa

### Yang sudah ada
- `RN Aid Offer` punya `batch_no` dan `expiry_date` (hanya di tawaran bantuan). `RN Stock Observation` (`stock_state`: available/reserved/damaged/expired/unknown) **tidak** punya tanggal kedaluwarsa atau batch; stok = pengamatan berjenis "snapshot", bukan buku besar.
- `services/stock.py` + `receive_flow_and_update_stock` menambah stok saat penerimaan; konversi kemasan di `packaging.py` / `RN Unit Conversion`.
- Papan kebutuhan publik (10f) memakai stok `available` — barang kedaluwarsa tidak otomatis keluar dari hitungan.

### Celah
1. Tanggal kedaluwarsa/batch hilang begitu tawaran diterima menjadi stok; tidak ada peringatan "kedaluwarsa dalam N hari" dan tidak ada FEFO (yang paling dulu kedaluwarsa dikeluarkan dulu).
2. Makanan/obat kedaluwarsa bisa terhitung "cukup" di papan kebutuhan (risiko: kebutuhan tertutup oleh stok tak layak pakai).
3. Tidak ada konsep gudang (lokasi/rak) selain posko.

### Rancangan singkat
- Tambah `expiry_date`, `batch_no` di `RN Stock Observation`; `receive_flow_and_update_stock` menyalin dari tawaran/flow bila ada.
- Turunan deterministik: `stock_state` efektif = `expired` bila `expiry_date < hari ini` (tanpa menulis ulang data); papan 10f dan KPI stok memakai stok efektif.
- Panel "Segera kedaluwarsa" (≤30 hari) per posko + urutan FEFO di saran distribusi. Notifikasi lewat `api_notify` ke pengelola posko (berbatas laju).
- Gudang sebagai posko bertipe `warehouse` (sudah ada tipe posko) — tanpa DocType rak/lokasi pada tahap 1.

### Pertanyaan owner
1. Kategori yang wajib punya kedaluwarsa (makanan, obat, air minum?) — barang lain boleh kosong?
2. Ambang peringatan (30 hari? beda untuk obat?).
3. Perlu stok per rak/lokasi di dalam gudang, atau cukup per posko?

---
## 10e — status akses & infrastruktur

### Yang sudah ada
- Tidak ada field/endpoint untuk jalan, jembatan, listrik, air, sinyal, bandara/pelabuhan. Hambatan hanya terlihat tidak langsung (flow `blocked`, "Peringatan & Hambatan" di Control Centre dari data flow/kebutuhan).
- `RN Posko` punya koordinat dan radius; `RN Disaster Event` punya wilayah; GIS peta (`api_gis`) menampilkan posko.

### Celah
Perencana rute dan donatur tidak tahu jalan mana putus/jembatan rusak/listrik padam; kiriman dikirim ke jalur yang tak bisa dilewati. Tidak ada riwayat (kapan putus, kapan pulih).

### Rancangan singkat
- DocType `RN Access Status`: `disaster_event`, `kind` (road/bridge/power/water/telecom/airport/port), `name`, `status` (open/limited/closed/unknown), titik (lat/lng) atau segmen (teks), `admin_area_id` (kode, setelah D.2), `reported_by` (aktor), `verification_status`, `observed_at`, `valid_until`, `note` (tanpa kontak pribadi).
- Pelaporan oleh pengelola posko/relawan terverifikasi; status kedaluwarsa otomatis (`valid_until`) agar data basi tidak menyesatkan ("data N jam lalu").
- Tampil di peta GIS (lapisan) + banner di rencana pengiriman; flow ke tujuan di wilayah `closed` diberi peringatan (bukan dilarang). Ringkasan publik hanya agregat per wilayah/jenis (tanpa pelapor).
- Riwayat append-only (seperti RN Custody Scan) agar bisa dilihat "kapan pulih".

### Pertanyaan owner
1. Jenis yang diprioritaskan (jalan+jembatan dulu, listrik/air/sinyal menyusul)?
2. Siapa boleh melapor dan siapa yang memverifikasi (pengelola posko, verifikator jaringan)?
3. Tampil publik atau hanya internal organisasi?

---
## 10g — mode latihan (drill/simulasi)

### Yang sudah ada
- Data simulasi (karhutla, kekeringan, Krakatau, dukungan nasional) ada sebagai event/posko biasa dengan label "Simulasi" di judul; tes memeriksa isinya. Tidak ada penanda sistem untuk "ini latihan": tidak ada flag di `RN Disaster Event`, dan tidak ada pemisahan dari angka nyata.
- Penjadwal BMKG membuat event DRAF; belum ada konsep event latihan.

### Celah
1. Latihan dan bencana nyata bisa bercampur di KPI nasional, peta, papan kebutuhan publik, dan notifikasi WA (risiko: donatur menyumbang ke posko latihan; WA latihan terkirim sungguhan).
2. Tidak ada tombol "reset latihan" yang aman (hapus data latihan tanpa menyentuh data nyata).

### Rancangan singkat
- Field `is_drill` (Check) + `drill_label` di `RN Disaster Event`; semua query publik/agregat nasional mengecualikan `is_drill=1` secara default (parameter eksplisit `include_drill` untuk panel internal). Satu fungsi pusat `real_events_filter()` agar tidak terselip di tiap endpoint (pelajaran BUG-1..6).
- Notifikasi: `api_notify` memaksa `simulasi` untuk event latihan (tidak pernah mengirim ke WA/SMS sungguhan).
- Banner merah "MODE LATIHAN" di semua halaman yang menampilkan event latihan; data latihan memakai awalan/penanda agar mudah dibersihkan.
- Skrip "buat latihan dari templat" (skenario siap pakai) dan "bersihkan latihan" yang hanya menghapus baris berelasi ke event `is_drill` — pratinjau dulu, daftar kosong tidak boleh memicu hapus massal (lihat catatan insiden filter kosong).

### Pertanyaan owner
1. Latihan boleh tampil publik (dengan label jelas) atau selalu internal?
2. Skenario templat mana yang pertama (banjir, gempa, karhutla)?
3. Siapa yang boleh membuat/menghapus event latihan (System Manager saja)?

---
## 10h — check-in relawan

### Yang sudah ada
- `RN Volunteer Assignment` punya graf status (`accepted → checked_in → in_progress → completed`) dan `checked_in_at`; `update_assignment_status` mengizinkan relawan sendiri atau pengelola posko tujuan (V-4). Dasbor menghitung jam (`checked_in_at` sampai sekarang).
- `RN Volunteer Accommodation`, `RN Safety Briefing` ada. Tidak ada check-out terpisah, tidak ada verifikasi lokasi, tidak ada QR/scan kehadiran, tidak ada absensi harian di luar penugasan.

### Celah
1. Check-in hanya klik tombol — bisa dari mana saja; tidak ada bukti hadir di posko. Tidak ada `checked_out_at` sehingga jam kerja = sampai "completed".
2. Relawan tanpa penugasan (datang langsung) tidak tercatat; posko tak tahu siapa yang sedang ada di lokasi (keselamatan/evakuasi).
3. Tidak ada briefing keselamatan wajib sebelum check-in.

### Rancangan singkat
- QR kehadiran per posko (token acak berputar, pola kartu 10b) dipindai relawan (`pages/scan.html` diperluas) → `RN Volunteer Presence` append-only: relawan, posko, `in_at`, `out_at`, koordinat opsional (lat/lng + jarak ke posko hanya sebagai penanda, bukan penolak), `offline_id` idempoten.
- Check-in menautkan ke penugasan aktif bila ada; relawan tanpa penugasan → "walk-in" yang perlu ditinjau pengelola.
- Daftar "sedang di lokasi" untuk pengelola posko; briefing keselamatan terbaru sebagai prasyarat lunak (peringatan, bukan blokir).
- Privasi: kehadiran tidak tampil publik; hanya hitungan agregat "N relawan aktif".

### Pertanyaan owner
1. Check-in wajib dengan QR di posko, atau tombol di aplikasi tetap boleh (dengan koordinat)?
2. Relawan walk-in diizinkan tercatat langsung, atau harus lewat penugasan?
3. Check-out otomatis bila lupa (mis. setelah 12 jam)?

---
## Status audit 10c–10h
Audit ditulis 2026-10-10. **Dibangun 2026-10-10 (owner: "kerjakan semua"; pertanyaan owner belum dijawab → dipakai usulan default di bawah, mudah diubah):**

| Fitur | Yang ada | Asumsi default (ganti bila owner memutuskan lain) |
|---|---|---|
| 10g mode latihan | `RN Disaster Event.is_drill/drill_label`; `services/drill.py` (`real_rows`, `guard_guest_refs`, hook `before_request`), `services/drill_tools.py` + `api_drill.py` (templat banjir/gempa/karhutla, pratinjau + hapus wajib `confirm_total`, berhenti bila ada Cash Donation/Donor Program/Verification Action/AI Usage Log); latihan hilang dari semua endpoint tamu (sapuan `test_drill_mode`), notifikasi WA/SMS latihan selalu simulasi, laporan nyata tak diarahkan ke event latihan; banner `rn-drill-banner.js` di semua halaman ber-`rn-frappe-client.js` | Latihan SELALU internal (tamu 404 lewat id eksplisit); hanya System Manager membuat/menghapus; templat pertama banjir/gempa/karhutla |
| 10h check-in relawan | `RN Volunteer Presence` (append-only), `api_presence.py` (QR berputar harian dari rahasia situs, tombol aplikasi + koordinat opsional, walk-in perlu tinjauan, idempoten offline, tutup otomatis 12 jam via scheduler jam-an), `pages/kehadiran-relawan.html` | QR dan tombol keduanya boleh; walk-in boleh tercatat (ditinjau pengelola); auto check-out 12 jam; tidak ada angka publik |
| 10d kedaluwarsa | `RN Stock Batch` (lot append-only dari penerimaan tawaran/flow yang bertanggal kedaluwarsa), `services/expiry.py` (alokasi FEFO, kuantitas kedaluwarsa dihitung saat dibaca), `api_stock_expiry.py` (expiring, add_lot), papan kebutuhan publik tak menghitung stok kedaluwarsa, notifikasi harian per posko | Ambang 30 hari (60 untuk obat/medis); tanpa rak/lokasi gudang; kedaluwarsa wajib hanya bila tawaran mengisinya |
| 10e status akses | `RN Access Status` (riwayat append-only, basi otomatis lewat `valid_until`), `api_access_status.py` (lapor: pengelola posko/pelapor terverifikasi/SM; verifikasi: verifikator aktif/SM; `board` tamu = ringkasan + tempat tertutup/terbatas tanpa pelapor/koordinat/catatan), peringatan nasihat di `create_flow` (`access_warnings`, perlu `admin_area_id` kedua sisi), `pages/status-akses.html` | Semua jenis sekaligus; publik hanya agregat; tidak ada lapisan peta GIS (belum) |
| 10c SMS | `services/sms.py` (templat tetap ≤160 ASCII tanpa data sensitif, hanya `peringatan`/`penugasan`, batas harian per skop, cadangan dari WA gagal + penyapu jam-an, skop `sms:global`), adapter `twilio_sms`; tanpa penyedia = simulasi | Penyedia SMS lokal (Zenziva/Vonage) BELUM dipilih → hanya Twilio + simulasi; batas harian 100; belum ada UI pengaturan SMS (pakai `save_notification_setting(scope="sms:global", provider=...)`) |

Belum dicoba di browser/perangkat/login nyata: semua halaman & banner baru. Perlu `bench migrate` (DocType/field baru: RN Disaster Event +2, RN Volunteer Presence, RN Stock Batch, RN Access Status, RN Notification Setting +daily_limit/+twilio_sms, RN Notification Log +fallback_of) dan `rn-deploy-app.sh` → **TER-DEPLOY 2026-10-10 11:36 atas izin owner (backup `rn-app-backup-20261010-113550.tgz`).**
