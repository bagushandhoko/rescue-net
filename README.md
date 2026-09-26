# Rescue-Net

Rescue-Net is an open-source Disaster Management System for coordinating disaster response across command centers, field posts, organizations, volunteers, donors, logistics, medical posts, shelters, search/found teams, evidence reviewers, and recovery programs.

## Live URLs

- Public host: `https://osiun.tail251e1e.ts.net/rescue-net/` (Tailscale Funnel)
- Control Centre: `/rescue-net/pages/war-room.html`
- Mock-up viewer: `/rescue-net/pages/mockup.html?screen=welcome`
- API (Frappe): `/rescue-net-frappe/api/method/<rescue_net.api_*.fn>`; health: `/rescue-net-frappe/api/method/frappe.ping`

## Purpose

Rescue-Net connects active disaster events, verified organizations, posko/field posts, logistics needs, aid offers, distribution flows, resource profiles, work tools, volunteers, shelters, medical posts, public kitchens, search/found cases, evidence, verification, donor programs, recovery projects, and AI-assisted situation analysis.

## Current Runtime

- **Backend / system of record: Frappe 15 + MariaDB.** Frappe app `rescue_net`, production site
  `osiun.localhost` in container `osiun-frappe-backend` (compose in `/volume1/docker/osiun-frappe-shadow/`).
- Frontend: static HTML/JS in this repo, served from disk under `/rescue-net/`.
- The former FastAPI + PostgreSQL backend was removed on 2026-09-26 (phase 3). Its code is kept only in the
  git tag `fastapi-final`; the final database backup is on the server in
  `/volume1/docker/osiun-backups/rescue-net-legacy/` (not in git). Frappe is the only backend.
- Branch: `main` (only branch).

## Repository Source Layout

- Frappe app source: `frappe_shadow/apps/rescue_net/rescue_net/` (API modules, DocTypes, tests)
- Website: repository root (`index.html`, `pages/`, `assets/`)
- Offline-first Web/PWA/Android/iOS/Desktop source: `apps/rescue-net-app/` (talks to Frappe; served from
  `/volume1/web/rescue-net-app/` as `/rescue-net-app/`)
- Status + open items: `HANDOVER.md`; working rules and how to run tests: `CLAUDE.md`;
  full history: `docs/history/`

A commit is not a deploy: the production container reads its own copy of the app. See `CLAUDE.md`.

## Tests

Automated tests run on an isolated Frappe test stack (never on production):

```sh
sh scripts/rn-test-stack.sh init   # once
sh scripts/rn-test-stack.sh test
```

## Live Modules

- Active Disasters
- War Room
- Map
- Organisasi & Posko
- Posko Detail
- Logistik
- Distribusi
- Dapur Umum
- Posko Medis
- Shelter
- Search & Found
- Program Khusus
- Donor Program
- Recovery / Reconstruction
- Kirim Bantuan
- Relawan
- Alat Kerja
- Profil Sumber Daya
- Evidence
- Verification
- AI Analyst
- AI Settings
- Sync Console
- Contact Directory

## Mock-up Viewer

The mock-up viewer is separate from the live prototype.

- File: `pages/mockup.html`
- Script: `assets/js/mockup.js`
- Images: `assets/img/mockup/*.png`

Rules:

- Use top header menu only.
- Do not add the live sidebar to mock-up pages.
- Show the full bitmap mock-up image as the design reference.
- Do not show extra title/subtitle/caption over the images.
- Keep Login & Registrasi at the end of the mock-up menu.

Current mapping includes:

- Welcome -> `welcome page rescue-net.png`
- Active Disasters -> `bencana aktif.png`
- War Room -> `war room.png`
- Organisasi & Posko -> `organisasi & posko.png`
- Registrasi & Verifikasi Posko -> `registrasi & verifikasi Posko.png`
- Posko Logistik -> `posko logistik.png`
- Distribusi -> `manajemen distribusi.png`
- Dapur Umum -> `dapur umum.png`
- Shelter -> `shelter & akomodasi.png`
- Search & Found -> `search & found.png`
- Program Khusus -> `program khusus.png`
- Relawan -> `manajemen relawan.png`
- Alat Kerja -> `manajemen alat kerja.png`
- Profil Sumber Daya -> `Profil Sumber Daya.png`
- Evidence Centre -> `evidence centre.png`
- Verification & Approval -> `verification & Approval.png`
- Alat Komunikasi -> `alat komunikasi.png`
- Tampilan HP -> `kompilasi tampilan HP.png`
- Login & Registrasi -> `login & registrasi.png`

To add a mock-up image, upload the PNG into `assets/img/mockup/`, then update the ordered manifest in `assets/js/mockup.js` or rebuild the manifest script if that workflow is being used.

## Safety Rules

Never commit:

- `.env`
- API keys
- database passwords
- database dumps
- uploaded evidence files
- real personal data
- real patient data
- production credentials

Before commit or push, run the secret scan helper:

```sh
sh scripts/rn-secret-scan.sh
```

The target output is empty.

## Push Checklist

Push goes over the SSH deploy key (`remote.origin.pushurl`). Do not push until the tests pass and the secret scan is clean.

```sh
git status --short
sh scripts/rn-test-stack.sh test
sh scripts/rn-secret-scan.sh
git add <changed-files>
git commit -m "Describe the Rescue-Net update"
git push origin main
git log --oneline origin/main..HEAD
```

After a successful push, `git log --oneline origin/main..HEAD` should be empty.

## Continuation Notes

- Do not audit from zero unless the owner asks for a full audit.
- Do not reintroduce global zoom/scale hacks.
- Do not reintroduce `rnLayoutDebugBadge`.
- Do not add 10-second polling sync; keep sync event-driven.
- Keep layout/color changes small until core functions are stable.
- Current status: `HANDOVER.md` (older `docs/HANDOFF*`/`docs/CURRENT_STATUS.md` are historical)
- Full blueprint: `docs/BLUEPRINT.md`
- Do not modify unrelated systems on the same server while working on Rescue-Net unless explicitly requested.
