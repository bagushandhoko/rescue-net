# Protokol Burst VPS Rescue-Net

Ditulis Suri, 27 Nov 2026. Permintaan owner:
- "untuk burst vps, saya setuju saran kamu, yang skr perlu dilakukan hanya penambahan/persiapan protokol, vps gunakan hdd aspire sbg simulasi, nanti jika bencana besar terjadi saya cukup klik satu button, beri alamat ip vps, login code, semua otomatis di create di vps itu dan burst siap jalan"
- "kombinasikan dengan desain duplikasi menu yang sudah disiapkan di RN"
- "ini terkait dengan testing beban yang sudah dilakukan"

Status: **RANCANGAN + PERSIAPAN**. Belum ada perubahan di produksi.

## 1. Dasar: hasil uji beban (bukan tebakan)

| Uji | Hasil | Arti untuk burst |
|---|---|---|
| 13 Nov, Flex langsung, tamu | nginx cache tamu 20 dtk: ±2.800–3.100 req/dtk, p95 ≤0,12 dtk | Halaman **publik** sudah murah. Mirror baca-saja tidak banyak menolong. |
| 20 Nov, lewat Cloudflare, tamu 150 | 294 req/dtk, p95 0,12 dtk, 0 error (429 hanya organisasi-posko) | Jalur publik aman. |
| 24 Nov, k6 6.000 (Nala) | Sehat sampai **1.000** pengguna (190 req/dtk). 2.000: p95 login 2,27 dtk. Berhenti di 4.000. **CPU Flex 96–98 %.** RAM masih sisa 1,3 GB. | Batasnya **CPU untuk pengguna login/API**. Burst harus menambah CPU untuk **seluruh aplikasi**. |
| rn-autoscale (Flex, tiap 1 menit) | Tidak bertindak saat uji karena pemicunya RAM, bukan CPU | Perlu **tingkat baru**: CPU tinggi bertahan → minta burst. |

Kesimpulan: menyalin database terus-menerus lalu pindah otomatis atau membuat **mirror baca** tidak menyelesaikan masalah. Yang dibutuhkan saat bencana besar:
1. **Pindah penuh terencana** ke VPS bertenaga besar (resize sesuai kebutuhan), dengan satu penulis data (tidak ada data terbelah).
2. **Membagi beban per menu/instansi** lewat desain node & federasi yang sudah ada.

## 2. Gabungan dengan desain yang sudah ada di RN

| Sudah ada | Dipakai sebagai |
|---|---|
| `node/pasang.sh --pulihkan`, `node/cadangan.sh`, `perbarui.sh` (paket instalasi 13 Nov) | **Mesin** pembuat RN di VPS |
| Menu **Setting › Cadangan & Pindah Server** (`ai-settings.html`, paket `.tar` + SHA256) | **Tempat tombol** "Burst ke VPS" |
| `ops/flex/rn-autoscale.sh` (tingkat 1: tambah RAM CT201; tingkat 2: matikan HA) | **Pendeteksi**. Tambah tingkat 3 = kirim **Siaga Burst** ke Telegram owner |
| Tunnel Cloudflare dengan beberapa konektor (Aspire VM101 + Flex CT201) | **Pengalih lalu lintas** tanpa ubah DNS: konektor VPS dinyalakan, konektor Flex dimatikan |
| Federasi v1 (`RN Federation Node`, outbox/inbox, `policy.py`, `open_menus.json`, `dms-menu.json` 36 menu TERBUKA/TERBATAS/RAHASIA, node instansi jenis B) | **Duplikasi per menu**: menu operasi instansi (BNPB/TNI/PMI/Kementerian) dijalankan di **node VPS instansi sendiri**. RN inti hanya menerima ringkasan lewat `push`. Beban terbagi tanpa data terbelah. |
| `rn-monitor.sh` (CT105, tiap 5 menit) + lapor Telegram | Pemantau setelah pindah (target ikut berganti) |

## 3. Tiga mode burst (pilihan di tombol)

| Mode | Kapan | Yang terjadi | Data | Jeda layanan |
|---|---|---|---|---|
| **A. Siaga** | Ada peringatan (siklon, gempa susulan) | VPS dibuat dan diisi cadangan terakhir. Worker/scheduler/tunnel **mati**. Dicek sehat. | Salinan, tidak dipakai | 0 |
| **B. Pindah penuh (burst)** | Beban naik (autoscale tingkat 3) atau Flex mau dirawat | Flex mode pemeliharaan → cadangan final → pulihkan di VPS → jobs + tunnel VPS **nyala** → tunnel Flex **mati** → cek. VPS jadi server utama. | Tidak hilang (cadangan final) | Target ≤15 menit (diukur saat gladi) |
| **C. Darurat (Flex mati)** | Laptop rusak, listrik padam lama | Sama dengan B, tetapi memakai **cadangan otomatis terakhir** di luar laptop | Hilang maksimal sejak cadangan terakhir (target 1 jam) | Waktu pemulihan |
| **Kembali ke Flex** | Bencana mereda | Kebalikan B (VPS → Flex), lalu VPS boleh dihapus/diperkecil | Tidak hilang | ≤15 menit |

