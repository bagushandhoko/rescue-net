# ADR-0002: Arsitektur dan Kebijakan AI Rescue-Net

Status: Accepted
Tanggal: 2026-09-27
Diputuskan oleh: owner (bagushandhoko)
Terkait: ADR-0001 (Arsitektur Inti), NEXT_STEPS Fase 7

## 1. Prinsip dasar
1. AI adalah analis, bukan pengambil keputusan. Keputusan
   operasional selalu di tangan manusia.
2. AI tidak pernah lebih berkuasa dari penggunanya.
3. Sistem tetap berjalan penuh tanpa AI.
4. Biaya ditanggung pemakai. Tidak ada subsidi.
5. Data minimum: AI hanya menerima data yang diperlukan.
6. Fungsi AI dasar selalu aktif. Fungsi AI lanjutan hanya aktif di
   disaster event yang diaktifkan super admin.

## 2. Kelompok AI

AI Platform
- Ditempatkan oleh: super admin
- Tugas: gambaran makro (tren lintas bencana, wilayah kekurangan
  bantuan, organisasi tidak aktif, kualitas data, anomali sistem),
  plus fungsi dasar untuk data tingkat platform.
- Data: hanya agregat dan data anonim lintas organisasi.
- Biaya: key platform.

AI Organisasi
- Ditempatkan oleh: admin organisasi
- Tugas: briefing posko milik organisasi, matching bantuan, bantuan
  verifikasi, laporan donor.
- Data: hanya data organisasi tersebut, sesuai permission.
- Biaya: BYOK organisasi. Wajib untuk semua organisasi, termasuk
  perusahaan, instansi pemerintah, TNI/Polri, dan NGO.

AI Personal
- Ditempatkan oleh: masing-masing user
- Tugas: bantuan kerja individu (ringkasan tugas, bantuan input,
  tanya jawab data).
- Data: persis sebatas permission user.
- Biaya: BYOK user.

Asisten Halaman
- Pintu masuk ke AI Organisasi atau AI Personal di setiap halaman
  untuk user login, otomatis mengetahui konteks halaman.
- Konteks dibangun di server dengan pengecekan permission.

Asisten Publik
- DITUNDA. Tidak dikerjakan di tahap ini.

## 3. Fungsi dasar dan fungsi lanjutan

Fungsi dasar (selalu aktif selama key dan anggaran tersedia, tidak
bergantung aktivasi per disaster event):
- Konsolidasi dan normalisasi kebutuhan logistik
- Deteksi kemungkinan duplikat
- Membaca dan menstrukturkan laporan masyarakat menjadi draft
Daftar fungsi dasar ditetapkan di kode, tidak diatur user.

Fungsi lanjutan (hanya aktif di disaster event yang diaktifkan
super admin): semua fungsi AI lain, termasuk briefing, tanya jawab
data, asisten halaman, matching bantuan, bantuan verifikasi,
laporan donor, dan fungsi makro AI Platform. Pekerjaan yang tidak
terkait disaster event mana pun tidak memakai fungsi lanjutan.

Aktivasi: toggle per disaster event yang hanya bisa diubah super
admin. Setiap perubahan tercatat (siapa, kapan).

Output fungsi dasar maupun lanjutan tetap mengikuti tingkat
otonomi (bagian 6).

## 4. Arsitektur teknis
Satu mesin AI, banyak profil.

Komponen:
- RN AI Profile (DocType baru): tingkat, pemilik, provider, rujukan
  key, tool yang diizinkan, cakupan data, batas anggaran, status.
- Pengaturan aktivasi AI per disaster event (super admin).
- Pengaturan izin data sensitif per organisasi (default: tidak
  diizinkan).
- Lapisan provider: OpenAI, Anthropic, Gemini, dan model lokal.
- Context builder: menyusun konteks di server sesuai halaman,
  profil, dan permission user.
- Tool registry: fungsi Frappe yang boleh dipanggil AI, dijalankan
  dengan permission user yang login.
