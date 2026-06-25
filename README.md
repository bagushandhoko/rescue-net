# Rescue-Net

Rescue-Net is an open-source Disaster Management System for coordinating disaster response across command centers, field posts, organizations, volunteers, donors, logistics, medical posts, shelters, search/found teams, evidence reviewers, and recovery programs.

## Live URLs

- Local web: `http://192.168.100.32/rescue-net/`
- Deployment web aktif: gunakan domain yang terpasang di server produksi.
- War Room: `/rescue-net/pages/war-room.html?event=event-sim-001`
- Mock-up viewer: `/rescue-net/pages/mockup.html?screen=welcome`
- API health: `http://127.0.0.1:8092/health`

## Purpose

Rescue-Net connects active disaster events, verified organizations, posko/field posts, logistics needs, aid offers, distribution flows, resource profiles, work tools, volunteers, shelters, medical posts, public kitchens, search/found cases, evidence, verification, donor programs, recovery projects, and AI-assisted situation analysis.

The prototype is designed for fast field operation first: small functional changes, quick smoke tests, then commits.

## Current Runtime

- Project path: `/volume1/web/rescue-net`
- Runtime API path: `/volume1/docker/rescue-net-api`
- API port: `8092`
- Database container: `postgres-main`
- Database name: `rescuenet_db`
- Branch: `main`

## Repository Source Layout

- Website: repository root (`index.html`, `pages/`, `assets/`)
- FastAPI backend: `backend/`
- Offline-first Web/PWA/Android/iOS/Desktop source: `apps/rescue-net-app/`
- Database migrations: `database/migrations/`
- Current operational handoff: `docs/HANDOFF_LATEST_RN.txt`

Runtime deployment paths are separate copies on Synology. After a live hotfix,
always synchronize the final backend/app source back into the repository.

Run quick checks on the Synology host:

```sh
curl -fsS http://127.0.0.1:8092/health
curl -fsS http://127.0.0.1:8092/ai/context/event-sim-001 | python3 -m json.tool
sh scripts/rn-smoke-test.sh
```

Run a short operational UAT with simulation data:

```sh
sh scripts/rn-uat-kilat.sh
```

This checks demo login, AI context summary, Resource Profile, Recovery, core pages, sync push/pull, audit endpoint, and sync conflict endpoint. It creates one simulated `resource_request` sync event each time it runs.

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

## Backend Routes To Guard

These route groups are expected to stay registered in OpenAPI:

- `/health`
- `/ai/context/{event_id}`
- `/resource-profiles`
- `/recovery-projects`
- `/recovery-project-updates`
- `/audit-events`
- `/sync-conflicts`
- `/sync-conflicts/{conflict_id}/resolve`

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

GitHub push may require the existing owner token/script on the Synology host. Do not push until the secret scan is clean.

```sh
git status --short
sh scripts/rn-smoke-test.sh
# run secret scan from the Safety Rules section
git add <changed-files>
git commit -m "Describe the Rescue-Net update"
./rn-push-main.sh
git fetch origin
git log --oneline origin/main..HEAD
```

After a successful push, `git log --oneline origin/main..HEAD` should be empty.

## Continuation Notes

- Do not audit from zero unless the owner asks for a full audit.
- Do not reintroduce global zoom/scale hacks.
- Do not reintroduce `rnLayoutDebugBadge`.
- Do not add 10-second polling sync; keep sync event-driven.
- Keep layout/color changes small until core functions are stable.
- Current handoff: `docs/HANDOFF_LATEST_RN.txt`
- Full blueprint: `docs/BLUEPRINT.md`
- Current status: `docs/CURRENT_STATUS.md`
- Do not modify unrelated systems on the same server while working on Rescue-Net unless explicitly requested.
