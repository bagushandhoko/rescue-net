# Rescue-Net Frappe Migration Map

Status: pre-Frappe migration planning baseline
Baseline commit: 03612dc
DB backup: _archive/pre-frappe-db-20260802-1715/rescuenet_db.dump
Live API inventory: docs/migration/api-inventory.md
Live DB schema inventory: docs/migration/db-schema-inventory.txt

## Migration Position

Rescue-Net is ready for staged Frappe migration planning and scaffolding. The current FastAPI/PostgreSQL prototype remains the operational source of truth until the Frappe app has matching DocTypes, permissions, import scripts, and War Room read models.

Do not cut over all modules at once. Run the Frappe implementation in parallel first, import sample/live data, validate War Room results, then move selected operational roles to Frappe.

## Phase 0 - Frozen Baseline

- Web/API prototype is preserved at commit 03612dc.
- Legacy frontend artifacts were archived under _archive/pre-frappe-cleanup-20260802-1645.
- PostgreSQL dump was created under _archive/pre-frappe-db-20260802-1715.
- API and DB inventories were generated under docs/migration/.

## Phase 1 - Core DocTypes

| Frappe DocType | Source Concept | Priority | Notes |
| --- | --- | --- | --- |
| Disaster Event | disasters and event tables | P0 | Parent operational event for all modules. |
| Organization | organizations and verifier orgs | P0 | Government, NGO, community, company, and verifier identity. |
| Posko | posko or command node | P0 | Links to Disaster Event and Organization. |
| Logistic Need | logistic needs and consolidated needs | P0 | Preserve quantity, unit, urgency, status, and source. |
| Aid Offer | aid offers | P0 | Donor contribution pipeline. |
| Distribution Flow | distribution flows | P0 | Movement of aid from source to destination. |
| Stock Ledger Entry | inventory movement tables | P1 | Use ledger entries instead of mutable stock totals. |
| Volunteer | volunteer registrations | P1 | Skills, availability, and assignment. |
| Evidence Source | evidence and source records | P1 | Verification and audit trail. |
| Verification Request | verification workflows | P1 | Trusted verifier workflow. |
| Community Report | public reports | P1 | Public reports before conversion into operational records. |
| War Room Snapshot | dashboard rollups | P0 | Read model generated from DocTypes. |
| AI User Setting | AI user/provider settings | P2 | Avoid raw secrets in migration docs. |
| Sync Log | sync and audit events | P2 | Offline/mobile reconciliation. |

## Phase 2 - Import Order

1. Disaster Event
2. Organization
3. Posko
4. Unit Catalog and Unit Conversion
5. Logistic Need
6. Aid Offer
7. Distribution Flow
8. Stock Ledger Entry
9. Evidence Source and Verification Request
10. Community Report
11. Volunteer and Resource Profile
12. War Room Snapshot rebuild

## Phase 3 - API Compatibility

Keep the old public API path /rescue-net-api alive during migration. Frappe should expose compatibility endpoints or an adapter for disasters, posko, logistic needs, aid offers, distribution flows, data consolidation, War Room, community reports, verification, and AI context.

The frontend should not be rewritten until these endpoint contracts are either supported or replaced with Frappe Desk/Portal screens.

## Phase 4 - Validation Gates

A module is migration-ready only when:

- DocType fields cover the source table/API fields.
- Import script can be rerun idempotently.
- Counts match between PostgreSQL and Frappe.
- Key War Room metrics match source API output.
- Role permissions are defined for admin, command, posko, verifier, public reporter, and donor.
- Audit/history is preserved or intentionally transformed into Frappe Version, Comment, or Activity records.

## Immediate Next Tasks

1. Scaffold Frappe app rescue_net.
2. Create P0 DocTypes: Disaster Event, Organization, Posko, Logistic Need, Aid Offer, Distribution Flow, War Room Snapshot.
3. Write an import command for Rescue-Net PostgreSQL data.
4. Test import against _archive/pre-frappe-db-20260802-1715/rescuenet_db.dump.
5. Build a Frappe workspace named Rescue-Net Command Center.
6. Rebuild War Room metrics from Frappe DocTypes and compare with current /rescue-net-api output.

## Non-Goals For First Cutover

- Do not migrate mobile/offline sync first.
- Do not rewrite AI analyst before core operational data is stable.
- Do not delete the FastAPI/PostgreSQL prototype.
- Do not replace public report flows until Frappe permissions and portal UX are ready.
