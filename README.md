# Rescue-Net

**Rescue-Net** is an open-source **Disaster Management System** for coordinating disaster response across communities, organizations, volunteers, donors, logistics posts, medical posts, shelters, transport providers, and decision makers.

## Full Blueprint

The full system blueprint is available here:

[docs/BLUEPRINT.md](docs/BLUEPRINT.md)

## Purpose

Rescue-Net helps connect disaster events, field needs, aid offers, donor flows, volunteers, transport capacity, medical posts, shelters, evidence, verification, programs, donations, and AI-assisted situation analysis.

The system is designed to support fast public participation while still providing accountability for organizations, companies, NGOs, and government agencies.

## Core Principles

- Fast emergency participation
- Non-bureaucratic public aid flow
- Verified organization workflow
- Logistics and distribution traceability
- Evidence-based verification
- Federated open-source deployment
- AI-assisted decision support
- Role-based privacy and access control

## Main Modules

- Active Disasters
- War Room
- Organization & Posko
- Volunteer Management
- Logistics
- Public Aid Submission
- Edit Aid by Phone + Edit Code
- Donor Organization Flow
- Transport Space
- Distribution Flow
- Management Distribusi
- Medical Post
- Dapur Umum
- Shelter / Temporary Accommodation
- Work Tools
- Communication Equipment
- Search & Found
- Evidence & Verification
- Program Khusus
- Program Donasi
- AI Situation Analyst
- AI Settings / Bring Your Own Key

## Prototype Status

This repository currently contains the early Rescue-Net prototype:

- Static web dashboard
- FastAPI backend
- PostgreSQL database design
- Docker deployment
- Public donor aid flow
- Edit aid by phone + edit code
- Volunteer management
- Logistics module
- Distribution management
- Organization and posko registry
- AI Situation Analyst concept
- AI context endpoint
- AI Settings with Bring Your Own Key design

## Backend

The backend prototype uses:

- FastAPI
- PostgreSQL
- Docker
- Swagger/OpenAPI documentation

Backend source is located in `backend/`.

## AI Design

Rescue-Net AI uses a **Bring Your Own Key** model.

AI keys belong to:

- individual users, or
- verified organizations

Secret keys must be stored encrypted in the backend and must never be committed to GitHub or stored in frontend JavaScript.

AI answers must be permission-aware and source-traceable.

## Branching

- `main` = stable / production / owner updates
- `dev` = contributor / Codex / testing

## Security Notice

Do not commit:

- `.env`
- API keys
- database passwords
- database dumps
- uploaded evidence files
- real personal data
- real patient data
- production credentials

## Continue Development

For a new ChatGPT/Codex session, use:

[docs/NEXT_AGENT_PROMPT.md](docs/NEXT_AGENT_PROMPT.md)

This file explains the current checkpoint, live environment, implemented modules, and safe continuation rules.
