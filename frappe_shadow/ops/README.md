# Frappe runtime ops

`docker-compose.shadow.yml` mirrors the runtime configuration of the production Frappe stack in
`/volume1/docker/osiun-frappe-shadow` (MariaDB, Redis, backend, workers, scheduler, socketio). The name
"shadow" is historical: since the 2026-08-25 cutover this stack is production and the only backend.

Deploy app changes with `sh scripts/rn-deploy-app.sh`; tests run on the isolated stack
(`sh scripts/rn-test-stack.sh test`). The retired FastAPI cutover scripts (P0 gate, readiness report,
final-sync rehearsal, smoke tests against FastAPI) were removed in phase 3 — see the `fastapi-final` tag.
