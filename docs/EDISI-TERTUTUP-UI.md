# Edisi Instansi RN — cakupan antarmuka awal

Tanggal: 2026-11-21  
Sumber: PDF `RN-Edisi-Tertutup.pdf` dari Edith (draf diskusi 19 Nov, 4 halaman). PDF membahas arsitektur, keamanan, fitur operasi dan tahapan; tidak berisi mockup antarmuka produk.

## Implementasi tampilan

- `index.html` mengarahkan pengunjung ke dashboard Edisi Instansi; halaman lama disimpan di `index-rn-publik.html`. Manifest PWA juga membuka dashboard.
- `pages/edisi-tertutup.html` adalah dashboard awal yang menautkan ke modul RN yang sudah ada: bencana, Control Centre, Peta Nasional, SITREP RN, distribusi/logistik, relawan, Search & Found, dan AI Analyst.
- `assets/css/rn-edisi-tertutup.css` mengambil warna navy `#1f2933`, terracotta `#b4542a`, krem `#fbf6f1`, dan garis pasir `#e3d5c8` dari palet visual dokumen. Theme dipasang setelah stylesheet tiap halaman agar tampilan umum konsisten tanpa mengubah alur bisnis.
- Navigasi menambah Pusat Komando Instansi; PWA cache v9 memasukkan dashboard dan stylesheet baru.
- Tidak ada KPI/statistik baru atau API palsu. Tautan membuka halaman RN yang sebenarnya. Sebagian modul operasional tanpa pilihan kejadian dapat memakai event simulasi bawaan; pengguna harus memilih konteks bencana sebelum melihat data operasional.

## Pemetaan isi PDF dan status RN

| Kebutuhan pada konsep PDF | Yang tampak di UI awal | Status sebenarnya |
|---|---|---|
| Koordinasi bencana, peta, posko, logistik, relawan, SITREP, analisis | Kartu tautan ke halaman yang sudah ada | Fitur RN tersedia; kesesuaian alur/format instansi belum diaudit |
| Satu codebase RN untuk node instansi | Label konseptual dan navigasi edisi instansi | Installer RN tersedia; profil edisi belum dirilis |
| Node privat dan federasi data pilihan | Diagram node → redaksi/persetujuan → RN publik | Federasi belum aktif; ADR-0006 masih Proposed |
| SSO AD/LDAP/Keycloak, 2FA wajib, perangkat terdaftar | Kartu “Rencana” | Belum diterapkan/diuji untuk edisi instansi |
| Klasifikasi Biasa/Terbatas/Rahasia dan redaksi | Kartu “Rencana” + peringatan data | Belum ditegakkan end-to-end; tema bukan kontrol akses |
| Jejak audit tahan ubah, enkripsi, kepatuhan | Kartu “Rencana” | Jejak Audit RN ada; target keamanan pada PDF belum diverifikasi/tersertifikasi |
| OPORD, BKO, COP berlapis, GPS dan personel/satuan | Kartu “Rencana” | Modul khusus perlu dirancang dan dibangun |
| Integrasi BMKG/InaRISK/Basarnas/SIMBNPB, radio/satelit, AI lokal | Kartu “Rencana” | Belum tersedia sebagai paket edisi instansi |

## Batas deployment

Perubahan ini hanya untuk front end node terpisah. Tidak mengubah backend, permission, SSO, klasifikasi, atau produksi. Paket dapat disiapkan di CT202 ketika berkas final disetujui; CT202 tetap stopped dan tidak menyajikan situs sampai owner mengizinkan aktivasi serta host memiliki RAM memadai.
