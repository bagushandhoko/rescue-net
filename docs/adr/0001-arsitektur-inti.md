# ADR-0001: Arsitektur Inti Rescue-Net

Status: Accepted
Tanggal: 2026-09-26
Diputuskan oleh: owner (bagushandhoko)

## Keputusan
1. Backend: Frappe sebagai satu-satunya backend.
2. Bentuk: modular monolith (satu aplikasi Frappe, terbagi per
   domain/module). BUKAN microservices.
3. Database: MariaDB. Tidak pindah ke PostgreSQL karena alasan skala.
4. Frontend: frontend statis yang memanggil whitelisted method
   Frappe (pola headless).
5. AI: model BYOK, semua output lewat alur suggest/accept, sistem
   tetap berfungsi penuh tanpa AI.

## Alasan
- Frappe menyediakan DocType, permission, audit trail, workflow,
  background job, dan scheduler, yang semuanya kebutuhan inti
  sistem bencana yang akuntabel.
- Tim kecil dibantu AI. Microservices menambah kompleksitas
  deployment dan konsistensi data tanpa manfaat sepadan.
- MariaDB cukup untuk skala satu bencana besar; beban juga terbagi
  lewat desain federasi. Ekosistem Frappe paling matang di MariaDB.
- Rewrite akan membuang progres yang ada tanpa keuntungan jelas.

## Alternatif yang dipertimbangkan dan ditolak
- Stack custom (Django/NestJS + PostgreSQL + React): harus membangun
  ulang permission, audit, workflow, dan admin.
- Microservices: tidak sesuai ukuran tim dan tahap proyek.
- Event sourcing penuh: terlalu berat. Idenya dipakai sebagian
  untuk federasi/sinkronisasi (lihat Fase 9).

## Batasan yang diketahui
- Frappe tidak punya federasi antar server dan sinkronisasi offline
  bawaan. Harus dirancang sendiri (Fase 9).
- Fitur spasial MariaDB terbatas. Jika butuh GIS berat, gunakan
  layanan GIS terpisah, bukan mengganti database utama.

## Kapan keputusan ini perlu ditinjau ulang
Jika muncul kebutuhan yang tidak bisa dipenuhi dalam batasan di
atas, tulis ADR baru berstatus Proposed dan minta persetujuan owner.
