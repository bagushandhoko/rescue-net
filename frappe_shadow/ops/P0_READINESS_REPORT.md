# Rescue-Net P0 Frappe Readiness Report

Generated at: 2026-08-20T16:23:19+07:00

## Decision State

- Mode: shadow-only
- Cutover allowed: false
- Production reroute: not performed
- Latest Git commit: a75b41b Add P0 readiness report

## Health

- Rescue-Net web: HTTP/1.1 200 OK
- Rescue-Net API: {"system":"Rescue-Net","version":"0.1.0","status":"running"}
- Frappe shadow web: HTTP/1.1 200 OK
- Frappe compatibility API: {"message":{"system":"Rescue-Net Frappe Shadow Compatibility API","status":"running","mode":"shadow-only","cutover_allowed":false}}

## Latest Backup Pack

- Path: /volume1/web/rescue-net/_archive/frappe-p0-precutover/20260803-151004

```text
created_at=20260803-151004
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
f9c235c2291879a849a53f24fbe05c48a87170c0563bff89b5707918cfa93adc  /volume1/web/rescue-net/_archive/frappe-p0-precutover/20260803-151004/rescuenet_pg.dump
0315c63f31cb83b4461eae9403f2cebb09f29d1f4a457150e20bb71ad1be9f18  /volume1/web/rescue-net/_archive/frappe-p0-precutover/20260803-151004/frappe_shadow_mariadb.sql
```

## Shadow Status Snapshot

```json
{"message":{"generated_at":"2026-08-20T09:23:07.219921+00:00","mode":"shadow-only","source":"rescue-net FastAPI/PostgreSQL","target_app":"rescue_net","source_counts":{"disaster_events":5,"organizations":8,"posko_nodes":10,"logistic_needs":6,"consolidated_needs":2,"aid_offers":8,"distribution_flows":6,"stock_opnames":1,"evacuee_registrations":0,"donation_tenders":0,"donation_bids":0,"action_plans":1,"action_plan_updates":0},"target_counts":{"RN Disaster Event":5,"RN Organization":8,"RN Posko":10,"RN Logistic Need":8,"RN Aid Offer":8,"RN Distribution Flow":6,"RN War Room Snapshot":1},"inline_migration_plan":{"scope":"P0 inline source-to-shadow calculation","totals":{"source":45,"target":45,"delta":0,"matched_doctypes":6,"blocked_doctypes":0,"coverage_percent":100.0},"rows":[{"doctype":"RN Disaster Event","source_tables":["disaster_events"],"source_count":5,"target_count":5,"delta_source_minus_target":0,"coverage_percent":100.0,"validation_status":"pass","action":"ready"},{"doctype":"RN Organization","source_tables":["organizations"],"source_count":8,"target_count":8,"delta_source_minus_target":0,"coverage_percent":100.0,"validation_status":"pass","action":"ready"},{"doctype":"RN Posko","source_tables":["posko_nodes"],"source_count":10,"target_count":10,"delta_source_minus_target":0,"coverage_percent":100.0,"validation_status":"pass","action":"ready"},{"doctype":"RN Logistic Need","source_tables":["logistic_needs","consolidated_needs"],"source_count":8,"target_count":8,"delta_source_minus_target":0,"coverage_percent":100.0,"validation_status":"pass","action":"ready"},{"doctype":"RN Aid Offer","source_tables":["aid_offers"],"source_count":8,"target_count":8,"delta_source_minus_target":0,"coverage_percent":100.0,"validation_status":"pass","action":"ready"},{"doctype":"RN Distribution Flow","source_tables":["distribution_flows"],"source_count":6,"target_count":6,"delta_source_minus_target":0,"coverage_percent":100.0,"validation_status":"pass","action":"ready"},{"doctype":"RN War Room Snapshot","source_tables":[],"source_count":0,"target_count":1,"delta_source_minus_target":-1,"coverage_percent":100,"validation_status":"n/a","action":"rebuild_snapshot"}],"next_step":"continue_shadow_only"},"war_room_metrics":{"active_posko_count":10,"open_need_count":8,"aid_offer_count":8,"distribution_flow_count":6},"war_room_counts":{"disaster_events":5,"organizations":8,"poskos":10,"logistic_needs":8,"aid_offers":8,"distribution_flows":6},"validation_summary":{"status":"pass","failure_count":0,"failures":[]},"readiness":{"status":"ready-for-next-shadow-step","checks":{"validation_passed":{"passed":true,"description":"Validation summary must be pass with zero failures."},"war_room_available":{"passed":true,"description":"Shadow War Room snapshot preview must build successfully."},"shadow_only":{"passed":true,"description":"Migration mode must remain shadow-only until an explicit cutover decision."},"inline_counts_matched":{"passed":true,"description":"Inline P0 source-to-shadow counts must have zero blocked doctypes."}},"cutover_allowed":false,"cutover_note":"Existing Rescue-Net remains live. This report does not authorize reroute/cutover."}}}
```

## Required Before Any Real Cutover

1. Explicit owner approval for cutover window.
2. Freeze P0 writes on existing Rescue-Net.
3. Run fresh pre-cutover backup.
4. Run final sync rehearsal or final sync procedure.
5. Run P0 cutover dry-run gate.
6. Confirm rollback path and backup paths.
7. Only then perform an approved reroute action.
