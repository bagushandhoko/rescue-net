# Rescue-Net Blueprint

**Rescue-Net** adalah open-source **Disaster Management System** untuk koordinasi cepat penanganan bencana, mulai dari warga, relawan, donatur, posko kecil, komunitas, organisasi besar, perusahaan, pemerintah, sampai pengambil keputusan.

Rescue-Net dirancang agar ringan, tidak birokratis, federated, dan dapat dideploy oleh banyak pihak. Setiap komunitas, organisasi, negara, atau posko dapat menjalankan server Rescue-Net sendiri dan nantinya dapat saling terhubung antarserver.

## 1. Prinsip Utama

1. **Fast response** — warga, relawan, donatur personal, dan posko kecil bisa langsung berpartisipasi tanpa proses rumit.
2. **Accountability** — organisasi besar, perusahaan, NGO, kampus, dan pemerintah tetap memiliki registrasi, verifikasi, evidence, audit, dan laporan.
3. **Federated open-source system** — siapa saja bisa deploy server Rescue-Net sendiri dan nantinya antarserver dapat saling terkoneksi.
4. **Data-driven coordination** — semua kebutuhan, bantuan, relawan, transport, evidence, medis, shelter, dan program dapat dilacak.
5. **AI-assisted decision support** — AI membantu membaca data Rescue-Net untuk analisa situasi, prioritas, distribusi, dan briefing keputusan.
6. **Privacy and role-based access** — data sensitif seperti nomor HP, data medis, korban, dan evidence tertentu hanya dapat dilihat sesuai izin.

## 2. Main Modules

### 2.1 Active Disasters

- Membuat disaster event.
- Mengelola status bencana.
- Menggabungkan duplikasi laporan bencana.
- Menjadi induk data posko, organisasi, relawan, bantuan, logistik, distribusi, evidence, medis, shelter, program, dan AI context.

Status: active, monitoring, closed.  
Severity: normal, urgent, critical.

### 2.2 Organization & Posko Registry

- Registrasi organisasi.
- Registrasi posko.
- Posko dapat menginduk ke organisasi atau berdiri sendiri.
- Organisasi dapat memiliki beberapa posko/sub-posko.
- Posko dapat berupa official post, komunitas, warga, dapur umum, gudang, titik distribusi, shelter, posko medis, atau posko komunikasi.

Jenis organisasi: government, NGO, community, corporate, campus, religious organization, medical organization, donor organization, volunteer group.

Jenis posko/node: logistics, kitchen, medical, shelter, warehouse, distribution point, communication post, field command post, collection point.

Verification level: self_reported, community_verified, organization_verified, official_verified.

### 2.3 Volunteer Management

Relawan diperlakukan sebagai resource operasional.

Data relawan:

- nama
- HP
- email
- skill utama
- lokasi
- ketersediaan waktu
- durasi bantuan
- status verifikasi
- organisasi/posko terkait
- kebutuhan konsumsi/akomodasi
- status penugasan

Skill contoh: driver, medis, dapur umum, radio komunikasi, logistik, evakuasi, pencarian orang hilang, data entry, teknisi listrik, PLTS, air bersih, shelter setup, psikososial.

### 2.4 Logistics

- Input kebutuhan posko/lapangan.
- Melihat kebutuhan critical.
- Menghubungkan kebutuhan dengan bantuan tersedia dan transport.
- Melacak stok, barang masuk, dan barang keluar.

Data kebutuhan: disaster event, posko/node, item, quantity, unit, priority, needed_before, status.

Priority: normal, urgent, critical.

Roadmap: estimasi stok habis, kebutuhan berbasis jumlah pengungsi, QR/barcode barang, transfer antarposko, matching otomatis dengan aid offers dan transport.

### 2.5 Donor Flow

Rescue-Net menggunakan dua jalur donatur.

#### Donatur Cepat / Personal Guest

Tidak perlu registrasi.

Flow:

