# Edisi Instansi RN — antarmuka berdasarkan mockup PDF

Tanggal: 2026-11-21  
Sumber visual: `Proposal Desain Sistem & Antarmuka — Rescue-Net Edisi Tertutup`, versi 2.4, 21 Nov 2026, dikirim owner melalui Edith. Dokumen berlabel TERBATAS; salinan dan screenshot PDF tidak dimasukkan ke situs preview.

## Pemetaan mockup ke UI

- `pages/edisi-tertutup.html` meniru komposisi mockup halaman 1: header DMS dengan pemilih profil BNPB/TNI/PMI/Kombinasi dan label klasifikasi; hierarki komando di kiri; peta operasi/Tactical GIS sebagai area tengah; SITREP, stok logistik, dan antrean federasi di kanan.
- Pilihan Kombinasi menampilkan tiga kartu profil visual terpisah seperti gambar halaman 2. Pemilih hanya mengubah presentasi pratinjau, bukan hak akses ataupun pemisahan data.
- Ruang peta juga menjadi ruang kerja jendela: modul atau beberapa posko bisa digeser, diubah ukuran, diminimalkan, dan dimaksimalkan. Di layar sempit jendela ditata vertikal.
- Peta SVG hanya ilustrasi desain; semua KPI dan stok memakai tanda kosong. Tidak ada angka operasi contoh yang disamarkan sebagai data live. Permintaan federasi dan kontrol persetujuan dinonaktifkan.
- `assets/css/rn-edisi-tertutup.css` mengadaptasi permukaan gelap navy/biru-abu pada mockup, garis tipis, aksen BNPB oranye, TNI hijau, PMI merah; theme diterapkan ke halaman RN lain. Warna visual bukan kontrol keamanan.
- Menu samping tetap mengarah ke modul RN yang sudah ada. Area modul khusus PDF seperti OPORD/BKO, lapisan COP terklasifikasi, pertukaran federasi, audit immutable, SSO/2FA, AI lokal, dan radio/satelit masih rancangan.
- Service worker v10 memuat versi tema dan window manager terbaru. PWA mulai dari dashboard Edisi Instansi.

## Batas fungsi

UI ini memakai engine/API RN yang sekarang hanya bila dibuka pada node RN yang telah dipasang. Tema dan pemilih profil tidak menambah backend, otorisasi, SSO/2FA, klasifikasi, enkripsi, redaksi, federasi, sertifikasi, atau integrasi instansi.

CT202 menyajikan salinan statis untuk review. Modul di dalam jendela pada preview adalah placeholder tanpa database atau aksi produksi. Preview belum diuji dengan login RN sungguhan dan bukan deployment produksi.
