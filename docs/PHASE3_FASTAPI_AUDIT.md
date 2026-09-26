# Phase 3 — FastAPI retirement audit (2026-09-26)

Architecture-review phase 3, step 1: what is still served by FastAPI, what is fully in Frappe, and which
clients still call FastAPI. **Nothing has been switched off or deleted.** The owner picks the cutover date
(step 2); only then are the remaining pieces moved and the legacy removed (steps 3–5).

Everything below was checked on the server on 2026-09-26 (container state, database contents, `grep` of
every client), not taken from older notes.

## 1. Runtime state today

| Piece | State | Checked how |
|---|---|---|
| FastAPI container `rescue-net-api` | **Exited 4 weeks ago** (restart policy `no`) | `docker ps -a` |
| PostgreSQL `rescuenet_db` (in container `postgres-main`, 12 MB) | Running, role `rescuenet_user` has `default_transaction_read_only=on` | `pg_roles.rolconfig` |
| Final legacy dump | `_archive/post-cutover/rescuenet-legacy-final.dump` (219 KB, 2026-08-25) — on the server inside the repo folder, **not committed** (only the `.sha256` is tracked) | `git ls-files` |
| Reverse proxy `/rescue-net-api` | **still configured**: `/usr/local/etc/nginx/conf.d/www.rescue-net-api-proxy.conf` → `127.0.0.1:8092`; answers **502** because the container is stopped | `curl /rescue-net-api/health` → 502 |

So FastAPI already serves **nothing**: every call to it fails today.

## 2. Clients that still point at FastAPI

| Client | Calls FastAPI? | Detail |
|---|---|---|
| Web frontend (`index.html`, `pages/*.html`, `assets/js/*.js`) | **No** — 0 references to `rescue-net-api`, `:8092`, `RN_API_BASE` | all 155 API paths go to `rescue_net.api_*` in Frappe |
| Web → Frappe compatibility adapter `rescue_net/compat/api.py` | Frappe, not FastAPI | only `compat.api.disasters` is still called (`assets/js/api.js`, `assets/js/disaster-detail.js`); its other 9 functions (`health`, `status`, `organizations`, `poskos`, `logistic_needs`, `aid_offers`, `distribution_flows`, `war_room`, `all_p0`) have no caller |
| **Offline app** (`/volume1/web/rescue-net-app/`, source copy in `apps/rescue-net-app/`; APK / Windows / Linux / iOS builds offered on the site's **Download** menu) | **Yes — only FastAPI** (`${origin}/rescue-net-api`, else `:8092`) | 14 endpoints, table 3. **Broken for every user since FastAPI stopped.** |

## 3. Offline app endpoints → Frappe

| App call (FastAPI) | Frappe equivalent | Status |
|---|---|---|
| `GET /health` | `rescue_net.compat.api.health` / `/api/method/ping` | exists |
| `GET /disasters` | `rescue_net.compat.api.disasters` (the web uses this) | exists |
| `GET /organizations` | `rescue_net.api_community_cluster.list_organizations` | exists |
| `GET /admin-areas/children` | `rescue_net.api_frontend_bridge.admin_area_children` | exists |
| `POST /public/community-reports` | `rescue_net.api_frontend_bridge.submit_community_report_bridge` | exists — **now needs a login** (owner rule 2026-09-26) |
| `POST /sync/push` | `rescue_net.api_sync.push` (the web's offline queue uses it) | exists, needs a login |
| `POST /device-registrations` | none (DocType `RN Device` exists, 0 rows in both databases) | **missing** |
| `GET /central-data/status` | `rescue_net.compat.api.status` is the closest | partial |
| `GET /consolidated-needs`, `POST /consolidated-needs/rebuild` | `rescue_net.api_intelligence.consolidated_need_snapshots`, `rebuild_consolidated_needs` | exists |
| `GET /data-consolidation/raw-reports` | `rescue_net.api_frontend_bridge.consolidation_raw_reports` | exists |
| `POST /duplicates/check` | `rescue_net.api_frontend_bridge.duplicates_check` | exists |
| `GET /unit-catalog`, `POST /unit-normalize` | `rescue_net.intelligence.normalization` (Python only, no whitelisted endpoint) | **missing endpoint** |

The app also sends FastAPI-style JSON and a bearer token; Frappe needs its own session/CSRF or API-key
login. Moving the app to Frappe is therefore a real (small) piece of work, not a URL change.

## 4. FastAPI features (148 routes in `backend/`, 8,764 lines) vs Frappe

| Route families | In Frappe | Legacy data |
|---|---|---|
| auth, disasters, organizations, poskos, logistic-needs, aid-offers (+public), transport-spaces, distribution-flows, stock (movements → Stock Observation model), evidence, map-context/points, community-reports, verification (requests, actions, endorsements, verifier profiles), kitchen, medical, shelter, search & found, volunteers, work tools, resources / requests / shares / assignments / ecosystem, donor & special programs, recovery projects, AI (BYOK), admin areas, geo, sync / sync-conflicts, consolidation / duplicates / consolidated needs, unit conversion | **yes** (`rescue_net.api_*`) | imported P0–P3 in August, reconciliation 0 invalid (handover 2026-08-25) |
| federation (nodes, repositories, manifest, sync logs — 7 routes) | no — it is **Fase 9** of the roadmap (stored, not started) | 0 rows |
| beneficiary-groups, command-corrections, operational-areas, central-data, audit-events, device-registrations, legacy-volunteers, unit-review | no dedicated endpoint (Frappe has its own audit trail / version log; command features are `api_command`) | 0 rows each, except `audit_events` (14 rows — pre-cutover system events) |

Legacy row counts today: `disaster_events` 5, `posko_nodes` 10, `logistic_needs` 6, `user_accounts` 7,
`audit_events` 14; every other table 0. Nothing in PostgreSQL is newer than the Frappe copy — the database
has been read-only for the application user since the cutover.

## 5. What remains to retire FastAPI (after the owner's go)

1. **Offline app** — decide: (a) move it to Frappe (login + the two missing endpoints: device registration,
   unit catalogue/normalise), rebuild the downloads; or (b) withdraw the Download menu until an app is
   rebuilt on the web's offline queue (`rn-sync-engine.js` already does offline reporting against Frappe).
2. Final PostgreSQL backup to a server folder outside the repo (e.g. `/volume1/docker/osiun-backups/`), keep
   the August dump next to it, then drop `rescuenet_db` and the `rescuenet_user` role (other databases in
   `postgres-main` are not Rescue-Net and stay).
3. Tag the last commit that contains the legacy code as `fastapi-final`, then remove from `main`:
   `backend/`, `database/` (PostgreSQL migrations), the unused 9 functions of `compat/api.py` (keep
   `disasters`, or move it into `api_control_centre` and update the 2 JS files), `migration/*_from_rescuenet_pg.py`
   importers once the owner no longer wants a re-import path.
4. Remove the nginx route `www.rescue-net-api-proxy.conf` (needs root on DSM), the stopped container `rescue-net-api` and its image; the separate repo
   `github.com/bagushandhoko/rescue-net-api` can be archived on GitHub.
5. Rewrite `FRAPPE_MIGRATION_MAP.md` to "selesai" (it still says FastAPI/PostgreSQL "remains the operational
   source of truth", which has not been true since 2026-08-25).

## 6. Questions for the owner

1. Cutover date for removing FastAPI + PostgreSQL (nothing depends on them for the web today)?
2. Offline app: move it to Frappe (a) or withdraw the downloads for now (b)?
3. Keep the `migration/` importers (re-import path from the August dump) or remove them with `backend/`?
