# Next Steps — roadmap Rescue-Net

Satu fase dikerjakan pada satu waktu; berhenti di akhir tiap fase dan tunggu review owner.
Status per fase yang sedang berjalan ada di `HANDOVER.md`.

## FASE 0 — Pisahkan lingkungan kerja agent dari produksi
PRIORITAS: dikerjakan sebelum Fase 1 setelah owner perintahkan.
Latar: agent saat ini bekerja di server yang juga menjalankan
produksi. Insiden 2026-09-20 (5 posko live terhapus) adalah
akibatnya.

Langkah:
1. Usulkan ke owner lingkungan kerja terpisah (container atau server
   lain) dengan site Frappe dan database sendiri, berisi salinan
   data yang sudah dianonimkan. Produksi tidak bisa dijangkau dari
   lingkungan ini.
2. Produksi hanya diperbarui lewat Git: commit → test otomatis →
   review owner → merge ke main → deploy dengan script tetap
   (git pull, bench migrate, restart). Agent tidak menjalankan
   perintah langsung di produksi.
3. Agent tidak memegang password database produksi, API key
   produksi, atau akses SSH produksi.
4. Buat .claude/settings.json yang melarang perintah berbahaya:
   bench ke site produksi, drop database, rm -rf di folder penting,
   dan perintah deploy manual.
5. Siapkan GitHub Actions yang menjalankan test di setiap pull
   request. Minta owner mengaktifkan branch protection pada main
   (hanya owner yang bisa melakukannya di Settings GitHub).
6. Untuk perubahan berisiko (migrate, hapus data, perubahan
   permission), agent menulis rencana dan menunggu persetujuan owner.
Selesai jika: agent bekerja sepenuhnya di luar produksi dan deploy
hanya lewat alur Git yang disetujui owner.
>>> BERHENTI, tunggu review owner.

## FASE 1–6 — Architecture review (2026-09-26)
1. Fondasi test otomatis (selesai).
2. Invariant bisnis ke controller DocType / `rescue_net/services/`; pecah `api_*.py` > 1.500 baris (berjalan).
3. Selesaikan pensiun FastAPI (tabel audit → owner memilih tanggal cutover → tag `fastapi-final`).
4. Pecah modul tunggal "Rescue Net" per domain.
5. Pembersihan frontend.
6. Kebersihan repo.

Detail dan progres: `HANDOVER.md` → "Architecture review".

## FASE 7–8
Semua fitur AI wajib mengikuti docs/adr/0002-kebijakan-ai.md. Urutan pengerjaan
Fase 7 mengikuti bagian 11 ADR-0002 (Urutan implementasi).

Belum tercatat di repo — isi saat owner menyampaikan rinciannya.

## FASE 9 — Federasi, sinkronisasi & interoperabilitas
Prasyarat: Fase 8 selesai. Fase ini dimulai dengan DOKUMEN DESAIN,
bukan kode. Setiap desain ditulis sebagai ADR berstatus Proposed
dan harus disetujui owner sebelum implementasi.

9a. Desain event log / outbox
- Setiap perubahan penting pada data operasional dicatat sebagai
  event (apa, siapa, kapan, server asal).
- Event log menjadi dasar sinkronisasi app offline dan pertukaran
  data antar server federasi. Tidak menyalin record apa adanya.
- Tentukan data mana yang ikut federasi dan mana yang tidak boleh
  keluar server (data medis, korban, nomor HP).

9b. Identitas global & aturan konflik
- ID record yang unik lintas server (mis. UUID + ID server asal),
  tanpa mengganggu penamaan DocType yang sudah ada.
- Aturan konflik yang jelas per jenis data: server/pemilik data
  mana yang berwenang, dan bagaimana konflik ditampilkan ke
  manusia untuk diputuskan.
- Kaitkan dengan analisis sync conflict yang sudah ada di api_ai.py.

9c. Standar data kemanusiaan
- P-code untuk wilayah administratif: audit RN Admin Area dan
  api_admin_areas.py, petakan ke P-code resmi.
- HXL untuk ekspor/impor data kemanusiaan.
- CAP (Common Alerting Protocol) untuk peringatan.
- Tujuan: data bisa dipertukarkan dengan BNPB, OCHA, dan NGO.

9d. Pelajari platform sejenis
- Kaji Sahana Eden, Ushahidi, dan KoBoToolbox/ODK: pelajaran desain
  yang relevan dan peluang integrasi (mis. impor form ODK/KoBo).
- Tulis ringkasan temuan dan rekomendasi. JANGAN mengganti
  Rescue-Net dengan platform tersebut.

9e. Implementasi bertahap
- Setelah desain disetujui: bangun dengan dua server test
  (simulasi dua organisasi) sebelum menyentuh produksi.
- Test wajib: sinkronisasi, konflik, data sensitif tidak bocor
  antar server, dan pemulihan setelah koneksi putus.

9f. Distribusi server federasi
Prasyarat: desain federasi (9a–9b) disetujui, Fase 0 dan Fase 1
selesai (test berjalan otomatis di CI).
1. Image Docker resmi Rescue-Net
   - Bangun di atas frappe_docker, berisi app rescue_net.
   - Rilis berversi (semantic versioning) lewat GitHub Actions,
     otomatis setelah test lulus.
   - Tidak ada secret, key, atau data di dalam image. Konfigurasi
     lewat environment/file terpisah saat instalasi.
