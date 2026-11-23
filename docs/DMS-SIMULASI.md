# Simulasi DMS pada backend Rescue-Net

`RN Disaster Event.drill_scope` memisahkan latihan DMS dari latihan RN. Event lama memakai lingkup RN, termasuk bila kolomnya kosong. `bench migrate` diperlukan. Mode Operasional Riil global tetap berlaku.

| Jalur | Tampilan Riil | Tampilan Simulasi |
| --- | --- | --- |
| Rescue-Net | Data riil | Perilaku simulasi RN yang sudah ada |
| Proxy DMS tepercaya | Data riil | Kejadian simulasi DMS dan data terkait |

## Proxy dan cache

Saat rilis disetujui, pasang perubahan template nginx RN dan buat ulang layanan `web` supaya template dirender ulang. Set `RN_DMS_PROXY_PEER` pada konfigurasi Compose RN ke **alamat sumber privat CT202 sebagaimana terlihat oleh nginx RN**. Gunakan satu alamat CT202. Verifikasi nilai tersebut setelah NAT, sebelum memberi akses. Bawaan menolak jalur DMS. Nginx RN membuang header DMS dari sumber selain alamat ini. Permintaan DMS yang membawa kunci melewati cache tamu RN, termasuk untuk penulisan cache.

CT202 saat ini meneruskan `Host` dan `X-Forwarded-Host` sebagai `rescue-net.online`. Pada blok proxy API CT202, pertahankan upstream dan `Host` yang dipakai untuk routing. Ganti atau tambahkan dua pengaturan ini dengan nilai tetap, termasuk saat meneruskan login.

```nginx
proxy_set_header X-Forwarded-Host disastermanagement.online;
include /etc/nginx/private/rn-dms-key.conf;
```

Simpan satu baris `proxy_set_header X-RN-DMS-Proxy-Key "<KUNCI>";` dalam include privat tersebut dan pasang nilai yang sama pada konfigurasi site Frappe `rn_dms_proxy_key`. Buat kunci acak minimal 32 byte, batasi izin berkas, dan gunakan jaringan privat CT202 → RN. Jalankan `nginx -t` sebelum reload. Pastikan CDN melewati cache untuk API DMS dan jangan catat header kunci. Uji header palsu pada jalur publik RN, jalur DMS yang sah, dan kedua mode sebelum membuka data. Browser memilih mode via `rn_tampilan`. Empat akun demo DMS menerima cookie `rn_tampilan=simulasi` setelah login.

## Isi ulang

Salin `assets/data/dms-simulasi.json` dari worktree frontend DMS dan `menu-gabungan.json` dari catatan tim ke jalur yang dapat dibaca bench. Masukkan kata sandi dari berkas CT102 `/root/.rahasia/dms-demo-akun.txt` lewat stdin pada perintah di bawah, melalui SSH dan `docker exec -i` bila bench berjalan dalam kontainer. Berkas berisi objek JSON dengan empat email demo dan harus berizin 600. Gunakan `/dev/stdin` pada proses bench agar tidak ada salinan kata sandi di mesin backend.

```sh
bench --site <site-RN> execute rescue_net.dms_sim.seed.run \
  --kwargs '{"map_path":"/tmp/dms-map.json","menu_path":"/tmp/menu-gabungan.json","credentials_path":"/dev/stdin"}'
```

Bahas backup dan persetujuan rilis sebelum menjalankan pada site produksi. Seed membuat tiga kejadian, 24 posko, 37 kebutuhan kritis, empat rute terhambat, data layanan dan catatan per menu. Rencana pengungsian berjumlah 48.250 jiwa. Peta sumber menandai tujuh posko kritis, sedangkan ringkasan skenario menyebut enam. Seed memakai status tiap titik dari peta. SITREP RN membaca data operasional berdasarkan horizon waktu dan rekap korban skenario tetap tercatat di payload kejadian. Entri SAR dan medis merupakan sampel, sehingga jumlah barisnya lebih kecil dari total dampak.

`menu_path` boleh dihilangkan untuk menyiapkan data dasar, atau menunjuk gabungan kelompok yang sudah divalidasi. Isinya objek dengan `menu_id` sebagai kunci dan daftar `records` berisi isian katalog. Baris `rows` dipakai frontend. Seed memakai tautan kejadian eksplisit jika disediakan, lalu kode kejadian yang tertulis di isian. Catatan tanpa kode memakai kejadian utama Palu. Rerun menambah entri baru dan mempertahankan entri lama beserta kata sandi yang sudah terpasang. Perubahan isi catatan dianggap entri tambahan. Penghapusan atau pengarsipan revisi lama dilakukan secara terpisah.

## Rollback data

Matikan akses di proxy DMS dan ambil backup. Untuk masing-masing `SIM-DMS-01`, `SIM-DMS-02`, dan `SIM-DMS-03`, tinjau daftar DocType dan nama sebelum menjalankan penghapusan dengan total yang sama.

```sh
bench --site <site-RN> execute rescue_net.dms_sim.rollback.preview \
  --kwargs '{"event":"SIM-DMS-01"}'
bench --site <site-RN> execute rescue_net.dms_sim.rollback.run \
  --kwargs '{"event":"SIM-DMS-01","confirm_total":<total-pratinjau>}'
```

Rollback memverifikasi ID, lingkup, flag latihan, serta sumber seed. Catatan audit dan keuangan terkait menghentikan penghapusan. Nonaktifkan empat akun demo melalui pengelolaan User bila seluruh simulasi ditarik. Organisasi dan keanggotaan demo dapat digunakan lagi saat seed berikutnya.