Pembagian per instansi (federasi) berjalan terpisah dari tiga mode di atas: node instansi = `pasang.sh` di VPS sendiri + daftar sebagai `RN Federation Node` (langkah F1–F6 di RANCANGAN-BACKEND-NODE-DAN-FEDERASI.md).

## 4. Satu tombol: alurnya

```text
Owner (RN › Setting › Cadangan & Pindah Server › "Burst ke VPS")
  isi: IP VPS, user (root), kode login (kata sandi/kunci), mode A/B/C, 2FA
        │  (hanya admin tertinggi (System Manager) + 2FA; kode login disimpan terenkripsi, dihapus setelah dipakai)
        ▼
RN Burst Request (DocType)  status: Menunggu → Berjalan → Selesai/Gagal, log langkah
        ▲ baca/tulis lewat API bertoken (bukan dari dalam kontainer RN)
        │
rn-burst-agent (CT102, di luar aplikasi RN, tiap 30 dtk)
  1. SSH ke VPS dengan kode login → pasang kunci SSH sendiri → matikan login sandi
  2. Cek VPS: CPU/RAM/disk/OS (minimal 2 CPU, 4 GB, 20 GB; disarankan 8 CPU/16 GB saat bencana)
  3. Pasang Docker + compose, firewall (hanya SSH dari kantor + keluar), jam NTP
  4. Ambil kode RN (kunci deploy baca-saja) + image produksi yang sama
  5. Ambil cadangan: mode A/C = cadangan otomatis terakhir; mode B = cadangan final dari Flex
  6. node/pasang.sh --pulihkan <cadangan>  (+ --dengan-jobs hanya untuk B/C)
  7. Uji sehat: beranda, api login, jumlah data = sumber
  8. B/C: nyalakan tunnel di VPS, matikan tunnel + jobs di Flex, rn-monitor pindah target
  9. Lapor tiap langkah ke halaman + Telegram owner (lapor-owner.sh)
```

Cadangan selain tombol: perintah Telegram ke Edith `/burst <IP>` (owner sudah terbiasa), memakai agen yang sama.

## 5. Keamanan
- Kode login VPS hanya dipakai sekali untuk memasang kunci SSH agen, lalu dihapus dari database. Login sandi di VPS dimatikan.
- Paket cadangan berisi kunci enkripsi: dikirim langsung lewat SSH (tidak lewat chat/email), dihapus dari VPS setelah dipulihkan.
- Token tunnel hanya aktif di **satu** server dalam mode B/C (aturan `node/README.md`).
- Tombol hanya untuk admin tertinggi (System Manager) + 2FA. Semua langkah tercatat di Jejak Audit.

## 6. Persiapan yang dikerjakan sekarang (tanpa ubah produksi)

| No | Pekerjaan | Tempat |
|---|---|---|
| P1 | **Cadangan otomatis tiap jam keluar laptop**: `node/cadangan.sh` di Flex → salin ke HDD Aspire (simulasi penyimpanan luar). Nanti bisa ke Cloudflare R2/VPS. Simpan 48 jam + 14 harian. | Flex cron + Aspire `/var/lib/vz/rn-cadangan` |
| P2 | **VPS simulasi** di HDD Aspire: VM Debian 13 bersih (2 vCPU, 3 GB, 30 GB, `onboot=0`), login root + sandi, seperti VPS baru sewaan. Hanya dinyalakan saat gladi (aturan owner: Aspire jangan dibebani terus). | Aspire VM |
| P3 | **rn-burst.sh** (mesin otomatis langkah 1–8) + **rn-burst-agent** | repo `ops/burst/`, jalan di CT102 |
| P4 | **Tombol & DocType** `RN Burst Request` di menu Cadangan & Pindah Server | cabang RN, deploy setelah izin owner |
| P5 | **rn-autoscale tingkat 3**: CPU >85 % bertahan 5 menit setelah tingkat 2 → Telegram "Siaga Burst, tekan tombol" (tidak pindah sendiri) | `ops/flex/rn-autoscale.sh` |
| P6 | **Gladi** di VPS simulasi: mode A, B (pakai salinan, tunnel uji, bukan tunnel produksi), Kembali. Ukur waktu. Catat di Scenario Tested. | Aspire VM |
| P7 | Lanjutan federasi F1–F3 (node instansi) untuk pembagian per menu | RANCANGAN-BACKEND-NODE-DAN-FEDERASI.md |

## 7. Keputusan owner nanti (bukan sekarang)
- Penyedia VPS sungguhan dan ukuran saat bencana (saran: Jakarta/Singapura, 8 vCPU/16 GB, bisa diperbesar dan diperkecil).
- Penyimpanan cadangan luar sungguhan (Cloudflare R2 / VPS kecil).
- Cache halaman statis di Cloudflare (tertunda sejak 13 Nov, butuh izin).