- AI Suggestion: tempat semua saran AI yang mengubah data
  (Draft/Accepted/Rejected). Perluas alur suggest/accept yang ada.
- RN AI Usage Log (sudah ada, diperluas): organisasi, kelompok AI,
  fitur, user, token, estimasi biaya.
- Fallback berbasis aturan dan antrian proses ulang (bagian 5).

Alur satu permintaan:
1. Jika fungsi lanjutan: cek apakah disaster event terkait sudah
   diaktifkan super admin. Jika tidak, tolak dengan pesan jelas.
2. Tentukan profil AI dan key yang berlaku (bagian 5).
3. Cek anggaran. Jika habis, jalankan fallback (bagian 5).
4. Context builder menyusun data sesuai permission dan izin data
   sensitif.
5. Kirim ke provider. AI hanya memanggil tool yang diizinkan.
6. Hasil yang mengubah data disimpan sebagai AI Suggestion.
7. Catat pemakaian di usage log.

## 5. Key, biaya, dan fallback

Resolusi key:
- Konteks organisasi: key organisasi. Jika tidak ada atau habis, AI
  nonaktif untuk konteks itu. TIDAK pindah ke key platform.
- Konteks personal: key personal. Jika tidak ada atau habis, nonaktif.
- Fungsi dasar untuk data tingkat platform (mis. laporan masyarakat
  yang belum ditangani organisasi mana pun): key platform, sebagai
  biaya operasional platform.
- Fungsi makro AI Platform: key platform.
- Tidak ada subsidi dan tidak ada sistem tagihan. Organisasi dan
  user membayar langsung ke provider lewat BYOK.

Anggaran:
- Batas harian dan bulanan per organisasi dan per user.

Saat anggaran habis atau provider gagal:
a. Peringatan ke admin organisasi (dan super admin untuk key
   platform) saat mencapai 80% dan saat habis, lewat notifikasi
   aplikasi dan kanal notifikasi yang ada.
b. Fallback otomatis:
   - Konsolidasi dan normalisasi logistik memakai aturan (RN
     Normalization Rule, fuzzy match), label "diproses tanpa AI".
   - Deteksi duplikat memakai pencocokan aturan (nama, lokasi, waktu).
   - Laporan masyarakat masuk antrian review manual, label "belum
     diproses AI".
c. Item yang belum diproses AI diproses ulang otomatis setelah
   anggaran/key diperbarui, dengan batas jumlah per jam.
d. Operasional tidak boleh terhenti karena AI tidak tersedia.

## 6. Tingkat otonomi
Otomatis tanpa persetujuan (tidak mengubah data operasional):
merangkum, menerjemahkan, menandai kemungkinan duplikat, label
prioritas sementara, briefing.

Saran wajib disetujui manusia: draft kebutuhan dari teks/voice
note/foto, usulan penggabungan duplikat, hasil konsolidasi
logistik, usulan matching bantuan, draft laporan donor.

Dilarang untuk AI: menetapkan status verifikasi, menyetujui
distribusi, keputusan medis, pencocokan final orang hilang, semua
yang menyangkut uang, perubahan permission atau akun.

## 7. Klasifikasi data
- Publik: kebutuhan posko yang dipublikasikan, info bencana umum.
- Internal: data operasional organisasi, sesuai permission.
- Sensitif: data medis, identitas korban, nomor HP, Search & Found,
  lokasi kelompok rentan. Hanya dikirim ke AI jika admin organisasi
  pemilik data mengizinkan secara eksplisit. Default: tidak
  diizinkan. Model lokal tetap disarankan.
- Agregat AI Platform: kelompok berisi kurang dari 5 orang tidak
  ditampilkan.

## 8. Keamanan dan log
- Prompt injection: isi laporan, pesan, dan dokumen adalah data,
  bukan perintah bagi AI.
- Key terenkripsi (field Password), tidak pernah muncul di response,
  log, maupun konteks AI.
