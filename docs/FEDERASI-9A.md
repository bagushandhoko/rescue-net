# Federasi antar node RN, tahap 9a

Cabang uji. ADR-0004 bagian A, B.2 dan C menjadi dasar implementasi. Skema transport `1`.

## Persiapan dan akses

- Migrasi membuat identitas lokal dan mengisi UUID pada data lama tanpa mengubah nama dokumen. Kunci lokal dibuat sekali, disimpan sebagai Password Frappe, dan dipakai untuk menghasilkan pseudonim aktor. Atur nama publik lewat konfigurasi site `federation_node_name`. Instal node mitra sebagai site baru agar identitasnya berbeda.
- System Manager mengaktifkan **Federation Share** per catatan operasional. Posko harus publik menurut kebijakan RN. Kebutuhan, penawaran, serta aliran terkait memerlukan event yang dibagikan dan posko terkait yang publik serta dibagikan. Latihan dan simulasi tidak memenuhi syarat. Kode wilayah kanonik dapat dicatat tanpa opt-in.
- Field dan nilai ekspor mengikuti `federation/policy.py`. Judul dan teks bebas tetap lokal karena bisa mengandung data pribadi. Klasifikasi agregat dicadangkan untuk proyeksi agregat yang ditinjau terpisah.
- Ekspor dimulai dari perubahan baru setelah migrasi. Backfill identitas data lama tidak membuat event historis. Pull mengecek ulang kelayakan catatan dan referensinya sebelum mengirim riwayat.

Gunakan `/rescue-net-frappe/api/method/rescue_net.api_federation.<endpoint>` lewat proxy RN, atau `/api/method/…` pada Frappe langsung.

| Endpoint | HTTP | Akses dan parameter |
| --- | --- | --- |
| `node_info` | GET | Publik. Mengembalikan `server_id`, `name`, `schema_version`, dan `fingerprint` dari kunci lokal. |
| `status` | GET | System Manager. Ringkasan node, `outbox_count`, `last_seq`, jumlah peer dan daftar peer dengan scope, status dan kedua kursor. Bisa dipakai panel DMS. |
| `register_peer` | POST | System Manager. `server_id`, `name`, `url` (HTTPS), `key_fingerprint`, `shared_secret`, `scope` (array nama DocType). Status awal `pending`. |
| `approve_peer` | POST | System Manager. `server_id` peer yang identitasnya sudah diperiksa. |
| `revoke_peer` | POST | System Manager. `server_id` peer yang aksesnya dicabut. |
| `pull` | POST | Peer `approved` dengan HMAC. Body JSON memuat `since_seq` dan `limit`, keduanya bilangan bulat. |

Administrator menukar kunci HMAC 32 byte acak per arah koneksi melalui saluran rahasia. Masukkan sebagai 64 karakter heksadesimal huruf kecil. `key_fingerprint` untuk registrasi adalah SHA-256 dari **byte kunci bersama**. Cocokkan secara terpisah dengan mitra. Fingerprint publik `node_info` adalah identitas kunci lokal, dan berbeda dari fingerprint kunci koneksi. Kirim kunci koneksi lewat POST HTTPS dan lewat penyimpanan rahasia pada klien. Respons API tidak mengembalikan kunci.

## Tanda tangan pull

Gunakan `Content-Type: application/json` dan tanpa sesi browser. Contoh body `{"since_seq":0,"limit":100}`. Empat header wajib:

| Header | Isi |
| --- | --- |
| `X-RN-Peer` | UUID node pemanggil, bentuk kanonik huruf kecil. |
| `X-RN-Timestamp` | Detik Unix UTC, 10 digit desimal, toleransi ±300 detik. |
| `X-RN-Nonce` | 16 byte acak, 32 karakter hex huruf kecil, baru setiap permintaan termasuk retry. |
| `X-RN-Signature` | HMAC-SHA256 dalam 64 karakter hex huruf kecil. |

Input HMAC adalah gabungan byte berikut dengan LF tunggal sebagai pemisah dan tanpa LF tambahan setelah body:

```text
RN-FEDERATION/1 pull
<server_id penerima HTTP>
<X-RN-Peer>
<X-RN-Timestamp>
<X-RN-Nonce>
<byte body persis seperti dikirim>
```

Gunakan kunci hasil decode hex. HTTPS melindungi permintaan dan respons. Redis menahan nonce yang sudah digunakan selama 601 detik. Jam sistem kedua node perlu sinkron.

Mulai dengan `since_seq=0`. Batas `limit` adalah 1–200. Respons Frappe di bawah `message` berisi `events`, `next_seq`, `has_more`, dan `schema_version`. Halaman kosong masih bisa mengembalikan `has_more=true` ketika visibilitas berubah. Simpan `next_seq` setelah pemrosesan halaman berhasil, lalu kirim nilai itu sebagai `since_seq` pada pull berikutnya. Kursor kirim di sisi sumber mencatat nilai terbesar yang diakui peer. Event dapat diambil kembali dengan kursor lama dan nonce baru. Deduplikasi berdasarkan `event_id`. `payload_checksum` adalah SHA-256 atas JSON `payload` yang diurutkan berdasarkan kunci, dengan escape ASCII dan tanpa spasi pemisah.

## Tahap berikutnya

- Implementasikan `ingest` yang memvalidasi payload dan mencatat `event_id` satu kali ke RN Sync Log dengan status belum diverifikasi. Kursor terima masih 0. Penerapan data, konflik, dan notifikasi penarikan data yang sebelumnya diterima berada di tahap berikutnya.
- Uji dua site, panel DMS, rotasi kunci, dan pemadatan outbox setelah semua peer mengakui event yang berumur minimal 90 hari belum tersedia. Penulisan langsung lewat SQL di luar jalur controller atau importer wilayah memerlukan integrasi eksplisit.
