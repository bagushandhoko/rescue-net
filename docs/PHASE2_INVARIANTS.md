# Phase 2 — business invariants inventory (2026-09-26)

Architecture-review phase 2, step 1: "inventory the rules that must ALWAYS hold, show the owner BEFORE moving them".
Nothing below has been moved yet. The owner reviews this list, then answers the questions at the end.

**Baseline (checked in code):** no DocType has `doc_events` in `hooks.py`; every DocType JSON grants write only to
System Manager; every whitelisted API writes with `ignore_permissions=True`. So today the rules live only in the
API function that happens to be used — another endpoint, Desk, an import or a seed script bypasses them. Most
controllers only do naming/defaults. The only `unique` field anywhere is `legacy_id`.

Legend: **ctrl** = enforced in the DocType controller today. **Risk** = what goes wrong through the bypass.
Items marked **(verified)** were re-read line by line this session; the rest come from a read-only code sweep
with line references and are re-checked when each one is moved.

## A. Rules that break data today (bugs — fixing them changes behaviour, needs owner OK)

| Id | Rule | Where it breaks | Risk |
|---|---|---|---|
| VF-1 **(verified)** | Role elevation needs an authorised approver | `api_verification.approval_action`: any user whose global role is posko/medical/shelter operator can approve a `user` role request → sets `role = requested_role` (incl. `command_center`) + `status=active`. `approve_posko_operator` is SM-only for the same thing | **High** — privilege escalation |
| VF-2 **(verified)** | Posko/org verification changes follow from→to order, scoped to the approver | same function: no from-state, no org/posko scope, no self-check → an operator can mark their **own** posko `official_verified` | High |
| VF-4 | A verifier cannot endorse a posko they manage | `api_verifier.endorse_posko` has no check; a posko can name its own manager as verifier | High |
| VF-6 | Sponsor-granted trust ≤ sponsor's own trust | explicit `trust_level` up to 5 accepted; revoked verifier can be reactivated | High |
| SF-4 **(verified)** | A reunited person stays reunited | `update_match_status(rejected)` on a *proposed* match resets both reports to `missing`/`found`, even when they are already reunited through another match | **High** — reunited person shows as missing again |
| L-3 **(verified)** | Each aid offer is counted into stock once | a flow receipt sets the offer to `delivered` and adds stock; `receive_aid_offer_and_update_stock` blocks only received/received_verified/cancelled, so it adds the same goods again | **Double-counted stock** |
| L-4 | New stock snapshot = effective stock (after kitchen usage) + receipt | both `receive_*` use the raw previous snapshot and reset the baseline, so kitchen usage since the snapshot is "refunded" | Stock too high |
| M-2 **(verified)** | Medical case follows `CASE_TRANSITIONS`; closed is terminal | `update_evacuation_status` sets the case to `evacuating`/`admitted` with `set_value`, no state check → a closed/deceased case can come back | High |
| O-7 **(verified)** | Only posko managers change posko data | `api_control_centre.set_posko_beneficiary` — any logged-in user, any posko, negative counts accepted | Medium |
| L-23 **(verified)** | Only posko operators edit stock | `api_control_centre.set_item_consumption` — any logged-in user; `correct_item_normalization` uses the weaker "contribute" right and can rewrite quantities | Medium |
| L-24 **(verified)** | Only the owner / resource manager approves a Resource Request | `api_frontend_bridge.approve_resource_request` needs only a login | Medium |
| L-16 | Tender goes draft→open→evaluation→awarded, one award, verified org only | `update_tender_status` allows any status incl. `open` for an unverified org; `set_bid_status` any→any | Medium — verification gate bypass |
| L-17 / L-9 | Money: confirmed once, totals add atomically | cash-donation confirm has no lock (double confirm = double amount); `current_amount`/`budget_*` are read-modify-write; `create_special_program` lets the creator set `budget_received` directly | Money double-count |
| O-2 | Membership decisions follow from→to | rejected/revoked members can be re-approved directly | Medium |
| O-4 | Attach/detach needs the *other* side's consent | `decide_org_link` accepts an owner of either side; a co-owner/deputy on the requester's side can approve | Medium |
| O-9 / O-10 | Posko rights only after an approved assignment | posko creator edits while the assignment is pending; `_create_posko_impl` auto-approves for a global `posko_operator` role | Medium |
| C-1 | Community report verify/reject follows from→to, not by the reporter | no from-state; reporter can verify own report | Medium |
| V-4 | Only the volunteer or a manager **of that posko** changes an assignment | accept/cancel and profile edits accept any global manager role | Medium |
| SF-3 | A match links reports of the same event, both open | `propose_match` checks neither | Medium |
| M-4 | One active evacuation per case, case not terminal | not checked | Medium |
| L-6 / L-12 | Transport bookings ≤ capacity, never on a cancelled armada; one capacity model | check skipped when capacity is 0/None, no lock; bookings ignore `transport_status`; cancelling one flow frees the armada for all | Overbooking |
| L-10 / L-11 | Flow follows the TRANSITIONS graph; offer status mirrors its flow | `claim_distribution_flow` uses a deny-list and never syncs offer/transport; `pickup_claimed` has no transitions (stuck); offer cancel/edit has no status gate | Stuck / orphan flows |
| L-19 / L-20 | offer.target_posko = flow destination; need still open | `claim_aid_pickup` takes a free destination; `fulfill_need` accepts closed needs | Aid to the wrong posko |
| O-11 | Delete a posko only when nothing links to it | the creator's own assignment is counted as a blocker, so delete always fails | Functional bug |

