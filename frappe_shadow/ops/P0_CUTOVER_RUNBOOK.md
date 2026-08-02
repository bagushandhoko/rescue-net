# Rescue-Net P0 Frappe Cutover Runbook

Status: draft gate, shadow-only. This runbook does not authorize cutover by itself.

## Scope

P0 includes disaster events, organizations, poskos, logistic needs, aid offers, distribution flows, and war-room snapshot/status.

Out of scope for this P0 gate: full volunteer workflows, evidence uploads, medical/shelter modules, donor programs, public write forms, federation sync, and UI redesign.

## Preconditions

- Existing Rescue-Net web and API are healthy.
- Frappe shadow is reachable on port 8095.
- `rescue_net` app is mounted persistently in backend, worker, and scheduler containers.
- Migration status returns `ready-for-next-shadow-step`.
- Compatibility API returns `shadow-only` and `cutover_allowed: false`.
- Latest code is pushed to GitHub.

## Dry-Run Gate

Run:

```bash
/volume1/docker/osiun-frappe-shadow/ops/p0-cutover-gate.sh
```

Expected result:

```text
P0 CUTOVER GATE PASS shadow-only dry-run
```


## Backup Pack

Run this before final sync or cutover rehearsal:

`ash
/volume1/docker/osiun-frappe-shadow/ops/pre-cutover-backup.sh
`

It creates PostgreSQL and Frappe MariaDB backups under /volume1/web/rescue-net/_archive/frappe-p0-precutover/<timestamp>/, plus SHA256SUMS and MANIFEST.txt.

## Manual Cutover Window

Do not start this section without explicit owner approval.

1. Announce short freeze window for P0 data writes.
2. Backup PostgreSQL source database.
3. Backup Frappe MariaDB shadow site.
4. Run final `import_live` from PostgreSQL into Frappe.
5. Run Link backfill.
6. Rebuild War Room snapshot.
7. Run smoke test and P0 cutover gate.
8. Confirm rollback path and backup file locations.
9. Only then decide whether to reroute P0 read traffic or keep shadow active.

## Rollback Principle

Existing Rescue-Net remains the source of truth until an explicit cutover command is approved and executed. If any gate fails, keep production routing unchanged and continue on shadow.
