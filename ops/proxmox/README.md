# Migrasi ke server baru (Proxmox) — Rescue-Net + SAC

Disusun 2026-10-09. **Kit ini belum pernah dijalankan end-to-end di host Proxmox** (hanya `export-from-nas.sh --dry-run`
dan cek sintaks di NAS). Gladi resik di VM uji wajib sebelum cutover (bagian 5).

## 1. Yang dipindahkan (inventaris)

| Komponen | Di NAS sekarang | Di server baru |
|---|---|---|
| Rescue-Net (Frappe `rescue_net`, situs `osiun.localhost`) | kontainer `osiun-frappe-*` (stack `/volume1/docker/osiun-frappe-shadow`) + repo `/volume1/web/rescue-net` | `backend`, `worker-default`, `scheduler`, `mariadb`, `redis-*` di compose ini |
| Web Rescue-Net (statis + proxy whitelist) | `rescue-web` (nginx, 127.0.0.1:8182) | `rescue-web`, mount `$BASE/src/rescue-net` |
| Portal SAC (Frappe `sac_portal`, situs `sac.localhost`) | `/volume1/docker/sac-frappe` (`up.sh`), port 8180 | `sac-backend` (gunicorn), `db`, `sac-redis-*` |
| Web publik SAC (statis) | `/volume1/web/sac` + `sac-web` (port 8181) | `sac-web`, mount `$BASE/src/sac-web` |
| Pintu publik | `cloudflared` (token; ingress diatur di dashboard Cloudflare → 127.0.0.1:8180/8181/8182) | `cloudflared` (profil `tunnel`, network host) |
| Data | DB + file privat (PO, bukti bayar) di volume Docker/bind | dipulihkan dari bundel |

**Tidak ikut:** semua yang milik OSIUN (Moodle, OpenEduCat, osiun-api, ai-teaching, …). Catatan penting: situs Rescue-Net bernama
`osiun.localhost` dan hidup di stack Frappe OSIUN; **pastikan DB situs itu tidak memuat data OSIUN lain** (setahu saya hanya data `rescue_net`
+ ERPNext bawaan yang tak dipakai). Kalau OSIUN juga pindah, itu proyek terpisah.

Rahasia yang ikut bundel (folder `secrets/`, chmod 600): `site_config.json` kedua situs (**`encryption_key` wajib sama** — API key AI,
token WhatsApp, kunci Google tersimpan terenkripsi dengan kunci itu; tanpa kunci yang sama semuanya tak terbaca), `.env` SAC, token tunnel.

## 2. Rekomendasi VM Proxmox

- **VM penuh (bukan LXC)**: Debian 12 atau Ubuntu 22.04/24.04, Docker CE + plugin compose. Docker di dalam LXC bisa, tetapi rawan masalah (nesting, AppArmor, overlayfs).
- **Sumber daya awal:** 4 vCPU (tipe CPU `host`), **8 GB RAM** (12 GB bila ERPNext keuangan SAC dipasang), disk 80–100 GB virtio pada penyimpanan SSD/ZFS. Matikan ballooning; aktifkan QEMU guest agent; *Start at boot*.
- **Disk:** pisahkan disk data (`/srv`) dari disk OS agar snapshot/backup bisa dibatasi ke data.
- **Backup:** vzdump harian ke penyimpanan lain (atau Proxmox Backup Server) + `bench backup` terjadwal (cron) ke `/srv/sacrn/backups`, salin ke luar VM. Snapshot VM sebelum tiap deploy besar.
- **Jaringan:** tidak ada port publik yang dibuka — semua lewat Cloudflare Tunnel. Firewall Proxmox/UFW: hanya SSH dari jaringan admin. Port 8180–8182 hanya `127.0.0.1`.
- **Waktu:** zona `Asia/Jakarta`, sinkron NTP (penting untuk cookie sesi dan jadwal BMKG).
- **Swap:** 2–4 GB sebagai pengaman (di NAS RAM sempit; jangan diulang).

## 3. Ekspor di NAS

