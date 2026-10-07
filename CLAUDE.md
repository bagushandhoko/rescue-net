# CLAUDE.md — working rules for Rescue-Net

Single source of rules for every agent working in this repo (`AGENTS.md` points here).

## Aturan keselamatan (selalu berlaku)

- **Jangan** menjalankan test, seed, cleanup, atau migrate eksperimen di site produksi (`osiun.localhost`,
  container `osiun-frappe-backend`). Semua itu di test stack terisolasi (lihat "Tests").
- **Jangan** memulai fase berikutnya tanpa perintah eksplisit owner. Berhenti di akhir tiap fase/sub-fase dan tunggu
  review. Rencana yang owner minta "disimpan" bukan perintah untuk dikerjakan.
- **Semua perubahan data oleh AI lewat AI Suggestion** (disetujui manusia) — ADR-0002. AI tidak pernah lebih
  berkuasa dari penggunanya.
- Jangan menaruh secret di repo (repo publik di GitHub); jalankan `sh scripts/rn-secret-scan.sh` sebelum commit.
- Operasi hapus data: tampilkan baris yang akan dihapus dulu; jangan pernah membuat filter dari daftar yang bisa
  kosong (`["in", ids or [""]]` pernah menghapus 5 posko nyata).

## Wajib dibaca

@docs/adr/0001-arsitektur-inti.md
@docs/adr/0002-kebijakan-ai.md
@docs/adr/0003-distribusi-server-klien.md

Sebelum memulai tugas atau fase baru, baca `docs/NEXT_STEPS.md` dan cek fase mana yang sedang aktif.
Detail status, item terbuka, dan gotcha ada di `HANDOVER.md`.

## Status saat ini

Perbarui bagian ini di akhir setiap sesi kerja. (Terakhir: 2026-10-07.)

- **Selesai (belum deploy):** "pelapor terverifikasi" (owner 2026-10-01) — role `verified_reporter`, hanya menambah
  Kebutuhan di posko mana pun (label pelapor + "belum dikonfirmasi" sampai posko konfirmasi/tolak; batas 30/jam;
  `services/reporter.py`, `tests/test_verified_reporter.py`); 214 test lulus. **Perlu `bench migrate` + `rn-deploy-app.sh`**
  (field baru RN User Account + RN Logistic Need). Architecture review Fase 6 menunggu review owner.
- **Search & Found mock-up pass 2 (2026-10-07, selesai, ter-deploy 2026-10-07):** halaman dibangun ulang sesuai mock-up (6 KPI, 4 tab,
  Papan Pencocokan dengan skor %, Reunifikasi Aktif, donut Status Identifikasi, Klaim & Serah Terima, Foto Bukti, Aksi Verifikasi).
  Backend: field `subject_type/age_years/gender` (laporan hilang+ditemukan), `identification_status`, `match_score`, DocType baru
  **RN Search Found Claim**, `services/search_found.py` (skor deterministik, tanpa LLM), endpoint `create_claim`,
  `update_claim_status`, `set_identification_status`; `dashboard` menambah `kpis/board/identification/claims/photos` (nama tidak pernah
  dikirim; foto hanya untuk operator). 222 test lulus. Ter-deploy (`rn-deploy-app.sh`, probe 200, dashboard publik tanpa nama); tombol operator belum dicoba dengan login nyata.
- **Program Khusus mock-up pass 2 (2026-10-07, selesai, ter-deploy 2026-10-07):** detail program sesuai mock-up (hero + Overall Progress, Target & Milestone,
  peta Lokasi, Kebutuhan Program, 4 kartu Support, Progress Lapangan / Evidence / Verifikasi Output; tab "Rencana Kerja" untuk pemilik).
  Model baru: RN Program Milestone / Location / Need + 7 field di RN Donor Program (sampul, mitra, verifikasi output);
  `services/program_plan.py`, `donor_program/plan.py` (`save_plan_item`, `delete_plan_item`, `set_output_verification`); KPI Milestone Terlambat /
  Lokasi Belum Terlayani / Butuh Dukungan memakai baris nyata (program tanpa rencana tetap pakai aturan lama). 228 test lulus.
  Ter-deploy (probe 200, `plan` terkirim); rencana masih kosong sampai pemilik mengisi; tombol edit belum dicoba dengan login nyata.
