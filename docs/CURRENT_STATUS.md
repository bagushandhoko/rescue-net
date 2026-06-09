# Rescue-Net Current Status

Last checkpoint: BYOK AI Analyst workflow and API deduplication.

## Running Environment

- Static web: `/volume1/web/rescue-net`
- Backend source/runtime: `/volume1/docker/rescue-net-api`
- API container: `rescue-net-api`
- API port: `8092`
- PostgreSQL container: `postgres-main`
- Database: `rescuenet_db`
- Main prototype event: `event-aceh-2025`

## Implemented Modules

### Core
- Active disaster data
- Organization and posko registry
- Ecosystem member consolidation
- Resource sharing
- Resource request / assignment
- Offline sync pull/push foundation
- Sync Console UI

### Logistics / Posko
- Posko Detail
- Stock movement
- Incoming aid verification
- Duplicate receiving protection
- Stock transfer between poskos
- Stock summary by posko

### Dapur Umum
- Kitchen context
- Meal production
- Ingredient stock deduction
- Kitchen UI

### Posko Medis
- Medical context
- Medical cases
- Medical supply usage
- Medical stock deduction
- Medical UI

### Shelter
- Shelter context
- Occupancy records
- Shelter needs
- Shelter UI

### Search & Found
- Missing person reports
- Found person reports
- Manual match
- Reunited / investigating / rejected status
- Search & Found UI

### AI
- Integrated `/ai/context/{disaster_event_id}`
- AI Context includes logistics, stock, kitchen, medical, shelter, search & found
- Encrypted BYOK user AI key storage
- `/ai/user-key`
- `/ai/user-model`
- `/ai/ask`
- AI Settings UI
- AI Analyst UI
- API duplicate routes cleaned

## Important Security Rules

- API keys must never be committed to GitHub.
- `.env` must not be committed.
- User AI keys are stored encrypted in `ai_user_settings`.
- API key is never returned to browser.
- UI only shows masked key like `****1234`.
- `AI_KEY_ENCRYPTION_SECRET` exists only in runtime `.env`.

## Current Known Notes

- User demo key is dummy and returns invalid API key from OpenAI.
- Real AI answer requires entering a real key in AI Settings UI.
- The encryption secret used in prototype was shown during development; rotate it before production.
- `main.py` grew large because prototype endpoints were appended quickly. Future refactor should split routes by module.

## Next Recommended Work

1. Refactor backend into module files:
   - `routes_ai.py`
   - `routes_posko.py`
   - `routes_logistics.py`
   - `routes_kitchen.py`
   - `routes_medical.py`
   - `routes_shelter.py`
   - `routes_search_found.py`
   - `routes_sync.py`
2. Add role-based auth.
3. Add production-grade migration runner.
4. Add test seed script.
5. Add UI sidebar shared template.
6. Add AI organization-key fallback after user-key.
7. Add audit logs for AI ask events without storing secret.
8. Add deployment README.

## Backend Refactor Started

Backend route-module structure prepared:

- backend/main.py
- backend/app_shared.py
- backend/routes/__init__.py
- backend/routes/ai_routes.py

Current status:
- Runtime endpoints still live in main.py.
- routes/ai_routes.py is currently a placeholder.
- Next planned refactor is to move AI routes from main.py into routes/ai_routes.py.

AI endpoints to move later:
- GET /ai/context/{disaster_event_id}
- POST /ai/user-key
- GET /ai/user-key/{user_id}
- POST /ai/user-model
- DELETE /ai/user-key/{user_id}
- POST /ai/ask

Refactor rule:
- Move one route group at a time.
- Run python3 -m py_compile main.py.
- Rebuild Docker.
- Verify /health, /openapi.json, /ai/context, /ai/user-key, and /ai/ask.

## Latest Prototype Modules Added

The following modules have been added after the previous checkpoint:

### Contact Directory / Notification Foundation

- New live page: `pages/contact-directory.html`
- New JS: `assets/js/contact-directory.js`
- Reads operational contacts from:
  - posko officer in charge
  - distribution officer in charge
  - aid donor contact
  - volunteer contact
  - donor program PIC
- Supports:
  - Call button
  - WhatsApp button
  - phone normalization for Indonesian numbers

### Frontend Role-Aware Session Controls

- New shared JS: `assets/js/session-role.js`
- Reads `RN_USER` and `RN_SESSION_TOKEN` from localStorage.
- Displays current user and role in page header.
- Supports frontend-only visibility rules for actions:
  - verify
  - upload evidence
  - create donor program
  - create work tool
  - create volunteer assignment
  - AI ask

Important note:
This is frontend role-awareness only. Backend role enforcement is still required before production.

### Map / Geospatial Foundation

- New live page: `pages/map.html`
- New JS: `assets/js/map.js`
- New migration: `013_map_geospatial_foundation.sql`
- API:
  - `GET /map-context/{disaster_event_id}`
  - `POST /map-points`
- Supports:
  - custom map points
  - posko location candidates
  - work tool locations
  - missing/found locations
  - Google Maps and OpenStreetMap links

### Auth & Role Foundation

- New live page: `pages/auth.html`
- New JS: `assets/js/auth.js`
- New migration: `012_auth_role_foundation.sql`
- API:
  - `GET /auth/roles`
  - `POST /auth/demo-login`
  - `GET /auth/me/{session_token}`
- Current roles:
  - command_center
  - posko_operator
  - medical_operator
  - shelter_operator
  - donor
  - volunteer
  - viewer

### Donor Program / Transparency

- New live page: `pages/donor-program.html`
- New JS: `assets/js/donor-program.js`
- New migration: `011_donor_program_transparency.sql`
- API:
  - `GET /donor-program-context/{disaster_event_id}`
  - `POST /donor-programs`
  - `POST /donor-program-updates`

### Evidence

- New live page: `pages/evidence.html`
- New JS: `assets/js/evidence.js`
- Uses existing:
  - `GET /evidence`
  - `POST /evidence/upload`

### Verification Approval

- New live page: `pages/verification-approval.html`
- New JS: `assets/js/verification-approval.js`
- New migration: `010_verification_approval_module.sql`
- API:
  - `GET /verification-context/{disaster_event_id}`
  - `POST /verification-actions`

## Current Remaining Production Gaps

Rescue-Net prototype is broad and working, but not production-ready yet.

Remaining major gaps:

1. Backend role enforcement middleware.
2. Real login/password/OAuth/JWT.
3. Audit logs for sensitive actions.
4. Leaflet visual map.
5. Shared sidebar/header template to remove repeated HTML.
6. Backend refactor from large `main.py` into route modules.
7. Migration runner and seed script.
8. Production backup/restore procedure.
9. Sensitive data permission for medical and search-found.
10. Federation conflict resolution.
