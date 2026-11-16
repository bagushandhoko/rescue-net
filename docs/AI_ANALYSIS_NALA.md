# AI Analysis Nala — fitur 2, 3, 5, 7 (16 November 2026)

Status: kode dan tes tanpa site siap direview; BELUM deploy, BELUM uji integrasi
Frappe/DB atau browser dengan login sungguhan. Jangan sebut fitur live.
Fondasi: becabd0e milik Suri. UI dan manual bab 47 dikerjakan Suri pada branch
suri/ai-analisis-20261116; perubahan ini hanya backend dan tes.

## Jalur dan kontrak

Endpoint tetap `rescue_net.ai.analysis.{triase_laporan,prakiraan_stok,dampak_gempa,cek_kejanggalan}`.
`analysis.py` mengimpor empat endpoint dari `analysis_nala.py` di bagian akhir.
Helper `_kunci`, `_tanya`, `_simpan`, `JENIS`, dan `ATURAN_UMUM` tetap milik
fondasi Suri. Akses helper dilakukan saat runtime supaya patch
`rescue_net.ai.analysis._tanya` bekerja. Hitungan murni berada di
`analysis_nala_calc.py`. Semua hasil hanya RN AI Report, tidak mengubah data
operasional atau mengeksekusi tindakan AI.

## Perilaku dan batas data

- **Triase**: periode bawaan 72 jam (batas 1–720), 150 laporan terbaru,
  JSON klaster/darurat/ringkasan. ID palsu dan bentuk tak sesuai dibuang;
  urgensi dibatasi 1–5 dan diurutkan tertinggi dahulu. Laporan tak terklaster
  dicatat untuk pemeriksaan manual. Deskripsi ke AI maksimal 600 karakter.
- **Privasi triase**: field pelapor tidak dipilih. Teks judul/deskripsi/
  kebutuhan diproyeksikan ke kosakata operasional, termasuk negasi sederhana.
  Pendekatan ini sengaja menghilangkan narasi bebas agar nama, nomor,
  identitas dan cerita pasien tak terkirim. Alamat bebas diganti koordinat
  kasar dua desimal (~1 km); tanpa koordinat, AI tidak diberi alamat. Ini
  membatasi kualitas triase: rincian dan negasi kompleks harus dicek di sumber.
- **Stok**: maksimal 5.000 observasi terbaru; kelompok posko+barang+satuan.
  Base quantity dipakai hanya bila konversi `ok`; nol tidak dianggap kosong.
  Laju harian eksplisit di satuan asli dikonversi ke satuan dasar bila perlu.
  Fallback laju = penurunan bersih observasi pertama–terakhir / selang hari.
  Observasi tunggal tanpa laju, timestamp sama, atau kenaikan stok memberi
  sisa hari tidak diketahui. Kritis <=3, waspada <=7. Calon surplus >30 hari,
  atau tanpa laju dengan stok >=100 unit dan >=2x median stok posko lain
  untuk barang+satuan sama (bila tanpa pembanding, >=100). Ini kandidat,
  bukan jaminan surplus. Umur observasi dan asumsi disimpan. Stok rusak/
  kedaluwarsa/reserved dan jumlah unknown/range tidak dipakai hitungan.
  Stok observasi bukan saldo ledger terkini: kiriman/pemakaian sesudah
  pencatatan wajib diperiksa, begitu juga kebutuhan posko donor.
- **Gempa**: warning bernama atau gempa terbaru menurut issued_at, maksimal
  10.000 posko dalam cakupan pengguna. Posko aktif, periode aktif sah dan
  jarak <=200 km; koordinat nol sah, koordinat rusak dilewati, jarak urut naik.
  Semua posko aktif dipertimbangkan, termasuk lintas event utama. Jarak
  permukaan bukan prediksi MMI. Prompt mewajibkan tindakan 0–6 dan 6–24 jam,
  mempertahankan negasi potensi tsunami, serta menyebut usia peringatan.
- **Kejanggalan**: bantuan sama donor+barang+jumlah+satuan dalam 48 jam;
  perubahan stok >5x (termasuk lintas nol); kebutuhan >10x median barang dan
  satuan; bid <50%/>200% median tender; laporan mirip dengan Jaccard bigram
  kata >=0,9 dan lokasi teks berbeda atau koordinat terpisah >1 km.
  Teks dibandingkan setelah normalisasi, maksimal 600 karakter, minimal 40.
  Median hanya digunakan bila >=3 data dan median >0. Nama donor dan teks
  warga diperiksa lokal dan tidak diteruskan ke AI. Hasil selalu 'perlu dicek',
  bukan tuduhan. AI hanya menilai ID kandidat sah; sisanya 'belum_dinilai'.
  Batas: bantuan/kebutuhan/tender 1.000, stok 5.000, bid 3.000, laporan 150;
  kandidat aturan maksimal 2.000, dikirim ke AI maksimal 150. Batas dan jumlah
  tersimpan; hasil bukan audit menyeluruh.
- **Scope**: mengikuti `_ai_scope_poskos(refresh=True)`. Laporan/stok/kebutuhan
  dibatasi posko; bantuan dibatasi target_posko. Tender hanya dalam scope
  global karena tidak memiliki posko, sesuai prinsip context.py. Bid selalu
  melalui ID tender event yang dipilih, tidak mengambil tender event lain.

## Bukti uji dan yang belum diuji

`python3 frappe_shadow/apps/rescue_net/rescue_net/tests/test_ai_analysis_nala.py`
menjalankan 42 tes tanpa site. Meliputi hitungan deterministik, privasi prompt,
JSON/ID palsu, scope kosong/terbatas, kegagalan kunci sebelum baca data,
filter gempa aktif dan radius, serta kontrak simpan ke empat report_type.
Endpoint memakai mock Frappe/DB dan patch `rescue_net.ai.analysis._tanya`.
Ini bukan bukti uji Frappe atau browser login.

`py_compile` empat file Python, `git diff --check`, dan secret scan juga lulus.
CT102 tidak punya container test berjalan; pemeriksaan read-only VM Aspire
via QEMU guest agent hanya menemukan cloudflared berjalan. Tidak menyalakan
stack atau menyentuh site produksi. Stack/DB, provider AI sungguhan, riwayat
RN AI Report dan browser dengan akun login sungguhan BELUM diuji.

## Langkah integrasi untuk Suri

1. Gabungkan branch Nala. Bila konflik di akhir `analysis.py`, pertahankan
   fitur Suri (foto/rencana kirim) dan letakkan import Nala setelah semuanya.
2. Sesuaikan manual bab 47 dengan batas dan privasi di atas pada deploy yang
   sama. Jangan mengumumkan fitur live sebelum deploy.
3. Jalankan tes di stack Frappe terisolasi saat tersedia; periksa query schema,
   whitelist endpoint, RN AI Report dan kontrol akses dengan akun asli.
4. Uji UI delapan kartu, empat endpoint, simpan/buka ulang laporan, tamu ditolak,
   pengguna scoped tidak menerima posko lain; browser desktop dan HP.
5. Deploy/migrate hanya setelah izin owner. Branch Nala tidak memerlukan
   perubahan schema tambahan; fondasi RN AI Report dari Suri memerlukan
   migrate saat deploy nanti. Nala tidak melakukan deploy/migrate/push main.