- **Mock-up pass 2 (perintah owner 2026-09-28, frontend = langsung live):** Dapur Umum, Manajemen Relawan,
  Manajemen Distribusi, Alat Komunikasi, Kebutuhan & Manajemen Alat Kerja (e58d554, tata letak mock-up atas
  pilihan owner) selesai; berikutnya Search & Found, Program Khusus, Evidence, dst. **Perlu `rn-deploy-app.sh`:**
  Distribusi (% kapasitas transport per volume) dan Alat Kerja (BBM Kritis per posko + PIC sesuai
  `posko_contacts_visible`; tanpa deploy, drill BBM tampil tanpa posko).
- **Fase berikutnya:** menunggu perintah owner. Kandidat prioritas: Fase 0 (pisahkan lingkungan agent dari
  produksi). Isi Fase 7–8 belum diberikan owner (Fase 7 wajib mengikuti ADR-0002 bagian 11).
- **Produksi:** ter-deploy sampai Fase 4 (12 modul RN; `rn-deploy-app.sh` 2026-09-27 09:51, patch
  drop_dead_doctypes + drop_old_module_def tercatat di Patch Log, 4 DocType mati hilang, ping 200); fix log key platform (df98b61) ter-deploy 2026-09-27 (`rn-deploy-app.sh`, semua probe 200); frontend Fase 5 sudah live (disajikan dari disk). Aturan nginx deny terpasang 2026-09-27
  (`.git`, docs, `frappe_shadow/`, `scripts/`, `.env`, `*.md` → 404; semua `pages/*.html` + `assets/` → 200).
- **Menunggu keputusan/aksi owner:**
  1. Blok hapus di `docs/PHASE6_REPO_HYGIENE.md` (backup/, scratchpad/, dll. — ditolak izin agent).
  2. Ganti password root MariaDB produksi (ditunda owner 2026-09-27, "nanti aja"); repo GitHub jadi private atau
     tetap publik.
  3. `scripts/komando-tests/` berjalan terhadap produksi — porting ke test stack (usul: Fase 0).
  4. Rebuild APK/desktop dari `apps/rescue-net-shell/`, lalu hapus
     `apps/rescue-net-app/`.
  5. 9g menyebut "lanjutkan dari `apps/rescue-net-app`", bertentangan dengan keputusan Fase 5 (`rescue-net-shell`).
  6. Build APK: wrapper `rescue-net-shell` sudah terpasang di `/volume1/web/rescue-net-build/app` (isi lama di
     `artifacts/app-before-shell-20260927-094134.tgz`). Jalankan satu baris ini:
     `cd /volume1/web/rescue-net-build && sudo sh scripts/rn-build-android-sudo.sh`
     Hapus `apps/rescue-net-app/` setelah langkah 2b `rn-deploy-app.sh` dibereskan.

## Layout

- Frappe app (backend, system of record): `frappe_shadow/apps/rescue_net/rescue_net/`
  - `api_*.py` — whitelisted endpoints (input check, permission check, call the service, shape the
    response). The six big ones are split into packages — `control_centre/`, `logistics/`, `ai/`,
    `resource_tools/`, `donor_program/`, `frontend_bridge/` — and `api_<name>.py` is only a compatibility
    layer re-exporting every name, so frontend paths `rescue_net.api_<name>.<fn>` keep working. Add new
    code to the package module of its sub-domain, not to the compat file. No module over ~1,500 lines.
  - `services/` — shared business rules called by controllers and APIs: `guards.py` (`assert_transition`,
    `assert_quantities`, `bypass` for data loads), `stock.py`, `money.py`, `transport.py`, `llm.py`
    (OpenAI / Claude / Gemini), `report_intake.py`, `report_routing.py`, `tool_needs.py`
  - `access_policy.py` (`rn_actor()`, posko/org permission helpers), `visibility.py` (public/summary
    scrubbing), `reference_resolver.py` (event/posko id resolution)
  - `rn_<domain>/doctype/rn_*/` — 74 DocTypes (JSON + controller) in 12 Frappe modules: `RN Core`,
    `RN Command`, `RN Community`, `RN Logistics`, `RN Shelter`, `RN Medical`, `RN Volunteer`, `RN Resources`,
    `RN Donor`, `RN Search Found`, `RN Verification`, `RN Intelligence` (`modules.txt`; grouping in
    `docs/PHASE4_MODULE_PROPOSAL.md`). A new DocType goes into the module of its domain. **Rules that must always hold live in the
    controller** (`validate` / `on_update`, via `services/`), not only in an API function — Desk, imports
    and other endpoints save through the controller too. Every such rule has a test that saves directly
    with `frappe.get_doc(...).save()`.
  - `patches.txt` + `patches/` — one-off data/schema patches run by `bench migrate`
  - `setup/` — idempotent default installers run by `after_install` / `after_migrate`
  - `tests/` — automated tests (see below)
