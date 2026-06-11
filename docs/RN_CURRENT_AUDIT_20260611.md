# Rescue-Net Current Audit

Updated: 2026-06-11

## Verification Status

Backup before this audit exists at:

`/volume1/docker/backup-rescue-net-prod-20260611-143742`

Included:

- `rescue-net-web.tar.gz`
- `rescue-net-api.tar.gz`
- `rescuenet_db.sql`
- `README.txt`

Smoke test status: passing.

Validated by `scripts/rn-smoke-test.sh`:

- API health
- AI context for `event-sim-001`
- Resource Profile endpoint
- Recovery endpoint
- OpenAPI route registration
- JS syntax for War Room, Resource Profile, Recovery, and Mock-up
- Required page existence

## What Already Exists

Rescue-Net is already a working pilot/demo prototype with:

- Static web UI in `/volume1/web/rescue-net`
- FastAPI backend in `/volume1/docker/rescue-net-api`
- PostgreSQL database `rescuenet_db`
- Dockerized API runtime on port `8092`
- GitHub repository at `https://github.com/bagushandhoko/rescue-net`
- Mock-up viewer with all current mock-up images matched
- Event-driven sync foundation instead of continuous 10-second polling
- BYOK AI settings and AI Analyst flow

Live module coverage:

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
- Mock-up Viewer

## Blueprint Alignment

The system already follows the main blueprint direction:

- Open code, controlled operational data
- Self-hosted deployment
- Offline-first field workflow foundation
- Federated sync direction
- Evidence-first accountability
- Role-aware operating model
- Relief, rehabilitation, and reconstruction coverage
- AI-assisted decision support, not AI as final decision maker

## Mock-up / Layout Alignment

The mock-up set is available in `assets/img/mockup/` and is registered in `assets/js/mockup-manifest.js`.

The live UI currently has the same module structure as the mock-ups. In the current phase, do not change the existing color palette yet. Focus first on layout, spacing, hierarchy, mobile behavior, and matching the mock-up screen structure while fixing functional gaps.

Recommended layout direction:

- Keep the dense command-center dashboard structure.
- Keep the current color palette until the owner explicitly approves a visual recolor pass.
- Preserve sidebar + command workspace on desktop.
- Use bottom navigation or compact module launcher on mobile.
- Avoid decorative-heavy pages; operators need fast scanning.
- Keep cards tighter and use color mainly for status, severity, and priority.

## Technical Debt / Unfinished Work

Backend:

- `backend/main.py` is still too large, around 5000 lines.
- Route module extraction has started but is incomplete.
- `backend/routes/ai_routes.py` is still a placeholder.
- Resource/Recovery routes appear duplicated in `backend/main.py`.
- Donor Program and Volunteers also have duplicate route definitions.
- Backend RBAC enforcement is not complete; frontend role-awareness is not enough for production.
- Audit logging is not applied across all create/update/delete actions.
- Evidence is not linked to every operational object yet.
- Some table creation logic is still ad-hoc and should move into migrations.

Offline / Sync:

- Event-driven sync exists.
- Full conflict handling is not complete.
- Object versioning, conflict policies, retry queues, and manual review workflow are still needed.

Security:

- Secrets are kept out of committed source.
