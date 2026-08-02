# Rescue-Net P0 Frappe Readiness Report

Generated at: 2026-08-02T20:46:36+07:00

## Decision State

- Mode: shadow-only
- Cutover allowed: false
- Production reroute: not performed
- Latest Git commit: c4aba61 Add P0 final sync rehearsal

## Health

- Rescue-Net web: HTTP/1.1 200 OK
- Rescue-Net API: {"system":"Rescue-Net","version":"0.1.0","status":"running"}
- Frappe shadow web: HTTP/1.1 200 OK
- Frappe compatibility API: {"message":{"system":"Rescue-Net Frappe Shadow Compatibility API","status":"running","mode":"shadow-only","cutover_allowed":false}}

## Latest Backup Pack

- Path: /volume1/web/rescue-net/_archive/frappe-p0-precutover/20260802-204118

```text
created_at=20260802-204118
mode=frappe-p0-precutover-backup
source_postgres_container=postgres-main
source_postgres_db=rescuenet_db
frappe_mariadb_container=osiun-frappe-mariadb
frappe_mariadb_db=_c85854d8ca9ba7b8
cutover_allowed=false
notes=Backup pack only. Existing Rescue-Net routing remains unchanged.
```

SHA256:

```text
2e41ee9eab28ebd94bdacb82623ca17202dea67b080a5b386f7704ee0ee1b22c  /volume1/web/rescue-net/_archive/frappe-p0-precutover/20260802-204118/rescuenet_pg.dump
7c1c0d79277b0e2dd08d127888fb8a1786e396d8beaf9c3201a39a67fd0b584d  /volume1/web/rescue-net/_archive/frappe-p0-precutover/20260802-204118/frappe_shadow_mariadb.sql
```

## Shadow Status Snapshot

```json
{"message":{"generated_at":"2026-08-02T13:46:34.052135+00:00","mode":"shadow-only","source":"rescue-net FastAPI/PostgreSQL","target_app":"rescue_net","source_counts":{"disaster_events":5,"organizations":8,"posko_nodes":10,"logistic_needs":6,"consolidated_needs":2,"aid_offers":7,"distribution_flows":6},"target_counts":{"RN Disaster Event":5,"RN Organization":8,"RN Posko":10,"RN Logistic Need":8,"RN Aid Offer":7,"RN Distribution Flow":6,"RN War Room Snapshot":1},"war_room_metrics":{"active_posko_count":10,"open_need_count":8,"aid_offer_count":7,"distribution_flow_count":6},"war_room_counts":{"disaster_events":5,"organizations":8,"poskos":10,"logistic_needs":8,"aid_offers":7,"distribution_flows":6},"validation_summary":{"status":"pass","failure_count":0,"failures":[]},"readiness":{"status":"ready-for-next-shadow-step","checks":{"validation_passed":{"passed":true,"description":"Validation summary must be pass with zero failures."},"war_room_available":{"passed":true,"description":"Shadow War Room snapshot preview must build successfully."},"shadow_only":{"passed":true,"description":"Migration mode must remain shadow-only until an explicit cutover decision."}},"cutover_allowed":false,"cutover_note":"Existing Rescue-Net remains live. This report does not authorize reroute/cutover."}}}
```

## Required Before Any Real Cutover

1. Explicit owner approval for cutover window.
2. Freeze P0 writes on existing Rescue-Net.
3. Run fresh pre-cutover backup.
4. Run final sync rehearsal or final sync procedure.
5. Run P0 cutover dry-run gate.
6. Confirm rollback path and backup paths.
7. Only then perform an approved reroute action.
