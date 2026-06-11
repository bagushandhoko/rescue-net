# Rescue-Net Production Grade Roadmap

## Current Prototype Status

Rescue-Net prototype module coverage is complete enough for demo/pilot.

Active modules:
- Active Disasters
- War Room
- Map
- Organization & Posko
- Logistics
- Distribution
- Public Kitchen
- Medical Posko
- Shelter
- Search & Found
- Program Khusus / Donor Program
- Recovery / Reconstruction
- Volunteers
- Work Tools
- Resource Profile
- Evidence
- Verification
- AI Analyst
- AI Settings
- Sync Console
- Contact Directory
- Mock-up Viewer

## Production Grade Priority

### Phase 1 — Safety Layer
- Smoke test script
- Backup-before-change script
- JS syntax check
- API endpoint check
- Database dump before risky patch

### Phase 2 — Audit Log
Every create/update/delete action should write to `audit_events`.

Minimum fields:
- id
- disaster_event_id
- actor_user_id
- actor_role
- action
- object_table
- object_id
- before_data
- after_data
- ip_address
- user_agent
- created_at

### Phase 3 — Auth / RBAC
Required roles:
- super_admin
- disaster_admin
- organization_admin
- posko_admin
- logistics_operator
- medical_operator
- shelter_operator
- volunteer_operator
- donor
- viewer
- auditor

### Phase 4 — Evidence Linking
Evidence should be linkable to:
- aid_offers
- logistic_needs
- stock_movements
- distribution_flows
- medical_cases
- shelter_needs
- missing_person_reports
- found_person_reports
- donor_programs
- recovery_projects
- resource_profiles
- verification_actions

### Phase 5 — Offline Sync Conflict Handling
Add object versioning and conflict policy:
- server_wins
- client_retry
- manual_review
- merge_if_non_conflicting

### Phase 6 — Database Migration
Move ad-hoc CREATE TABLE logic into migrations:
- database/migrations/001_initial.sql
- database/migrations/002_resource_recovery.sql
- database/migrations/003_audit_log.sql
- database/migrations/004_rbac.sql

### Phase 7 — AI Context Hardening
Resource/Recovery should be integrated into AI Context carefully:
- no regex insertion
- manual function edit
- py_compile before build
- smoke test before and after rebuild
