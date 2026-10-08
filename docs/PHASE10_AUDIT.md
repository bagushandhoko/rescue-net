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
## Tidak diaudit sekarang (bukan prioritas owner)
10c SMS, 10d gudang/kedaluwarsa, 10e status akses/infrastruktur, 10g mode latihan, 10h check-in relawan: menunggu giliran; audit dilakukan saat dipilih.