1. Pilih bencana.
2. Isi nama.
3. Isi HP/WhatsApp.
4. Isi jenis bantuan.
5. Isi jumlah dan satuan.
6. Pilih cara pengiriman.
7. Submit.
8. Sistem menampilkan Aid ID dan Kode Edit.
9. Donatur dapat mengedit bantuan memakai HP + Aid ID + Kode Edit.

Delivery mode:

- need_pickup
- self_deliver_to_posko
- drop_to_collection_point

Kode edit ditampilkan di layar untuk prototype. Nanti bisa dikirim via SMS, email, WhatsApp API, atau operator manual. Database hanya menyimpan hash, bukan kode asli.

#### Donatur Terdaftar / Organization Donor

Perlu registrasi dan verifikasi.

Cocok untuk perusahaan, yayasan, NGO, kampus, donor besar, donor rutin, organisasi keagamaan, dan organisasi profesi.

Fitur: dashboard donor, multi PIC, batch bantuan, jadwal pengiriman, dokumen dan evidence, laporan penerimaan, laporan penggunaan dana/barang, audit trail, program donasi, dan program khusus.

### 2.6 Distribution Management

- Menghubungkan bantuan, kebutuhan, transport, relawan, dan posko tujuan.
- Memantau barang dari donor sampai posko.
- Melihat bantuan need pickup.
- Melihat bantuan self delivery.
- Mengelola transport space.
- Membuat distribution flow.

Status distribusi: need_pickup, self_delivery_planned, drop_to_collection_point, assigned_pickup, in_transit, arrived_at_posko, received_verified, cancelled.

### 2.7 Transport Space

Penyedia transport dapat menginformasikan kapasitas angkut.

Data: provider name, transport type, route origin, route destination, capacity weight kg, capacity volume m3, departure time, ETA, status.

Jenis transport: darat, laut, udara, pickup, truk, kapal, pesawat, motor, perahu, ambulans, drone.

### 2.8 Medical Post

- data posko medis
- kapasitas layanan
- kebutuhan obat
- tenaga medis
- ambulans
- rujukan
- evidence medis terbatas

Data pasien tidak boleh publik. Data medis hanya untuk role berizin.

### 2.9 Dapur Umum

- data dapur umum
- kapasitas masak per hari
- kebutuhan bahan makanan
- jadwal distribusi makanan
- relawan dapur
- kebutuhan gas, air, alat masak
- link ke shelter/posko penerima

### 2.10 Shelter / Temporary Accommodation

- data shelter
- kapasitas orang
- jumlah penghuni
- air bersih
- toilet
- listrik
- keamanan
- kebutuhan keluarga
- akomodasi relawan

### 2.11 Work Tools / Alat Kerja

- pendataan alat kerja
- peminjaman alat
- dukungan program khusus
- status penggunaan
- bukti penggunaan

Contoh: genset, pompa air, chainsaw, PLTS portable, alat komunikasi, alat evakuasi, alat berat, peralatan dapur, peralatan medis.

### 2.12 Communication Equipment

Alat komunikasi menjadi objek sistem.

Contoh: HT, repeater, satphone, Starlink, router, power supply, antenna.

### 2.13 Search & Found

Modul untuk orang hilang, orang ditemukan, korban ditemukan, aset hilang, aset ditemukan, hewan peliharaan hilang, dan hewan ditemukan.

Kategori: missing_person, found_person, deceased_found, lost_asset, found_asset, lost_pet, found_pet.

Data korban sangat sensitif, display publik harus terbatas, dan verifikasi harus ketat.

### 2.14 Evidence & Verification

Evidence dipakai untuk bukti bantuan, bukti penerimaan, bukti posko, bukti kondisi lapangan, bukti program, bukti penggunaan dana, verifikasi organisasi, verifikasi relawan, dan verifikasi distribusi.

Evidence dapat terkait ke aid_offer, logistic_need, distribution_flow, posko, organization, volunteer, medical_post, shelter, search_found, program, dan donation.

