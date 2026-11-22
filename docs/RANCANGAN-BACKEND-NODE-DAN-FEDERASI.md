# Rancangan backend node & anggota federasi Rescue-Net

Ditulis Ming Ming, 22 Nov 2026, atas permintaan owner: *"rancangan back end untuk nanti bisa komunikasi dengan jalur federasi ini, tulis agar Suri bisa teruskan"* dan *"jadi ada 2 anggota federasi nanti: yang pertama another RN dari negara lain, yang kedua dari organisasi tertutup yang berdiri sendiri tapi kompatibel dengan ekosistem RN"*.

Dokumen terkait: [FEDERASI-9A.md](FEDERASI-9A.md), [FEDERASI-PROTOKOL-v1.md](FEDERASI-PROTOKOL-v1.md), [ADR-0004](adr/0004-federasi-event-log-identitas-konflik.md), ADR-0006 (cabang `nala/federasi-node-adr`, status Proposed), Manual Teknis bab 1, 13, 14.

## 1. Posisi saat ini (live 507ec622, 22 Nov 2026)

| Bagian | Status |
|---|---|
| Identitas node RN (`server_id`, kunci lokal, `node_info` publik) | LIVE |
| Kotak keluar (RN Event Outbox) + kebijakan default-deny (`federation/policy.py`) | LIVE, outbox kosong (belum ada data yang dibagikan) |
| `pull` bertanda tangan HMAC (mitra menarik data publik RN) | LIVE |
| `push` bertanda tangan + RN Federation Inbox (node mengirim ringkasan/permintaan bantuan) | LIVE |
| `assistance.response` (jawaban RN ke node pengirim) | LIVE |
| Peer terdaftar | **0**. Belum ada data keluar/masuk. |
| Klien contoh `scripts/rn-federation-node-client.py` | Ada di repo |

**Celah yang harus ditutup lebih dulu:** `_authenticate()` di `api_federation.py` menolak node tanpa `organization` tertutup. Itu benar untuk node instansi, tetapi **memblokir RN negara lain** (jenis A di bawah). Lihat langkah F1.

## 2. Dua jenis anggota federasi

| | **A. RN negara lain (peer RN)** | **B. Node instansi tertutup (berdiri sendiri, kompatibel RN)** |
|---|---|---|
| Contoh | Rescue-Net Filipina, Rescue-Net Timor-Leste | DMS BNPB/BPBD, TNI/POLRI, PMI, Kementerian (CT202 = calon pertama) |
| Hubungan | Setara (dua arah), antarnegara | Instansi = **organisasi tertutup** di RN, tapi datanya di backend sendiri |
| Wakil di RN | RN Federation Node `peer_type=rn_peer`, **tanpa** organisasi | RN Federation Node `peer_type=instansi` + satu RN Organization `privacy_mode=closed` + `operation_template` (bnpb/tni/pmi/kementerian) |
| Data yang ditukar | Data **publik** sesuai `policy.py`: bencana, posko publik, kebutuhan, penawaran, status aliran, kode wilayah. Arah dua-duanya lewat `pull`. | Node → RN lewat `push`: `org.summary`, `assistance.request`, `sitrep.summary`, `need.published`, `menu.record` (TERBUKA saja). RN → node lewat `pull`: `assistance.response` + data publik RN sesuai scope. |
| Tidak boleh keluar | Data pribadi, lampiran, teks bebas | Itu juga + OPORD, RFL, data korban, posisi militer, semua menu TERBATAS/RAHASIA |
| Kedaulatan data | Tiap negara pemilik datanya; tidak ada server pusat | Instansi pemilik datanya; RN hanya menyimpan agregat/permintaan |
| Kode | Sama persis (Rescue-Net) | Bebas (Frappe/RN, Django, .NET, dll.) asal memenuhi Protokol v1. **Disarankan memakai kode RN** (lihat bagian 4). |

## 3. Arsitektur sasaran

```text
                 Internet (HTTPS, Cloudflare)
   ┌───────────────────────┬─────────────────────────────┐
   │                       │                             │
┌──▼──────────────┐   pull ⇄ pull   ┌──────────────────┐ │
│ RN Indonesia    │◄───────────────►│ RN negara lain   │ │  A. peer RN
│ (Flex CT201)    │                 │ (servernya sendiri)│ │
│ outbox · inbox  │                 └──────────────────┘ │
│ RN Org tertutup ◄─── push ──┐                          │
│  "BNPB (node)"  │── pull ──►│                          │
└─────────────────┘           │                          │
                     ┌────────┴──────────────────────────▼┐
                     │ Node instansi (B)                   │
                     │ DMS frontend (CT202 pages)          │
                     │ + backend sendiri + database sendiri│
                     │ + job federasi (push/pull terjadwal)│
                     └─────────────────────────────────────┘
```

Tidak ada hub pusat. Setiap hubungan bilateral, punya kunci sendiri per arah, dan bisa dicabut sepihak.

## 4. Rancangan backend node instansi (jenis B)

