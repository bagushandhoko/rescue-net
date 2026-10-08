# ADR-0004: Federasi — event log (outbox), identitas global, aturan konflik

Status: **Accepted** (owner 2026-10-08). Jawaban owner 2026-10-08: pertanyaan 1-3 diterima sesuai rekomendasi (pemilik data = server asal; klasifikasi C apa adanya; retensi outbox 90 hari). Implementasi bertahap, di test stack dulu; gerbang review owner sebelum produksi.
Tanggal: 2026-10-08
Terkait: ADR-0001, ADR-0003, NEXT_STEPS Fase 9a–9b

## Konteks (fakta kode saat ini)
- `RN Sync Log` + `api_sync.push/pull` sudah ada: setiap event membawa `event_id`, `object_type`, `operation`,
  `source_device_id/server_id/user_id/organization_id`, `payload_checksum`, `apply_status`, `conflict_status`.
  Idempoten lewat `event_id` (`_existing_log`).
- Yang bisa di-apply baru: `resource_request` (create), `community_report` (create), event bencana, booking armada.
  Produksi hanya melihat 1 `source_server_id`.
- Nama record Frappe (`name`) dibuat per server — dua server bisa membuat nama yang sama untuk hal berbeda.
- Belum ada outbox: perubahan data operasional (kebutuhan, stok, flow, kasus medis, ...) tidak dicatat sebagai event.

## Keputusan yang diusulkan

### A. Event log / outbox (9a)
1. DocType baru **RN Event Outbox** (satu baris per perubahan penting): `event_id` (UUIDv7), `origin_server_id`,
   `seq` (urut naik per server), `object_type`, `object_uid`, `operation` (create/update/status/delete-soft),
   `actor_ref` (pseudonim, bukan nama), `occurred_at`, `payload` (hanya field yang diizinkan), `payload_checksum`,
   `classification` (lihat C), `sent_to` (daftar node + status kirim).
2. Ditulis di **controller DocType** (hook `on_update`/`after_insert`) dalam transaksi yang sama dengan perubahan datanya —
   bukan di endpoint — sehingga jalur apa pun (web, app, sync, desk) tercatat dan tidak ada event yang hilang.
3. Event bersifat **append-only**; koreksi = event baru. Retensi: outbox yang sudah diakui semua node boleh dipadatkan
   setelah 90 hari; `RN Sync Log` (sisi terima) tetap bukti audit.
4. `RN Sync Log` dipertahankan sebagai sisi **terima**; `api_sync.push/pull` diperluas dari event outbox, bukan diganti
   (app offline yang ada tetap jalan).
5. Transport: pull berbasis kursor (`seq` terakhir yang diakui per node) lewat HTTPS; push dari Box saat koneksi ada.
   Setiap node punya kunci penandatangan (HMAC/Ed25519) — event tanpa tanda tangan sah ditolak.

### B. Identitas global & konflik (9b)
1. **ID global** = `uid` (UUIDv7) di setiap DocType yang ikut federasi, ditambah `origin_server_id`. `name` Frappe tidak
   diubah. Backfill: `uid` dibuat oleh patch untuk baris lama; nama lama tetap dipakai UI.
2. **ID server** dibuat saat wizard instalasi (ADR-0003): `server_id` = UUID + nama organisasi; disimpan di
   `RN Federation Node` (DocType baru: node dikenal, kunci publik, status, kursor, data yang boleh dikirim).
3. **Pemilik data (authoritative server)**: tiap record dimiliki server tempat ia dibuat (`origin_server_id`).
   Hanya pemilik yang boleh `update`/`status`; node lain mengirim **usulan** (event bertipe `proposal`) yang menunggu
   persetujuan pemilik — selaras dengan model "approval pihak lain" yang sudah dipakai untuk hierarki organisasi.
4. **Aturan konflik per jenis data:**
   | Jenis | Aturan |
   |---|---|
   | Status berurutan (graf status di controller) | langkah lebih jauh di graf menang; mundur ditolak + ditandai |
   | Angka stok/observasi | observasi terbaru (`occurred_at`) menang; yang lama disimpan sebagai riwayat, bukan ditimpa |
   | Laporan warga / kebutuhan duplikat antar server | **tidak digabung otomatis** — masuk antrian duplikat (saran AI + keputusan manusia, ADR-0002) |
   | Verifikasi / persetujuan | hanya server pemilik organisasi pemverifikasi |
   | Data yang diedit dua pihak bersamaan | tidak ada last-write-wins diam-diam: `conflict_status=needs_review`, tampil di konsol sync, manusia memutuskan |
5. Jam: `occurred_at` dari server asal + `received_at` lokal; perbedaan jam > 10 menit ditandai (Box tanpa internet bisa melenceng).

### C. Klasifikasi data (apa yang boleh keluar)
- **Tidak pernah keluar server:** nomor HP, email, nama pelapor, identitas korban, rekam medis individual (kasus medis,
  evakuasi), kunci/secret, token.
- **Keluar hanya agregat/anonim:** hitungan kasus, jiwa berisiko per posko, stok total.
- **Boleh keluar penuh antar node yang disetujui:** event bencana, posko publik, kebutuhan/penawaran/aliran logistik,
  wilayah administratif, bukti yang berstatus publik.
- Klasifikasi dicatat di registri di kode (`federation/policy.py`) per DocType + per field, dan diuji: test wajib
  memastikan field terlarang tidak pernah ada di payload outbox (uji kebocoran, seperti BUG-1..6).

## Alternatif yang ditimbang
- Replikasi database (MariaDB/Galera): menyalin semua baris termasuk data sensitif, tidak bisa selektif, rapuh di jaringan putus-putus. Ditolak.
- Last-write-wins global: mudah, tapi diam-diam menimpa data lapangan. Ditolak.
- CRDT penuh: berlebihan untuk graf status + pemilik data yang jelas. Tidak dipilih.

## Konsekuensi
- Setiap DocType federasi butuh `uid` + hook outbox + entri kebijakan; DocType baru tanpa entri kebijakan = tidak ikut federasi (aman secara default).
- Biaya: tulis ganda (data + outbox) — kecil dibanding nilai audit.
- Implementasi (9e) hanya setelah ADR ini Accepted, dibangun dulu di dua server test (simulasi dua organisasi).

## Pertanyaan untuk owner
1. Server pemilik data per record (B.3) diterima, atau ada jenis data yang harus "milik bersama"?
2. Daftar klasifikasi C: ada jenis data yang perlu dipindah kategori?
3. Retensi outbox 90 hari cukup?