```sh
cd /volume1/web/rescue-net
git status --short                           # pastikan bersih; commit dulu bila tidak
sh ops/proxmox/export-from-nas.sh --dry-run  # lihat rencananya
sh ops/proxmox/export-from-nas.sh            # -> /volume1/migrasi/bundle-<waktu>/ (SHA256SUMS di dalamnya)
```
Salin bundel ke VM (`rsync -a --info=progress2 bundle-… vm:/root/`). Bundel **memuat rahasia**: jangan ke GitHub/cloud publik.

## 4. Impor di server baru

```sh
git clone <bundle>/git/rescue-net.bundle /root/rescue-net     # atau salin folder ops/proxmox saja
cd /root/rescue-net/ops/proxmox
sh import-on-new-host.sh /root/bundle-… --check   # prasyarat + checksum
sh import-on-new-host.sh /root/bundle-…           # impor penuh (tanpa tunnel)
sh verify.sh
```
Skrip: membuat `.env` (password DB **baru** diacak), memulihkan kode dari git bundle, membuat situs baru lalu `bench restore` DB + berkas
publik/privat, menyalin `encryption_key`/`host_name`/`allow_cors` dari situs lama, `migrate`, menyalakan semua layanan, menjalankan probe.

## 5. Gladi resik (wajib)

1. Buat VM uji, jalankan bagian 3–4 **tanpa** `TUNNEL_TOKEN`.
2. `sh verify.sh` harus semua OK.
3. Akses lewat SSH tunnel/`curl` dengan header Host: login nyata Rescue-Net (admin), buka Bencana Aktif, Kebutuhan Publik; portal SAC: login staf, buka satu pesanan, lihat PO dan bukti bayar (berkas privat), kirim pesan uji WA (mode simulasi bila token belum dipasang).
4. Jalankan tes aplikasi terhadap salinan bila perlu (`scripts/rn-test-stack.sh` butuh stack uji terpisah).
5. Catat waktu total import → itu jendela henti layanan saat cutover.

## 6. Cutover (hari-H)

1. Umumkan jendela perawatan. Di NAS: commit semua perubahan, jalankan ekspor akhir (bagian 3).
2. Di server baru: impor ulang bundel akhir (hapus `$BASE` lama atau pakai VM bersih), `verify.sh`.
3. **Matikan tunnel di NAS dulu:** `sudo docker stop cloudflared` (token yang sama tidak boleh aktif di dua host sekaligus untuk rute yang sama; dua konektor memang diizinkan Cloudflare, tetapi lalu lintas terbagi dan data bisa tertulis di dua tempat).
4. Nyalakan di server baru: `docker compose --env-file .env --profile tunnel up -d cloudflared`.
5. Uji dari luar: `https://rescue-net.online`, `https://sac-energi.online`, `https://portal.sac-energi.online`, login Google (redirect URI tetap sama karena domain tidak berubah).
6. Pantau 24 jam. **NAS jangan dihapus 7–14 hari** (kontainer dihentikan, bukan dibuang).

**Rollback:** `docker compose stop cloudflared` di server baru → `sudo docker start cloudflared` di NAS. Data yang ditulis sesudah cutover tidak otomatis kembali ke NAS (ekspor ulang bila perlu).

## 7. Sesudah pindah

- Aktifkan backup terjadwal (vzdump + `bench backup` + salinan luar), uji pulihkan satu kali.
- `docker compose logs` dipantau; pasang pemantauan sederhana (uptime check pada tiga domain).
- Rotasi: password root DB sudah baru; **rotasi token tunnel** dan kunci API yang pernah tersimpan di NAS bila NAS akan dilepas/dijual.
- Perketat: `bench serve` (Rescue-Net) → gunicorn seperti SAC; worker Rescue-Net hanya antrean `default` seperti di NAS (tambahkan `short,long` bila ingin jadwal berat terproses).
- Rencana keuangan SAC (ERPNext) memakai VM yang sama: tambah RAM (lihat bagian 2).

## 8. Hal yang perlu keputusan/aksi Anda

- Akses dashboard Cloudflare (token tunnel; ingress tetap menunjuk 127.0.0.1:8180–8182 sehingga tidak perlu diubah).
- Konfirmasi situs `osiun.localhost` hanya berisi data Rescue-Net.
- Spesifikasi VM final dan lokasi backup luar.
- Jadwal cutover (disarankan malam/akhir pekan; jendela henti kira-kira lama import + verifikasi).
