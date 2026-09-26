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

1. **Automated test foundation — DONE 2026-09-26, reviewed; owner said fix BUG-1..6, then phase 2.** Isolated stack `rescuenet-test-*`
   containers + site `rescuenet-test.localhost` (`allow_tests`; production has no such flag); 57 tests in
   `rescue_net/tests/` pass (9 skips = the known bugs below). How to run: `CLAUDE.md` → Tests.
2. Business invariants → DocType controllers / `rescue_net/services/`; split api_*.py > 1,500 lines.
   **Step 1 (inventory) DONE 2026-09-26 → `docs/PHASE2_INVARIANTS.md`; owner answered: fix ALL group A, VF-1 = System Manager only, S-2 accept + flag, no stock recount.**
   Progress (each commit = rules in the controller + direct-save tests): VF-1/2 ✔, VF-3..6 ✔, SF-2/3/4 ✔, M-2/3/4 ✔ (medical case/evacuation graphs + cascade in the controllers), L-3/L-4 ✔ (`services/stock.py`: one receipt path; a flow-carried offer is never received twice; a receipt starts from effective stock = snapshot − kitchen usage; existing rows not recounted). O-7/L-23/L-24 ✔ (beneficiary count, daily consumption, stock quantity corrections = posko operators only; resource request approval = the resource owner), L-16 ✔ (tender + bid graphs in the controllers, only a verified org opens bidding, one final winner; `update_tender_status` now saves through the controller), L-9/L-17 ✔ (`services/money.py`: program totals grow by SQL increment, a cash donation is decided once under a row lock, a new special program starts at received/spent 0 unless System Manager). Seen, not changed: an org owner with no posko of that org cannot create an organisation program (`_allowed_owner` goes through `_allowed_poskos`). Note: moving a flow to `received` via plain `update_flow_status` still adds no stock (only `receive_flow_and_update_stock` does). Next: the rest of group A, group B, API split.
3. Finish the FastAPI retirement (audit table → owner picks the cutover date → archive tag `fastapi-final`).
4. Split the single "Rescue Net" module per domain.
5. Frontend cleanup (dead/duplicate JS, shared components, web vs `apps/rescue-net-app` decision).
6. Repo hygiene (backup/, _archive/, scratchpad/, _sandbox_desain/, root .txt/.md, one push script).

## Known bugs found by the tests (2026-09-26)

**BUG-1..6 FIXED 2026-09-26** (owner: "perbaiki BUG-1 sampai BUG-6 dulu"), each now has a positive + negative test
(70 tests, 1 skip = GAP-P2). **Committed + pushed, NOT deployed to production** (Claude's `docker cp` into
`osiun-frappe-backend` is blocked) — owner/teammate: deploy the changed `api_*.py` + `visibility.py`, then
`bench --site osiun.localhost migrate` (2 new fields on the Search & Found doctypes), then restart.

| Id | Where | Fix |
|---|---|---|
| BUG-1 | `api_control_centre.posko_distribusi_board` | booking PIN, booker phone/contact, donor contact only for the posko's own operators (`_posko_actor_flags` manage) |
| BUG-2 | `api_control_centre.posko_verification_checklist` | PIC email/phone/name values → `None` unless `visibility.posko_contacts_visible` (share mode full) |
| BUG-3 | `api_shelter.dashboard` | Guest: household `notes`/`destination` → `None`, PIC phone/email follow share mode |
| BUG-4 | `api_ai._build_context` | no longer whitelisted |
| BUG-5 | `api_resource_tools.resource_profile_board` | phone/email only for the profile owner + System Manager |
| BUG-6 | `api_volunteer.dashboard` | Guest: volunteer `contact` → `None`, PIC contacts follow share mode |
| GAP-P2 | RN Distribution Flow | status transitions enforced only in `update_flow_status` — phase 2 (`@known_bug` test) |
| DATA-1 | production DB | 12 Custom Fields exist only in production (made in Desk) — fresh install breaks 5 boards; phase 2/4 |

Owner answers to the questions (2026-09-26), implemented:
- `fulfill_need`: a posko not open to the public takes no outside donations → same gate as `create_aid_offer`
  (`_user_aid_posko_allowed`: public detail + `public_participation` + `accept_goods`, or own organisation).
- `restricted_record` for a report with no posko: stays open to operators, **but the reporter must be reachable** →
  new `reporter_name` / `reporter_contact` on RN Missing/Found Person Report (typed on the form, else the account's
  phone/email; a posko-less report without any contact is refused); `restricted_record` returns them. Never public.
- Guest vs logged-in Search & Found count difference: not changed (no answer needed yet).

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
