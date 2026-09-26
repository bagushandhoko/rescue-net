# Next Steps — roadmap Rescue-Net

Satu fase dikerjakan pada satu waktu; berhenti di akhir tiap fase dan tunggu review owner.
Status per fase yang sedang berjalan ada di `HANDOVER.md`.

## FASE 1–6 — Architecture review (2026-09-26)
1. Fondasi test otomatis (selesai).
2. Invariant bisnis ke controller DocType / `rescue_net/services/`; pecah `api_*.py` > 1.500 baris (berjalan).
3. Selesaikan pensiun FastAPI (tabel audit → owner memilih tanggal cutover → tag `fastapi-final`).
4. Pecah modul tunggal "Rescue Net" per domain.
5. Pembersihan frontend.
6. Kebersihan repo.

Detail dan progres: `HANDOVER.md` → "Architecture review".

## FASE 7–8
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

>>> BERHENTI di akhir tiap sub-fase, tunggu review owner.
