# Rescue-Net — Working Handover

> Living status doc: what is done, what is in flight, what is next. Keep it SHORT —
> update it in the same commit as the work it describes. The full per-feature log
> up to 2026-09-25 (76 sections: design notes, data seeded, verification runs) is
> archived at `docs/history/HANDOVER-log-2026-08-31_to_2026-09-25.md` — search it
> before assuming something was never built.

_Last updated: 2026-09-26_

## System snapshot

- **System of record:** Frappe 15.113.4 / MariaDB. Production site `osiun.localhost` in container
  `osiun-frappe-backend` (compose: `/volume1/docker/osiun-frappe-shadow/`). The app is `rescue_net`
  (70 DocTypes, one module "Rescue Net"). ERPNext is installed on the site but unused by rescue_net.
- **App source of truth:** this repo, `frappe_shadow/apps/rescue_net/rescue_net/`. The container reads a
  separate copy (`/volume1/docker/osiun-frappe-shadow/apps/rescue_net`) — a commit is NOT a deploy.
- **Frontend:** `index.html`, `pages/*.html`, `assets/` — served straight from disk (live on save).
- **Public host:** `https://osiun.tail251e1e.ts.net` — static site `/rescue-net/`, API `/rescue-net-frappe/api/method/...`.
- **Legacy:** FastAPI `backend/` + PostgreSQL `rescuenet_db` are retired (container stopped, DB read-only,
  rollback dump in `_archive/post-cutover/`). Do not re-enable. Formal removal = architecture-review Phase 3.
- **Automated tests:** isolated test stack, see `CLAUDE.md` → "Tests" (`sh scripts/rn-test-stack.sh test`).

## Architecture review (2026-09-26) — 6 phases, one at a time, owner approves each

1. **Automated test foundation — IN PROGRESS** (this session). Isolated stack `rescuenet-test-*` containers +
   site `rescuenet-test.localhost`; tests in `rescue_net/tests/`.
2. Business invariants → DocType controllers / `rescue_net/services/`; split api_*.py > 1,500 lines.
3. Finish the FastAPI retirement (audit table → owner picks the cutover date → archive tag `fastapi-final`).
4. Split the single "Rescue Net" module per domain.
5. Frontend cleanup (dead/duplicate JS, shared components, web vs `apps/rescue-net-app` decision).
6. Repo hygiene (backup/, _archive/, scratchpad/, _sandbox_desain/, root .txt/.md, one push script).

## Open items (not part of the review phases)

- **Dapur Umum mock-up QA pass 2, items 4-6** (Jadwal Masak as meal-slot cards, Status Gas/BBM tiles with
  "sisa ± N hari" from real `RN Kitchen Ingredient Usage` rate, Kapasitas progress bar) — code COMMITTED,
  frontend live, but **`api_kitchen.py` is NOT deployed**: the Claude session's `docker cp` into the
  production container was blocked. Owner/teammate: deploy `api_kitchen.py` + `docker restart osiun-frappe-backend`.
  Until then the page renders the fuel tiles from the old response shape (no `category`/`recorded` keys).
- Dapur Umum item 5 (title/header right side vs mock-up) — same open item as Shelter.
- Shelter: no pixel-diff scores yet (screenshots `rn-shelter-*.png` in `/volume1/docker/osiun-playwright-check`).
- Next mock-up QA pages after Dapur Umum: Relawan, Distribusi.
- "Org config shows empty now" (org settings) still needs a repro.

## Rules / gotchas

- **Never build a delete from a possibly-empty id list** (`["in", ids or [""]]` deleted 5 real poskos on
  2026-09-20; restored from backup). Preview the plan, skip empty lists.
- **Never run tests, seeds, experimental migrates or cleanups against `osiun.localhost`.** Use the test stack.
- Frappe 15.113.4 has no `frappe.rate_limit` — use `from frappe.rate_limiter import rate_limit`.
- Python changes are not hot-reloaded: deploy = back up the target, `docker cp` the file, `chown 1000:1000` +
  `chmod 644` (docker cp keeps the repo's restrictive modes; directories land unreadable), `docker restart
  osiun-frappe-backend`, verify md5 host == container. New DocType fields need `bench migrate`.
- Frappe `Int` columns read 0 for old rows — never treat 0 as "reported zero" without an "observed" marker.
- Bench console via stdin breaks on multi-line loops: `exec(open('/tmp/x.py').read(), {'__name__':'__main__'})`.
- `File.file_url` rejects non-`/files/` paths; sim evidence lives in `legacy_payload.evidence.image`.
- Do not hardcode map pins in JS; fix coordinates on the `RN Posko` record.
- Playwright runs only inside Docker image `mcr.microsoft.com/playwright:v1.56.1-noble`
  (scripts in `/volume1/docker/osiun-playwright-check/`).
- Check `git status` before assuming code doesn't exist — a prior session may have left it uncommitted.
- The NAS powers off at **23:00 WIB**: have everything committed/pushed and this file updated by ~22:30.
- Push: `git push origin main` works over the SSH deploy key (`remote.origin.pushurl`); `main` is the only branch.