## B. Rules that hold today but only inside one API function (pure moves, no behaviour change)

| Id | Rule | Enforced today | Move to |
|---|---|---|---|
| GAP-P2 / L-10 | Distribution Flow status graph | `api_logistics.update_flow_status` (TRANSITIONS) | `RNDistributionFlow.validate` (from-state via `get_doc_before_save`) |
| L-1 | Need / Offer / Flow qty > 0, stock ≥ 0 | user/guest offer paths only | controllers |
| L-2 | Received qty ≤ flow/offer qty | nowhere (new) | controller / `services/stock.py` |
| M-2/M-3 | Medical case + evacuation transition maps | `api_medical` | controllers; evacuation cascade goes through the case controller |
| S-2/S-3/S-5/S-6 | Shelter occupancy ≤ capacity, functional ≤ total, household + need transitions | API / nowhere | controllers (S-2 as a warning flag first — real data may exceed capacity) |
| SF-2 | Match transitions | `api_search_found.update_match_status` | `RNSearchFoundMatch.validate` |
| V-2/V-3 | One active assignment per volunteer; assignment transitions | `api_volunteer` (no lock) | controller + row lock |
| L-13/L-14/L-15 | Booking, kitchen production, tool deployment transitions | API + partial ctrl | controllers |
| C-2/C-4 | Trust score 0–100, affected people ≥ 0 | API / nowhere | controller |
| O-1 | Posko public only when the org allows it | ctrl **already** + read-time | keep; add cascade when an org closes |
| M-1, S-1, S-4, SF-1, V-1, AI-1 | enums, counts ≥ 0, unique AI setting | ctrl **already** | keep |

## C. Plan (after owner OK)

1. `rescue_net/services/transitions.py` — one helper `assert_transition(doc, field, graph)` using
   `doc.get_doc_before_save()`; controllers call it. Legacy/seed imports keep their `legacy_id` escape hatch.
2. Move group B rule by rule, one DocType per commit, each with a test that saves directly via
   `frappe.get_doc(...).save()` and expects the rule to hold (phase-2 step 5). GAP-P2's `@known_bug` becomes a real test.
3. Fix group A items the owner approves, highest risk first (VF-1, VF-2, SF-4, L-3, M-2, then the rest).
4. Split the six API files over 1,500 lines, one new file per commit, re-exporting the old dotted paths so the
   frontend URLs (`rescue_net.api_logistics.create_flow` …) keep working:
   `api_control_centre` 5,555 · `api_logistics` 3,555 · `api_frontend_bridge` 2,877 · `api_ai` 2,467 ·
   `api_resource_tools` 2,084 · `api_donor_program` 1,717.
5. DATA-1: the 12 production-only Custom Fields go into the DocType JSON (then `setup_test_site.ensure_custom_fields`
   can be removed).

Production deploys stay with the owner (Claude's `docker cp` into production is blocked); every step is tested on
the isolated `rescuenet-test-*` stack.

## D. Questions for the owner

1. Group A: fix all of them in phase 2, or only the High ones now and the rest later?
2. VF-1: should approving a role request be System-Manager-only (like `approve_posko_operator`), or may a
   `command_center` user approve too?
3. S-2 (occupancy > capacity): refuse the save, or accept it and flag it (field reality: shelters do overflow)?
4. L-3/L-4 fix changes stock numbers going forward (no more double count / refunded usage). Existing stock rows
   stay as they are unless you want a one-off recount (on a copy first).
