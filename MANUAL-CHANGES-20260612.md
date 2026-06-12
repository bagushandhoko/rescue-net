# Manual Changes - 2026-06-12

Status terakhir:
- Welcome page mobile sudah dirapikan.
- Title welcome dipindah ke antara logo dan menu 3 garis.
- Menu 3 garis welcome sudah diperbaiki dan normal.
- Halaman internal utama diberi mobile page title pendek di header.
- Title asli di topbar disembunyikan pada mobile agar tidak double.
- Menu kecil horizontal: War Room diletakkan setelah Active Disasters.
- Perubahan global yang sempat merusak layout sudah direstore.

Catatan penting:
- Jangan apply patch global ke semua halaman tanpa cek struktur HTML.
- Welcome page memakai struktur berbeda dari halaman internal.
- laporan-masyarakat.html dan mockup.html punya struktur khusus.
- Hindari trial-error CSS dengan banyak top per halaman.
- Perlu cleanup CSS karena beberapa patch eksperimen masih menumpuk di assets/css/style.css.
