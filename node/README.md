# Rescue-Net Node — paket instalasi server

Satu folder untuk memasang Rescue-Net lengkap di server mana pun (Proxmox VM/LXC, VPS, PC Linux):
database MariaDB, Redis, Frappe v15 (frappe + erpnext + rescue_net), dan nginx sebagai pintu depan.
Cloudflare Tunnel opsional. Dipakai juga untuk **pindah server** dan **cadangan**.

## Kebutuhan
- Linux 64-bit, Docker Engine + plugin compose, internet (unduh image ±2 GB sekali).
- Minimal 2 CPU, 4 GB RAM, 20 GB disk. Disarankan SSD.
- Repo rescue-net utuh (paket memakai `../frappe_shadow/apps/rescue_net` dan halaman web di folder induk).

## Pasang baru
```sh
git clone <repo-rescue-net> && cd rescue-net/node
./pasang.sh
```
`pasang.sh` membuat `.env` (kata sandi acak), menyetel jumlah pekerja web & cache database dari CPU/RAM mesin,
membuat situs, memasang aplikasi, menyalakan layanan, lalu menguji halaman utama. Web: `http://127.0.0.1:8182/rescue-net/`.

## Pindah server (data lama ikut)
Di server LAMA:
```sh
./cadangan.sh                      # -> backups/<waktu>/ (DB, berkas, site_config.json berisi kunci enkripsi)
```
Salin folder itu ke `node/backups/` di server BARU, lalu:
```sh
./pasang.sh --pulihkan backups/<waktu>    # atau: backups/<berkas>.tar dari menu Setting > Cadangan
```
Kunci enkripsi ikut dipulihkan — tanpa itu API key AI, token WhatsApp, dan login Google tidak terbaca.

Server uji/gladi dengan data asli: **jangan** pakai `--dengan-jobs` (worker & scheduler mati) supaya
notifikasi tidak terkirim dua kali ke orang sungguhan. Di server utama setelah pindah:
`docker compose --profile jobs up -d`.

## Pembaruan
```sh
git pull && ./perbarui.sh          # cadangan dulu -> migrasi -> restart
```

## Internet publik (Cloudflare Tunnel)
Isi `RN_CF_TUNNEL_TOKEN` di `.env`, lalu `docker compose --profile tunnel up -d`.
Satu token hanya boleh aktif di **satu** server: matikan tunnel di server lama dulu.

## Isi folder
| Berkas | Guna |
|---|---|
| `docker-compose.yml` | susunan layanan (image dipatok ke versi yang sama dengan produksi) |
| `.env.example` | contoh pengaturan; `.env` asli tidak masuk git |
| `nginx/` | pintu depan: hanya halaman web + daftar putih API; Desk/`/app` tertutup |
| `pasang.sh` | pasang baru / pulihkan |
| `cadangan.sh` | cadangan lengkap ke `backups/` |
| `perbarui.sh` | pasang versi terbaru dari git |

## Penyetelan
`RN_WORKERS` (pekerja gunicorn, default 2×CPU+1, maks 17) dan `RN_DB_BUFFER` (cache MariaDB, default RAM/5)
dihitung otomatis bila kosong. Ubah di `.env`, lalu `docker compose up -d`.
