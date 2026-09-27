# Frappe migration — status: SELESAI

The move from the FastAPI + PostgreSQL prototype to Frappe + MariaDB is finished.

| Step | Date | Result |
|---|---|---|
| Data import P0–P3 from `rescuenet_db` | Aug 2026 | reconciliation 0 invalid |
| Production cutover to Frappe | 2026-08-25 | Frappe is the system of record; FastAPI stopped, PostgreSQL read-only |
| Web frontend on Frappe only | 2026-08-29 | 0 FastAPI calls |
| Offline app on Frappe | 2026-09-26 | `apps/rescue-net-app` router → `rescue_net.*` methods |
| FastAPI + PostgreSQL removed | 2026-09-26 | code in git tag `fastapi-final`; final DB dump in `/volume1/docker/osiun-backups/rescue-net-legacy/` |

Audit behind the removal: `docs/PHASE3_FASTAPI_AUDIT.md`. The per-table mapping that used to live here is
in the `fastapi-final` tag (`git show fastapi-final:FRAPPE_MIGRATION_MAP.md`).
