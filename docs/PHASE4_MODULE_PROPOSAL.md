# Phase 4 — proposal: split the "Rescue Net" module per domain (2026-09-26)

Architecture-review phase 4, step 1: **proposal only — nothing has been moved.** The owner approves (or
changes) the grouping below; then the DocTypes move one module per commit, each followed by `bench migrate`
and the full test suite on the test site, and finally a migrate rehearsal on a copy of production data.

## Today (checked in code and in the production database)

- 78 DocTypes, all in one Frappe module `Rescue Net` (`rescue_net/rescue_net/doctype/`).
- Only 14 code imports use a DocType folder path (`rescue_net.rescue_net.doctype.rn_distribution_flow…` ×8,
  `rn_medical_case` ×3, `rn_medical_evacuation`, `rn_search_found_match`, `rn_volunteer_assignment`) — they
  change with the move. No fixtures, workspaces, reports or print formats are tied to the module.
- DocType names (`RN Posko`, …) do **not** change, so data, links, permissions, Custom Fields and every API
  call stay the same. Only the module label and the folder move.

## Proposed modules (12)

Module names carry the `RN` prefix so they can never clash with a Frappe/ERPNext module (e.g. ERPNext's
`Stock`); folders are `rescue_net/rn_<name>/doctype/…`. Row counts are production, 2026-09-26.

| Module | DocTypes | Rows |
|---|---|---|
| **RN Core** — events, organisations, poskos, accounts, areas | Disaster Event, Organization, Organization Membership, Org Merge Request, Posko, Posko Assignment, User Account, User Reference, Admin Area, Device, Sync Log, Notification Setting, Notification Log | 5 · 27 · 24 · 3 · 44 · 13 · 43 · 1 · 14 · 0 · 1 · 0 · 3 |
| **RN Command** — Control Centre, komando terpusat, plans | Command Change Request, Action Plan, Action Plan Update, Map Point | 0 · 10 · 0 · 0 |
| **RN Community** — laporan masyarakat | Community Report, Community Report Evidence, Community Report Update, Community Report Verification, Community Need, Community Feedback | 31 · 25 · 0 · 1 · 1 · 3 |
| **RN Logistics** — needs, aid, distribution, stock, transport, kitchen, tender | Logistic Need, Aid Offer, Distribution Flow, Stock Observation, Transport Space, Transport Booking, Kitchen Production, Kitchen Ingredient Usage, Procurement Tender, Tender Bid | 37 · 29 · 30 · 51 · 10 · 9 · 6 · 0 · 5 · 7 |
| **RN Shelter** — pengungsian | Shelter Occupancy, Shelter Household, Shelter Need, Displacement Plan | 10 · 5 · 8 · 4 |
| **RN Medical** | Medical Case, Medical Evacuation, Medical Evidence, Medical Supply Use | 13 · 0 · 0 · 2 |
| **RN Volunteer** | Volunteer Profile, Volunteer Assignment, Volunteer Accommodation, Safety Briefing | 15 · 16 · 2 · 2 |
| **RN Resources** — alat kerja, alat komunikasi, profil sumber daya | Resource Profile, Resource Request, Work Object, Work Tool Request, Work Tool Deployment, Comms Device, Comms Frequency, Comms Operator | 39 · 30 · 5 · 10 · 5 · 17 · 11 · 7 |
| **RN Donor** — donor & program khusus, recovery | Donor Program, Donor Program Update, Cash Donation, Recovery Project, Recovery Project Update | 13 · 7 · 1 · 5 · 1 |
| **RN Search Found** | Missing Person Report, Found Person Report, Search Found Match | 6 · 5 · 2 |
| **RN Verification** — verification, verifiers, evidence | Verification Request, Verification Action, Verification Endorsement, Verifier Profile, Operational Evidence, Evidence File | 2 · 0 · 0 · 4 · 2 · 0 |
| **RN Intelligence** — consolidation, normalisation, AI | Consolidated Need Snapshot, Consolidation Group Override, Duplicate Candidate Resolution, Normalization Rule, Unit Conversion, AI User Setting, AI Usage Log | 0 · 1 · 0 · 11 · 21 · 3 · 0 |

That covers 74 DocTypes. The remaining 4 are FastAPI-era leftovers that **no code reads or writes**:

| DocType | Rows | Why it is dead |
|---|---|---|
| RN Volunteer | 3 | imported from FastAPI; replaced by RN Volunteer Profile |
| RN User Session | 22 | imported FastAPI login sessions; Frappe has its own sessions |
| RN War Room Snapshot | 1 | cutover-era snapshot |
| RN Trusted Verification Request | 0 | FastAPI verification flow, replaced by Verification Request |

Proposal: export their rows to the legacy backup folder, then delete the 4 DocTypes (in line with
"sampah buang saja"), instead of giving them a module.

## How the move is done (after approval)

1. Per module, one commit: create `rescue_net/rn_<name>/` with `doctype/`, add the module to `modules.txt`,
   `git mv` the DocType folders, set `"module"` in each JSON, update the path imports, add a
   `pre_model_sync` patch that creates the Module Def if Frappe does not do it on migrate.
2. After each commit: `rn-test-stack.sh migrate` + full suite on the test site.
3. Before production: restore the latest production backup into the test stack, run `bench migrate` there,
   check every DocType opens and the probes answer, run the suite.
4. `rn-deploy-app.sh` gets a step that removes the old DocType folders from the container (it copies git
   files but never deletes, so the old folders would stay behind as dead copies).

Risk: low — no DocType is renamed and no data moves; the only runtime change is where Frappe finds each
controller, and that is verified on the test site and on the production copy before the owner deploys.

## Questions for the owner

1. Is this grouping right (12 modules; e.g. kitchen under Logistics, recovery under Donor, evidence under
   Verification)?
2. Delete the 4 dead DocTypes (rows exported first), or keep them?