- Retensi log: detail RN AI Usage Log dihapus otomatis setelah
  7 hari (scheduled job). Rekap harian per organisasi/user (jumlah
  permintaan, token, estimasi biaya; tanpa isi percakapan) disimpan
  lebih lama untuk anggaran dan dashboard biaya.
- Log tidak menyimpan data sensitif mentah.
- Rate limit per user dan per organisasi.
- Kontrol: toggle per disaster event sebagai kontrol utama fungsi
  lanjutan; kill switch global dan per fitur oleh super admin;
  admin organisasi bisa mematikan AI untuk organisasinya.

## 9. Instansi pemerintah dan TNI/Polri
Disarankan menjalankan server Rescue-Net sendiri lewat federasi,
dengan AI pilihan mereka termasuk model lokal. Platform hanya
menerima data yang mereka izinkan untuk dibagikan.

## 10. Evaluasi
- Rasio accept/reject per fitur di AI Suggestion.
- Fitur dengan penolakan tinggi diperbaiki atau dimatikan.
- Bandingkan hasil fallback berbasis aturan dengan hasil AI.
- Dashboard pemakaian dan biaya per organisasi dan super admin.

## 11. Urutan implementasi
1. Lapisan provider dan RN AI Profile
2. Resolusi key, anggaran, usage log diperluas, retensi log
3. Fallback berbasis aturan dan antrian proses ulang
4. Fungsi dasar di atas mesin ini
5. Toggle aktivasi per disaster event dan izin data sensitif
6. Asisten halaman untuk user login
7. Fungsi lanjutan (briefing War Room, intake, dll.)
8. Fungsi makro AI Platform
Ditunda: Asisten Publik.

## Catatan kesesuaian dengan kode saat ini

Dicek 2026-09-27 terhadap `rescue_net/api_ai.py` (lapisan kompatibilitas ke
`rescue_net/ai/`: `chat.py`, `common.py`, `context.py`, `keys.py`, `public.py`),
`services/llm.py`, `services/report_intake.py`, `api_intelligence.py`,
`intelligence/normalization.py`, DocType RN AI User Setting, RN AI Usage Log,
RN Normalization Rule. Kode tidak diubah. Catatan ini menunjukkan jarak kode
ke ADR; penutupannya mengikuti bagian 11.

Sudah sesuai:
- Key disimpan di field Password (`RN AI User Setting.api_key`); response hanya
  memberi 4 digit terakhir (`_safe_setting`). Key platform hanya dipakai untuk
  intake laporan masyarakat, tidak untuk chat (`resolve_platform_key`).
- Tidak ada fallback ke key platform untuk chat user/organisasi.
- Lapisan provider sudah ada untuk OpenAI, Anthropic, dan Gemini
  (`services/llm.py`, HTTP langsung).
- Saran yang mengubah data sudah melalui suggest/accept di jalur yang ada:
  `suggest_need` → `accept_suggestion` (normalisasi kebutuhan), draft laporan
  masyarakat yang ditinjau pelapor sebelum dikirim, dan
  `RN Consolidation Group Override` (qty dari manusia, `ai_suggestion` sebagai
  catatan). Analisis AI (`ask`, `analyze_duplicate_candidate`,
  `analyze_rollup_group`, `analyze_sync_conflict`) hanya mengembalikan teks,
  tidak menulis data.
- Konteks chat dibatasi pada posko yang boleh dilihat user
  (`_ai_scope_poskos`), dan dibangun di server.
- Normalisasi logistik dan routing laporan sudah deterministik (RN
  Normalization Rule, aturan kata kunci); intake laporan punya parser aturan
  (`rules_extract`) saat tidak ada key platform, dan menyimpan parser yang
  dipakai (`rules` atau `ai:<provider>`).

Berbeda / belum ada:
1. **RN AI Profile belum ada.** Key disimpan di RN AI User Setting
   (`owner_type` user/organisasi, key platform = baris organisasi khusus
   `PLATFORM_OWNER`). Belum ada field tingkat, tool yang diizinkan, cakupan
   data, batas anggaran.