- Frontend: `index.html`, `pages/*.html`, `assets/js/*.js`, `assets/css/*.css` (vanilla JS, served from disk).
  The web root is the git checkout: only `index.html`, `manifest.webmanifest`, `sw.js`, `pages/`, `assets/` are
  public; `ops/nginx/www.rescue-net-static-deny.conf` 404s the rest. A new top-level folder or root file that
  must stay private needs a line there.
- Old offline app `apps/rescue-net-app/` (router onto Frappe, served from `/volume1/web/rescue-net-app/`) is being
  retired: the website is the installable app, native builds wrap it (`apps/rescue-net-shell/`). There is no
  FastAPI any more (git tag `fastapi-final`) — never add a second backend.

## Production — hands off

- Production site: `osiun.localhost` in container `osiun-frappe-backend`.
- A commit is not a deploy. Deploy = `sh scripts/rn-deploy-app.sh` (backup code + DB, copy the git-tracked
  app files, `bench migrate`, restart, probe). Copying files without the migrate is not a partial deploy,
  it is a broken production: the running backend picks up new code at once and fails on missing columns.
  Say explicitly in HANDOVER.md when a change is committed but not deployed.

## Tests (mandatory for every change)

Isolated stack — containers `rescuenet-test-db` (MariaDB 10.6), `rescuenet-test-redis`,
`rescuenet-test-bench` (same `frappe/erpnext:v15` image as production, Frappe 15.113.4) on docker network
`rescuenet-test` (10.78.0.0/24, no published ports). Site `rescuenet-test.localhost` has
`allow_tests: true`; production does NOT and must never get it.

```sh
sh scripts/rn-test-stack.sh init      # once: create the site + install rescue_net (~10 min on the NAS)
sh scripts/rn-test-stack.sh test      # copy the repo's app into the bench and run all rescue_net tests
sh scripts/rn-test-stack.sh test --module rescue_net.tests.test_logistics_chain   # one module
sh scripts/rn-test-stack.sh migrate   # after changing a DocType JSON
sh scripts/rn-test-stack.sh wipe      # throw everything away (then init again)
```

