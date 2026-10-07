# Fase 0 — Pisahkan lingkungan kerja agent dari produksi

Status 2026-10-07: **sebagian dikerjakan di repo; langkah 1–3 dan 5 menunggu keputusan/aksi owner.**

## Sudah ada di repo
| Langkah roadmap | Isi |
|---|---|
| 4. Larangan perintah berbahaya | `.claude/settings.json` (deny: container/site produksi, port 8095, script deploy, drop/truncate, push ke main/force push; ask: push, migrate) |
| Test tidak menyentuh produksi | `scripts/rn-test-stack.sh` (stack terisolasi); `scripts/komando-tests/*` menolak `osiun.localhost` dan berjalan lewat `rn-test-stack.sh e2e` |
| 2. Deploy hanya dari Git | `scripts/rn-deploy-from-git.sh`: clone bersih commit di `origin/main`, tolak commit di luar main, lalu pakai `rn-deploy-app.sh` |
| 5. Test di setiap PR | `.github/workflows/tests.yml` (DRAFT, belum pernah dijalankan di GitHub; kemungkinan perlu penyesuaian pertama kali) |

## Keterbatasan jujur
`.claude/settings.json` hanya pagar lunak: pola string bisa dilewati (mis. lewat `sh -c` atau skrip lain), dan aturan
`Bash(*osiun-frappe-*)` juga memblokir tugas sah. Pertahanan sebenarnya adalah langkah 1 + 3 di bawah.

## Perlu keputusan / aksi owner
1. **Akun agent tanpa akses produksi (inti Fase 0).** Hari ini agent berjalan sebagai `admin` dengan `sudo docker`, jadi bisa menjangkau
   produksi. Usul: buat user NAS terpisah `rn-agent` tanpa sudo, tanpa grup docker, tanpa baca `/volume1/docker/osiun-*`; ia hanya
   punya clone repo di `/volume1/rn-agent/rescue-net` dan akses ke test stack lewat socket Docker rootless / Docker terpisah.
   Pilihan: (a) user terpisah di NAS yang sama (murah, isolasi sedang), (b) VM/mini-PC lain dengan test stack sendiri (isolasi kuat).
2. **Web root bukan checkout git.** `/volume1/web/rescue-net` sekarang = working tree agent = situs publik. Usul: situs disajikan dari
   salinan hasil deploy (`rsync` dari clone bersih oleh `rn-deploy-from-git.sh`), agent bekerja di clone sendiri.
3. **Data uji teranonimkan.** Test stack hari ini berisi data seed/test saja; bila ingin salinan produksi, perlu skrip anonimisasi
   (nama, telepon, email, PIN, koordinat posko) — belum ditulis, tunggu keputusan.
4. **Branch protection `main` + review PR** (Settings → Branches di GitHub; hanya owner). Setelah aktif, agent bekerja lewat branch + PR,
   bukan push ke main; `scripts/rn-push-main.sh` hanya untuk owner.
5. Tanpa password DB produksi di sisi agent: ganti password root MariaDB (sudah tertunda) setelah langkah 1.
6. Perubahan berisiko (migrate, hapus data, permission): agent menulis rencana di PR, owner menyetujui, owner menjalankan deploy.

## Selesai jika
Agent bekerja di akun/lingkungan tanpa jalur ke produksi, dan satu-satunya jalan ke produksi adalah `rn-deploy-from-git.sh`
yang dijalankan owner atas commit yang sudah di-review.
