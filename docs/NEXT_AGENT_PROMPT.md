# Rescue-Net Next Agent Prompt

Continue Rescue-Net from the current live checkpoint. Do not audit or redesign from zero.

Read in order:

1. `README.md`
2. `docs/CURRENT_STATUS.md`
3. `docs/HANDOFF_LATEST_RN.txt`
4. `docs/BLUEPRINT.md`
5. `docs/CROSS_PLATFORM_APP_DESIGN.md`

Do not modify OSIUN. This task scope is Rescue-Net unless the owner explicitly says otherwise.

## Environment

- Repository/static web: `/volume1/web/rescue-net`
- Runtime API: `/volume1/docker/rescue-net-api`
- Cross-platform app runtime: `/volume1/web/rescue-net-app`
- API: `http://127.0.0.1:8092`
- Public web: `https://osiun.tail251e1e.ts.net/rescue-net/`
- Public API: `https://osiun.tail251e1e.ts.net/rescue-net-api`
- PostgreSQL: `postgres-main`, database `rescuenet_db`
- GitHub: `https://github.com/bagushandhoko/rescue-net`
- Branch: `main`
- Default event: `event-sim-001`

## Rules

- Backup all touched live files before edits.
- Preserve unrelated user changes.
- Keep raw reports separate from operational facts.
- Keep identity/location/report/need verification separate.
- Do not unsafe-SUM overlapping reports.
- Do not convert unknown packaging without a trusted conversion.
- Do not commit secrets or `.env`.
- Rebuild API with its env file.
- Run smoke and secret scan before push.

## API Rebuild

```sh
cd /volume1/docker/rescue-net-api
sudo /usr/local/bin/docker build -t rescue-net-api:0.1 .
sudo /usr/local/bin/docker rm -f rescue-net-api
sudo /usr/local/bin/docker run -d \
  --name rescue-net-api \
  --restart unless-stopped \
  --env-file /volume1/docker/rescue-net-api/.env \
  -p 8092:8092 \
  rescue-net-api:0.1
curl -fsS http://127.0.0.1:8092/health
```

## Validate

```sh
cd /volume1/web/rescue-net
sh scripts/rn-smoke-test.sh
sh scripts/rn-secret-scan.sh
```

## Important Current Features

- Offline-first cross-platform app.
- Data consolidation with minimum/optimal/maximum scenarios.
- Posko/report duplicate detection.
- National drill-down and command correction audit.
- Trusted Verifier registry, token requests, scoped endorsement, and revoke.
- Separate identity/location/report/need status.
- War Room verification and consolidation signals.

## Database Compatibility

- Use `trusted_verification_requests`.
- Do not reuse the legacy `verification_requests` table.
- Do not assume API DB user owns all tables.
- Do not ALTER `volunteer_profiles` from runtime startup.

## Recommended Next Task

Implement real verifier notification delivery:

1. Add provider abstraction for SMS/email/WhatsApp.
2. Send the existing secure verification URL.
3. Record delivery attempts without storing provider secrets.
4. Add resend and expiry UI.
5. Add rate limits and abuse controls.
6. Preserve the existing manual share URL fallback.

After completing any task, synchronize runtime source back into:

- `backend/`
- `apps/rescue-net-app/`
- relevant web files

Then update `docs/CURRENT_STATUS.md`, commit, and push `main`.