The script copies `frappe_shadow/apps/rescue_net` into the test bench on every run (a bind mount does not
work: Synology ACLs hide the repo from the container's uid 1000), so tests run against the code in git,
not what is deployed.

Rules:
- Run the full suite before every commit that touches `frappe_shadow/`; push to `main` only when it passes.
- A new feature or bug fix comes with a test. Permission/visibility changes need a test that proves the
  wrong role (and Guest) is refused.
- Tests build their own data with `rescue_net/tests/factories.py` — never depend on production/sim records
  (`event-sim-001`, `ld1.demo@…`).
- Test classes use `frappe.tests.utils.FrappeTestCase` (Frappe 15); each test runs in a transaction that is
  rolled back.
- Call endpoints the way the browser does when the check matters: `api_call("rescue_net.api_x.fn", ...)`
  applies Frappe's whitelist / `allow_guest` check for the current `as_user(...)` / `as_guest()` session.
- A confirmed bug the owner has not approved fixing yet gets a test marked `@known_bug("BUG-n")` (reported as
  a skip). When the fix lands the test fails with "looks fixed — remove @known_bug": remove the marker in the
  same commit. Bug ids and descriptions: `HANDOVER.md` → "Known bugs found by the tests".
- New `allow_guest` endpoint → `test_public_endpoints.GUEST_ENDPOINTS` fails until you review what it returns
  to Guest and add it; the Guest sweep then checks it against the sentinel secrets.
- The 12 former production-only Custom Fields are standard DocType fields since DATA-1 (patch `rescue_net.patches.v2026_09.custom_fields_into_doctype`).
  A new field must go into the DocType JSON, never be created by hand in Desk.

Suite (2026-09-26, end of phase 2): 197 tests in `rescue_net/tests/`, ~4 min on an idle NAS (up to 16 min
under load), including `test_sim_kekeringan` (a full drought scenario).

## Conventions

- Commits: small, one logical change each, clear message. Push `git push origin main` (SSH deploy key).
- Refactors must not change user-visible behaviour unless fixing a bug already reported to the owner.
- Frappe 15.113.4: `from frappe.rate_limiter import rate_limit` (no `frappe.rate_limit`).
- UI text is Indonesian; code comments English.
- Frontend: bump the `?v=` cache-buster on a page's `<script>`/`<link>` when changing the file.
- The website is the installable app (PWA): `manifest.webmanifest`, `sw.js`, `assets/js/rn-pwa.js` on every page. A new
  page gets the manifest `<link>` and `rn-pwa.js`; bump `CACHE` in `sw.js` when the precache list changes. Never let
  the service worker cache `/api/method/` answers. Native builds are only a wrapper (`apps/rescue-net-shell/`).
- Frontend helpers live in `assets/js/rn-ui.js` (`window.RNUI`: `esc`, `fmt`, `shortDate`, `fmtTime`, `eventId`,
  `chip`, `kpiCard`, `modal`). Use them in new code instead of another local copy; a page that uses them loads
  `rn-ui.js` before its own script.
- Keep `HANDOVER.md` short and current in the same commit as the work.

## Keputusan Arsitektur

ADR yang berlaku ada di `docs/adr/` dan diimpor di "Wajib dibaca". Jangan mengusulkan perubahan yang bertentangan
dengan ADR tanpa alasan kuat; jika perlu, tulis ADR baru berstatus Proposed dan minta persetujuan owner.

- ADR-0001: Frappe satu-satunya backend, modular monolith, MariaDB, frontend statis headless, AI BYOK suggest/accept.
- ADR-0002: AI tidak lebih berkuasa dari user; perubahan data lewat AI Suggestion; tanpa subsidi (BYOK); fungsi
  dasar selalu aktif, fungsi lanjutan hanya di bencana yang diaktifkan super admin; data sensitif butuh izin admin
  organisasi; ada fallback berbasis aturan saat AI tidak tersedia.
- ADR-0003: server Rescue-Net didistribusikan sebagai image Docker berversi (plus installer dan Rescue-Net Box),
  BUKAN .exe berisi Frappe. Target EXE/APK adalah aplikasi klien.

## Next Steps

Roadmap: `docs/NEXT_STEPS.md`. Fase 9 (federasi, sinkronisasi offline, standar data kemanusiaan P-code/HXL/CAP)
dimulai dengan desain berupa ADR Proposed setelah Fase 8 selesai — jangan dikerjakan sebelum owner memerintahkan;
9f–9g: distribusi server (image Docker, installer, perawatan) dan Rescue-Net Box + aplikasi klien (ADR-0003).
Fase 0 (prioritas, sebelum Fase 1 setelah owner perintahkan): lingkungan kerja agent dipisah dari produksi dan
deploy hanya lewat alur Git yang disetujui owner. Fase 10: backlog fitur baru (peringatan dini BMKG, QR bantuan &
kartu pengungsi, SMS, gudang, status akses, papan kebutuhan publik, mode latihan, check-in relawan) — tiap fitur
mulai dari audit kode + desain singkat yang disetujui owner.
