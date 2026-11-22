# Panduan kontribusi Rescue-Net

1. Buat cabang dari versi terbaru `main`. Ajukan pull request ke `main` dengan ringkasan perubahan, dampak pada data, dan hasil pengujian.
2. Jalankan `sh scripts/rn-test-stack.sh test`. Uji perubahan antarmuka di browser dengan akun uji sungguhan dan sebagai tamu bila berlaku.
3. Untuk perubahan skema, sertakan JSON DocType di aplikasi Frappe. Jalankan `sh scripts/rn-test-stack.sh migrate` di lingkungan uji dan verifikasi data lama tetap terbaca. Sertakan patch migrasi bila perubahan perlu mengisi atau memindahkan data.
4. Jalankan dan pertahankan tes sentinel yang memeriksa kebocoran data kepada tamu. Tambahkan cakupan saat mengubah respons publik atau izin akses. Pakai data simulasi dan simpan rahasia di luar repo.
5. Pakai Bahasa Indonesia untuk teks antarmuka. Saat mengubah aset, perbarui parameter `?v=` pada rujukan HTML yang memuatnya dan periksa perilaku cache PWA bila relevan.

Baca [kode etik](CODE_OF_CONDUCT.md) dan gunakan [kanal keamanan](SECURITY.md) untuk melaporkan celah.
