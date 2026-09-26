# CLAUDE.md — working rules for Rescue-Net

Read `HANDOVER.md` first (current status, open items, gotchas). This file holds the rules
that do not change from session to session.

## Layout

- Frappe app (backend, system of record): `frappe_shadow/apps/rescue_net/rescue_net/`
  - `api_*.py` — whitelisted endpoints; `access_policy.py` (`rn_actor()`, posko/org permission helpers),
    `visibility.py` (public/summary scrubbing), `reference_resolver.py` (event/posko id resolution)
  - `rescue_net/doctype/rn_*/` — 70 DocTypes (JSON + controller)
  - `setup/` — idempotent default installers run by `after_install` / `after_migrate`
  - `tests/` — automated tests (see below)
- Frontend: `index.html`, `pages/*.html`, `assets/js/*.js`, `assets/css/*.css` (vanilla JS, served from disk).
- Legacy (retired, do not extend): `backend/` (FastAPI), `database/` (PostgreSQL migrations).
- Offline app source: `apps/rescue-net-app/`.

## Production — hands off

- Production site: `osiun.localhost` in container `osiun-frappe-backend`.
- **Never** run tests, seed scripts, experimental migrates or data cleanup against production.
  All of that happens on the isolated test stack below.
- A commit is not a deploy. Deploying a Python/DocType change = back up the target file, `docker cp`,
  `chown 1000:1000` + `chmod 644`, `bench migrate` if a DocType JSON changed, `docker restart
  osiun-frappe-backend`, verify md5 host == container. Say explicitly in HANDOVER.md when a change is
  committed but not deployed.
- Destructive data operations: preview the exact rows first; never build a filter from a list that can be
  empty (`["in", ids or [""]]` once deleted 5 real poskos).

## Tests (mandatory for every change)

Isolated stack — containers `rescuenet-test-db` (MariaDB 10.6), `rescuenet-test-redis`,
`rescuenet-test-bench` (same `frappe/erpnext:v15` image as production, Frappe 15.113.4) on docker network
`rescuenet-test` (10.78.0.0/24, no published ports). Site `rescuenet-test.localhost` has
`allow_tests: true`; production does NOT and must never get it.

```sh
sh scripts/rn-test-stack.sh init      # once: create the site + install rescue_net (~10 min on the NAS)
sh scripts/rn-test-stack.sh test      # copy the repo's app into the bench and run all rescue_net tests
sh scripts/rn-test-stack.sh test --module rescue_net.tests.test_logistics_chain   # one module
sh scripts/rn-test-stack.sh migrate   # after changing a DocType JSON
sh scripts/rn-test-stack.sh wipe      # throw everything away (then init again)
```

The script copies `frappe_shadow/apps/rescue_net` into the test bench on every run (a bind mount does not
work: Synology ACLs hide the repo from the container's uid 1000), so tests run against the code in git,
not what is deployed.

Rules:
- Run the full suite before every commit that touches `frappe_shadow/`; push to `main` only when it passes.
- A new feature or bug fix comes with a test. Permission/visibility changes need a test that proves the
  wrong role (and Guest) is refused.
- Tests build their own data with `rescue_net/tests/factories.py` — never depend on production/sim records
  (`event-sim-001`, `ld1.demo@…`).
- Test classes use `frappe.tests.utils.FrappeTestCase` (Frappe 15); each test runs in a transaction that is
  rolled back.

## Conventions

- Commits: small, one logical change each, clear message. Push `git push origin main` (SSH deploy key).
- Refactors must not change user-visible behaviour unless fixing a bug already reported to the owner.
- Frappe 15.113.4: `from frappe.rate_limiter import rate_limit` (no `frappe.rate_limit`).
- UI text is Indonesian; code comments English.
- Frontend: bump the `?v=` cache-buster on a page's `<script>`/`<link>` when changing the file.
- Keep `HANDOVER.md` short and current in the same commit as the work.
