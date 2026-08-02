# Frappe Shadow Status

Date: 2026-08-02

## Current State

- Existing Rescue-Net web/API remains unchanged and live.
- Shadow Frappe runs separately on port 8095.
- Frappe shadow was repaired by removing broken osiun_core from active apps.txt/apps.json.
- App rescue_net was scaffolded and installed into the shadow site osiun.localhost.
- P0 DocType skeletons were created for the staged migration.

## P0 DocType Skeletons

- RN Disaster Event
- RN Organization
- RN Posko
- RN Logistic Need
- RN Aid Offer
- RN Distribution Flow
- RN War Room Snapshot

## Runtime Notes

The source app is stored under /volume1/docker/osiun-frappe-shadow/apps/rescue_net and mirrored in this repository under frappe_shadow/apps/rescue_net for versioning.

The docker-compose.yml in /volume1/docker/osiun-frappe-shadow has been prepared with a rescue_net app mount. Existing containers were not recreated with compose because this server does not have docker compose available; the app was copied into running backend, worker, and scheduler containers for the first shadow install.

Next persistent hardening step: recreate the Frappe shadow containers using the updated compose file or an equivalent docker run flow so the rescue_net app mount is permanent across container replacement.

## Safety Rule

Do not route production /rescue-net or /rescue-net-api traffic to Frappe yet. This is shadow-only until import, compare, and role validation gates pass.

## Verification 2026-08-02

- Existing RN web: HTTP 200 at /rescue-net/.
- Existing RN API: running at /rescue-net-api/.
- Shadow Frappe: HTTP 200 at port 8095.
- rescue_net app: listed in Frappe site apps.
- P0 DocTypes: reloaded successfully; current shadow counts are 0 rows each before import.
- Import scaffold: rescue_net.migration.import_from_rescuenet_pg exposes shadow_status, compare_doctype_counts, and dry-run import_from_pg placeholder.
