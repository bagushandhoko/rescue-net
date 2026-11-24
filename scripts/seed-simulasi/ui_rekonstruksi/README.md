# UI Peduli — Rekonstruksi Fasilitas Belajar

Skenario **simulasi** untuk program `rn-donor-f5fa707a9c62`, event `disaster_events:event-sim-001`. Rehabilitasi dua kelas dan satu perpustakaan di sekolah fiktif di Johan Pahlawan, Aceh Barat. Fondasi dinilai masih layak dalam skenario. Delapan kolom dan rangka beton bertulang diperkuat sebelum pekerjaan atap dan ruang. Gambar menunjukkan lingkup dan ukuran untuk simulasi.

RAB memakai asumsi harga satuan terpasang Aceh Barat 2026, dengan [SSH TA 2026, Keputusan Bupati Aceh Barat No. 419/2025](https://acehbaratkab.go.id/media/2025.08/standar_satuan_harga_ta_20261.pdf) sebagai acuan tingkat harga bahan dan upah. Target program mengikuti total RAB. Angka dan tanggal dipakai bersama oleh generator dan seed melalui `rek_data.py`.

## Regenerasi dokumen

Di folder ini, dengan Python dan Chromium Playwright yang sudah tersedia:

```sh
python -m pip install playwright 'qrcode[pil]'
python -m playwright install chromium
python gen_docs.py
```

Output terdiri dari RAB PDF dua halaman, masing-masing halaman dalam PNG, GK-01/GK-02, PNG QR berisi teks peringatan, dan PDF rekening koran simulasi. Tidak ada aset foto; sampul generik dari seed lama dikosongkan, bila ada.

## Jalankan pada Frappe uji terisolasi

Gunakan branch ini di lingkungan uji dengan program, event, dan akun pemrakarsa simulasi yang sudah tersedia. Pastikan Frappe dapat membuat PDF dengan wkhtmltopdf. Salin seluruh folder ini ke `/tmp/ui-rekonstruksi` pada backend uji. Salin `../ui_rekonstruksi.py` ke `/tmp/ui_rekonstruksi.py`.

Dari folder bench, ganti `SITE-UJI` di kedua tempat dengan nama site uji, lalu buka console:

```sh
RN_UI_REK_TEST_SITE=SITE-UJI bench --site SITE-UJI console
```

Jalankan satu baris ini di console:

```python
exec(compile(open("/tmp/ui_rekonstruksi.py", "rb").read(), "/tmp/ui_rekonstruksi.py", "exec"), {})
```

Seed memakai akun `sim-ui-peduli@example.org` dan harus dijalankan oleh operator site uji. DB dikunci per program dan di-commit setelah rekonsiliasi. Eksekusi ulang setelah commit tidak mengubah data. Seed mengganti entri contoh yang dikenali dari `program_donasi.py` tanpa menghapus berkas aslinya. QR tersedia bagi pengelola dan tampil publik bila pemrakarsa terverifikasi menurut aturan Rescue-Net.

Rekening koran menyajikan enam donasi terkonfirmasi (Rp 194.750.000), tiga pengeluaran (Rp 120.770.000) dan tambahan saldo Rp 73.980.000. Satu komitmen Rp 2.000.000 tetap menunggu konfirmasi. Jika program sudah menyimpan dana masuk/terpakai, seed merangkum keduanya dalam saldo awal dan membuat PDF dari saldo tersebut. PDF contoh yang disimpan di repo memakai saldo awal nol.

Sesudah seed, buka detail program dan login sebagai pemrakarsa simulasi untuk memeriksa RAB, gambar, QR, rekening koran, kabar, donasi, serta tab rencana. Jalankan seed ulang untuk memeriksa bahwa item dan saldo tetap sama.