2. **Resolusi key mencampur personal dan organisasi.** `_resolve_ai_key` memakai
   key personal dulu, lalu key organisasi mana pun tempat user menjadi anggota.
   Belum ada pembedaan "konteks organisasi" dan "konteks personal". Artinya
   anggota tanpa key pribadi memakai key organisasi untuk tanya jawab pribadi.
   Selain itu ada provider `auto` (key aktif yang terakhir disimpan), yang tidak
   diatur ADR.
3. **Model lokal belum didukung.** Provider di `services/llm.py` hanya openai,
   anthropic, gemini.
4. **Toggle aktivasi per disaster event belum ada.** Fungsi yang oleh ADR
   digolongkan lanjutan (`ask`/briefing, analisis rollup, analisis konflik sync)
   bisa berjalan di disaster event mana pun.
5. **Izin data sensitif per organisasi belum ada.** `ask()` mengirim
   `medical_cases`, `missing_person_reports`, `found_person_reports`, dan data
   hunian ke provider. Penyaringan field kontak (`_public_scrub`) hanya dipakai
   di jalur publik, tidak di konteks chat user login.
6. **Anggaran belum ada.** Tidak ada batas harian/bulanan, peringatan 80%/habis,
   maupun antrian proses ulang. Rate limit hanya ada di
   `analyze_duplicate_candidate` (20/jam per user) dan endpoint publik
   (120/menit). `ask()` tidak punya rate limit, dan belum ada rate limit per
   organisasi.
7. **Belum ada DocType AI Suggestion umum** (Draft/Accepted/Rejected), sehingga
   rasio accept/reject per fitur (bagian 10) belum bisa dihitung. Jalur
   suggest/accept yang ada spesifik per fitur.
8. **RN AI Usage Log belum diperluas.** Belum ada field kelompok AI, fitur,
   estimasi biaya. Belum ada job retensi 7 hari maupun rekap harian
   (`scheduler_events` hanya backup harian).
9. **Kemungkinan bug log pemakaian key platform.** Intake laporan mencatat
   `owner_type="platform"` dan `key_source="platform"`, padahal opsi Select di
   RN AI Usage Log hanya `user` dan `organization`. Validasi Select Frappe
   kemungkinan besar menolak insert, dan `_log_ai_usage` menelan error itu,
   sehingga pemakaian key platform tidak tercatat. Perbaikan 2026-09-27: opsi
   `platform` ditambahkan ke `owner_type` dan `key_source`, `ai_usage_summary`
   menghitungnya, dan `test_platform_ai_key_parses_the_narrative` memeriksa baris
   lognya. Lulus test suite (201 test, 2026-09-27); belum di-deploy.
10. **Fallback intake berbeda dengan ADR.** Tanpa key platform (atau jika
    provider gagal), laporan diurai aturan lalu dikirim pelapor seperti biasa.
    Belum ada antrian review manual berlabel "belum diproses AI", dan belum ada
    proses ulang otomatis.
11. **Deteksi duplikat berbasis aturan (nama, lokasi, waktu)** sebagai fallback
    belum berupa fungsi dasar. Analisis duplikat AI hanya dipanggil manual.
12. **Prompt injection:** system prompt intake dan chat belum menyatakan secara
    eksplisit bahwa isi laporan/pesan adalah data, bukan perintah.
13. **Kill switch belum ada:** tidak ada kill switch global/per fitur oleh super
    admin. Admin organisasi hanya bisa menghapus key organisasi, dan belum bisa
    mematikan AI untuk anggotanya (key personal anggota tetap berjalan).
14. **Asisten Halaman, AI Platform makro, tool registry, dan penyembunyian agregat
    < 5 orang belum ada.** Chat saat ini berupa tanya jawab per disaster event
    di halaman War Room/Control Centre.