### 4.1 Pilihan teknologi — rekomendasi: **pasang Rescue-Net sebagai node terpisah**
- Kode yang sama (`rescue_net` di Frappe 15 + MariaDB), **site dan database terpisah**, server/CT terpisah. Sesuai ADR-0006 "satu node mandiri per instansi".
- Untung: login, izin, audit, backup, Tanya AI, outbox/inbox, tes, manual sudah ada. Frontend DMS (CT202) hampir tanpa perubahan: cukup arahkan proxy `/rescue-net-frappe/` ke backend node, bukan ke RN.
- Profil instansi lewat konfigurasi site (`federation_node_name`, template default, branding), **bukan** fork kode.
- Alternatif (backend lain) boleh, tetapi wajib lulus vektor uji HMAC dan JSON Schema di Protokol v1.

### 4.2 Komponen yang perlu dibuat di node
| Komponen | Isi | Catatan |
|---|---|---|
| `RN DMS Record` (DocType baru) | `menu_id`, `organization`, `classification` (salin dari `dms-menu.json`), `data` (JSON terstruktur sesuai `isian`), `status`, audit | Satu tabel untuk 36 menu. Validasi server: field sesuai definisi menu, wajib/pilihan/angka. |
| API `rescue_net.api_dms.list / save / get` | Izin: anggota org + peran; RAHASIA hanya peran tertentu | Dipakai `rn-edisi-data.js` sumber `NODE`. |
| Adaptor frontend | `rn-edisi-data.js`: sumber `NODE` memanggil `api_dms`, sumber `RN` tetap untuk data publik RN | Sudah disiapkan Nala: tinggal isi cabang NODE. |
| Job `federation_push` (scheduler 5 menit) | Bangun event dari data lokal: `org.summary` (agregat), `assistance.request` (dari menu Permintaan Bantuan), `need.published`, `menu.record` (TERBUKA) → `push` ke RN | Simpan `seq` lokal, `event_id` UUID, retry dengan nonce baru, catat hasil per event. |
| Job `federation_pull` (scheduler 5 menit) | `pull` dari RN sejak kursor; simpan `assistance.response` ke inbox lokal, tampilkan di menu Permintaan Bantuan | Deduplikasi `event_id`. Belum menerapkan data publik RN ke tabel operasional (tahap berikutnya). |
| Penyimpanan rahasia | Kunci 32 byte per arah di Password field Frappe / secret manager | Jangan di repo, log, atau layar. |
| Jam & TLS | NTP aktif (toleransi ±300 dtk), HTTPS valid | |

### 4.3 Kapasitas
Minimum per node: 2 CPU, 4 GB RAM, 20 GB SSD (ADR-0006). CT202 sekarang hanya 1 CPU / 256 MB (frontend statis) → **perlu host/CT baru**. Flex tersisa ±1,9 GB RAM, Aspire ±3,1 GB: belum cukup untuk node penuh tanpa menambah RAM atau server. Keputusan owner.

## 5. Langkah kerja untuk penerus (Suri)

Urutan, masing-masing satu cabang, tes di stack uji CT102, deploy hanya dengan izin owner.

- **F1 — Jenis peer (kecil, sisi RN).** Tambah field `peer_type` (`rn_peer` / `instansi`) di RN Federation Node. `_authenticate`: `instansi` wajib org tertutup (seperti sekarang); `rn_peer` tanpa org, hanya boleh `pull` dan event publik, `push` ditolak sampai F5. Patch: node lama → `instansi`. Tes: rn_peer bisa pull, tidak bisa push; instansi tanpa org ditolak. Butuh migrate.
- **F2 — Panel admin federasi di RN.** Halaman System Manager: daftar peer (jenis, status, kursor, terakhir kontak), tombol daftar/setujui/cabut/rotasi kunci, isi inbox. Pakai API yang sudah ada (`status`, `register_peer`, `approve_peer`, `revoke_peer`, `rotate_peer_key`, `inbox`).
- **F3 — Node instansi uji.** Pasang site Rescue-Net kedua di stack uji (`rescuenet-node.localhost`), data sintetis, profil BNPB. Buat `RN DMS Record` + `api_dms` + isi sumber NODE di `rn-edisi-data.js`. Frontend CT202 diuji terhadap node ini.
- **F4 — Job push/pull node.** Implementasi 4.2 + uji dua site: daftar silang, push ringkasan & permintaan bantuan, jawab di RN, pull jawaban, putus-sambung, replay, rotasi & cabut kunci, kebocoran (sentinel data RAHASIA tidak pernah sampai ke RN).
- **F5 — Peer RN negara lain.** Dua site RN di stack uji saling `pull`. Tambah penerapan event publik dari peer ke tampilan "Bencana lintas negara" (baca-saja, ditandai asal negara), konflik sesuai ADR-0004. Pertimbangkan zona waktu, bahasa, kode negara pada kode wilayah.
- **F6 — Gerbang pilot.** Daftar uji penerimaan ADR-0006, backup/pulih node, pemantauan, prosedur insiden, persetujuan tertulis instansi peserta. Baru setelah itu node sungguhan di host baru.

## 6. Keputusan yang masih ditunggu dari owner
1. Instansi pertama untuk node pilot dan host/server-nya (lihat 4.3).
2. Negara/mitra RN pertama untuk federasi jenis A.
3. Setuju node instansi memakai kode Rescue-Net (4.1)?
4. Data publik RN mana yang boleh ditarik peer negara lain pada tahap awal (semua kategori `policy.py` atau agregat saja)?