2. Installer sekali klik
   - Linux/VPS: satu script yang memasang Docker (jika belum ada),
     menarik image, membuat site, dan menampilkan langkah awal.
   - Windows: installer yang memeriksa/menyiapkan Docker Desktop dan
     WSL, lalu menjalankan Rescue-Net.
   - Wizard pendaftaran awal: nama organisasi, admin pertama, dan
     identitas server untuk federasi (ID global server, sesuai 9b).
3. Perawatan bawaan
   - Update: pengecekan versi baru dan update dengan satu perintah,
     dengan backup otomatis sebelum update dan rollback jika gagal.
   - Backup: jadwal otomatis ke lokasi terpisah (drive eksternal atau
     penyimpanan lain), plus perintah restore yang sudah diuji.
   - Health check: status layanan, sisa disk, status backup terakhir,
     status sinkronisasi federasi; tampil di halaman admin.
4. Dokumentasi instalasi untuk organisasi non-teknis (bahasa
   Indonesia, langkah demi langkah).
5. Test: instalasi bersih, update antar versi, restore dari backup,
   dan dua server test yang saling sinkron.
>>> BERHENTI, tunggu review owner.

9g. Rescue-Net Box dan aplikasi klien
Prasyarat: 9f selesai.
1. Rescue-Net Box
   - Usulkan ke owner spesifikasi perangkat (mini PC, penyimpanan,
     daya/baterai, WiFi lokal) dan OS dasar.
   - Image siap tulis ke perangkat: Linux + Docker + Rescue-Net,
     menyala otomatis saat perangkat dihidupkan.
   - Berjalan di jaringan lokal (WiFi posko) tanpa internet; sinkron
     ke server federasi saat koneksi tersedia (mis. Starlink).
   - Enkripsi disk dan kata sandi admin wajib diganti saat pertama
     dipakai (perangkat bisa hilang/dicuri di lapangan).
   - Panduan singkat: menyalakan, menghubungkan, mematikan dengan aman.
2. Aplikasi klien EXE/APK
   - Klien terhubung ke server organisasi atau Rescue-Net Box, dengan
     pilihan server saat login.
   - Lanjutkan dari apps/rescue-net-app (Capacitor/PWA). Untuk Windows,
     usulkan ke owner pembungkus desktop (mis. Tauri atau Electron)
     atau cukup PWA terinstal.
   - Satu basis kode untuk web, Android, dan desktop sejauh mungkin
     (sejalan dengan Fase 5).
   - Mode offline mengikuti hasil uji Fase 8e.
>>> BERHENTI, tunggu review owner.

>>> BERHENTI di akhir tiap sub-fase, tunggu review owner.


## FASE 10 — Backlog fitur baru
Prasyarat: fondasi dan fitur AI inti stabil. Untuk setiap fitur,
cek dulu apa yang sudah ada di kode, tulis desain singkat, dan minta
persetujuan owner sebelum membangun. Prioritas owner-review: 10b,
10f, 10a.

10a. Integrasi peringatan dini dan data resmi
- Integrasi data terbuka BMKG (gempa, cuaca) dan sumber resmi lain
  (mis. inaRISK BNPB).
- Gempa/kejadian di atas ambang tertentu → DRAFT Disaster Event,
  tandai posko/organisasi di sekitar, kirim notifikasi. Aktivasi
  tetap oleh manusia.
- Pertimbangkan standar CAP (lihat Fase 9c).

10b. QR code paket bantuan dan kartu pengungsi
- QR per paket/batch bantuan, di-scan saat dikirim, transit, dan
  diterima → rantai bukti (chain of custody) otomatis, terhubung ke
  Distribution Flow dan evidence.
- Kartu QR per kepala keluarga pengungsi untuk mencegah penerimaan
  ganda. QR tidak boleh memuat data sensitif secara langsung, hanya
  ID yang diverifikasi di server.
- Harus bisa di-scan offline dan disinkronkan belakangan.

10c. SMS sebagai jalur cadangan
- Laporan kebutuhan/status via SMS dengan format sederhana, dan
  notifikasi keluar via SMS.
- Melengkapi intake WhatsApp (Fase 7c); output tetap lewat AI
  Suggestion / review manual.

10d. Manajemen gudang dan inventaris
- Stok per gudang/posko, tanggal kedaluwarsa untuk makanan dan obat,
  prinsip kedaluwarsa duluan keluar duluan, peringatan mendekati
  kedaluwarsa.
- Bangun di atas RN Stock Observation yang sudah ada.

10e. Status akses dan infrastruktur
- Layer peta status jalan/jembatan (terbuka, rusak, putus), listrik,
  dan sinyal, dengan sumber dan waktu pembaruan.
- Dipakai transport booking untuk memilih rute realistis.
- Lihat batasan GIS di Fase 8d.

10f. Papan kebutuhan publik untuk donatur
- Halaman publik kebutuhan aktual per wilayah/posko, termasuk barang
  yang TIDAK dibutuhkan, untuk mencegah donasi salah sasaran.
- Audit dulu apakah halaman kebutuhan publik yang ada sudah
  memenuhi fungsi ini. Tanpa data sensitif.

10g. Mode latihan
- Perkuat mode simulasi (sudah ada jejak event-sim-001): data
  latihan ditandai jelas, terpisah dari data nyata, mudah dibersihkan
  tanpa risiko menyentuh data nyata.
- Dipakai untuk uji lapangan Fase 8g.

10h. Check-in/check-out relawan di zona bahaya
- Koordinator selalu tahu siapa yang sedang di lapangan, dengan
  peringatan jika relawan melewati batas waktu tanpa check-out.
- Audit dulu fitur check-in dan safety briefing yang sudah ada.
>>> BERHENTI di akhir tiap fitur, tunggu review owner.
