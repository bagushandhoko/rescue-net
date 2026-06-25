# Rescue-Net Current Status

Updated: 2026-06-20

## Runtime

- Web repository/live static files: `/volume1/web/rescue-net`
- FastAPI runtime source: `/volume1/docker/rescue-net-api`
- Cross-platform app runtime source: `/volume1/web/rescue-net-app`
- API container: `rescue-net-api`
- API port: `8092`
- PostgreSQL container: `postgres-main`
- Database: `rescuenet_db`
- Public web: use the active production domain configured on the server, path `/rescue-net/`.
- Public API proxy: use the active production domain configured on the server, path `/rescue-net-api`.
- Main simulation event: `event-sim-001`
- GitHub: `https://github.com/bagushandhoko/rescue-net`
- Branch: `main`

The runtime API must be started with:

```sh
--env-file /volume1/docker/rescue-net-api/.env
```

Without the env file, the container falls back to PostgreSQL on localhost and fails startup.

## Source Of Truth

After the 2026-06-20 GitHub synchronization:

- Website source: repository root.
- Backend source: `backend/`.
- Cross-platform app source: `apps/rescue-net-app/`.
- Runtime deployment copies remain in the three Synology paths above.

Do not edit only the runtime copy and leave the repository behind. After a live fix, copy the final source back into the repository before committing.

## Working Features

### Web and operations

- Welcome / Active Disasters
- War Room
- Data Konsolidasi
- Community Reports
- Map and administrative location foundation
- Organizations and poskos
- Logistics and stock movement
- Distribution and transport
- Public kitchen
- Medical post
- Shelter
- Search & Found
- Volunteers
- Work tools
- Resource profiles and requests
- Aid offers and donor programs
- Recovery / reconstruction
- Evidence
- Verification & Approval
- AI Analyst and BYOK settings
- Event-driven sync and conflict queue
- Audit endpoints

### Consolidation

- Raw reports remain separate from operational facts.
- Location is classified as GPS/map/admin-area/manual/aggregate.
- Duplicate candidates exist for needs, community reports, and poskos.
- First-pass consolidation uses MAX instead of SUM when overlap is possible.
- National rollup supports:
  - `minimum`: minimum value per same area; aggregate reports excluded.
  - `optimal`: consolidated detail using MAX per posko/detail.
  - `maximum`: optimal plus aggregate context.
- National values can be traced to area, posko, and raw source IDs.
- Aggregate province/city/district reports are marked as context.
- Command Center can apply manual corrections without overwriting raw data.
- Manual corrections store original value, corrected value, delta, actor, reason, and note.
- War Room identifies how much of a displayed value comes from manual correction.
- Unit normalization preserves unknown local packaging for review instead of unsafe summation.

### Trusted Verifier

Trusted Verifier is implemented end-to-end.

It separates:

- identity verification
- location verification
- organization membership
- report-source verification
- report verification
- consolidated need status

Implemented tables:

- `verifier_profiles`
- `trusted_verification_requests`
- `verification_endorsements`

The table is intentionally named `trusted_verification_requests`; an older unrelated table named `verification_requests` already exists in the database.

Verifier lifecycle:

- `candidate_verifier`
- `community_verifier`
- `organization_verifier`
- `government_verifier`
- `official_verifier`
- `trusted_public_verifier`
- suspended/rejected states

Request flow:

1. Registrant selects an RN verifier, invites a verifier, or continues without one.
2. RN creates a seven-day token.
3. Only the token hash is stored.
4. Verifier approves, requests correction, rejects, or states they do not know the target.
5. Approval creates an endorsement for one explicit scope.
6. Endorsement may be revoked.
7. Identity badge does not verify reports or needs.

UAT completed:

- register verifier
- approve verifier and scopes
- create token request
- approve posko identity
- verify separate badge fields
- revoke endorsement
- remove UAT records

### Cross-platform application

The same offline-first core is used for:

- Web/PWA
- Android via Capacitor
- iOS source project
- Windows portable package
- Linux portable package

Features:

- local registration profile
- offline community reports
- offline evidence photo data
- local sync queue
- event/organization context gate when online
- administrative area tree with local RN source and `wilayah.id` fallback
- GPS capture
- device registration
- Trusted Verifier fields in registration

Service worker cache: `rescue-net-app-v6`.

An already-installed APK contains its bundled assets. Web/PWA updates do not update an old APK. Rebuild/reinstall the APK after app source changes.

## Important Endpoints

Core:

- `GET /health`
- `GET /ai/context/{event_id}`
- `GET /central-data/status`
- `GET /audit-events`
- `GET /sync-conflicts`

Consolidation:

- `GET /data-consolidation/summary`
- `GET /data-consolidation/raw-reports`
- `GET /data-consolidation/national-rollup`
- `GET /data-consolidation/posko-coverage-review`
- `POST /duplicates/check`
- `GET /duplicates/candidates`
- `POST /duplicates/{candidate_id}/resolve`
- `POST /consolidated-needs/rebuild`
- `GET /consolidated-needs`
- `POST /command-corrections`
- `GET /command-corrections`

Trusted Verifier:

- `POST /public/verifier-profiles`
- `GET /verifier-profiles`
- `PATCH /verifier-profiles/{id}/status`
- `POST /public/verification-requests`
- `GET /verification-requests`
- `POST /public/verification-requests/respond?token=...`
- `GET /verification-endorsements`
- `POST /verification-endorsements/{id}/revoke`
- `GET /verification-context/{event_id}`

App registration:

- `POST /device-registrations`
- `GET /admin-areas/children`
- `GET /admin-areas/tree`

## Validation

Run after backend or shared frontend changes:

```sh
cd /volume1/web/rescue-net
sh scripts/rn-smoke-test.sh
```

Expected result:

```text
OK: ALL SMOKE TESTS PASSED
```

Before GitHub push:

```sh
sh scripts/rn-secret-scan.sh
```

The scan must produce no secret finding.

## Known Risks

- `backend/main.py` is large and should be split gradually, one route family at a time.
- CSS contains multiple historical override blocks; do not delete them blindly.
- RBAC middleware exists but production enforcement and real authentication still require hardening.
- Medical and Search & Found data need stricter production privacy policies.
- SMS/email delivery for verifier invitations is not integrated. The API currently returns a secure shareable verification URL.
- Some older database tables are owned by another PostgreSQL role. Do not assume the API user can ALTER every table.
- `volunteer_profiles` was intentionally not altered by Trusted Verifier migration; volunteer endorsements remain in the endorsement table.
- Existing UAT/demo records are present. Avoid treating them as production facts.

## Next Priorities

1. Add real SMS/email delivery for verification URLs.
2. Add rate limits and suspicious verifier scoring.
3. Display identity/location/report/need badges on every relevant profile/detail page.
4. Rebuild Android/iOS/Desktop artifacts from the synchronized app source.
5. Add automated tests for consolidation scenarios and Trusted Verifier.
6. Harden authentication/RBAC.
7. Move schema creation into versioned migrations.
8. Refactor backend route groups incrementally.