### 2.15 Program Khusus

Organisasi dapat membuat program kerja spesifik seperti pemasangan PLTS, air bersih, rehabilitasi sekolah, klinik lapangan, dapur umum besar, shelter sementara, distribusi obat, komunikasi darurat, dan pembersihan puing.

Program dapat memakai modul logistic needs, aid offers, transport, volunteers, work tools, evidence, distribution flows, dan donation reporting.

### 2.16 Program Donasi

Untuk penggalangan dana dan pertanggungjawaban.

- organisasi membuat campaign
- donatur dapat memantau penggunaan dana
- pengeluaran dicatat
- bukti transaksi diupload
- laporan penggunaan dana
- verifikasi penggunaan
- link ke program khusus atau kebutuhan bencana

## 3. AI Situation Analyst

Rescue-Net memiliki **Decision Intelligence Layer**.

AI tidak menjadi pengambil keputusan final. AI membantu membaca data dan memberi rekomendasi.

AI dapat membantu:

- ringkasan situasi
- critical needs analysis
- matching bantuan dan kebutuhan
- analisa transport
- prioritas relawan
- briefing command center
- deteksi bottleneck
- deteksi data belum verified
- donor flow analysis

## 4. Bring Your Own Key AI Design

AI key tidak melekat global ke Rescue-Net.

AI key melekat ke:

- user personal
- organisasi terverifikasi

Rescue-Net hanya menjadi orchestrator:

1. cek permission
2. ambil data sesuai hak akses
3. ambil AI key milik user/organisasi
4. kirim konteks ke provider AI
5. tampilkan jawaban dengan sumber
6. simpan usage log tanpa menyimpan secret

Secret key tidak boleh disimpan di frontend, dimasukkan ke GitHub, ditulis di log, atau ditampilkan ke publik.

Suggested tables: ai_provider_keys, ai_usage_logs, ai_queries, ai_answer_sources, ai_briefings, ai_rules.

Suggested endpoints: GET /ai/context/{disaster_event_id}, POST /ai/settings/keys, GET /ai/settings/keys, POST /ai/settings/keys/test, POST /ai/ask, GET /ai/briefing/{disaster_event_id}, GET /ai/alerts/{disaster_event_id}.

AI guardrails:

- bedakan fakta, estimasi, rekomendasi
- tampilkan sumber data
- tandai data belum verified
- jangan buka data medis sensitif tanpa izin
- jangan tampilkan nomor HP penuh ke publik
- keputusan final tetap manusia

## 5. Federated Deployment

Rescue-Net dirancang agar banyak pihak bisa deploy server sendiri.

Tipe server: komunitas, organisasi, pemerintah daerah, NGO, donor besar, posko besar, dan negara lain.

Federasi dapat mendukung disaster event sharing, public needs publishing, aid flow exchange, organization verification, cross-region support, dan cross-country support.

## 6. Technical Architecture

Prototype saat ini:

Static Web Frontend → FastAPI Backend → PostgreSQL → Evidence Upload Storage → AI Context Endpoint

Target arsitektur:

Web / APK / EXE → Rescue-Net API → PostgreSQL → Evidence Storage → AI Orchestration Layer → External or Local AI Provider → Federated Server Gateway

## 7. Current Prototype Status

Sudah mulai dibuat:

- Active Disasters
- Organization & Posko
- Volunteer Management
- Logistics
- Public Donor Aid Submission
- Edit Aid by HP + Edit Code
- Transport Space
- Distribution Flow
- Management Distribusi live dashboard
- AI Situation Analyst page
- AI Settings page
- FastAPI backend
- PostgreSQL database
- Docker deployment
- GitHub repository

## 8. Branching

- main = stable / production / owner updates
- dev = contributor / Codex / testing

Owner can push directly to main. Contributor/Codex should work in dev.

## 9. Security Rules

Do not commit `.env`, API keys, database passwords, database dumps, uploaded evidence files, real personal data, real patient data, or production credentials.

