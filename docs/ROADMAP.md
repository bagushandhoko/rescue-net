# Rescue-Net Roadmap

## Completed Foundation

- Active Disasters
- Disaster Detail / Ecosystem
- Organization & Posko basic
- Volunteer Management basic
- Logistics basic
- Public Aid / Donatur Cepat
- Distribution Management
- Shared Resources
- Resource Requests
- Resource Assignments
- Offline Sync Foundation
- Sync Console
- AI Context endpoint
- Ecosystem consolidation schema

## Immediate Next Work

1. Posko Detail
2. Stock Movement
3. Posko Logistics Stock In/Out
4. Posko Aid Receiving Verification
5. Posko Volunteer Assignment

## Posko Detail Target

Create:
- pages/posko-detail.html
- assets/js/posko-detail.js
- GET /posko-context/{posko_id}

Show:
- posko overview
- organization owner
- role in disaster
- logistic needs
- incoming aid
- stock summary
- distribution flows
- assigned volunteers
- evidence
- sync status

## Stock Movement Target

Create table:
- stock_movements

Create API:
- GET /stock-movements/{posko_id}
- POST /stock-movements

Movement types:
- stock_in
- stock_out
- transfer_in
- transfer_out
- adjustment
- reserved
- damaged
- expired
