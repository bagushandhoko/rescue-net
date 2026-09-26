# CLAUDE.md — working rules for Rescue-Net

Read `HANDOVER.md` first (current status, open items, gotchas). This file holds the rules
that do not change from session to session.

## Layout

- Frappe app (backend, system of record): `frappe_shadow/apps/rescue_net/rescue_net/`
  - `api_*.py` — whitelisted endpoints (input check, permission check, call the service, shape the
    response). The six big ones are split into packages — `control_centre/`, `logistics/`, `ai/`,
    `resource_tools/`, `donor_program/`, `frontend_bridge/` — and `api_<name>.py` is only a compatibility
    layer re-exporting every name, so frontend paths `rescue_net.api_<name>.<fn>` keep working. Add new
    code to the package module of its sub-domain, not to the compat file. No module over ~1,500 lines.
  - `services/` — shared business rules called by controllers and APIs: `guards.py` (`assert_transition`,
    `assert_quantities`, `bypass` for data loads), `stock.py`, `money.py`, `transport.py`, `llm.py`
    (OpenAI / Claude / Gemini), `report_intake.py`, `report_routing.py`, `tool_needs.py`
  - `access_policy.py` (`rn_actor()`, posko/org permission helpers), `visibility.py` (public/summary
    scrubbing), `reference_resolver.py` (event/posko id resolution)
  - `rn_<domain>/doctype/rn_*/` — 74 DocTypes (JSON + controller) in 12 Frappe modules: `RN Core`,
    `RN Command`, `RN Community`, `RN Logistics`, `RN Shelter`, `RN Medical`, `RN Volunteer`, `RN Resources`,
    `RN Donor`, `RN Search Found`, `RN Verification`, `RN Intelligence` (`modules.txt`; grouping in
    `docs/PHASE4_MODULE_PROPOSAL.md`). A new DocType goes into the module of its domain. **Rules that must always hold live in the
    controller** (`validate` / `on_update`, via `services/`), not only in an API function — Desk, imports
    and other endpoints save through the controller too. Every such rule has a test that saves directly
    with `frappe.get_doc(...).save()`.
  - `patches.txt` + `patches/` — one-off data/schema patches run by `bench migrate`
  - `setup/` — idempotent default installers run by `after_install` / `after_migrate`
  - `tests/` — automated tests (see below)
- Frontend: `index.html`, `pages/*.html`, `assets/js/*.js`, `assets/css/*.css` (vanilla JS, served from disk).
- Offline app source: `apps/rescue-net-app/` — a router in `src/app.js` maps its REST-style calls onto
  Frappe methods; deployed as static files in `/volume1/web/rescue-net-app/`. There is no FastAPI any more
  (removed in phase 3, history in the git tag `fastapi-final`) — never add a second backend.

## Production — hands off

- Production site: `osiun.localhost` in container `osiun-frappe-backend`.
- **Never** run tests, seed scripts, experimental migrates or data cleanup against production.
  All of that happens on the isolated test stack below.
- A commit is not a deploy. Deploy = `sh scripts/rn-deploy-app.sh` (backup code + DB, copy the git-tracked
  app files, `bench migrate`, restart, probe). Copying files without the migrate is not a partial deploy,
  it is a broken production: the running backend picks up new code at once and fails on missing columns.
  Say explicitly in HANDOVER.md when a change is committed but not deployed.
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
- Call endpoints the way the browser does when the check matters: `api_call("rescue_net.api_x.fn", ...)`
  applies Frappe's whitelist / `allow_guest` check for the current `as_user(...)` / `as_guest()` session.
- A confirmed bug the owner has not approved fixing yet gets a test marked `@known_bug("BUG-n")` (reported as
  a skip). When the fix lands the test fails with "looks fixed — remove @known_bug": remove the marker in the
  same commit. Bug ids and descriptions: `HANDOVER.md` → "Known bugs found by the tests".
- New `allow_guest` endpoint → `test_public_endpoints.GUEST_ENDPOINTS` fails until you review what it returns
  to Guest and add it; the Guest sweep then checks it against the sentinel secrets.
- The 12 former production-only Custom Fields are standard DocType fields since DATA-1 (patch `rescue_net.patches.v2026_09.custom_fields_into_doctype`).
  A new field must go into the DocType JSON, never be created by hand in Desk.

Suite (2026-09-26, end of phase 2): 197 tests in `rescue_net/tests/`, ~4 min on an idle NAS (up to 16 min
under load), including `test_sim_kekeringan` (a full drought scenario).

## Conventions

- Commits: small, one logical change each, clear message. Push `git push origin main` (SSH deploy key).
- Refactors must not change user-visible behaviour unless fixing a bug already reported to the owner.
- Frappe 15.113.4: `from frappe.rate_limiter import rate_limit` (no `frappe.rate_limit`).
- UI text is Indonesian; code comments English.
- Frontend: bump the `?v=` cache-buster on a page's `<script>`/`<link>` when changing the file.
- Frontend helpers live in `assets/js/rn-ui.js` (`window.RNUI`: `esc`, `fmt`, `shortDate`, `fmtTime`, `eventId`,
  `chip`, `kpiCard`, `modal`). Use them in new code instead of another local copy; a page that uses them loads
  `rn-ui.js` before its own script.
- Keep `HANDOVER.md` short and current in the same commit as the work.

## Keputusan Arsitektur

Keputusan arsitektur yang berlaku ada di `docs/adr/` (mulai `0001-arsitektur-inti.md`: Frappe satu-satunya
backend, modular monolith, MariaDB, frontend statis headless, AI BYOK suggest/accept).
Jangan mengusulkan perubahan yang bertentangan dengan ADR tanpa alasan kuat. Jika perlu, tulis ADR baru
berstatus Proposed dan minta persetujuan owner.

## Next Steps

Roadmap: `docs/NEXT_STEPS.md`. Fase 9 (federasi, sinkronisasi offline, standar data kemanusiaan P-code/HXL/CAP)
dimulai dengan desain berupa ADR Proposed setelah Fase 8 selesai — jangan dikerjakan sebelum owner memerintahkan.
