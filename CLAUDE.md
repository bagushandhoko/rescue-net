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

Perbarui bagian ini di akhir setiap sesi kerja. (Terakhir: 2026-10-08 sore.)

- **Selesai (belum deploy):** "pelapor terverifikasi" (owner 2026-10-01) — role `verified_reporter`, hanya menambah
  Kebutuhan di posko mana pun (label pelapor + "belum dikonfirmasi" sampai posko konfirmasi/tolak; batas 30/jam;
  `services/reporter.py`, `tests/test_verified_reporter.py`); 214 test lulus. **Perlu `bench migrate` + `rn-deploy-app.sh`**
  (field baru RN User Account + RN Logistic Need). Architecture review Fase 6 menunggu review owner.
- **Mock-up pass 2 SELESAI untuk semua file di `assets/img/mockup/` (2026-10-07; rincian per halaman: HANDOVER.md "Mock-up pass 2").**
  Frontend langsung live. Backend baru: Search & Found + Program Khusus **ter-deploy**; Verification & Approval (RN Approval Log, risk) dan
  Organisasi & Posko (counts/resources/trust) **belum deploy** → `sh scripts/rn-deploy-app.sh` dari `/volume1/web/rescue-net` (>120 dtk, jalankan dengan `!`),
  plus Distribusi (% kapasitas) dan Alat Kerja (BBM per posko) dari pass sebelumnya. Belum dicoba dengan login nyata: tombol operator Search & Found,
  Rencana Kerja Program Khusus. Celah tercatat: foto posko (Registrasi), KPI "dari kemarin" (butuh riwayat harian), "Merge" (sengaja tidak dibuat).
  Gotcha CSS: `.rn-ev-page` = tombol pager (halaman Evidence pakai `rn-evc-page`); aturan mobile site-wide membuat input/label lebar penuh. 234 test lulus.
- **Fase 0 (mulai 2026-10-07, menunggu review owner):** `docs/PHASE0_ENV_SEPARATION.md` — `.claude/settings.json`, `scripts/rn-deploy-from-git.sh`, draf CI `.github/workflows/tests.yml` (belum pernah jalan di GitHub) ada di repo; inti (akun agent tanpa sudo/docker, web root bukan checkout, branch protection) butuh keputusan owner.
- **Fase 7 (owner perintah 2026-10-08):** langkah 1-3 **ter-deploy** (2026-10-08 15:30, 6 probe 200). Langkah 4 (committed, belum deploy; tanpa migrate): AI menempatkan kebutuhan logistik yang tidak dikenali aturan kata kunci (`ai/queue.py::enqueue_unmatched_needs` + `_need_handler`, kunci platform, saran draf `RN AI Suggestion`; posko/Control Centre menerima → `canonical_*` + `normalization_source=ai`). Duplikat + laporan warga sudah ber-AI sejak langkah 2-3. UI: `assets/js/rn-ai-suggestions.js` (panel "Saran AI menunggu keputusan" di Laporan Masyarakat + Posko Logistik) dan label `ai_status` di kartu laporan — frontend langsung live, tombol Terima/Tolak butuh backend langkah 3 (sudah ter-deploy). 280 test lulus. Belum dicoba login nyata: panel saran AI. **Langkah 5: isi belum ditulis di dokumen mana pun — tanya owner.**
- **Fase berikutnya:** menunggu perintah owner (Fase 7 langkah 4; Fase 0 owner-side; Fase 9/10 hanya rencana).
- **Domain publik (owner, 2026-10-08):** `rescue-net.online` (+www), `sac-energi.online` (+www), `portal.sac-energi.online` lewat Cloudflare Tunnel (container `cloudflared`) ke container nginx `rescue-web` (:8182, whitelist file situs di `/rescue-net/` + endpoint `rescue_net.api_*`, login, logout, callback Google; Desk/`/api/resource`/file = 404) dan `sac-web` (:8181); portal SAC :8180. Infra di `/volume1/docker/{rescue-web,sac-web,cloudflared}/` (bukan git). Produksi: `host_name` = `https://rescue-net.online`, `allow_cors` = hanya `https://rescue-net.online`, 12 akun simulasi `enabled=0`. Funnel Tailscale 10000/8443 mati, 443 sengaja tetap (OSIUN, APK lama, `rescue-net-shell`). nginx DSM: `/rescue-net-frappe/` hanya `rescue_net.api_*`/login/logout, Odoo `/web/database/*` = 404 (`install-nginx-blocks.sh`). **OSIUN sengaja tidak disentuh** (akan dimigrasi ke Frappe; rencana osiun.org dibatalkan). Rincian: HANDOVER.md + memori `nas-public-domains`.
- **Menunggu owner (2026-10-08):** (a) tambahkan redirect URI baru + JS origin di Google Cloud (rescue-net client `995503168695-…`, SAC client `821040674461-…`) — sampai itu login Google ditolak `redirect_uri_mismatch`; (b) deploy Fase 7 langkah 3 sudah; coba login nyata di AI Analyst; (c) push sudah (2026-10-08); (d) email DSM "osiun-frappe-backend stopped unexpectedly": penyebab dugaan = `docker restart` saat deploy/reboot + memori NAS ketat (swap 88%, 83 container); perbaikan menunggu data jam email + persetujuan; (e) `demo@demo.example` (demo/demo) masih terbuka; cookie `sid` tanpa flag `Secure`.
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