## 10. Roadmap

Phase 1 — Static + Core API: static web prototype, FastAPI backend, PostgreSQL schema, basic CRUD.

Phase 2 — Operational Workflow: donor flow, logistics workflow, distribution matching, volunteer assignment, evidence verification.

Phase 3 — Organization Workflow: user accounts, organization accounts, role-based access, verification approval, donor organization dashboard.

Phase 4 — AI Decision Support: AI context endpoint, AI briefing, AI source citation, BYOK AI provider settings, permission-based AI.

Phase 5 — Federation: multi-server discovery, disaster event sync, cross-organization coordination, cross-country aid support.

Phase 6 — Apps: APK, EXE, offline-first mode, QR/barcode logistics, mobile evidence capture.

## 11. Final Vision

Rescue-Net adalah sistem koordinasi bencana terbuka yang dapat dipakai dari level warga sampai negara. Sistem ini menghubungkan kebutuhan, bantuan, relawan, posko, transport, evidence, program, donasi, dan AI decision support agar penanganan bencana lebih cepat, transparan, dan kolaboratif.

---

# Disaster Ecosystem Consolidation & Offline Sync

## 1. Core Concept

Rescue-Net tidak membatasi bencana berdasarkan area atau organisasi. Satu disaster event menjadi satu **disaster ecosystem** bersama.

Dalam satu disaster event, banyak pihak dapat bergabung:

- pemerintah
- TNI/Polri
- BPBD
- PMI
- NGO
- komunitas relawan
- komunitas transport
- perusahaan donor
- posko warga
- dapur umum
- posko medis
- shelter
- organisasi internasional

Semua pihak tetap memiliki data masing-masing, tetapi data operasional yang relevan dapat dikonsolidasikan untuk koordinasi bersama.

Contoh:

- Transport milik TNI dapat dibagikan sebagai resource dalam disaster ecosystem.
- Komunitas Harley dapat melihat atau meminta akses transport tersebut sesuai permission.
- Command center dapat melihat seluruh kebutuhan, bantuan, transport, bottleneck, dan rekomendasi.
- Data yang aman dapat dikonsolidasikan ke level nasional atau global/federated.

## 2. Ownership vs Access

Setiap data tetap memiliki owner, tetapi bisa dibagikan sesuai scope dan policy.

Contoh data transport TNI:

- `transport_spaces.owner_type = organization`
- `transport_spaces.owner_id = org-tni`
- `visibility_scope = disaster_ecosystem`
- `access_policy = owner_approval_required`

Artinya:

- TNI tetap pemilik transport.
- Transport dapat terlihat dalam ekosistem bencana.
- Organisasi lain dapat request.
- Approval tetap mengikuti policy.
- Semua aktivitas tercatat di audit log.

## 3. Visibility Scope

Level visibility:

- `private`
- `organization`
- `partner`
- `disaster_ecosystem`
- `public`
- `national`
- `federated_global`
- `restricted`
- `medical_restricted`

Contoh:

- Kapasitas transport TNI: `disaster_ecosystem`
- Nomor HP driver: `restricted`
- Ringkasan kebutuhan air: `public` atau `national`
- Data pasien: `medical_restricted`
- Summary kebutuhan internasional: `federated_global`

## 4. Access Policy

Access policy menentukan bagaimana resource dapat digunakan.

- `view_only`
- `request_required`
- `owner_approval_required`
- `command_center_assign`
- `auto_assign`

## 5. Disaster Ecosystem Members

Tabel `disaster_ecosystem_members` menghubungkan banyak aktor dalam satu disaster event.

Member type:

- `organization`
- `posko`
- `community_group`
- `government_unit`
- `international_partner`
- `personal_volunteer_group`
- `donor_organization`

Role in disaster:

- `command`
- `logistics`
- `transport`
- `medical`
- `shelter`
- `kitchen`
- `search_rescue`
- `donor`
- `last_mile_delivery`
- `communication`
- `observer`
- `international_support`

