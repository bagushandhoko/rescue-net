# Rescue-Net Handoff

Last updated: 2026-06-08
Owner: bagushandhoko
Repository: https://github.com/bagushandhoko/rescue-net

## Important Instruction

Do not audit or redesign from scratch. Continue from the current architecture.

Rescue-Net design principle:
Active Disasters is the entry point. One active disaster opens Disaster Detail. Disaster Detail contains the disaster ecosystem: organizations, posko, volunteers, donors, resources, transport, logistics, evidence, sync, and AI context.

## Current Server

Synology RS815+
IP: 192.168.100.32
Static web: /volume1/web/rescue-net
Backend: /volume1/docker/rescue-net-api
API container: rescue-net-api
API port: 8092
PostgreSQL container: postgres-main
Database: rescuenet_db

Local URLs:
Web: http://192.168.100.32/rescue-net/
API health: http://127.0.0.1:8092/health
API docs: http://192.168.100.32:8092/docs

## Current Working Modules

1. Active Disasters
- index.html
- assets/js/api.js
- list disasters
- create disaster
- disaster card links to Disaster Detail

2. Disaster Detail / Ecosystem
- pages/disaster-detail.html
- assets/js/disaster-detail.js
- shows one disaster ecosystem
- ecosystem members
- shared resources
- resource requests
- resource assignments
- AI context summary

3. Organization & Posko
- pages/organisasi-posko.html
- assets/js/org-posko.js
- basic organizations and posko registry

4. Volunteer Management
- pages/management-relawan.html
- assets/js/relawan.js
- basic volunteer listing and creation

5. Logistics
- pages/posko-logistik.html
- assets/js/logistik.js
- logistic needs and aid offers overview

6. Public Aid / Donatur Cepat
- pages/kirim-bantuan.html
- pages/edit-bantuan.html
- assets/js/public-aid.js
- personal donor without registration
- submit aid
- edit aid using phone + Aid ID + edit code

7. Distribution Management
- pages/management-distribusi.html
- assets/js/distribusi.js
- aid pickup/self-delivery
- transport spaces
- distribution flows

8. Shared Resource Flow
- TNI shares transport
- Harley/community can request transport
- command/owner can approve
- assignment created

9. Offline Sync Console
- pages/sync-console.html
- assets/js/sync-console.js
- browser localStorage simulates offline device
- Sync Push sends event to /sync/push
- server applies resource_request create
- Sync Pull reads latest state from /sync/pull/{disaster_event_id}

10. AI Context
- GET /ai/context/{disaster_event_id}
- reads disaster, posko, needs, aid, transport, distribution, volunteers, ecosystem, resources, requests, assignments
- returns summary, alerts, recommendations, sources

## Current Important API

GET /health
GET /disasters
POST /disasters
GET /organizations
POST /organizations
GET /poskos
POST /poskos
GET /volunteers
POST /volunteers
GET /logistic-needs
POST /logistic-needs
GET /aid-offers
POST /public/aid-offers
POST /public/aid-offers/verify-edit
PUT /public/aid-offers/{aid_offer_id}
GET /transport-spaces
POST /transport-spaces
GET /distribution-flows
POST /distribution-flows
GET /ecosystem-members/{disaster_event_id}
GET /resources/{disaster_event_id}
GET /resource-shares/{disaster_event_id}
GET /resource-requests
POST /resource-requests
POST /resource-requests/{request_id}/approve
GET /resource-assignments
POST /sync/push
GET /sync/pull/{disaster_event_id}
GET /ai/context/{disaster_event_id}

## Database Foundation

Operational tables:
- disaster_events
- organizations
- posko_nodes
- volunteers
- logistic_needs
- aid_offers
- transport_spaces
- distribution_flows
- evidence_files

Ecosystem and sync tables:
- servers
- devices
- disaster_ecosystem_members
- resources
- resource_shares
- resource_requests
- resource_assignments
- coordination_channels
- coordination_messages
- sync_events
- sync_batches
- sync_conflicts
- audit_logs

Migration:
database/migrations/001_ecosystem_sync_foundation.sql

## Design Decisions

Do not make Disaster Ecosystem a duplicate top-level module.

Correct structure:
Active Disasters
- Disaster Detail
  - Overview
  - Ecosystem Members
  - Shared Resources
  - Resource Requests
  - Resource Assignments
  - Logistics
  - Distribution
  - Evidence
  - AI Context

One disaster can include many actors:
- government
- TNI/Polri
- BPBD
- PMI
- NGO
- community groups
- transport communities
- donors
- personal posko
- dapur umum
- medical posts
- shelters
- international partners

Each data object keeps ownership and sharing rules:
- owner_type
- owner_id
- visibility_scope
- access_policy
- verification_status
- trust_level

Offline sync design:
local device change -> sync_event -> /sync/push -> server validates -> server applies -> /sync/pull returns latest state

Current sync apply rule:
object_type = resource_request
operation = create
creates row in resource_requests

## Current Test Data

Main disaster:
event-aceh-2025
Gempa Aceh Barat 2025

Sample ecosystem members:
org-bpbd-aceh
org-tni
org-pmi
group-harley-rescue
posko-dapur-melati

Sample resource:
res-tni-transport-air-01
TNI Air Transport Slot 01

## Rebuild Backend

cd /volume1/docker/rescue-net-api
python3 -m py_compile main.py && echo "SYNTAX_OK"
sudo docker build --no-cache -t rescue-net-api:0.1 .
sudo docker rm -f rescue-net-api 2>/dev/null || true
sudo docker run -d \
  --name rescue-net-api \
  --restart unless-stopped \
  -p 8092:8092 \
  --env-file /volume1/docker/rescue-net-api/.env \
  -v /volume1/docker/rescue-net-data/uploads:/data/uploads \
  rescue-net-api:0.1

## Security Rules

Never commit:
- .env
- API keys
- OpenAI keys
- database passwords
- database dumps
- uploaded evidence
- real personal data
- real medical data
- real victim identity data
- production credentials

## Next Recommended Work

Next after this handoff:
1. Posko Detail page
2. Posko context API
3. Stock Movement table and API
4. Logistics stock in/out
5. Dapur Umum module
6. Posko Medis module
7. Shelter / temporary accommodation module
8. Search & Found module
9. Evidence verification workflow
10. Role/user/organization permission
11. AI BYOK backend storage
12. APK/desktop offline client using SQLite

Do not start with APK yet. Finish web/API workflows first.
