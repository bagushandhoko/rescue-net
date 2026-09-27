# ADR-0003: Distribusi Server dan Aplikasi Klien

Status: Accepted
Tanggal: 2026-09-27
Diputuskan oleh: owner (bagushandhoko)
Terkait: ADR-0001, NEXT_STEPS Fase 9

## Keputusan
1. Server Rescue-Net (Frappe, MariaDB, Redis, worker, scheduler)
   didistribusikan sebagai IMAGE DOCKER berversi, dibangun di atas
   proyek resmi frappe_docker.
2. Di atas image tersebut disediakan:
   a. Installer sekali klik (Windows via Docker Desktop/WSL; Linux/
      VPS via satu script).
   b. Rescue-Net Box: perangkat (mini PC) dengan Linux dan Rescue-Net
      terpasang, siap dipakai di posko/pusat komando, bisa berjalan
      di jaringan lokal tanpa internet.
3. Target EXE/APK di blueprint adalah APLIKASI KLIEN yang terhubung
   ke server organisasi atau Rescue-Net Box, bukan server.

## Alasan
- Frappe terdiri dari banyak layanan yang berjalan bersamaan dan
  tidak mendukung Windows secara native. Membungkusnya menjadi satu
  .exe rapuh, sulit di-update, dan sulit diperbaiki di lapangan.
- Docker memberi instalasi yang konsisten, update per versi, dan
  rollback yang mudah.
- Rescue-Net Box sesuai kondisi bencana: listrik dan internet tidak
  stabil, butuh server lokal yang siap pakai.

## Alternatif yang ditolak
- Satu .exe berisi Frappe dan seluruh dependensinya.
- Instalasi manual bench di setiap server organisasi.

## Konsekuensi
- Setiap server federasi adalah infrastruktur yang harus dirawat.
  Distribusi wajib menyertakan update, backup, dan pemeriksaan
  kesehatan bawaan.