## 6. Shared Resource Model

Resource yang dapat dibagikan:

- `transport`
- `warehouse`
- `volunteer_team`
- `medical_team`
- `kitchen`
- `shelter`
- `equipment`
- `communication`
- `funding`
- `logistics_stock`

Resource tetap memiliki owner, tetapi bisa dishare ke disaster ecosystem.

Flow:

1. Resource owner membuat resource.
2. `resource_shares` menentukan visibility/access.
3. Pihak lain membuat `resource_request`.
4. Owner atau command center approve.
5. `resource_assignment` dibuat.
6. `distribution_flow` dapat dibuat.

## 7. Offline-First Sync

Rescue-Net mendukung HP/laptop/posko yang bekerja offline.

Alur:

1. Device offline.
2. Simpan perubahan di local database.
3. Catat `sync_event`.
4. Saat online, push `sync_event` ke server.
5. Server validasi.
6. Apply ke object.
7. Catat audit log.
8. Jika ada benturan data, masuk `sync_conflicts`.

Local database:

- Android APK: SQLite
- Laptop EXE: SQLite
- PWA Web: IndexedDB
- Server posko/organisasi: PostgreSQL

## 8. Sync Event, Not Raw Table Merge

Rescue-Net tidak merge tabel mentah langsung. Semua perubahan dikirim sebagai event.

Operation:

- `create`
- `update`
- `delete`
- `status_change`
- `verify`
- `attach_evidence`
- `assign`
- `receive`
- `cancel`
- `merge`

Keuntungan:

- bisa audit
- bisa replay
- bisa detect conflict
- bisa konsolidasi bertingkat
- aman untuk offline

## 9. Conflict Resolution

Jika dua pihak mengubah data yang sama secara offline, sistem tidak boleh overwrite sembarangan.

Rule awal:

- verified data menang atas self_reported
- owner data menang atas non-owner
- command center assignment menang untuk operasi resmi
- newer update menang hanya jika role setara
- medical/victim data wajib manual review
- quantity conflict masuk `sync_conflicts`

## 10. National and Global Consolidation

Satu disaster event dapat dikonsolidasikan ke banyak level:

- Local Posko View
- Organization View
- Disaster Event View
- Regional View
- National View
- Federated Global View

Data yang dapat naik ke nasional/global:

- summary kebutuhan
- verified public needs
- total aid available
- distribution bottlenecks
- transport capacity summary
- shelter capacity summary
- medical aggregate
- verified evidence summary

Data yang dibatasi:

- nomor HP penuh
- data pasien
- identitas korban
- alamat detail sensitif
- dokumen pribadi
- evidence restricted

## 11. Required Schema Layer

Tabel operasional tetap dipakai, tetapi ditambah field standar:

- `owner_type`
- `owner_id`
- `visibility_scope`
- `access_policy`
- `source_server_id`
- `source_device_id`
- `source_organization_id`
- `source_posko_id`
- `created_by_user_id`
- `updated_by_user_id`
- `version`
- `sync_status`
- `deleted_at`

Tabel baru:

- `servers`
- `devices`
- `disaster_ecosystem_members`
- `resources`
- `resource_shares`
- `resource_requests`
- `resource_assignments`
- `coordination_channels`
- `coordination_messages`
- `sync_events`
- `sync_batches`
- `sync_conflicts`
- `audit_logs`

## 12. AI Integration

AI Situation Analyst harus membaca data sebagai disaster ecosystem, bukan hanya satu organisasi.

Contoh endpoint:

- `GET /ai/context/{disaster_event_id}?scope=disaster_ecosystem`
- `GET /ai/context/{disaster_event_id}?scope=public_verified`
- `GET /ai/context/{disaster_event_id}?scope=national`
- `GET /ai/context/{disaster_event_id}?scope=federated_global`

AI harus menghormati owner, visibility, access policy, verification status, trust level, role permission, dan privacy restriction.
