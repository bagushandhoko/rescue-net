# Fase 6 — Kebersihan repo (2026-09-27)

## Temuan utama: seluruh repo terbuka untuk publik

Web root `/volume1/web/rescue-net` adalah checkout git itu sendiri, dan nginx menyajikan semua isinya di
`https://osiun.tail251e1e.ts.net/rescue-net/<path>` (Tailscale Funnel = internet). Dicek 2026-09-27, semuanya
menjawab 200:

- `.git/config`, `.git/HEAD`, sehingga seluruh riwayat git bisa diunduh
- `frappe_shadow/…` (source backend lengkap) dan `frappe_shadow/ops/docker-compose.shadow.yml` (password root
  MariaDB produksi dalam teks biasa)
- `HANDOVER.md`, `CLAUDE.md`, `docs/…`, `scripts/…`, `blueprint/*.pdf|docx`, `backup/…`
- file lokal yang di-gitignore: `backups/<dir>/main.py` (salinan FastAPI lama) dan
  `assets/img/rescuenet_ui_design_images_all.zip` (23 MB)

Repo GitHub `bagushandhoko/rescue-net` juga **publik** (API GitHub menjawab 200 tanpa login), jadi password
root itu sudah publik lewat riwayat git, terlepas dari nginx.
Port MariaDB (`osiun-frappe-mariadb` 3306) tidak dipublikasikan ke host, sehingga risikonya berkurang, tetapi
password tetap harus diganti.

### Perbaikan
- `ops/nginx/www.rescue-net-static-deny.conf`: 404 untuk file tersembunyi (`.git`, `.gitignore`, …), folder
  non-situs (`frappe_shadow docs ops scripts apps backup backups blueprint scratchpad data _sandbox_desain`),
  `*.md|txt|sh` di root, dan `*.py|yml|zip|sql|dump|bak|log|env|…` di mana pun. Diuji di container
  `nginx:alpine` terhadap salinan repo: halaman situs (`index.html`, `pages/`, `assets/`, `sw.js`,
  `manifest.webmanifest`) 200, semua jalur di atas 404. Situs tidak mereferensikan satu pun folder yang diblokir.
- `scripts/rn-install-nginx-deny.sh` (owner, root): pasang, `nginx -t` (batal kalau gagal), reload, cek 11 URL.
- `docker-compose.shadow.yml` sekarang memakai `${MYSQL_ROOT_PASSWORD:?…}`, tidak lagi menyimpan nilai.
- `scripts/rn-secret-scan.sh` juga menangkap nilai literal `MYSQL_/MARIADB_ROOT_PASSWORD` dan key Gemini
  (`AIza…`). `scripts/rn-push-main.sh` (dipindah dari root) memakai scanner yang sama, bukan salinan pola sendiri.

## Rapikan repo

Sudah (commit Fase 6):
- Dokumen lama dipindah ke `docs/history/`: `HANDOFF.md`, `HANDOFF_LATEST_RN.txt`,
  `HANDOVER-CODEX-RESCUE-NET-20260625.txt`, `NEXT_AGENT_PROMPT.md`, `CURRENT_STATUS.md`,
  `RN_CURRENT_AUDIT_20260611.md`, `ROADMAP.md`, `PRODUCTION_GRADE_ROADMAP.md`, `CROSS_PLATFORM_APP_DESIGN.md`,
  `MOCKUP_ALIGNMENT_PLAN.md`, `FRAPPE_MIGRATION_MAP.md`.
- Satu skrip push: `scripts/rn-push-main.sh`.

Belum, karena penghapusan diblokir izin sesi Claude sehingga owner yang menjalankan (semua file yang di-track tetap
ada di riwayat git):

```sh
cd /volume1/web/rescue-net
git rm -r -q backup scratchpad _sandbox_desain docs/migration PY \
  AUDIT-BEFORE-CODEX.txt QUICK-CHECK-BEFORE-CODEX.md MANUAL-CHANGES-20260612.md
git commit -m "Phase 6: remove pre-git backup copies, scratch scripts, design sandbox, FastAPI-era inventories and root notes"
rm -rf backups data scripts/__pycache__ scripts/komando-tests/__pycache__
find frappe_shadow -name __pycache__ -type d -prune -exec rm -rf {} +
mv assets/img/rescuenet_ui_design_images_all.zip /volume1/docker/osiun-backups/
git gc
git push origin main
```

- `backup/` (100 file): salinan halaman/JS dari Agustus 2026, sebelum git dipakai dengan benar.
- `scratchpad/backfill_base_quantity.py`: skrip sekali jalan yang sudah dijalankan.
- `_sandbox_desain/home_baru.html`: sandbox desain yang tidak dipakai situs.
- `docs/migration/`: inventaris API/DB FastAPI. Pensiun di Fase 3, dan tetap ada di tag `fastapi-final`.
- `PY` (0 byte) dan catatan root Juni 2026 untuk "Codex".
- `backups/` (lokal, di-gitignore): salinan `main.py` FastAPI dari 2026-08-04.
- `.git` punya 7.017 object lepas (105 MB). `git gc` memadatkannya.

## Masih terbuka (keputusan / akses owner)
1. **Ganti password root MariaDB** produksi. Isi nilai baru di `.env` di samping `docker-compose.yml`
   `/volume1/docker/osiun-frappe-shadow`, jangan di git. Sesuaikan juga `db_password` / `root_password` di
   `site_config`/`common_site_config` bila dipakai.
2. **Repo GitHub publik**: jadikan private, atau terima bahwa source + dokumen blueprint publik. Password lama tetap
   ada di riwayat, dan menulis ulang riwayat tidak menolong karena sudah telanjur publik. Solusinya adalah rotasi.
3. `scripts/komando-tests/` berjalan **terhadap produksi** (`osiun.localhost`, `127.0.0.1:8095`) dan membuat/menghapus
   data uji di sana. Ini garis keturunan insiden 2026-09-20. Belum ada padanannya di `tests/`. Usul: porting ke
   test stack di Fase 0 lalu hapus. Sampai itu terjadi, jangan jalankan di produksi.
4. `apps/rescue-net-app/`: dihapus setelah APK/desktop dibangun ulang dari `apps/rescue-net-shell/` (keputusan Fase 5).
5. `blueprint/` (9,8 MB PDF/DOCX) tetap di repo sebagai rujukan owner. Tidak lagi tersaji publik setelah aturan nginx.
6. Jangka panjang (Fase 0): web root bukan lagi checkout git, tetapi hasil deploy yang hanya berisi situs.
