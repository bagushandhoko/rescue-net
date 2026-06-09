# Rescue-Net Next Agent Prompt

Continue Rescue-Net from the latest checkpoint. Do not redesign from scratch.

Read first:
1. README.md
2. docs/CURRENT_STATUS.md
3. docs/HANDOFF.md
4. docs/ROADMAP.md
5. docs/BLUEPRINT.md

Live environment:
- Static web: /volume1/web/rescue-net
- Backend runtime: /volume1/docker/rescue-net-api
- API container: rescue-net-api
- API port: 8092
- PostgreSQL container: postgres-main
- Database: rescuenet_db
- GitHub: https://github.com/bagushandhoko/rescue-net

Current checkpoint:
Rescue-Net is a working prototype with static web UI, FastAPI backend, PostgreSQL, Docker, offline sync foundation, AI context, encrypted BYOK AI key, and multiple operational modules.

Implemented modules:
- Active Disaster
- Organization & Posko
- Ecosystem consolidation
- Resource sharing/request/assignment
- Sync Console
- Posko Detail
- Stock movement
- Incoming aid verification
- Stock transfer
- Dapur Umum / Kitchen
- Posko Medis
- Shelter
- Search & Found
- AI Context
- AI Settings BYOK
- AI Ask
- AI Analyst UI

Important endpoints:
- GET /health
- GET /ai/context/{disaster_event_id}
- POST /ai/user-key
- GET /ai/user-key/{user_id}
- POST /ai/user-model
- DELETE /ai/user-key/{user_id}
- POST /ai/ask
- GET /sync/pull/{disaster_event_id}
- POST /sync/push
- POST /stock-transfer
- GET /posko-context/{posko_id}
- GET /kitchen-context/{posko_id}
- GET /medical-context/{posko_id}
- GET /shelter-context/{posko_id}
- GET /search-found-context/{disaster_event_id}

Security rules:
- Never commit .env.
- Never commit API keys.
- Never expose full AI keys.
- BYOK keys are encrypted in ai_user_settings.
- Browser may only see masked key, like ****1234.
- Rotate AI_KEY_ENCRYPTION_SECRET before production.

Current priority:
1. Stabilize backend.
2. Refactor main.py into route modules gradually.
3. Do not break live endpoints.
4. Move one route group at a time.
5. Always test health, openapi, and relevant endpoint.
6. Commit and push after each safe checkpoint.

Refactor direction:
backend/
- main.py
- app_shared.py
- routes/__init__.py
- routes/ai_routes.py

Suggested next task:
Move AI routes from main.py to routes/ai_routes.py only after shared helpers are stable.
