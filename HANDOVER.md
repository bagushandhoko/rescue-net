# Rescue-Net — Working Handover

> Living status doc so a fresh session (any AI account, or a teammate) can pull
> this repo and immediately know **what is done, what is in flight, what is next**.
> Update this file in the same commit as the work it describes.

_Last updated: 2026-09-06 (3-level posko-access model — guest view-only / member manages own-org / cross-org coordinator — **PHASE 2 COMPLETE** on Posko Logistik + Posko Distribusi; commits 1faea9f · 0e46bbd · 2c16f6c · 0ab55c9 · 1d98459 · 9a0e62b · 9db44ec · 5b0ad21 · 08fe2b9 · c28724c)_

---

## 3-level posko-access model — PHASE 2 COMPLETE (2026-09-06)

One consistent model across `logistik_board`, `posko_distribusi_board`,
`posko_edit_scope` and `rn-posko-scope.js`:

| viewer | flag | can do (Posko Logistik / Posko Distribusi) |
|---|---|---|
| not logged in | — | **view only**, every input control hidden |
| logged-in, **operator or approved member of the posko's org** | `can_manage` | full: +Tambah kebutuhan, Ubah jiwa, Terima kiriman, Kartu Stok / Kelompok Barang panels · daftarkan/perbarui armada, konfirmasi/tolak booking, tugaskan relawan, klaim pickup |
| logged-in, **member of another org, posko opened participation** | `can_coordinate` | **coordinate only**: "Tambah Bantuan Tersedia" (send aid) · "Pesan Slot" on an armada. Never edits that posko's internal data |

- `can_manage` = `effective_posko_share` reason ∈ `_POSKO_OWNER_REASONS`
  (`system_manager` / `posko_operator` / `org_member` / `posko_assignment` /
  `org_membership`) — helper `_posko_actor_flags(posko, actor)`.
- `can_coordinate` (Logistik) mirrors `api_logistics.create_aid_offer`'s
  `public_ok` EXACTLY: `public_posko_allowed(posko)` (org `privacy_mode=open`
  + `allow_posko_public_choice` + posko `public_detail=public`) ∧
  `public_participation` ∧ `accept_goods`. Distribusi booking only needs
  `public_participation` (any logged-in user may `book_transport_space`).
- `posko_edit_scope.can_edit_current` == `can_manage`;
  `.can_coordinate_current` == the Logistik `can_coordinate` gate.
  `rn-posko-scope.js`: read-only banner + `hideEditForms()` only fire when
  `can_edit_current === false`; `hideEditForms(keepCoordination)` spares
  `#aidOfferPanel` when `can_coordinate_current`, and the banner relabels
  "Hanya-lihat" → "Koordinasi".

### Collected-stock dispatch chain (2026-09-06, `c437e3b`) — DONE & DEPLOYED
Owner: on Posko Logistik after login a collector posko should see its stock,
click an item → where it came from, then a "kirim kemana" link — straight to
a receiver posko OR routed via a transport posko (kapal TNI AL / Land Rover),
that choice a pull-down; and another transport posko can book it.
- `api_control_centre.logistik_stock_sources(posko, item)` — "asal item"
  (received aid offers + arrived flows). `logistik_dispatch_options(
  disaster_event, source_posko)` — receiver poskos + available armada.
- `api_logistics.create_flow` now sets `disaster_event`; NEW
  `claim_distribution_flow(flow, transport_space)`.
- `posko_distribusi_board.pickup_queue` also lists unassigned outgoing
  `RN Distribution Flow` (`kind:"flow"`), matched by event or by
  source/destination posko in the event.
- `logistik.js`: Kartu Stok item name → "Asal item" drawer; "Kirim" button
  (`can_manage`) → `openDispatch()` (qty · Tujuan `<select>` · Lewat
  `<select>` = "Langsung / cari transporter" OR an armada) → `create_flow`.
- `posko-distribusi.js`: `renderPickupQueue` `kind:"flow"` rows → armada
  `<select>` + "Booking" → `claim_distribution_flow`.
- `?v=dispatch-20260906`. Backend e2e verified (create_flow no-transport →
  pickup_queue kind:flow → claim → assigned_pickup + Land Rover provider,
  row leaves queue). Browser DOM not re-verified (container↔host net down).

### Bug + layout sweep (2026-09-06) — DONE & DEPLOYED
- `3fbc90a` / `eb4b4ce` — `quantity_mode:"known"` → `"exact"` (logistik ×2,
  shelter ×1): every "+ Tambah Kebutuhan" / "Tambah Bantuan" / shelter-need
  submit 417'd on `ValidationError` (field only allows exact/estimated/range/
  unknown). Found by the cross-org aid e2e.
- `349575b` — `program-khusus.html`: legacy `loadPrograms()` let
  `api_donor_program.context` (login-only) throw for guests → console error
  on every guest visit. Now caught; the legacy `<details>` directory shows a
  "login untuk direktori lengkap" hint. Modern guest board unaffected.
- `4b80cd3` — `management-distribusi.html`: legacy `distribusi.js dashboard()`
  → `api_logistics.dashboard` for the hardcoded fallback posko threw
  "Anda tidak memiliki akses ke Posko ini" for logged-in non-managers. Now
  catches → empty ctx. Modern `distribusi_board` (guest) is separate.
- `765f3f6` — Shelter "Daftar Shelter" rows linked to
  `shelter-detail.html?id=<docname>` — but that page has NO per-posko view
  (event-wide overview only) so a click just reloaded the same dashboard, and
  older docnames leaked the `posko_nodes:` / `disaster_events:` prefix into
  the URL. New `_shelter_href()` strips the prefix (`_bare`) and points every
  row + KPI drill item at `posko-detail.html?id=<bare>&event=<bare>`.
  (Owner: "klik shelter over capacity tidak ke detail, kembali ke halaman yg
  sama".) Verified: click now navigates to `posko-detail.html`.
- `db83951` — `posko-distribusi.html` layout: topbar now uses the shared
  `rn-logistik-topbar`/`rn-logistik-controls`/`rn-inline-select` pattern (one
  clean wrapping row, no cramped stack colliding with the Login pill); the
  "Relawan Pickup" panel + the "Antrean Pickup" claim columns are hidden for
  non-managers (`#pdRelawanPanel`, `.pd-claim-col`, `.rn-md-row2--solo`) so
  guests don't see an empty panel + two dead columns.

Health sweep (guest 22 pages + logged-in 14 pages): otherwise 0 console
errors / broken pages.

**E2E verified (`3fbc90a`, Playwright):** LD2 (Komunitas Landrover member,
NOT a member of `SIM-NS-WARGA`) opens `posko-logistik.html?id=SIM-NS-POSKO-WARGA`
→ `can_coordinate:true`, `#aidOfferPanel`+`#aidCoordNote` shown, `+Tambah` /
operator panels hidden, "Koordinasi" banner. Fills + submits "Tambah Bantuan
Tersedia" (500 dus Air Mineral) → **"Bantuan tersimpan."**; `logistik_board`
`public_shipments` 6→7, the new `RN Aid Offer` targets WARGA and renders in
its "Kiriman Masyarakat" table (donor "Komunitas Landrover — bantuan lintas
organisasi (simulasi)"), where a WARGA operator can "Terima" it into stock.
**Bug found + fixed en route:** `logistik.js` sent `quantity_mode:"known"`
(invalid — doctype allows `exact|estimated|range|unknown`) on both
`create_need` and `create_aid_offer` → every submit 417'd. Now `"exact"`.
`shelter-detail.js:445` still has the same `"known"` bug (untouched).

**Phase 2 checklist — all DONE & DEPLOYED:**
1. `08fe2b9` — Logistik "Tambah Bantuan Tersedia" enabled for `can_coordinate`
   viewers; `can_coordinate` tightened to the exact `create_aid_offer` gate;
   demo seed on `SIM-NS-POSKO-WARGA` (+ `SIM-NS-WARGA` org) so the case is
   testable.
2. `9a0e62b` — `posko-distribusi.html` wired to `RNPoskoPicker` + 3-level
   access; NEW "Pesan Slot" booking form in the armada drill for
   `can_coordinate`.
3. `c28724c` — `posko_edit_scope.can_edit_current` realigned to `can_manage`
   (was `can_manage_posko()` = assignment/coordinator-role only, so a plain
   org member wrongly got a read-only banner on their own org's posko).

**Verified (Playwright, LD2 = Komunitas Landrover member):** own-org
non-operated posko (`SIM-LR-POSKO-LD6`) → `can_edit_current == can_manage ==
true`, no scope banner, all operator controls; other-org open
(`SIM-NS-POSKO-WARGA`) → both `can_manage:false`, `can_coordinate:true`,
`#aidOfferPanel` + `#aidCoordNote` visible & survive the scope.js timer,
green "Koordinasi" banner; other-org closed (`SIM-NS-POSKO-BNPB`) → all
false. Guest → dashboard only, 0 forms. 0 console errors in every case.

**Open (not blocking, low priority):**
- `posko-distribusi.html` `can_coordinate` "Pesan Slot" path is code-complete
  but not browser-verified (no sim transport posko has `public_participation`
  for a non-member session — SIM-LR poskos are all Komunitas Landrover).
- Posko Distribusi still English-shell-ish vs a dedicated mockup (there is
  none — `manajemen distribusi.png` is the coordination page); layout polish
  optional.

---

## Posko Distribusi — shared picker + 3-level access + booking (2026-09-06) — DONE & DEPLOYED

Same 3-level model as Posko Logistik, applied to `posko-distribusi.html`.

### Backend — `api_control_centre.py` (deployed)
- NEW `_posko_actor_flags(posko)` → `(logged_in, can_manage, can_coordinate)`
  (module-level `_POSKO_OWNER_REASONS`; `posko_detail()` reuses the set).
- `posko_distribusi_board()` now returns `viewer` + `logged_in`/`can_manage`/
  `can_coordinate`, and `transporter_poskos` carry `organization` +
  `public_participation`.

### Frontend — `posko-distribusi.js` / `.html` (`?v=poskodist-20260906`)
- selector → `RNPoskoPicker.mount()` (org member: "Posko organisasi saya" +
  "Posko lain — terbuka untuk koordinasi"; guest: flat). Falls back to the
  old flat `<select>` if the picker script is missing. Still navigates (full
  reload) on change.
- `applyAccess(data)` — `can_manage` gates `#armadaAddBtn`, `#armadaForm`
  (Daftarkan Armada), `[data-assign-form]` (Tugaskan Relawan); `renderBookings`
  only draws the Konfirmasi/Tolak PIN box for a manager; `renderPickupQueue`
  only draws the destination select + "Ambil & Antar" for a manager (else "—").
  `#pdNoManage` shows a calm one-liner ("Mode lihat…" / "Anda bukan pengelola…
  bisa memesan slot").
- NEW **`bookingForm(a)` / `wireBookingForm(a)`** in the armada drill modal,
  shown when `data.can_coordinate` → `api_logistics.book_transport_space`
  (any logged-in user; returns a PIN unless the armada's policy is `open`).
  The armada "Perbarui armada" edit `<details>` now only renders for
  `can_manage`.
- `rn-posko-picker.js` + `rn-posko-scope.js` (`poskoscope-20260906c`) added to
  the page; `style.css` bumped `?v=poskodist-20260906`.

### Verified (Playwright, host.docker.internal)
- **Guest** `SIM-LR-POSKO-LD3`: selector flat (4 opts); "+ Daftarkan Armada",
  Daftarkan Armada form, Tugaskan Relawan form all `display:none`; pickup
  queue 12 rows with "—" in the action column; "Mode lihat…" hint. 0 armada
  create/booking affordances.
- **Operator** (member sid, same posko): selector shows "Posko organisasi
  saya"; add button + both forms `display:block`; 12 claim buttons; no hint.
- `can_coordinate` "Pesan Slot" path is code-complete but not browser-verified
  (needs a logged-in non-member session on a `public_participation` transport
  posko).

---

## Posko Logistik → mockup dashboard, guest read-only / operator inline-edit (2026-09-06) — DONE & DEPLOYED

**Follow-up (`1d98459`):** the rebuilt dashboard had lost its click-through
("kok nggak bisa di klik detail nya"). Restored: the 4 KPI tiles
(`data-kpi` + `role=button`) open a drill drawer, and a Kebutuhan Mendesak
row opens a detail drawer (with "Penuhi kebutuhan ini" → `openFulfill` only
when `can_manage`). `style.css` `.rn-kpi-clickable` hover + `#urgentNeedsBody`
row hover.

**Follow-up 4 (`c28724c`):** `posko_edit_scope.can_edit_current` now aligned
with `logistik_board.can_manage`. It used `can_manage_posko()` (operator /
posko-assignment / `community_coordinator` role only) → a plain approved
org member viewing an OWN-org posko they don't personally operate got
`can_edit_current:false` → `rn-posko-scope.js` showed a "Hanya-lihat"
banner and hid the forms, **even though `_can_contribute` / the write
endpoints actually let them write**. Now `posko_edit_scope` uses
`_posko_actor_flags(posko, actor)` (share reason ∈ `_POSKO_OWNER_REASONS`,
incl. `org_member`) — same bar as `logistik_board.can_manage`. Verified
4 cases ALIGNED: own-org non-operated / own-org operated →
`can_edit_current == can_manage == true` (no banner, full operator
controls); other-org open → both false + `can_coordinate_current:true`;
other-org closed → both false. `can_coordinate_current` logic unchanged
(still the `create_aid_offer` public_ok mirror). Backend only, no
cache-buster.

**Follow-up 3 (`08fe2b9`):** aid form wired for `can_coordinate`.
`logistik.js renderManageAccess` now shows `#aidOfferPanel` (+ new
`#aidCoordNote`) on `can_manage || can_coordinate`; `itemGroupPanel` /
`stockCardsPanel` stay `can_manage`-only. `rn-posko-scope.js applyReadOnly`
now passes `scope.can_coordinate_current` into `hideEditForms(keepCoord)`
so the sweep spares `#aidOfferPanel`. Backend: `logistik_board.can_coordinate`
and `posko_edit_scope.can_coordinate_current` tightened to mirror
`api_logistics.create_aid_offer`'s `public_ok` EXACTLY — now also require
`access_policy.public_posko_allowed(posko)` (org `privacy_mode=open` +
`allow_posko_public_choice` + posko `public_detail=public`), on top of
`public_participation` + `accept_goods`, so the form only shows when a
submit will succeed. **Demo seed:** `SIM-NS-POSKO-WARGA` set
`public_participation=1, accept_goods=1, public_detail=public` +
`SIM-NS-WARGA` org `privacy_mode=open, allow_posko_public_choice=1` (via
bench console) — a genuine "warga posko opens itself for cross-org aid"
case. Verified: LD2 (Komunitas Landrover, non-member) on WARGA →
`can_coordinate:true`, `#aidOfferPanel` visible + survives the scope.js
timer, operator panels + "+ Tambah" hidden, green "Koordinasi" banner,
0 console errors. Cache-busters `logistikmock-20260906f` /
`poskoscope-20260906d`.

**Follow-up 2 (`9db44ec` + `5b0ad21`):** owner — the KPI drill "hanya tampil 2, tidak
keliatan dari posko mana, harusnya bisa ditrace … sdh pernah dibuat". The
first cut sliced the single-posko `LOGISTIK_BOARD`; now `openLogistikDrill`
calls the shared **`api_control_centre.kpi_drilldown`** (guest) — the same
board Control Centre uses. `kritis→kebutuhan`, `stok→stok`, `menuju→distribusi`;
`jiwa` stays a local note. `drillGroupsHtml()` renders it grouped by org:
open orgs list item rows (each `📍 posko · 🏢 org →` linking to
`posko-detail.html` for the full trace), closed orgs show a summary +
"N baris disembunyikan". Verified: "Kebutuhan Kritis" → 29 rows / 7 orgs
(3 open w/ 16 links, 4 summary, 13 hidden). `style.css` `.rn-drill-*`.
Cache-buster `?v=logistikmock-20260906c`.


Owner: the greyed-out console from the previous pass was "ngarang layout".
`posko-logistik.html` must follow **`assets/img/mockup/posko logistik.png`** —
a read-only monitoring dashboard — for a NOT-logged-in viewer; the logged-in
"Posko Logistik" is the same layout **plus inline edit** (owner answers:
"Betul, itu view tanpa login" / "Dashboard mockup + edit inline" / "Pakai ulang
renderer itu").

### `pages/posko-logistik.html` — restructured `<main>` (`?v=logistikmock-20260906`)
Mockup order now: 4 KPI tiles (`kpi-grid`: Jiwa Dilayani / Stok Menipis /
Kebutuhan Kritis / Bantuan Menuju Posko) → content-grid { **Kebutuhan Mendesak**
table, **Kiriman Masyarakat** table, **Barang Masuk / Keluar** (Masuk/Keluar
tabs) | aside: Asal & Trace, Bukti Kondisi, Konversi & Volume }. Removed the
console-only panels `manageNeedPanel` / `jiwaDilayaniPanel` / `publicShipPanel`.
`itemGroupPanel` (Kelompok Barang/Normalisasi AI), `stockCardsPanel` (Kartu Stok
Rinci) and `aidOfferPanel` (Tambah Bantuan) kept but **`hidden`** — operator only.
`#btnOpenAddNeed` moved into the Kebutuhan Mendesak header, `#btnEditJiwa` onto
the Jiwa KPI card, both `hidden` by default.

### `assets/js/rn-logistik-info.js` — now also loaded on posko-logistik.html
The read-only KPI / Kebutuhan Mendesak / Barang Masuk-Keluar renderers built for
posko-detail.html (`RNLogistikInfo.renderKpi` / `renderUrgentNeeds` /
`renderMovements` / `wireMovementsTabs`) are reused verbatim — no duplicate code.
Same `logistik_board` RPC feeds both pages.

### `assets/js/logistik.js` (`?v=logistikmock-20260906`)
`loadBoard()` calls the `RNLogistikInfo` renderers for the dashboard, then
`renderManageAccess(b)` which toggles the operator layer purely on
**`b.can_manage`**: shows `#btnOpenAddNeed`, `#btnEditJiwa`, `#itemGroupPanel`,
`#stockCardsPanel`, `#aidOfferPanel`, and adds the "Terima" column to Kiriman
Masyarakat. Non-operator → clean read-only dashboard + a calm one-liner
("Mode lihat — login sebagai operator …", link → `auth.html`). `renderPublicShipments`
rewritten for the mockup's `publicShipInfoPanel` (5 cols + optional Aksi).

### `assets/css/style.css` (`?v=logistikmock-20260906`)
- `button[hidden], a.btn[hidden] { display:none !important }` — `.btn`'s explicit
  `display` has equal specificity to `[hidden]` and was winning, so `hidden`
  buttons stayed visible. Scoped to buttons, not a global `[hidden]` rule.
- `.rn-kpi-edit` — absolute top-right, for the "Ubah" on the Jiwa KPI card.

### Verified (Playwright, host.docker.internal)
- **Guest** `SIM-NS-POSKO-WARGA`: KPI 1.200 / 0 / 2 / 2; Kebutuhan Mendesak 2
  rows; Kiriman Masyarakat 6 rows; Barang Masuk/Keluar 2 rows; Trace + 3 Bukti +
  5 Konversi rows. `#btnOpenAddNeed` / `#btnEditJiwa` computed `display:none`;
  itemGroup / stockCards / aidOffer hidden. Screenshot matches the mockup shape.
- **Operator** (member sid, `SIM-LR-POSKO-LD4`): "+ Tambah", "Ubah", "Terima"
  column, and the three operator panels all visible; no "Mode lihat" hint;
  selector shows the "Posko organisasi saya" group.

**Phase 2 — all DONE** (`c28724c` align `can_edit_current`; `08fe2b9` aid form
for `can_coordinate`; `9a0e62b` posko-distribusi picker + Pesan Slot). See the
"3-level posko-access model — PHASE 2 COMPLETE" section at the top of this file.

---

## Posko selector + input gating — 3 access levels (2026-09-06) — DONE & DEPLOYED

Owner: the operational pages did not tell "umum" (not logged in) from "login"
apart. Correct model (owner, verbatim intent):

1. **Not logged in** — the national posko list like before, **view only, zero
   add/input forms**. National coordination transparency.
2. **Logged in, own posko** — full management: tambah kebutuhan, catat stok,
   terima kiriman, ubah jiwa.
3. **Logged in, ANOTHER org's posko that opened participation**
   (`RN Posko.public_participation`) — may **coordinate** (booking transport /
   send aid) but **never** edit that posko's internal needs/stock. Non-open
   poskos of other orgs are simply not in the operational picker.

### Selector — `assets/js/rn-posko-picker.js` (`?v=poskopicker-20260906b`)
`RNPoskoPicker.mount({ selectEl, points, viewer, current, sortFn, labelFn,
onChange })`. One `<select>`:
- guest / non-org viewer → one flat list of every posko (unchanged).
- logged-in org member → `<optgroup>` **"Posko organisasi saya"** (own-org) +
  **"Posko lain — terbuka untuk koordinasi"** (other org **and**
  `point.public_participation`). Always both, **no toggle** (the earlier
  "Posko nasional" checkbox + localStorage was removed). Own group on top.
- the `?id=` posko is always kept selectable even outside both groups
  (own "Posko dipilih" group) so a deep link never breaks.

### Backend — `api_control_centre.py` (deployed via `docker cp` + chown/chmod + restart)
- `map_points()` each point now carries `public_participation` (the generic
  "opened to outside coordination" flag the selector groups on).
- `event_poskos` returns `{points, viewer}` (from commit 1faea9f).
- `posko_detail()` / `logistik_board()` now return **`logged_in`**,
  **`can_manage`** (share reason ∈ {system_manager, posko_operator, org_member,
  posko_assignment, org_membership}), **`can_coordinate`** (logged-in ∧ not
  manager ∧ posko `public_participation` ∧ `accept_goods` — mirrors
  `api_logistics.create_aid_offer`'s `public_ok`), `public_participation`.
  `detail_allowed` (view gating) unchanged and separate.
- `posko_edit_scope()` now also returns **`can_coordinate_current`**
  (`public_participation` ∧ `accept_goods` on a posko the member does NOT
  manage).

### Frontend — `logistik.js` / `rn-posko-scope.js` / `posko-logistik.html` (`?v=…906c`)
- **First pass hid the input panels for guests → owner: "kenapa posko logistik
  jadi kosong, seharusnya tampil spt sebelumnya".** Reverted: `renderManageAccess()`
  keeps `b.detail_allowed` for panel *visibility* (page looks exactly as before)
  and new `setManageControls(b.can_manage)` **disables (not hides)** every write
  control for a non-manager — `#btnOpenAddNeed`, `#btnEditJiwa`, the
  `[data-rn-create-aid-offer]` submit + inputs + selects (with a
  "Login sebagai operator…" hint), and the per-row "Terima" buttons in
  `renderPublicShipments()`. So a guest sees the full populated page with every
  input dead ("tanpa login, add & input tidak ada" without an empty column).
- `rn-posko-scope.js` (`?v=poskoscope-20260906c`) — `hideEditForms(keepCoordination)`:
  when `scope.can_coordinate_current`, spares `#aidOfferPanel` /
  `[data-rn-create-aid-offer]` so a member of another org may still record aid
  bound for an open posko; read-only banner switches its label to "Koordinasi".
- `posko-logistik.html` — `#aidOfferPanel` id kept (no `hidden`); dead
  `#logistikPoskoScope` span removed; `style.css` dropped `.rn-posko-scope-toggle`.

### Verified
- Backend live (guest, via container localhost): `logistik_board` for
  `SIM-NS-POSKO-WARGA` → `logged_in:false, can_manage:false, can_coordinate:false,
  detail_allowed:true`; `posko_edit_scope` → `can_coordinate_current:false` (new
  field, no error); `event_poskos` → 18 points w/ `public_participation`.
- Playwright guest load of posko-logistik → **no** "butuh login" banner;
  Tambah Kebutuhan / Jiwa Dilayani / Kiriman Masuk / Tambah Bantuan panels all
  visible; `#btnOpenAddNeed`, `#btnEditJiwa`, aid submit + all aid inputs
  `disabled`; Kartu Stok 7 rows, Kelompok Barang 5 rows, selector 18 opts.
  Screenshot confirms the page is full again.
- 18-case Node unit test of `mount()` (guest flat / member two groups /
  open-others = other-org ∧ public_participation / deep-link preservation /
  empty own-org placeholder).
- Playwright-container ↔ funnel is flaky (intermittent 403 / DNS); verify
  backend via `sudo docker exec osiun-frappe-backend curl -s http://localhost:8000/api/method/…`.

**Phase 2 — DONE (see "3-level posko-access model — PHASE 2 COMPLETE" at the
top of this file for the consolidated state):**
1. ✅ `08fe2b9` — `logistik.js renderManageAccess` surfaces `#aidOfferPanel`
   (+ `#aidCoordNote`) for `can_coordinate`; `can_coordinate` tightened to the
   exact `create_aid_offer` `public_ok` gate; demo seed on `SIM-NS-POSKO-WARGA`.
2. ✅ `9a0e62b` — `posko-distribusi.html` on `RNPoskoPicker` + 3-level access;
   NEW "Pesan Slot" booking form (`book_transport_space`) in the armada drill
   for `can_coordinate`. `posko_distribusi_board` returns `viewer` +
   `logged_in`/`can_manage`/`can_coordinate`; `transporter_poskos` carry
   `organization` + `public_participation`.
3. ✅ `c28724c` — `posko_edit_scope.can_edit_current` realigned to `can_manage`.

---

## Post-gap batch — A + B + C11/C13 (2026-09-04) — DONE & DEPLOYED

Owner: after the 3 blueprint gaps, "di setiap posko ada tanda level verifikasi";
"lanjutkan A dan B, untuk c nomer 11 dan 13".

### A — verif-badge everywhere + verifier UX (commit `f4a8ea8`)
- **NEW `assets/js/rn-verif-badge.js`** (`?v=vbadge-20260904`) — one shared
  `RNVerifBadge.html(status, count)` badge + CSS `.rn-vbadge--{self,warn,pend,comm,org,off}`.
  Wired: posko-detail (subtitle + overview + a new **"Kredibilitas & Verifikasi"**
  panel from `api_verifier.posko_verification_public`), registrasi-posko Daftar
  Posko table, koordinasi-organisasi posko cards. `posko_detail` /
  `posko_registry_board` / `my_org_coordination` now return `trusted_verifier_count`.
- `verifikator.js` request form lists the operator's **managed poskos**
  (`my_verification_requests` → `my_poskos`), so a first request is possible.
- `registrasi-posko` — new **"Minta Verifikasi Wilayah"** (site_visit /
  network_vouch → `request_posko_verification`) + link to verifikator.html.
- `kirim-bantuan` — hardcoded `disaster_event_id` textbox → **"Pilih Bencana"**
  `<select>` from `api_ai.public_active_disasters`.
- Demo endorsement committed: `SIM-NS-POSKO-WARGA` = `official_verified` (1 verifier).

### B5 — data-consolidation rollup panels (commit `ce882c0`)
`/national-rollup` was a dead `consolidation_summary` (counts-only) map → always
empty. Now `api_intelligence.control_centre_summary` (the honest 3-bucket
consolidation). `renderNationalRollup` = per canonical-group×base-unit
(terukur / perkiraan AI / belum terukur); `renderRollupTrace` = "mana yang perlu
ditinjau". `?v=datacons-20260904b`. + MOCKUP_ALIGNMENT_PLAN comms_board checkbox
ticked (12/12 done).

### B6 — Perencanaan Pengungsi + Masukan Masyarakat (commit `9b71142`)
Two blueprint Rehabilitation modules with no backing.
- **`RN Displacement Plan`** + `api_displacement.py` (`displacement_board` guest,
  `create_/update_displacement_plan`) + `pages/perencanaan-pengungsi.html`.
  KK/kelompok, asal, in_camp, health_status healthy/needs_care/orphan/mixed,
  plan_type return_home/relocate/undecided, est biaya kembali + bantuan awal,
  dukungan diperlukan. Rollup kembali vs relokasi + estimasi dana total.
- **`RN Community Feedback`** + `api_forum.py` (`feedback_threads` guest +
  category filter, `post_feedback` / `upvote_feedback` guest no-account,
  `respond_feedback` operator) + `pages/masukan-masyarakat.html` (tabs, upvote,
  reply, tanggapan resmi).
- `setup/rehab_forum_defaults.py` (hooks) — 4 plans + 3 threads.
- Nav 2.0.7→2.0.8 + 2 entries. **6 new doctype controllers** added (these +
  the 4 verifier doctypes) so a fresh install imports them.

### B7 — Tender / RAB (commit `470f54d`)
`RN Procurement Tender` + `RN Tender Bid` + `api_tender.py` (`tender_board` guest
w/ open/RAB-total/bids KPI; `tender_detail` guest w/ bidder contacts **masked**
unless owner; `create_tender` / `update_tender_status` login; `submit_bid`
allow_guest, only while open + before `bidding_closes_at`; `set_bid_status` —
"awarded" flips tender + rejects the rest). `pages/pengadaan-tender.html` — list,
download RAB link, inline "Ajukan Penawaran" (no account), owner "Tetapkan
pemenang". `setup/tender_defaults.py` — 2 tenders + 5 bids. Nav 2.0.8→2.0.9.

### C11 — BYOK AI organisation keys + usage log (commit `2fa008a`)
- `api_ai.py`: `save_org_key` / `get_org_key_status` / `delete_org_key` (gated
  `can_manage_organization`), `test_ai_key` (tiny provider call, user OR org
  scope, never returns the key), `ai_usage_summary` (30-day call/token counts).
  **`_resolve_ai_key`** = personal key first, then the asker's approved-org key;
  `ask()` uses it and writes an **`RN AI Usage Log`** row per call (counts only,
  no question/answer text, no secret) on success + every failure.
- `ai-settings.html/.js` (`?v=byok-org-20260904`) — "Uji Koneksi", a "Kunci AI
  Organisasi" section (org admins), "Pemakaian AI (30 hari)" panel.
- Verified (bench console as SIM-LR-ORG owner): save→saved (`****ghij`);
  `_resolve_ai_key` for a member w/o personal key → `organization / SIM-LR-ORG`;
  `test_ai_key` fake key → "Kunci ditolak (401)"; non-owner blocked.

### C13 — Peta Nasional / GIS rollup (commit `1fa77c6`)
`api_gis.national_situation(active_only)` guest — per-province rollup across ALL
active disasters (posko count, verified/official, distinct events + max severity,
jiwa, open needs, cities drill) + `points[]` = every posko w/ coords.
`pages/peta-nasional.html` + `peta-nasional.js` — KPI, a **Leaflet + OSM** map
(vendored) with severity-coloured circleMarkers + verif-badge popups + province
filter, and a province rollup table. Nav 2.0.9→**2.1.0** + "Peta Nasional".
Verified: guest → 3 provinces + "Belum Terdata", 31 posko, 6 disasters, 4.980
jiwa, 36 needs; Playwright → 21 OSM tiles + 31 markers, 0 console errors.

**Deploy notes this batch:** container `docker cp` lands files mode `000`/`044`
even after `chown frappe` — must `docker exec -u root … chmod 0644` every copied
`.py`/`.json`/doctype file or `bench migrate` reports the DocType JSON "missing"
and a fresh DocType's controller import fails (`ModuleNotFoundError`). Nav
cache-buster walked `navorg`→`navverif`→`navrehab`→`navtender`→`navgis`-20260904.

---

## Blueprint gap-closure (2026-09-04) — closing 3 vision gaps

Owner audit vs `docs/BLUEPRINT.md`: RN mostly matches the "open + closed-org
coordination, auto-consolidation, AI item grouping" vision; 3 gaps found and
being closed.

### Gap 6 — Guest ("Donatur Cepat") aid submission + Aid ID + Kode Edit — DONE & DEPLOYED

Blueprint: "Donatur Cepat / Personal Guest — tidak perlu registrasi" + Aid ID +
Kode Edit (edit via HP + code). Was login-only.

- **`RN Aid Offer` +3 fields** (`bench migrate`): `submitted_channel`
  (account/guest, default account), `guest_batch` (Data), `edit_code_hash`
  (Data, hidden — only the SHA-256 hash of the code is stored).
- **`api_logistics.py` — 3 new `allow_guest=True` endpoints:**
  `submit_guest_aid_offer_multi(disaster_event, donor_name, donor_contact,
  items_json, handling_mode, target_posko?, pickup_location?, ready_at?, notes?)`
  → one RN Aid Offer per item, all sharing one `guest_batch` + one 8-char
  `edit_code` (returned once, `_guest_code_hash` = `sha256("rn-guest-aid:"+CODE)`);
  `get_guest_aid_offer(aid_offer, edit_code, donor_contact?)` → current values +
  batch siblings; `edit_guest_aid_offer(aid_offer, edit_code, donor_contact?,
  item_text?/quantity?/unit?/pickup_location?/ready_at?/notes?/cancel?)`. All
  verify the code hash; `donor_contact` (HP) must also match if supplied.
  `target_posko` (optional) must be a `public_posko_allowed` + `public_participation`
  + `accept_goods` posko. Normalization runs on insert as usual (canonical_group,
  base_quantity).
- **Frontend:** `public-aid.js` (`?v=guestaid-20260904`) — `kirim-bantuan.html`
  submit now calls `submit_guest_aid_offer_multi` (no login); success box shows
  **Aid ID + Kode Edit** in a "simpan sekarang, ditampilkan sekali" warning box.
  `edit-bantuan.html` rebuilt for the guest flow: Aid ID + Kode Edit + HP →
  "Muat data bantuan" (`get_guest_aid_offer`, prefills the form + lists batch
  siblings) → edit or **Batalkan bantuan** checkbox (`edit_guest_aid_offer`).
  Deep-link `edit-bantuan.html?aid=<id>` from the success box.
- **Verified:** guest HTTP — submit 2 items (Air mineral→Air Minum, Beras→Bahan
  Pangan) with `edit_code`; get with right code+HP OK; wrong code / wrong HP →
  `PermissionError`; edit qty 10→18; cancel → `offer_status=cancelled`.
  Playwright end-to-end on `kirim-bantuan.html` → success box shows the code,
  then `edit-bantuan.html` loads + prefills "Selimut". Test rows deleted.

### Gap 8 — Club membership + HQ (pusat) approval — DONE & DEPLOYED

Blueprint: "anggota club bisa di verifikasi oleh pusatnya". The
`RN Organization Membership` doctype + `request_membership` existed but had 1 row
and no approval surface.

- **`RN Organization Membership` +3 fields** (`bench migrate`): `member_verified`
  (Check — HQ attests the member's identity is real), `verified_at` (Datetime),
  `decision_note` (Small Text).
- **`api_community_cluster.py` — new endpoints:** `org_membership_admin(organization?)`
  (join-request queue + member roster for orgs the caller owns — `_owns_org` =
  `can_manage_organization`); `decide_membership(membership, action, member_verified?,
  note?)` (approve / reject / revoke; approve+`member_verified` stamps
  `verified_at`); `set_member_verified(membership, verified)` (toggle the HQ
  attestation on an approved member); `my_memberships()` (caller's own
  memberships + `verified_member_of`).
- **`setup/membership_defaults.py`** (new, wired into `hooks.py`
  after_install/after_migrate, idempotent): seeds owner + member rows for
  SIM-LR-ORG (LD1 owner; LD2..LD6 members, LD2/LD4 `member_verified`),
  SIM-NS-BNPB, KH-ORG-BPBD, plus a few **pending** join requests (yusuf.hidayat +
  dwi_bagus → SIM-LR-ORG; KH-USER-GAMBUT → KH-ORG-BPBD). 15 rows on first run.
- **Frontend:** `koordinasi-organisasi.html` / `.js` (`?v=koordorg-20260904b`) —
  new **"Keanggotaan Organisasi"** section: for an org owner, pending requests
  with Setujui / Tolak (+ "identitas terverifikasi pusat" checkbox) and a member
  roster with Verifikasi identitas / Keluarkan; for a plain member, their own
  membership status line. `organisasi-posko.html` / `org-posko.js`
  (`?v=orgposko-20260904`) — an **"Ajukan Keanggotaan"** button per org card
  (`request_membership`).
- **Verified:** `bench console` as LD1 → `org_membership_admin` `is_org_admin:true`,
  2 pending / 6 members; `decide_membership(approve, member_verified=1)` →
  `approved` + `member_verified:true`; `my_memberships` as LD2 →
  `verified_member_of: ['Komunitas Landrover']`. Playwright as LD1 → member
  section + admin panel render, 0 console errors.

### Gap 9 — External verifier network (lurah / polsek / tokoh publik) — DONE & DEPLOYED

Owner: an **independent / warga posko** becomes credible when a **verifier in its
wilayah** endorses it. A verifier is government OR a willing public figure.
Verification is by **site visit** or a **"member-get-member" network vouch**
("via kenalan dia"). A verifier is onboarded by System Manager OR vouched in by a
senior verifier (trust ≥ 2). "Setiap posko bisa ajukan verifikasi ke verifikator
di wilayahnya."

- **4 DocTypes brought into the repo** (were DB-only from the FastAPI migration,
  0 rows): `RN Verifier Profile` (+ `wilayah`, `sponsor_verifier`,
  `endorsement_count`), `RN Verification Request` (+ `verifier`, `method`,
  `wilayah`), `RN Verification Endorsement` (+ `method`
  site_visit/network_vouch/document_review, `vouched_via`), `RN Verification
  Action` (audit). Minimal JSON — migrate adds the new columns, legacy columns
  left untouched.
- **`api_verifier.py` (NEW):**
  - `apply_as_verifier(display_name, verifier_type, wilayah, position_title?,
    public_role_description?, phone?, email?, sponsor_verifier?)` — anyone
    logged-in applies; status `pending`.
  - `verifier_directory(wilayah?, status="active")` — `allow_guest`; wilayah is
    a loose token match (kelurahan ⊂ kecamatan ⊂ kota).
  - `approve_verifier(verifier, action, trust_level?, note?)` — System Manager or
    a `trust_level>=2` active verifier (becomes `sponsor_verifier`, sponsee
    starts one trust level below).
  - `request_posko_verification(posko, verifier?, method, note?)` — the posko's
    manager asks; `verifier` optional (empty = open request for the wilayah);
    wilayah derived from the posko's village/district/city.
  - `my_verification_requests()` — requests for poskos the caller manages.
  - `verifier_inbox()` — direct requests + open requests matching the verifier's
    wilayah.
  - `endorse_posko(request?/posko?, method, statement?, vouched_via?,
    verification_level?)` — active verifier only; `network_vouch` requires
    `vouched_via`. Recomputes `RN Posko.trusted_verifier_count` +
    `verification_status`: ≥1 active endorsement → `community_verified`; a
    government verifier (trust ≥ 2) or ≥2 endorsements → `official_verified`.
    Writes an `RN Verification Action` audit row; bumps the verifier's
    `endorsement_count`.
  - `revoke_endorsement(endorsement, reason?)` — verifier or SM; recomputes
    credibility (can drop back to `self_reported`).
  - `posko_verification_public(posko)` — `allow_guest` credibility panel
    (status, count, endorser names / method / statement).
- **`setup/verifier_defaults.py`** (hooks after_install/after_migrate,
  idempotent) — 3 active verifiers (Keuchik Johan Pahlawan gov/trust2 linked to
  `admin.osiun@gmail.com`; Kapolsek Kaway XVI gov/trust2; Tgk. Imam Meulaboh
  religious/trust1), 1 pending (Ketua Karang Taruna Samatiga, sponsored by the
  Keuchik, linked to yusuf.hidayat), + 2 verification requests (SIM-NS-POSKO-WARGA
  → Keuchik site_visit; SIM-NS-POSKO-PELAJAR → open network_vouch). 6 rows first run.
- **Frontend:** NEW `pages/verifikator.html` + `assets/js/verifikator.js`
  (`?v=verifikator-20260904`) — role-aware: **verifier inbox** (endorse w/
  site_visit or network_vouch + vouched_via + statement), **"Verifikasi Posko
  Saya"** (request form, pick a wilayah verifier or open), **approval queue** for
  SM / senior verifiers, a **wilayah-searchable directory**, and a **"Jadi
  Verifikator"** apply form (with optional sponsor). Nav
  `rn-navigation-v2.js` 2.0.6→**2.0.7** + "Jaringan Verifikator" entry;
  cache-buster `navorg-20260903` → **`navverif-20260904`** on
  `rn-navigation-v2.{js,css}` across 33 pages.
- **Deploy:** api_verifier.py + hooks.py + verifier_defaults.py + 4 doctype dirs
  → `osiun-frappe-backend`; `bench migrate` (4 doctypes + new columns +
  verifier seed 6 rows) + restart. Frontend from disk.
- **Verified:** guest `verifier_directory` → 3 active, wilayah=Kaway → 1;
  `bench console` as the Keuchik → `verifier_inbox` (1 direct + 1 wilayah-open),
  `endorse_posko` from the request → endorsement active, request→completed,
  `SIM-NS-POSKO-WARGA` `trusted_verifier_count 1` + `verification_status
  official_verified` (gov path); `posko_verification_public` shows the endorser +
  statement; LD3 (no verifier profile) blocked from `endorse_posko`. Playwright
  guest load of `verifikator.html` → directory 3 cards, wilayah filter works,
  apply form + sponsor dropdown populated, 0 console errors.

**Note (infra, not code):** during this work the Tailscale **Funnel** (public
`osiun.tail251e1e.ts.net`) went unreachable (`000`); the backend + app serve
fine on `http://localhost/rescue-net{,-frappe}/`. If the public host is still
down, it's the Funnel, not Rescue-Net.

---

## Loose-ends batch 2 (2026-09-04) — DONE (frontend only, served from disk)

Owner: "kerjakan semua" on the three next loose ends. No backend / no deploy —
every endpoint used already existed.

### 1. Stale `event-aceh-2025` default → active event

Several still-legacy files defaulted to the near-empty `event-aceh-2025` when no
`?event=` was present → blank dashboards. Now default to the active event
(`?event=` / `localStorage.rn_active_event` / `"event-sim-001"`), matching every
rebuilt page.
- **JS:** `contact-directory.js` + `verification-approval.js` (`DISASTER_ID` now
  reads the query param + `rn_active_event`), `search-found.js` +
  `disaster-detail.js` (`getDisasterId` fallback `event-sim-001`; disaster-detail
  also accepts `?event=`), `rn-sync-engine.js` (`rnGetEventId` default),
  `sync-console.js` (2 spots).
- **HTML form prefills** `value="event-aceh-2025"` → `"event-sim-001"`:
  `evidence.html`, `management-distribusi.html`, `organisasi-posko.html`,
  `kirim-bantuan.html`, `search-found.html`, `sync-console.html`.
- Cache-busters bumped: `…?v=eventfix-20260904` on contact-directory /
  disaster-detail / search-found / sync-console / rn-sync-engine (5 pages),
  `verif-20260904` on verification-approval.
- **Verified (Playwright):** all four affected pages load with 0 console errors.
- Left on purpose: `pages/_static_archive/disaster-ecosystem.html` (archive).

### 2. `update_transport_space` — now has a UI

`api_logistics.update_transport_space` existed (login-required) with no
frontend. Added a **"Perbarui armada"** `<details>` form inside the Posko
Distribusi armada-detail modal (`#pdArmadaEditForm`), prefilled from the board
row: status / mode layanan / kebijakan booking / lokasi saat ini / jam berangkat
+ ETA (`datetime-local`) / titik + narahubung + no. kontak serah terima /
catatan. Submit → `update_transport_space`, then `closeDrill()` + `load()`.
Board `"-"` placeholders are stripped before prefill; `"YYYY-MM-DD HH:MM"` →
`datetime-local` value. `assets/js/posko-distribusi.js` `?v=poskodist-20260904`
+ new `.rn-pd-edit` CSS block in `style.css` (page style.css buster bumped too).
**Verified (Playwright):** drill opens, edit form renders with all 10 fields, 0
console errors.

### 3. `pages/data-consolidation.html` — partial re-wire (bounded, not a full rebuild)

This page was written against the FastAPI response shape; the Frappe
`api_frontend_bridge.*` endpoints return different shapes, so most panels showed
0 / "undefined". Bounded fixes in `assets/js/data-consolidation.js`
(`?v=datacons-20260904`):
- **KPI tiles** — `consolidation_summary` only returns `*_count` totals, so the
  5 tiles (`raw_reports_total` / `consolidated_needs` / … keys that don't exist)
  always read 0. Now derived from the lists actually fetched: raw =
  `rawReports.length`, consolidated = `consolidated.length`, duplicates =
  `duplicates.length`, review/aggregate = counts over `rawReports`
  `consolidation_status` / `area_level`.
- **`renderRawReports`** — rows are `RN Community Report`
  (`report_type` / `affected_people_count` / `consolidation_status` /
  `verification_status`), not the old flat shape. Fixed field names; the
  "Review Lokasi / Tandai Agregat / Verified Unique" buttons (gated on a
  non-existent `source_type === "community_report"`, so never rendered) now
  always render for these rows.
- **`renderConsolidated`** — `consolidated_needs` returns raw
  `RN Community/Logistic Need` rows → fall back
  `quantity_final ?? quantity`, `quantity_unit ?? unit`,
  `item_name || canonical_group`; `safe()`-guard the merge metadata.
- **`renderAreas`** — `operational_areas` rows are place tuples
  (`province/city/district/village_name`, `area_level`), not
  `owner_type` / `owner_id` / `verification_status` → render a location line +
  area level.
- **Verified (Playwright, logged in as LD2):** status "Loaded", KPIs
  26 / 25 / 0 / 0 / 0, 26 raw cards + 78 action buttons, 25 consolidated cards,
  **no "undefined" on the page**, 0 console errors.
- **Still legacy / not touched (needs its own session):** the national-rollup
  and rollup-trace panels are fed by `/national-rollup` → `consolidation_summary`
  which has no rollup data, so they show honest empty-states; `duplicate_candidates`
  / `consolidation_auxiliary` beneficiary-groups + evidence-requirements return
  `[]` by design. A real "consolidated needs" surface = migrate this page to
  `control_centre_summary` `item_groups` (3-bucket) — separate work unit.

---

## Three-item cleanup batch (2026-09-04) — DONE & DEPLOYED

Owner: "kerjakan semua" on the three remaining loose ends.

### 1. LD1 coordinator edit rights — the phase-3 open item, now decided: coordinator CAN edit

`community_coordinator` (LD1, no posko of their own) now has edit rights on
**every posko owned by their own organisation** (was pure-viewer through phases
1-3).

- **`access_policy.py`:** new `ORG_COORDINATOR_ROLES = {"community_coordinator"}`,
  `is_org_coordinator(actor)`, `can_coordinate_posko(actor, posko)` (true iff the
  actor is an org coordinator **and** `RN Posko.organization == actor.organization`).
  `can_manage_posko()` now returns true when `approved_posko_assignment(...)` OR
  `can_coordinate_posko(...)`. Every write guard (`api_logistics` / `api_medical`
  / `api_shelter` / `api_kitchen` / `api_volunteer` / `api_posko_contact` /
  `api_privacy` / `api_search_found` / `api_resource_tools`) picks this up
  automatically — a coordinator can now create/edit records for any sibling posko.
- **`my_org_coordination` / `posko_edit_scope`** already thread `can_manage_posko`
  per card → LD1's sibling cards now come back `can_edit:true`,
  `editable_count:5`, `can_edit_current:true`. No endpoint change.
- **`assets/js/koordinasi-organisasi.js` (`?v=koordorg-20260904`):** the
  no-`my_posko` empty state now branches on `editable_count>0` → shows
  "Anda koordinator organisasi — … bisa mengelola semua posko organisasi di
  bawah ini." (was always the pure-viewer text). The `card()` helper already
  renders "Kelola Posko" + "Bisa dikelola" when `can_edit` is true.
- **`rn-posko-scope.js` unchanged:** a coordinator opening
  `posko-logistik.html?id=<sibling>` now gets `can_edit_current:true` → no
  read-only overlay, forms visible. `primary_posko` stays null (no own posko) so
  the no-`?id=` redirect simply doesn't fire for them.
- **Deploy:** `access_policy.py` cp→`osiun-frappe-backend` (md5 host==container,
  `ast.parse` OK, backup `access_policy.py.bak-20260904-coordedit`), restart
  (502→200 ~10s). Frontend from disk.
- **Verified (`bench console` as each user + Playwright as LD1):** LD1 →
  `can_manage_posko` true for all 5 SIM-LR poskos, **false** for other-org poskos
  (`SIM-NS-*`, `posko-sim-dapur`); `my_org_coordination` `editable_count:5`, 5×
  "Kelola Posko" buttons, 0 "Hanya-lihat" tags on siblings, 3 open externals
  still `extEditTags:0`; 0 console errors. **Regression:** LD2
  (`logistics_operator`) still edits only its own posko, `false` on all siblings.

### 2. FE stock_summary contract — one real bug (dapur-umum), two dead files

Investigated the "legacy provisional shape" note. Findings:
- **`war-room.js` and `rn-control-centre-v4.js` are DEAD** — referenced only under
  `backup/`. The live Control Centre / war-room page both load
  `rn-control-centre-final.js`, which builds its critical-needs table from
  `logistic_needs.realized_quantity` and **never joins `stock_summary`** — so
  there is no live shape bug there.
- **`dapur-umum.js` `renderLegacyStock` WAS broken:** read
  `s.current_quantity ?? s.quantity ?? s.effective_quantity` but
  `api_kitchen.dashboard` sends `effective_available` (stock left after kitchen
  usage) + `snapshot_quantity` → the panel always showed **0**. Fixed to
  `s.effective_available ?? s.snapshot_quantity ?? …`, plus a
  "(snapshot N)" annotation when the two differ. `?v=dapur-20260904`.
  Verified against live `api_kitchen.dashboard?posko=posko-sim-dapur`
  (Gas LPG 1 tabung / Beras 40 kg / Air Mineral 2 dus — all now render).
- **`war-room.js` + `rn-control-centre-v4.js`** also aligned (`quantity ??
  exact_total ?? current_quantity`, group-key `canonical_group || item_name`)
  so if either is ever revived it matches the real `api_ai` / `available_stock`
  payloads. No deploy needed — dead code + FE-from-disk.
- **Not touched (still deliberate):** `control_centre_logistics.available_stock`
  has no FE consumer; the war-room "Kebutuhan Kritis" item↔stock join keys on
  `item_name` because `api_ai` `logistic_needs` rows carry no `canonical_group`.

### 3. Step 12/12 — mobile / HP pass — DONE (roadmap complete)

`osiun-playwright-check/rn-mobile-step12.js` — horizontal-overflow + page-error
sweep across **all 35 pages × {390, 360}px** (70 checks).

- **69/70 clean.** The one miss: `shelter-detail.html` overflowed at both widths
  (`docW 404 vs vw 390`). Cause: the 6-tile `.rn-sh-kpi` grid — the caption
  `<small>bayi/anak/lansia/bumil/disabilitas</small>` is one unbreakable token
  (`/` is not a CSS break opportunity) so it set each KPI card's min-content
  width and forced the grid — and the page — past the viewport, even at the
  2-column ≤640px breakpoint.
- **Fix — `assets/css/style.css`:** `overflow-wrap: anywhere` added to
  `.kpi-card span, .kpi-card small`. Global + safe (only lets long
  slash-lists / IDs / URLs in a KPI caption wrap). `shelter-detail.html`
  style.css buster → `?v=shelter-20260904`.
- **Re-verified:** shelter-detail `docScrollW == vw` at 390 **and** 360; full
  re-sweep 69/70 again (the 1 = a transient 45s nav timeout on
  `ai-settings.html` at 390 under NAS load — `ok` at 360 and on the first run,
  not a layout defect).

---

## Koordinasi Internal Organisasi — org-member workspace (2026-09-03..04) — PHASE 1 + 2 + 3 DONE & DEPLOYED

Owner brief: "jika login sbg member organisasi, spt Land Rover Club, seharusnya
yang tampil posko dia [sendiri], dia sendiri yang [me]rubah — bukan posko member
lain. Dia lebih ke viewer: yang tampil = posko member se-organisasi + posko org
lain yang open. Kalau mau lengkap, dari Control Centre. Jadi terasa sebagai
koordinasi internal organisasi." + "malahan bisa halaman seakan design Landrover".

**Finding (verified by logging in as `ld2.demo@rescue-net.local`):** the backend
permission model already does exactly this — `can_manage_posko(actor, posko)` is
true only for the member's own assigned posko, false for siblings/externals;
`effective_posko_share` already returns full for own-org + open externals,
summary for closed. **The gap was purely a missing member-facing surface** — the
existing posko pages just take `?id=` / a free switcher and never key off "who am
I logged in as".

**Built — phase 1 (a dedicated page, not surgery on the 3 posko pages):**
- **NEW `api_control_centre.my_org_coordination(disaster_event=None)`**
  (`allow_guest=True`; guests get `{logged_in:false, login_href, control_centre_href}`).
  For a logged-in `RN User Account`: `my_posko` (own assignment, `can_edit=true`),
  `my_org_poskos[]` (rest of the actor's org, `can_edit=false`),
  `open_external_poskos[]` (other orgs' poskos where `effective_posko_share=="full"`,
  event-scoped, `can_edit=false`). Each card carries `share_mode`, `operate_href`
  (routed by posko_type → posko-logistik / posko-distribusi / posko-medis-detail /
  shelter-detail / dapur-umum / posko-detail), `detail_href`. Plus `brand`
  = light per-org skin: `{title, accent, initial}` — `_ORG_BRAND_ACCENT` map
  (SIM-LR-ORG → green `#2f6f3e`) + deterministic HSL hue fallback from the org
  name (no new DB fields / migrate). Helpers `_org_brand`, `_operate_href`.
  `can_edit` is strictly `can_manage_posko(actor, posko)` — a coordinator with
  no posko (LD1) edits nothing, pure viewer, exactly per "dia lebih ke viewer".
- **NEW `pages/koordinasi-organisasi.html` + `assets/js/koordinasi-organisasi.js`**
  (`?v=koordorg-20260903`). Org-branded header (accent CSS var + initial badge),
  status line, 3 sections: **Posko Saya** (own posko card + "Kelola Posko" →
  operate_href; empty-state for no-posko coordinators), **Posko <Org>**
  (siblings, read-only cards, "Hanya-lihat" + share badge + "Lihat detail"),
  **Posko Organisasi Lain (Terbuka)** (open externals, read-only). Prominent
  "Buka Control Centre →" in the header + footer note. Not-logged-in / not-a-member
  states show a notice with login + Control Centre links. Scoped `<style>` block,
  no shared style.css change.
- **Nav:** `rn-navigation-v2.js` 2.0.5→**2.0.6**, added "Koordinasi Organisasi"
  to the Posko group. Cache-buster `navdist-20260903` →
  **`navorg-20260903`** on `rn-navigation-v2.{js,css}` across all 32 pages.
- **Deploy:** `api_control_centre.py` cp→container + restart (502→200 ~30s,
  container backup `api_control_centre.py.bak-<ts>-orgcoord`). Frontend served
  straight from `/volume1/web/rescue-net/` = already live.
- **Verified:** guest → `{logged_in:false}` clean. Real login as LD2
  (`logistics_operator`, posko `SIM-LR-POSKO-LD2`) → my_posko LD2 `can_edit:true`,
  4 sibling LR poskos `can_edit:false`, 3 open externals (Gudang Jogja / BNPB /
  Warga, all `full_authorized`). LD1 (`community_coordinator`, no posko) →
  `editable_count:0`. Playwright as LD2: green skin, all sections render,
  0 edit tags on siblings, 0 console errors.
- **Demo passwords set** (were unset): `ld1.demo@rescue-net.local` /
  `ld2.demo@rescue-net.local` → `LandRover2026!` (sim `.demo` accounts).

**Built — phase 2 (layering onto the real posko pages + brand fields):**
- **NEW `api_control_centre.posko_edit_scope(posko=None, disaster_event=None)`**
  (`allow_guest=True`). Returns `{logged_in, is_org_member, is_system_manager,
  can_edit_current, my_poskos[], primary_posko, brand, coordination_href,
  control_centre_href}`. `can_edit_current` = `can_manage_posko(actor, posko)`;
  left `true` for guests / non-members / System Managers / the real operator so
  existing flows are untouched. `my_poskos` = direct `RN User Account.posko` +
  approved `RN Posko Assignment` rows (new helper `_my_posko_names`).
- **NEW `assets/js/rn-posko-scope.js`** (`?v=poskoscope-20260903`), included on
  `posko-logistik.html` / `posko-distribusi.html` / `posko-detail.html` right
  after `rn-frappe-client.js`. For a logged-in org member only:
  (a) no `?id=` in the URL → `location.replace` to `?id=<primary_posko>` (default
  to my own posko); (b) `?id=` is a posko he does not manage → read-only mode:
  hides `.panel.create-panel` / create-form drawers (keeps read-only
  `rn-stockcards-panel`), injects a "Hanya-lihat" banner with links to *his*
  posko + Koordinasi Organisasi + Control Centre. Sweeps a few times so
  late-rendered forms are caught too. Guests / non-members / SM / real operators:
  script no-ops.
- **`RN Organization` + `brand_color` (Data) + `brand_logo` (Attach Image)** —
  editable in Desk. `_org_brand()` now prefers these, then the `_ORG_BRAND_ACCENT`
  map, then the HSL hue. `my_org_coordination` + `posko_edit_scope` return
  `brand.logo`; `koordinasi-organisasi.js` (`?v=koordorg-20260903b`) renders the
  logo in the header badge when set.
- **Deploy:** `api_control_centre.py` + `rn_organization.json` cp→container,
  `bench --site osiun.localhost migrate` (adds the 2 columns, after_migrate
  clean), restart (502→200 ~33s, backup `api_control_centre.py.bak-<ts>-scope`).
  Frontend served from disk.
- **Verified (authenticated curl as LD2):** `posko_edit_scope` — guest →
  `can_edit_current:true` (no-op); own posko LD2 → `true`; sibling LD4 →
  `false` + `primary_posko:SIM-LR-POSKO-LD2`; no posko → `primary_posko` set for
  the redirect. E2E screenshot `rn-poskoscope-ld4.png` (2026-09-03 21:44) shows
  the `posko-logistik` read-only overlay rendering for a sibling posko.

**Built — phase 3 (2026-09-04): gate the type-specific detail pages + real org brand:**
- **`assets/js/rn-posko-scope.js` (`?v=poskoscope-20260904`)** now also included on
  `posko-medis-detail.html` / `shelter-detail.html` / `dapur-umum.html` (after
  `rn-frappe-client.js`). Changes to the shared script:
  - `hideEditForms()` gained the record-form ids `#caseForm` / `#supplyUseForm`
    (medis), `#occupancyForm` / `#needForm` (shelter), `#mealForm` (dapur).
  - For a matched `<form>` the host is resolved as
    `closest("aside") || closest(".panel.create-panel") || the form itself` — so a
    record form living inside a **mixed "Riwayat" drawer** (e.g. shelter "Shelter
    Needs (Riwayat)" = history list + an `Add Shelter Need` aside) hides only the
    aside/form, never the whole drawer; the read-only history stays visible.
  - Dropped the blanket `.rn-input-drawer` selector (it would have hidden the
    read-only `#occupancyPanel` / `#stockPanel` / "Riwayat" drawers on the new
    pages; `.panel.create-panel` already covers the real create drawers on
    posko-logistik / posko-distribusi).
  - The **no-`?id=` → own-posko redirect** is now limited to
    `posko-logistik|posko-distribusi|posko-detail` (regex on `location.pathname`);
    a logistics operator opening `posko-medis-detail.html` with no id is no longer
    bounced onto a medical posko that has no data for him. Read-only gating still
    applies on all six pages when an `?id=` he can't manage is present.
- **`setup/org_brand_defaults.py`** (new) — idempotent installer, wired into
  `hooks.py` `after_install` + `after_migrate`. Seeds `RN Organization.brand_color`
  for 13 demo orgs (SIM-LR-ORG `#2f6f3e`, org-landrover `#005a2b`, SIM-NS-BNPB
  `#1f5fa8`, SIM-NS-GARUDA `#0f4c81`, SIM-NS-TNIAL `#0b3d69`, SIM-NS-PELAJAR
  `#b8232f`, SIM-NS-WARGA `#a8571e`, SIM-LOG-ORG-SOLID `#6a3d9a`, KH-ORG-BPBD /
  BKSDA / MANGGALA / MPA / TNIAU). **Skips any org whose `brand_color` was set in
  Desk** — never clobbers a hand-edited value. `brand_logo` left null on purpose:
  no first-party logo assets for these `[SIMULASI]` orgs, and the initial-badge
  already carries identity. `_org_brand()` already prefers `brand_color` over the
  `_ORG_BRAND_ACCENT` map / HSL-hue fallback, so these now flow through
  `my_org_coordination` + `posko_edit_scope`.
- **Deploy:** `setup/org_brand_defaults.py` + `hooks.py` cp→container (chown
  frappe, md5 host==container, `ast.parse` OK), `bench execute
  rescue_net.setup.org_brand_defaults.install_defaults` → 13 set / 0 skipped,
  `docker restart osiun-frappe-backend` (200 after ~16s, backup
  `hooks.py.bak-<ts>-orgbrand`). Frontend (JS + 3 HTML) served from disk = live.
- **Verified:** authenticated curl as LD2 → `posko_edit_scope` sibling LD4 returns
  `brand.accent:"#2f6f3e"` (now DB-sourced). Playwright
  `/volume1/docker/osiun-playwright-check/rn-poskoscope3.js` as LD2 vs a sibling
  posko on all 3 detail pages — **ALL PASS**: shelter-detail + dapur-umum fired
  the real "Hanya-lihat" banner live (`realBanner=true`), medis-detail confirmed
  by the deterministic selector run (endpoint round-trip timed out under NAS
  load-avg ~7, same shared code path proven live on the other two); record forms
  hidden, every read-only "Riwayat" panel still visible, 0 console errors.
  Screenshots `rn-poskoscope3-{posko-medis-detail,shelter-detail,dapur-umum}.png`.

**Phase 3 / open item — RESOLVED 2026-09-04:** `community_coordinator` (LD1, no
posko) now gets edit on **all of their own org's** poskos (not other orgs').
Implemented in `access_policy.can_coordinate_posko` — see "Three-item cleanup
batch (2026-09-04)" at the top of this file. This work unit is fully done.

---

## Konversi kuantitas — sebar ke Control Centre + Kelompok Alat (2026-09-03) — DONE & DEPLOYED

Owner: "perubahan tampilan baris item sudah di semua halaman?" → propagasi
3‑bucket (Terukur/Perkiraan AI/Belum Terukur) + satuan dasar ke surface lain.

- **NEW `packaging.bucket_quantity(...)`** — helper bucketing bersama; dipakai
  `api_logistics._row_base_split` (kini wrapper tipis), `api_intelligence._group_rows`,
  `api_resource_tools.tools_board`. `stored=<row>` → percaya field konversi
  tersimpan; `stored=None` → hitung `resolve_base_quantity` on the fly
  (RN Community Need tak menyimpan field itu). `_raw_split()` port dari
  `_split_qty`. Step **4b** baru di `resolve_base_quantity`: counter generik
  ("unit"/"pcs"/"buah") tanpa sinyal kemasan → `direct/ok` bila item tak punya
  satuan dasar lain (mis. "5 ekskavator" = terukur), tetap `needs_review` bila
  item ingin satuan lain ("100 bh" Air Minum → liter). `_BASE_ALIAS` += unit→pcs.
- **`api_intelligence._group_rows` (Control Centre consolidation):** key kini
  `(event, wilayah, canonical_group, base_unit)`. Tiap grup +`base_unit`,
  `qty_measurable`, `qty_estimated`, `qty_total`, `unmeasurable_count`. Sumber:
  RN Community Need (dihitung on the fly). Field `estimate_min/max` + `units` lama
  tetap. Dipakai Frappe `www/data-consolidation.html` (kartu diupdate: baris
  "Konsolidasi (satu satuan dasar)" + "Estimasi aman (satuan asli)").
- **`api_resource_tools.tools_board` (Kelompok Alat):** tiap grup +`base_breakdown`
  `[{base_unit, measurable, estimated}]` + `unmeasurable_count`. `unit_breakdown`
  lama tetap. `alat-kerja.js` (`?v=alatkerja-20260903a`) — kolom total pakai
  base_breakdown (±prefix utk perkiraan) + chip "N belum terukur".
- **Deploy:** packaging.py, api_logistics.py, api_intelligence.py,
  api_resource_tools.py, www/data-consolidation.html → container, restart
  (502→200 ~15s). Frontend alat-kerja.{js,html} in-place.
- **Verified:** Kelompok Alat sim: Ekskavator/Chainsaw/Forklift/Pompa/Perahu =
  5 pcs **measurable** (dulu semua estimated), Genset 5 pcs + 2 set, belum=0.
  `control_centre_summary` shape OK (data RN Community Need tipis di site ini,
  cuma 1 baris). `item_groups` regresi 0 (Air Minum 122.209,92 L sama).
- **Fragmentasi "Air Bersih*" di Control Centre — FIXED (2026-09-03).** Baris
  "Air Bersih" / "Air Bersih Siap Distribusi" / "Air Bersih (mobil tangki/
  tandon)" tampil terpisah karena `canonical_group` NULL (dibuat sebelum rule
  registry aktif) → `item_groups`/`_group_rows` fallback ke `raw_item_text`
  sebagai nama grup. Fix: (a) rule "Air Bersih" +alias ("air bersih siap
  distribusi", "tandon air", "tangki air", "air tangki", "water tank") di DB
  live + `normalization_defaults.py`; (b) `scratchpad/reclassify_null_groups.py`
  (ran) — re-`classify_text` semua baris canonical_group kosong di RN Aid Offer/
  Logistic Need/Stock Observation (non-manual), set canonical_* + re-`enrich_document`.
  Hasil: 5 baris di-reclassify → "Air Bersih · liter" jadi 1 baris 2.570.000 L.
  Sisa "still_unmatched" = teks bebas non-air, wajar.
- **Keputusan owner (2026-09-03): "Air Minum" ≠ "Air Bersih" — tetap 2 grup
  terpisah.** Air layak konsumsi vs air MCK/sanitasi = kebutuhan operasional
  beda (sumber/urgensi/penanganan). Tidak digabung. Fragmentasi di atas beda
  soal (bug klasifikasi, bukan kebijakan grup).
- **TIDAK disentuh (sengaja, dilaporkan ke owner):**
  - `stock_summary` di war-room.js / dapur-umum.js / rn-control-centre-v4.js —
    baca `ctx.stock_summary` shape **legacy provisional** (`item_name`,
    `current_quantity`) yang beda dari `control_centre_logistics.available_stock`
    (`canonical_group`, `exact_total`); kode sendiri bertanda "backend nanti
    menyediakan…". Butuh perbaikan kontrak dulu (utang migrasi FE), bukan
    tempat menambah base_quantity.
  - `control_centre_logistics.available_stock` — **tak ada konsumen FE** sama
    sekali. Enhance = no-op sampai ada yang render.
  - "Kartu Stok Rinci" (`logistik.js` stock_cards) — ledger **per-item** dengan
    laju konsumsi + estimasi habis; sengaja granular di satuan asli posko,
    bukan surface konsolidasi.
  - `pages/data-consolidation.html` — pakai `api_frontend_bridge` (list flat
    per-baris, `quantity_final`/`quantity_unit` belum diwire), bukan
    `control_centre_summary`. Setengah-migrasi.

## Normalisasi AI — registry wiring fix (2026-09-03) — DONE & DEPLOYED

Owner: "ai untuk grouping item sejenis + satuan bermacam-macam" harus **fleksibel
tapi reliable** — bukan DB rigid. Aturan editable (`RN Normalization Rule`, Desk)
harus dikonsultasi di **semua** jalur, bukan cuma hook insert.

- **Bug:** `api_intelligence.py` + `api_resource_tools.py` meng-import
  `classify_text` langsung dari `intelligence.normalization` (built-in RULES saja),
  jadi endpoint `suggest_need` / `control_centre_summary` grouping + fallback
  "Kelompok Alat" **mengabaikan** `RN Normalization Rule`. Hook insert doctype
  (aid_offer/logistic_need/community_need/stock_observation/distribution_flow)
  sudah benar (pakai `normalization_registry`).
- **Fix:** kedua file kini import `classify_text` dari
  `rescue_net.intelligence.normalization_registry` (built-in + DB rules,
  priority-ranked). `normalize_unit` tetap dari `.normalization` (registry tak
  membungkusnya).
- **Perf:** `normalization_registry._enabled_rules()` mem-memo daftar rule di
  `frappe.local` (reset per request) — `classify_text` dipanggil dalam loop oleh
  `item_groups` / `tools_board`, sebelumnya 1 query per baris.
- **Deploy:** `api_intelligence.py`, `api_resource_tools.py`,
  `intelligence/normalization_registry.py` (cp via docker exec, md5 host==container,
  `ast.parse` OK) → `docker restart osiun-frappe-backend` (502→200 ~24s). Backup
  `*.bak-<ts>-regfix` di container.
- **Verified:** `classify_text("pertalite 5 liter")` (alias hanya ada di DB rule
  "BBM", tak ada di built-in) → `canonical_group=Bahan Bakar`,
  `normalization_rule=BBM`, `matched_alias=pertalite`. `tools_board` guest 200,
  `control_centre_summary` 403 (butuh auth, wajar).
## Konversi kuantitas lintas kemasan (2026-09-03) — DONE & DEPLOYED

Owner: normalisasi tak boleh DB rigid (melibatkan awam) — RN lewat aturan
deterministik menyederhanakan + mengkonversi "mie instan dus isi 24 bh" /
"2 karung kecil" / "1 tas kresek" / "aqua gelas 100 bh" / "air mineral 2 dus" /
"5 botol" → satu kelompok + **satu satuan dasar terukur** (liter/kg/bungkus),
dengan tingkat keandalan yang jujur.

- **NEW `intelligence/packaging.py`:** `parse_packaging(text)` (regex murni, tanpa
  DB) mengekstrak `outer_quantity` ("2 dus"→2), `content_quantity` ("100 bh"→100),
  `form_unit` (kata bentuk-produk: gelas/botol/dus…), `pack_size` ("isi 24"→24),
  `pack_certainty` (explicit/constant/**unmeasurable**). `resolve_base_quantity()`
  memilih berjenjang: isi eksplisit → satuan == base unit item (direct) → tabel
  `RN Unit Conversion` → satuan dasar dikenal (direct) → paket luar tanpa faktor
  (needs_review) → heuristik. `unmeasurable` untuk "karung kecil"/"tas kresek"/
  "seadanya". Base unit pakai `_canon_base()` (ruang terpisah dari
  `normalize_unit()` yang melipat "bungkus"→"sachet").
- **NEW DocType `RN Unit Conversion`** (editable Desk, System Manager):
  scope_type canonical_item|canonical_group|global, from_unit→to_base_unit,
  factor, certainty standar|perkiraan (perkiraan → hasil ditandai needs_review),
  priority. Seed `setup/unit_conversion_defaults.py` = **21 baris** (Air Minum
  Kemasan gelas/botol/dus/karton/galon/jerigen→liter; Mie Instan dus/karton/pak/
  renceng→bungkus; Beras karung/sak/liter→kg; Minyak Goreng dus/jerigen/botol→
  liter; group-level Air Minum/Bahan Pangan; global lusin/kodi/gross→pcs).
- **+5 field × 3 DocType** (RN Aid Offer / Logistic Need / Stock Observation):
  `base_quantity`, `base_unit`, `pack_size`, `conversion_source`
  (none/explicit/table/direct/heuristic/manual), `conversion_status`
  (ok/needs_review/unmeasurable). Diisi di `before_insert` via
  `packaging.enrich_document(doc)` (tak menimpa nilai manual).
- **+2 normalization rule** (Mie Instan, Minyak Goreng) supaya konversi bisa
  menyasar `canonical_item`.
- **`api_logistics.py`:** `_row_base_split()` = 3 ember (TERUKUR = konversi
  dipercaya & bukan estimasi; PERKIRAAN AI = konversi kabur / input estimasi;
  BELUM TERUKUR = tanpa angka / kemasan tidak baku). `item_groups` sekarang
  di-key `(canonical_group, base_unit)` → satu baris per kelompok, output
  `qty_measurable` / `qty_estimated` / `qty_total` / `unmeasurable_count` /
  `conversion_review` (+ alias lama `qty_exact`/`estimate_member_count` untuk
  cache frontend). `item_group_members` +field konversi + `measured_bucket`.
  `correct_item_normalization` +arg `base_quantity` / `base_unit` / `pack_size`:
  isi eksplisit → base = qty×pack_size; base_quantity manual → apa adanya;
  else → `resolve_base_quantity` ulang. Semua → conversion_source=manual.
- **`hooks.py`:** `after_install` + **NEW `after_migrate`** menjalankan kedua
  installer (idempotent).
- **Frontend:** `assets/js/rn-item-groups.js` (`?v=itemgroups-20260903c`) — kolom
  Terukur / Perkiraan AI / Total / Belum Terukur; drill menamp: input asli,
  isi/kemasan, kuantitas dasar, badge konversi; form Koreksi +field "Isi per
  kemasan" & "Kuantitas dasar". `pages/posko-logistik.html` header + deskripsi.
- **Deploy:** 14 file backend cp→container, `bench --site osiun.localhost migrate`
  (buat tabel RN Unit Conversion + 15 kolom, after_migrate seed OK), restart
  (502→200 ~15s). Backfill `scratchpad/backfill_base_quantity.py` → 29 Aid Offer
  + 37 Logistic Need + 43 Stock Observation di-enrich.
- **Verified:** 10 kalimat awam parser+resolver (mie dus isi 24→24 bungkus;
  karung kecil / tas kresek / seadanya → unmeasurable; aqua gelas 100→24 L;
  2 dus→11.52 L; 3 karung beras→75 kg; 2 jerigen migor→36 L; 5 dus isi 10
  strip→50). `item_groups` guest 200: "Air Minum" 21 anggota → 1 baris
  122.209,92 liter (semua perkiraan, conv?=21). `correct_item_normalization`
  pack_size=24: 160→96 bungkus, source=manual/ok/accepted. Drill Bahan Pangan/kg
  → Beras direct/terukur.
- **Catatan:** faktor dus/karung sengaja `perkiraan` → masuk kolom "Perkiraan
  AI", bukan "Terukur", sampai koordinator set `standar` di Desk atau posko
  koreksi. Bare "air" (tanpa "minum"/"mineral") masih tak terklasifikasi —
  di luar scope ini.

## Manajemen Distribusi ↔ Posko Distribusi split (2026-09-03) — DONE & DEPLOYED

Owner: keep **Manajemen Distribusi** data+layout **persis mock-up**
(`manajemen distribusi.png`) = the coordination dashboard. Move the
armada/space/booking registration to a separate **Posko Distribusi** =
the transport-provider posko (`posko_type='transport'` — already an option in
registrasi-posko): bisa Garuda, kapal TNI AL, motor pick-up, Land Rover club.

- **`pages/management-distribusi.html` reverted to mock-up-exact:** removed the
  "Armada Distribusi Posko" panel, "Pencocokan Relawan Pickup" panel, and the
  3 drawers (`#armadaForm` / `#bookingForm` / `#bookingConfirmForm`). Left: 6
  KPI, Papan Pencocokan, **Ruang Transportasi** (donut legend now
  **Tersedia / Terpakai / Blocked** per the mock-up — `_cap_bucket` gained
  `blocked_m3` = confirmed+requested booking volume, donut is a 3-stop
  conic-gradient), Alur Distribusi, Peringatan, Pedoman/Panduan/Trace, + the
  pre-existing `<details>` history drawers. One-line xref → posko-distribusi.
  `distribusi.js` stripped of all armada/booking code. `?v=distribusi-20260903e`.
- **NEW `pages/posko-distribusi.html` + `assets/js/posko-distribusi.js`:**
  transport-provider workspace, scoped `?id=<posko>&event=`. Posko switcher
  (from `transporter_poskos`), 4 KPI (Armada Terdaftar / Kapasitas Total /
  Kapasitas Terpakai / Booking Menunggu), **Armada Terdaftar** table (row →
  `#pdDrill` detail modal with booking inbox for that armada), **Booking
  Masuk** table with inline **Konfirmasi (PIN) / Tolak** per requested row,
  **Relawan Pickup** panel + assign/unassign form, `<details>` **Daftarkan
  Armada** form (`create_transport_space`, `coordination_posko` = current
  posko). `?v=poskodist-20260903`.
- **Backend:** NEW `api_control_centre.posko_distribusi_board(posko,
  disaster_event)` guest — posko_info + `is_transport_posko` + armada[] (with
  capacity block) + booking_inbox[] (contacts + PIN) + relawan_candidates[] +
  totals + transporter_poskos[]. Deployed to `osiun-frappe-backend` + restart
  (no migrate). Write endpoints reuse the existing
  `create_transport_space` / `confirm_`/`reject_transport_booking` /
  `assign_pickup_volunteer`.
- **Nav:** `rn-navigation-v2.js` 2.0.4→**2.0.5**; `CONFIG.posko` "Posko
  Distribusi" now → `posko-distribusi.html`; `CONFIG.modules` gained
  "Manajemen Distribusi". Cache-buster `navcomms-20260903` →
  **`navdist-20260903`** on `rn-navigation-v2.{js,css}` across all pages.
- **Seed `scratchpad/seed_poskodist.py` (ran):** every `RN Transport Space`
  reassigned to a transporter posko by provider keyword
  (Garuda/TNI-AU→`SIM-NS-POSKO-GARUDA`, TNI-AL/KRI/Ro-Ro→
  `SIM-NS-POSKO-TNIAL-SHIP`, pickup/motor/truk→`SIM-NS-POSKO-PELAJAR`, Land
  Rover→`SIM-LR-POSKO-LD3`, heli→`KH-POSKO-HELIBASE`) + 3 vivid new armada
  (Garuda 737F, KRI Teluk Bintuni LST, LRCI konvoi 8-unit) + 1 booking
  (SIM-BOOK-GRD-1). The old SIM-ARMADA-* bookings follow their
  `transport_space` link.
- **Verified:** guest HTTP `posko_distribusi_board` for all 4 sim transporter
  poskos; Playwright `rn-dist-split.js` — MD has no armada panel + donut
  legend Tersedia/Terpakai/Blocked; PD KPI/tables/modal/switcher/mobile all
  OK, 0 JS errors.
- **Follow-ups (`0c47a20`):** MD header toolbar per mock-up — search box
  (filters Alur Distribusi rows), status filter select, "+ Buat Distribusi"
  button → opens the Buat Distribution Flow drawer (`#flowDrawer`). Alur rows
  cached in `ALUR_ALL`, re-rendered via `applyAlurFilter()`.
  `?v=distribusi-20260903f`.
- **E2E booking chain verified (`scratchpad/e2e_booking2.py`):** book (normal
  user) → `requested` + PIN, capacity soft-held (200000→198500 kg avail);
  confirm (System Manager / coordinator) with PIN → `confirmed`, held→used,
  `capacity_committed_*` recomputed; both boards reflect it (PD inbox
  "Terkonfirmasi", MD Ruang Transportasi LAUT `blocked_m3` = booking volume);
  a non-coordinator user gets PermissionError on confirm (gate works);
  cancel + delete restores capacity cleanly.

## Full-app health sweep (2026-09-03) — 22 pages, 2 real bugs found + fixed

Playwright `rn-health-sweep.js` (guest load + data-presence + console/HTTP
errors across every rebuilt page). 20/22 clean. Two fixes (`0-…` commit):
- **Broken image** `assets/img/demo-landrover/evidence/logistik.jpg` (404) —
  one DB row `RN Community Report SIM-LR-RPT-LOGISTIK` had that path in its
  `legacy_payload.evidence.image`; the file never existed. Repointed to the
  real `evidence/pnbp_posko_logistik.jpg` via `frappe.db.set_value` (data
  fix, not a repo change).
- **Welcome page live summary + Bencana Aktif list broken for guests
  (`assets/js/api.js`, `?v=pubctx-20260903b`):** (a) `/ai/context/` route
  called login-only `rescue_net.api_ai.context` → switched to guest
  `api_ai.public_context` (no auth loosening — public_context was already
  `allow_guest`); (b) `/disasters` mapping returned
  `compat.api.disasters`'s wrapper `{mode, cutover_allowed, disasters:[…]}`
  as-is, so `disasters.filter/.map` threw — now unwraps `.disasters` and
  normalises canonical field names (`legacy_id`→`id`, `title`→`name`,
  `location_summary`→`location`, `event_status`→`status`). Verified guest:
  6 active disasters / "3 critical" / 18 posko / 8 needs / 7 volunteers, 6
  disaster cards, **0 console errors**.
- Deliberately left (owner "Jangan, biarkan"): `api_donor_program.context`
  403 in the Program Khusus legacy drawer; `api_sync.pull` 403 polling.

## Shared evidence lightbox (2026-09-03)

Owner: evidence photos should enlarge in-page like the Control Centre "Bukti
Lapangan" modal, not open in a new tab. Dapur Umum / Shelter / Evidence
Center thumbnails were plain `target="_blank"` links.

- NEW `assets/js/rn-lightbox.js` + `assets/css/rn-lightbox.css` — one shared
  click-to-enlarge overlay (image + caption + meta + "buka di tab baru" +
  ←/→ within a group + ESC/backdrop close). Auto-binds by capture-phase
  click delegation on `a.rn-bukti-thumb`, `a.rn-ev-cell`,
  `.rn-dp-evidence-strip a`, `[data-rn-lightbox]`, `img[data-zoomable]`;
  also `window.RNLightbox.open({src,caption,meta})`. Skips non-image hrefs
  and `[data-no-lightbox]`.
- Wired into `dapur-umum.html` / `shelter-detail.html` / `evidence.html`
  (css `?v=lb-2`, js `?v=lb-2`); their `renderBukti`/row builders now emit
  `data-caption` + `data-meta` from the evidence row (caption stripped of a
  leading `[tag]`), and evidence.js marks non-image rows `data-no-lightbox`.
  JS cache-busters: dapur `?v=dapur-20260903c`, shelter
  `?v=shelter-20260903c`, evidence `?v=evidence-20260903c`.
- Control Centre (`evidenceModal`) and Posko Logistik (`buktiModal`) keep
  their own richer bespoke modals — not touched.
- Verified Playwright `rn-lightbox.js`: all 3 pages open the overlay with the
  enlarged image loaded + caption; nav arrows only when >1 photo; ESC closes;
  0 console errors.

## Kirim Bantuan — multi-item per submission (2026-09-03)

Owner: "buat item barang bisa tidak satu barang". `kirim-bantuan.html` had a
single Item/Jumlah/Satuan trio.

- **`kirim-bantuan.html`**: those 3 fields replaced with a repeatable
  `.rn-aid-items` block — a `<template data-aid-row-tpl>` row (item / jumlah /
  satuan / ✕), "＋ Tambah item" button; last row's delete is disabled.
  `?v=aidmulti-20260903` on style.css + public-aid.js.
- **`public-aid.js`**: `initAidItems(form)` manages the rows and exposes
  `form.__collectAidItems()` / `__resetAidItems()`. Submit now collects the
  array, validates each row has qty+unit, and calls the new
  `create_user_aid_offer_multi`. `renderCreateSuccess` lists every created
  Aid Offer ID + item.
- **Backend `api_logistics.create_user_aid_offer_multi`** (login, same gate
  as the single version): takes `items_json` (list of {item_text, quantity,
  unit, quantity_mode?}) + shared donor/delivery fields; loops
  `create_user_aid_offer` → one `RN Aid Offer` per item (the app models an
  offer as one item/qty/unit); blank rows skipped; ≤30 rows; returns
  `{aid_offers:[…], count, handling_mode, target_posko}`. Deployed to
  `osiun-frappe-backend` (restart, no migrate).
- Verified: console `create_user_aid_offer_multi` → 3 offers from one call
  (blank row skipped), shared donor/notes; Playwright — add/remove rows,
  `__collectAidItems` returns the array, delete disabled at 1 row, 0
  overflow / errors.

## End-to-end simulation run (2026-09-03) — 8 scenarios

Scripts: `scratchpad/e2e_final.py` (data flows) + `osiun-playwright-check/
rn-e2e-ui.js` (guest reads, mobile, images).

| # | scenario | result |
|---|---|---|
| 1 | donatur → posko: multi-item aid → boards → `auto_match_distribution` | PASS — 2 RN Aid Offer, boards load, auto-match created 3 RN Distribution Flow |
| 2 | transporter: book space → PIN confirm → capacity blocked | PASS — held 1200 kg → confirmed → MD "Blocked" donut = 5 m³ → PD inbox → cancel frees |
| 3 | cross-role: register → approval → role granted | PASS — pending/no-role → `approval_action(kind=user, name, action=approve)` → role=relawan, status approved |
| 4 | connectivity crisis: posko `disconnected` → comms KPI + alert | PASS — Posko Tidak Terhubung KPI +1, posko in Peringatan Konektivitas (restored after) |
| 5 | evidence consistency + broken images | PASS after fix — Control Centre evidence ⊆ Evidence Center ⊇ posko bukti; **found & fixed 4 DB rows** (`SIM-LR-RPT-TRANSPORT/-SAMATIGA/-WOYLA/-KAWAY`) pointing at non-existent `evidence/{transport,woyla,kaway,samatiga}.jpg` → repointed to real evidence photos (data fix, no repo change — `scratchpad/fix_ev_imgs.py`). Now 0 broken images on any page. |
| 6 | multi-event isolation sim-001 vs karhutla | PASS — armada sets disjoint (9 vs 1), comms poskos disjoint (18 vs 9), `kpi_drilldown(kebutuhan)` groups differ (6 vs 4) |
| 7 | mobile 390px on 6 flow pages | PASS — 0 horizontal overflow, 0 JS errors |
| 8 | guest read vs write | PASS — 11 board endpoints return 200 for guest; `book_transport_space` / `confirm_transport_booking` / `create_user_aid_offer` / `approval_action` all reject guest |

Only real defect surfaced was #5's stale image paths (fixed). Everything
else passed on the first real assertion; earlier "failures" in the run log
were test-script bugs (json.dumps of datetimes, wrong kwarg names, a phone
string with letters).

## Aid pickup: per-item ready-at + active/passive Posko Distribusi (2026-09-03)

Owner: item list needs a per-item "kapan siap" (siap bisa beda-beda); an
*active* transporter posko (motor pick-up, Land Rover club) can **book to
pick up** an aid offer and choose which posko it delivers to; passive poskos
only provide space.

- **`create_user_aid_offer_multi`**: each `items_json` row may carry its own
  `ready_at` (falls back to the shared one). `kirim-bantuan.html` item row
  gained a "Siap" field (`?v=aidmulti-20260903b`).
- **`RN Distribution Flow`**: `VALID_STATES` += `pickup_claimed` (doctype .py,
  cp + restart).
- **`api_logistics.claim_aid_pickup(transporter_posko, aid_offer,
  destination_posko, eta?, note?)`** (login, `_can_contribute` on the
  transporter posko + `_posko_is_active_pickup` check): creates an
  RN Distribution Flow (`flow_status=pickup_claimed`, `transport_provider` =
  posko title, `title` set) linking offer→destination; sets the aid offer
  `offer_status=pickup_claimed` + a "Akan dijemput oleh X → Y" note; rejects
  a second claim.
- **`api_control_centre`**: `_DISTRIBUSI_STATUS_LABEL["pickup_claimed"] =
  "Akan Dijemput"`, added to `_INTRANSIT_STATES` (NOT `_DRILL_BLOCKED_FLOW`,
  so it does NOT count in "Distribusi Terhambat"). `posko_distribusi_board`
  now returns `is_active_pickup` / `pickup_mode_label`, `pickup_queue` (open
  aid offers needing pickup, minus already-flowed), `destination_options`
  (event poskos, non-transport).
- **`posko-distribusi.html` / `.js` (`?v=poskodist-20260903b`)**: header
  "Pickup Aktif" / "Pasif — Hanya Sediakan Space" badge; new "Antrean Pickup
  Bantuan" panel (active poskos only) — per row a destination `<select>` +
  "Ambil & Antar" → `claim_aid_pickup`; passive poskos see a note instead.
- Verified console: per-item ready_at stored, active/passive badge, queue
  gated, claim → "Akan Dijemput" in Alur (not in Terhambat KPI), leaves
  queue, dup-claim rejected. Playwright: both pages render, 12 claim rows,
  0 errors.

## AI Analyst page fixed for guests + friendly proxy-error message (2026-09-03)

Owner hit "Sync failed: Frappe returned non-JSON: <!DOCTYPE html>…" on the AI
page. Two causes: (1) they loaded it during one of this session's backend
restarts → 502 → the Synology reverse-proxy HTML error page; (2) the page ran
`rn-sync-engine.js` (offline field-queue) which calls login-only
`api_sync.pull` → 403 shown raw, and `ai-analyst.js` called login-only
`api_ai.context` → whole dashboard broke for guests.

- **`rn-frappe-client.js` + `rn-sync-engine.js` (`?v=nonjson-20260903`, all
  pages):** a non-JSON body that starts with `<!doctype`/`<html>` now throws
  "Server sedang tidak tersedia (mungkin restart). Coba lagi sebentar." with
  `err.transient=true`; the sync engine shows a calm "Sync ditunda…" for
  transient / 502-504 instead of dumping HTML.
- **`ai-analyst.js` (`?v=ai-guestfix-20260903`):** `loadAiContext` now calls
  guest-safe `api_ai.public_context` (not `api_ai.context`) and no longer
  gates on `ensureSession()`; `frappeCall` strips HTML tags from error
  bodies and maps 403 → "Perlu login untuk fitur ini."; the "Tanya AI" form
  still needs login. **Removed `rn-sync-engine.js` from `ai-analyst.html`** —
  it is a read-only analysis dashboard, nothing to queue.
- Verified Playwright (guest): AI page loads context (Posko 18 / Needs 31,
  15 recommendations, 11 sources), `RNSync` not loaded, 0 console errors.

## AI item/unit grouping — checked + improved (2026-09-03)

Owner asked "ai untuk mengroupkan satuan dan item2 yang sejenis, jalan
nggak?". Findings + fixes:

- **Item grouping WORKED** (rule-based `classify_text()` — deterministic
  keyword map, honestly labelled "rule", not a black-box AI). Visible live in
  Alat Kerja → "Kelompok Alat (Normalisasi AI Lintas Posko)"
  (`tools_board.groups`). Term lists were thin — **added ~30 terms**
  (AMDK / le minerale / indomie / mie / sarden / kornet / susu / biskuit /
  nasi kotak / paracetamol / oralit / antiseptik / vitamin / popok /
  pembalut / tikar / sleeping bag …).
- **Unit normalisation was MISSING entirely** — "dus"/"Dus"/"kardus"/"box"/
  "karton" were 5 separate rows. Added `normalization.normalize_unit()` +
  `_UNIT_SYNONYMS` map (dus·kg·pcs·liter·karung·paket·botol·tablet·set·… ~25
  canonical units, case-folded, plural-trimmed). Applied in
  `api_resource_tools.tools_board` unit_breakdown and
  `api_logistics` stock_summary grouping keys.
- **Coverage was ~0 on seed data** — `RN Aid Offer`/`RN Logistic Need`
  `before_insert` classifies only non-legacy rows, and every demo row has a
  `legacy_id` → never classified. Backfilled via
  `scratchpad/backfill_canon.py` (`classify_text` over existing rows):
  RN Aid Offer canonical_group **1/29 → 19/29**, RN Logistic Need +24,
  RN Stock Observation +1. Grouped view now shows e.g. "Air Minum — 10 offers
  [3653 dus]", "Bahan Pangan — 5 [3025 kg · 1850 paket · 100 karung]".
- Deployed (normalization.py + api_resource_tools.py + api_logistics.py, cp +
  restart, no migrate). Verified console + Playwright (Kelompok Alat panel: 8
  groups, units folded "unit"→"pcs").
- Still `— (belum)` for rare/brand terms — expand `RULES` term lists or use
  the `RN Normalization Rule` DocType (config-driven, `normalization_registry`
  already reads it) as more real vocabulary appears.

### Kelompok Barang panel + posko-side correction (2026-09-03)

Owner: a group's total must show **kuantitas akurat + perkiraan AI**,
clickable to detail, correctable by the receiving posko (ubah kemasan /
jadikan satu).

- **`api_logistics` (3 guest/login endpoints):**
  - `item_groups(disaster_event, posko?, kinds?)` — rolls up RN Aid Offer +
    RN Logistic Need + RN Stock Observation by `(canonical_group,
    normalize_unit(unit))`. Each group: `qty_exact` (mode=exact/unknown),
    `qty_estimated` (mid of range / estimated rows), `est_range`,
    `estimate_note`, `member_count`, `needs_review` (status=suggested),
    `posko_spread`, `source`.
  - `item_group_members(group, disaster_event, unit?, posko?)` — the member
    records with full normalisation detail for the drill.
  - `correct_item_normalization(doctype, name, canonical_group?,
    canonical_item?, unit?, quantity?, quantity_mode?, note?, also_apply?)`
    — login, `_can_contribute` on the record's posko. Sets
    `normalization_status=accepted` / `source=manual`. `also_apply` = JSON
    list of {doctype,name} → "jadikan satu" in one approval.
- **NEW `assets/js/rn-item-groups.js`** (self-contained widget, mounts into
  `#itemGroupPanel`, injects its own `#rnIgModal`): table with Kuantitas
  Akurat / Perkiraan AI / Total columns; row → drill modal listing members
  with a per-member "Koreksi" form (satuan/kemasan, pindah kelompok, tandai
  akurat) + a "Jadikan Satu" merge bar.
- **`posko-logistik.html`**: new visible "Kelompok Barang (Normalisasi AI)"
  panel before "Kartu Stok Rinci"; loads `rn-item-groups.js`
  (`?v=itemgroups-20260903b`), css `?v=logistik-mockup-20260903d`. Widget is
  posko-scoped via `?id=`.
- Seeded 2 estimate/range needs (`E2E-EST-1` "Air mineral ~500 dus",
  `E2E-RNG-1` "Beras 200-300 karung") so the akurat-vs-perkiraan split is
  visible.
- Verified: console `correct_item_normalization` (unit→karton, group move,
  mode→exact, status→accepted) + merge (`also_apply` 3 rows) + revert;
  Playwright — panel renders posko-scoped groups, drill opens (7 members,
  merge bar, correction form toggles), 0 errors.

## Icon set (STARTED, not wired) — `assets/js/rn-icons.js`

Owner chose "full SVG icon set (menu + KPI)". `rn-icons.js` is committed but
**not loaded anywhere yet** — a dependency-free inline-SVG registry
(`window.RNIcon(name)`, auto-fills `[data-icon]`, `rn:icons-refresh` event,
~40 Lucide-style 24px stroke icons + alias table for module/KPI names).
Next: bump `rn-navigation-v2.js` (add `icon` per CONFIG entry + render in
`linkHtml`/group summary, version 2.0.5→2.0.6, cache-buster), load
`rn-icons.js` before it on all pages, then add `data-icon="…"` to every
`.kpi-card` across the rebuilt pages.

## Distribusi booking UX pass (2026-09-03) — DONE & DEPLOYED

Owner feedback on the armada booking:
1. whole armada row = link to the **posko penyedia transport** (drop the
   separate "detail →" link);
2. clicking **Booking** opens a form **scoped to that posko's armada** — pick
   the **waktu**, the **space** used, and **antar sendiri vs pakai transporter
   posko**;
3. after booking, the **posko distribusi side has the data + a contact person
   to follow up** — both the *pensuplai* (booker) and the *transporter*.

- **`RN Transport Booking` +2 fields** (migrated): `delivery_method`
  (use_transporter / self_deliver), `requested_window` (Data).
- **`api_logistics.book_transport_space`:** takes `delivery_method` +
  `requested_window`; rejects `use_transporter` on a `space_only` armada.
- **`api_control_centre.distribusi_board`:** armada rows now also expose
  `transporter_contact_person/phone`; each `bookings[]` row carries
  `delivery_method(+label)`, `requested_window`, and
  `supplier_contact_person/phone` — so the coordinating posko has both
  follow-up contacts.
- **Frontend (`?v=distribusi-20260903c`):** armada `<tr>` is now
  `rn-ba-row` → `posko-detail.html?id=<coordination_posko>` (Booking button
  `stopPropagation`s). Booking drawer: `#bookingContext` header (posko
  penyedia, armada+mode, jadwal, sisa kapasitas, titik serah terima),
  `transport_space` is a locked hidden input, `requested_window` +
  `dropoff_location` prefilled from the armada, `delivery_method` radios
  (use_transporter disabled + self_deliver auto-checked when the armada is
  `space_only`). Bookings sub-row redesigned to a 3-col layout showing
  Pensuplai contact + Transporter contact + status/id. Radio-safe form
  serializer (skips unchecked radios).
- **Verified:** guest HTTP — SIM-BOOK-1 "Pakai transporter posko", SIM-BOOK-2
  "Antar sendiri", each with supplier contact; armada carries transporter
  contact. Playwright `rn-booking-ux.js` / `rn-armada3.js`.
- **Follow-up fix (`beee112`, `?v=distribusi-20260903d`):** armada row click
  was going to `posko-detail` of the coordination posko (read as "dumped into
  Posko Logistik"). Now it opens an **armada detail modal** (reuses
  `#distribusiDrill`) — penyedia/posko pengelola/mode/kebijakan/kapasitas
  total+sisa/jadwal/lokasi/rute/serah terima+narahubung/relawan/booking masuk
  with supplier contacts — plus a "Booking di armada ini" button and a
  secondary "Buka posko pengelola →" link. Also: the Armada + Pencocokan
  Relawan Pickup sections were `.content-grid` (1fr + 370px rail) so a lone
  panel used ~70% width — added `.rn-md-wide` (single column) so the panel
  fills the content area. 0 overflow at 1440/390/360px.

## Step 12 — mobile/HP responsive pass — VERIFIED CLEAN (2026-09-03)

Playwright `rn-mobile-sweep.js` (17 rebuilt pages × {390px, 360px} = 34
checks): **0 horizontal overflow, 0 JS errors**. `rn-mobile-ux.js` sample:
KPI grid collapses to 2 columns at 390px, sidebar out of flow + hamburger
present, every `.rn-table-wrap` scrolls (no clipping). The global fix from
earlier steps (`.content-grid > *, .kpi-grid > * { min-width:0 }` +
`minmax(0,1fr)` breakpoints) covers it; the two new pieces this session were
built with `minmax(0,1fr)` breakpoints from the start. The HP mockup's
bottom-tab-bar was **not** added — the app's established mobile pattern is the
`rn-mobile-drawer.js` hamburger drawer, which already serves navigation; a
bottom nav would touch all 28 pages for no functional gain.

## Manajemen Distribusi — armada jadi bookable + kurir pickup (2026-09-03) — DONE & DEPLOYED

Owner follow-up: the armada list must sit **directly under the KPIs**, and
space/waktu must be **real DB fields** (selectable / bookable / blocking
available capacity), tied to **relawan-transport pickup matching** — "di
distribusi ini adalah penyedia space sekaligus antarkan barang, ada yang
sifatnya spt kurir pick up".

- **`RN Transport Space` +9 fields** (migrated): `departure_at` / `eta_at`
  (Datetime — the old `departure_time`/`eta` Data stay as freeform fallback),
  `service_mode` (space_only / courier_pickup / both), `booking_policy`
  (pin_verify / open), `capacity_committed_kg` / `_m3` (read-only, recomputed),
  `pickup_volunteer` (Link RN Volunteer Profile) + `pickup_volunteer_name`.
- **NEW DocType `RN Transport Booking`** (migrated): transport_space + cargo +
  qty_weight_kg/qty_volume_m3 + pickup/dropoff + contact + status
  (requested/confirmed/rejected/cancelled/completed) + verification_pin +
  timestamps. Confirmed bookings block capacity; requested ones soft-hold it.
- **`api_logistics.py`:** `create_transport_space`/`update_transport_space`
  extended (service_mode, booking_policy, departure_at, eta_at). NEW
  `book_transport_space` (any login — checks available capacity, open policy →
  auto-confirm, else returns a 4-digit PIN), `confirm_transport_booking`
  (coordinator + PIN), `reject_transport_booking`, `cancel_transport_booking`
  (booker or coordinator — frees blocked space), `assign_pickup_volunteer`
  (coordinator links a relawan as courier). Helpers `_transport_capacity`,
  `_recompute_transport_committed`.
- **`api_control_centre.distribusi_board`:** transports query + the new fields;
  fetches `RN Transport Booking`. `armada_posko[]` rows now carry
  `service_mode(_label)`, `booking_policy`, capacity block
  (`kapasitas_total_kg/m3`, `kapasitas_tersedia_kg/m3`, `kapasitas_pct`),
  `pickup_volunteer_name`, `bookings_count`, `bookings[]`. NEW top-level
  `pickup_matches[]` — courier-capable armada with no volunteer + candidate
  relawan (distribution assignments at the same posko) + open-need count.
- **Frontend** (`management-distribusi.html` / `distribusi.js` / `style.css`,
  `?v=distribusi-20260903b`): the **Armada Distribusi Posko** panel moved to
  directly under the KPI grid; table reworked to Mode badge / capacity meter
  (tersedia vs total, blocked space shaded) / Berangkat→Tiba / Serah Terima+
  Narahubung / Relawan Pickup / Status+booking count / **Booking** button;
  confirmed+requested bookings render as an expandable sub-row. New
  "Pencocokan Relawan Pickup" panel from `pickup_matches`. New drawers:
  **Booking Ruang Armada** (`book_transport_space`, shows returned PIN) and
  **Konfirmasi / Tolak Booking** (`confirm_`/`reject_transport_booking`).
  Register-armada form: Berangkat/ETA → `datetime-local`, + Mode Layanan &
  Kebijakan Booking selects.
- **Deploy:** 3 files + new doctype dir → `osiun-frappe-backend` (md5
  verified) → `bench migrate` (exit 0) → restart. Seed
  `scratchpad/seed_booking.py`: structured schedule + service_mode on the 3
  SIM/KH armada, 2 `RN Transport Booking` (SIM-BOOK-1 confirmed, SIM-BOOK-2
  requested) on SIM-ARMADA-DARAT-1, 1 relawan pickup assigned.
- **Verified:** guest HTTP — SIM-ARMADA-DARAT-1 shows tersedia 3050/4000 kg
  (450 confirmed + 500 held blocked), 2 bookings, relawan "Yusuf Hidayat",
  4 pickup_matches. Playwright `rn-armada2.js` — armada panel is section #2
  (right under KPIs), 6 cap bars, 18 mode chips, 6 booking buttons, booking
  drawer prefills the space id, confirm drawer opens, register form has the 4
  new inputs, 0 mobile overflow, only the pre-existing guest 403.

## Step 11/12 — Alat Komunikasi (NEW PAGE) — DONE & DEPLOYED (2026-09-03)

`pages/alat-komunikasi.html` + `assets/js/alat-komunikasi.js` — matches
`assets/img/mockup/alat komunikasi.png`. 6 KPI (Alat Komunikasi Aktif / Posko
Tidak Terhubung / Repeater Aktif / Internet Darurat Dibutuhkan / Operator Radio
Dibutuhkan / Baterai Kritis, all clickable → `#komDrill` modal), Inventari Alat
Komunikasi table (Kategori/Total/Aktif/Cadangan/Tidak Aktif/Perlu Perhatian +
total footer, tab Semua/Perlu Perhatian), Operator Radio list (+ Tambah
Operator), Konektivitas Posko (legend Terhubung/Lemah/Tidak Terhubung/Belum
Terdata + posko table + Lihat Peta), Status Daya & Baterai (bar per unit,
lowest first), Status Frekuensi & Jaringan table, Peringatan Konektivitas
`.event-card` list. Plus 3 collapsed create forms (device / operator / freq).

- **3 new DocTypes** (`bench migrate` OK): `RN Comms Device` (existed
  half-built — kept), `RN Comms Operator`, `RN Comms Frequency`. Minimal JSON
  shape like every other doctype in the app.
- **2 RN Posko Custom Fields** (via seed script, no migrate):
  `rn_comms_status` (connected/weak/disconnected), `rn_comms_last_contact`.
- **`api_comms.py` (NEW):** `comms_board(disaster_event)` guest — one payload
  (totals + kpi_items + inventory + inventory_total + konektivitas + operators
  + daya_baterai + frekuensi + peringatan). Connectivity = explicit posko flag,
  else derived from that posko's device rows; poskos with neither → **"Belum
  Terdata"** (NOT counted as an outage, so KPIs stay realistic). Battery skips
  mains-only categories (antena_mast/vsat) and Int-NULL→0 phantom rows. Writes
  (login): `create_comms_device` / `update_comms_device` /
  `create_comms_operator` / `create_comms_frequency` / `set_posko_comms_status`.
- **Nav:** `rn-navigation-v2.js` CONFIG.version 2.0.3→**2.0.4** + new
  "Posko Alat Komunikasi" entry in `CONFIG.posko`; cache-buster
  `navfix-20260902`/`warroom-navfix-20260902`/`poskofn-20260831` →
  **`navcomms-20260903`** on `rn-navigation-v2.{js,css}` across all `pages/*.html`
  + `index.html`.
- **Deploy:** api_comms.py + 3 doctype dirs piped to `osiun-frappe-backend`
  (md5 verified) → `bench migrate` (exit 0) → restart. Seed
  `scratchpad/seed_comms.py` (idempotent): custom fields + 17 devices + 7
  operators + 11 frequencies for event-sim-001 & karhutla + 7 posko
  connectivity flags.
- **Verified:** guest HTTP `comms_board` sim-001 → KPI 9/1/1/1/0/2, konektivitas
  2/1/1/14-belum-terdata; Playwright `rn-komunikasi.js` — 6 KPI, 7 inv rows +
  footer, 5 operators, 18 conn rows, 10 battery, 8 freq, 5 alerts, drill opens,
  Perlu Perhatian tab filters to 3, operator form opens, 0 mobile overflow,
  only the pre-existing guest `session_info` 403.
- **Left:** Step 12 (final mobile/HP pass). `contact-directory.html` untouched
  (separate concern — it's a contact list, not comms-equipment).

## Armada Distribusi Posko — koordinasi penyerahan (2026-09-03) — DONE & DEPLOYED

Owner ask (per `blueprint/DISASTER MANAGEMENT SYSTEM (1).docx` → *Management
Distribusi*: "Link dengan pihak lain, kapasitas, pihak yang dihubungi"): let a
posko register its **armada distribusi** (kendaraan darat / kapal / pesawat)
with capacity, jadwal berangkat + ETA, current location, handover point, and a
contact number for koordinasi penyerahan.

- **DocType — `RN Transport Space` gained 5 fields** (`rn_transport_space.json`,
  `bench migrate` run OK): `current_location`, `handover_location`,
  `handover_contact_person`, `handover_contact_phone` (Data), `coordination_notes`
  (Small Text). Container backups `*.bak-20260903-*-armada`.
- **Backend `api_logistics.py`:** `create_transport_space` extended with those 5
  kwargs + `disaster_event` (was never linking the event before — new records
  now set `disaster_event`, falling back to `disaster_event_legacy_id`). NEW
  `update_transport_space(transport_space, …)` — login + `_can_contribute`
  gated, patches only the fields passed (status / lokasi / jadwal / handover /
  contact / notes) so a posko keeps the record current as the trip runs.
- **Backend `api_control_centre.distribusi_board`:** transports query switched to
  `_sf(...)` + the new fields + `coordination_posko`/`departure_time`/`eta`. New
  return key **`armada_posko[]`** (provider, posko title, jenis, kapasitas,
  lokasi_saat_ini, rute, berangkat, eta, lokasi_serah_terima, narahubung,
  kontak, catatan, status/status_label, href → posko-detail). `matching_board.
  transportasi` items now show current location + ☎ + deep-link to the
  coordinating posko; `ruang_transportasi…units` carry berangkat/eta/handover/
  kontak too.
- **Frontend `management-distribusi.html` + `distribusi.js` + `style.css`
  (`?v=distribusi-20260903`):** new always-visible panel **"Armada Distribusi
  Posko — Koordinasi Penyerahan"** (11-col table, `renderArmada`, tel: links,
  row → posko-detail) above "Alur Distribusi"; the old "Tambah Transport Space"
  `<details>` rebuilt as **"Daftarkan Armada Distribusi"** — adds Posko
  Koordinator + Jenis `<select>` + Lokasi Saat Ini / Lokasi Serah Terima /
  Narahubung / No. Kontak Koordinasi Penyerahan / Catatan; "+ Daftarkan Armada"
  button on the panel opens+focuses it; save now also refreshes the board via
  `window.__distribusiReloadBoard`. Added global `.rn-form textarea` /
  `.rn-form-wide` CSS (were unstyled app-wide).
- **Deploy:** 3 files piped to `osiun-frappe-backend` (md5 verified) → `bench
  migrate` (exit 0, `after_migrate` hooks clean) → `docker restart`.
- **Seed `scratchpad/seed_armada.py` (ran):** backfilled all 6 existing
  RN Transport Space rows with handover contact/location; added 3 posko-
  registered armada — `SIM-ARMADA-DARAT-1` / `SIM-ARMADA-LAUT-1`
  (`posko-sim-logistik`, event-sim-001) + `KH-ARMADA-UDARA-1`
  (`KH-POSKO-KOMANDO`, karhutla). (`disaster_event` on the 3 new rows had to be
  set directly to `disaster_events:event-*` — the script's legacy-id lookup
  missed the `disaster_events:` prefix.)
- **Verified:** guest HTTP `distribusi_board` → `armada_posko` = 6 (sim-001) / 1
  (karhutla) with all coordination fields; Playwright `rn-armada.js` — 6 rows,
  tel: links, register form opens with 15 fields, 0 mobile overflow, only the
  pre-existing guest `session_info` 403 in console.
- **Not done:** no UI yet for `update_transport_space` (endpoint only); Step 11
  Alat Komunikasi still pending (half-built `rn_comms_device` doctype untracked
  in the tree, `rn_comms_frequency`/`rn_comms_operator` are empty dirs).

## Mockup-alignment pass (2026-09-01, in progress)

Pass to match each `pages/*.html` to its `assets/img/mockup/*.png` + the DMS
spec (`blueprint/DISASTER MANAGEMENT SYSTEM.docx.pdf` — only extractable text;
`blueprint/dms.pdf`/`dms (2).pdf` are image-only, no text layer, cannot render
here). Owner decisions this pass: **fix as we go** (report per page), and
**keep the dev sidebar** (the full page-link list) for now — so "match mockup"
= match the **content area**, not the chrome. Pre-pass backup:
`_archive/mockup-align-20260901-190457/` (pages/, index.html, style.css, js/).

- **Welcome (`index.html`) — DONE (polish).** Added "Pelajari lebih lanjut →"
  on every role card, icons on the two secondary hero CTAs, icons on the 4
  footer items (+ `.role-more` / CTA-icon CSS). Deviations left as-is: KPI has
  no "delta dari kemarin" (needs yesterday snapshot); the "Bencana Aktif + Live
  Summary" section is extra vs the mockup (kept — functional).

- **Login & Registrasi (`pages/auth.html`) — REBUILT, DEPLOYED (2026-09-01).** Was a
  dev console (Demo Login buttons / Role Matrix / Access Model). Now matches
  `assets/img/mockup/login & registrasi.png`: tabbed Masuk/Daftar card
  (`.rn-auth-*` CSS block appended to `style.css`), password show/hide, live
  password-rule checklist, "+62" phone prefix, role radios + rail role-cards
  that cross-fill, trust rail ("Aman, Terpercaya…" 3 rows + 4 role cards),
  bottom 4-point trust bar, "Lanjut dengan Google" button (points at Frappe
  `login_via_google` — only works if Google social login is configured), and a
  "Sesi Aktif" panel shown when already logged in.
  - **Frontend:** `pages/auth.html` main area replaced; `assets/js/auth.js`
    fully rewritten (IIFE; nothing global). Cache-busters: `auth.html` →
    `style.css?v=authredesign-20260901`, `auth.js`/`rn-frappe-client.js`
    `?v=authredesign-20260901`. Frontend is served straight from
    `/volume1/web/rescue-net/` so these are already live.
  - **Backend (DEPLOYED 2026-09-01, verified live over guest HTTP):** new
    `rescue_net.api_auth.register` (`allow_guest=True`, rate-limited 6/hour by
    email). NOTE: this Frappe (15.113.4) does **not** export `frappe.rate_limit`
    — had to `from frappe.rate_limiter import rate_limit` and use `@rate_limit(...)`.
    Container backup `api_auth.py.bak-20260901-191829-register`.
    Creates a Frappe **Website User** (`new_password` sets the pw) + an
    **RN User Account** (`frappe_user`, `email`, `phone`, `role=""`,
    `requested_role=<relawan|donatur|organisasi|petugas_posko>`,
    `role_request_status="pending"`, `status="pending_verification"`). Empty
    `role` → `_effective_role` resolves to `viewer` (read-only) until the
    existing verification-approval flow grants the requested role. Rolls back +
    logs on RN User Account failure. Password rule: ≥8 chars, ≥1 uppercase,
    ≥1 digit (mirrored client-side).
  - **DEPLOY:** apps dir is bind-mounted (`/volume1/docker/osiun-frappe-shadow/apps/rescue_net`
    → `/home/frappe/frappe-bench/apps/rescue_net` in `osiun-frappe-backend`).
    `admin` cannot write that shadow dir (owned uid 1000) and non-docker `sudo`
    has no TTY. **Working method:** pipe the file through docker exec as frappe —
    `sudo docker exec osiun-frappe-backend cp -a <CPATH>/f.py <CPATH>/f.py.bak-$(date +%Y%m%d-%H%M%S)`
    then `cat <repo>/f.py | sudo docker exec -i osiun-frappe-backend sh -c 'cat > <CPATH>/f.py'`,
    verify md5 host==container, then `sudo docker restart osiun-frappe-backend`
    (ping 502 for ~10s, then 200). CPATH = `/home/frappe/frappe-bench/apps/rescue_net/rescue_net`.
  - **TEST after deploy:** guest `POST
    /rescue-net-frappe/api/method/rescue_net.api_auth.register`
    with `full_name,email,password,phone,role` → `{ok:true,...}`; then the
    Daftar tab should auto-login and redirect; weak password → 417 with the
    Indonesian rule message; duplicate email → "Email sudah terdaftar".

- **Bencana Aktif (`pages/bencana-aktif.html` + `assets/js/bencana-aktif.js`) — BUILT & DEPLOYED (2026-09-01).**
  Matches `assets/img/mockup/bencana aktif.png` content area: 4 KPI tiles
  (Bencana Aktif / Jiwa Berisiko / Kebutuhan Kritis / Distribusi Terhambat,
  rolled up across all active events), left "Daftar Bencana Aktif" `rn-table`
  with **expandable per-region (kabupaten/kota) child rows** (status pill
  Kritis/Siaga/Waspada, jiwa, kebutuhan kritis, distribusi, terakhir diperbarui),
  client-side search + pagination (page size 3) + "Buka Semua"; right rail
  "Ringkasan Bencana" (selected event: id, updated, 4 stat boxes) + "Isu Kritis
  Teratas" list + "Buka Control Centre" / "Lihat Detail". Row click selects →
  updates the rail.
  - **Backend:** new guest endpoint
    `rescue_net.api_control_centre.active_disasters_board(limit=60)` — appended to
    `api_control_centre.py` (helpers `_ba_*`, consts `_SIT_*`/`_SEV_STATUS`).
    Per active `RN Disaster Event`: pulls its `RN Posko` / `RN Logistic Need` /
    `RN Distribution Flow`, groups poskos by `city_name` (→ province → "Wilayah
    lain"), region status = worst `operational_status`, kebutuhan kritis = open
    needs with urgency critical/urgent/high, distribusi terhambat = flows in
    `_DRILL_BLOCKED_FLOW`. Deployed to `osiun-frappe-backend` + restarted;
    container backup `api_control_centre.py.bak-20260901-<ts>-bencanaboard`.
    Verified live over guest HTTP (6 active events) and Playwright
    (`/volume1/docker/osiun-playwright-check/rn-bencana-aktif.js`, run with
    `--add-host=host.docker.internal:host-gateway`; cold worker needs ~15 s).
  - **KPI tiles are clickable (2026-09-01b)** — each `<button class="kpi-card
    rn-kpi-btn" data-kpi>` opens a drill-down modal (`#baDrill` / `.rn-ba-modal`):
    Bencana Aktif → table of all events (row → select + scroll); Jiwa Berisiko →
    per-event region breakdown + "Buka Control Centre"; Kebutuhan Kritis → all
    open critical/urgent needs grouped by event, each row deep-links
    `posko-logistik.html?id=<posko>&event=<ev>&penuhi=<item>`; Distribusi
    Terhambat → blocked flows (honest empty-state when 0). "Isu Kritis Teratas"
    rail items are links too. Endpoint `active_disasters_board` enriched to return
    `kebutuhan_items` / `distribusi_items` / `posko_kritis_items` (each with
    `href`) + `totals.posko_kritis`. Deployed; container backup
    `api_control_centre.py.bak-20260901-*-bakpi`. Cache-buster on the page's
    css/js bumped to `?v=bencana-20260901b`.
  - Accepted deviations vs mockup (same as welcome page): KPI tiles have no
    sparkline / "N dari kemarin" delta (no yesterday snapshot); KPI icon glyphs
    omitted (matches the app's plain `.kpi-card`). Data is thin for real events
    (Longsor Bogor / banjir sumatar / Luwu have 0 poskos) — honest, reflects DB.
  - **Menu access:** `assets/js/rn-public-header.js` `links[]` now has a
    "Bencana Aktif" entry (after Home) → shows in the shared top header on all
    28 sub-pages; cache-buster on `rn-public-header.js` bumped
    `?v=eventpicker-20260831` → `?v=bencana-20260901` across `pages/*.html` (sed,
    28 files). `index.html` "Bencana Aktif" embed header also links it
    ("Semua Bencana Aktif"); the new page's own sidebar `<nav>` has the entry.
    Other pages' LEFT sidebars get it during their rebuild.
  - CSS: `.rn-ba-*` block appended to `style.css`; cache-buster
    `?v=bencana-20260901` on the new page's css/js tags.
- **Remaining pages — comparison DONE, plan written: `docs/MOCKUP_ALIGNMENT_PLAN.md`
  (2026-09-01).** 11 pages left (organisasi-posko, verification-approval,
  management-distribusi, shelter-detail, search-found, program-khusus,
  management-relawan, alat-kerja, resource-profile, evidence) + 2 NEW pages
  (`registrasi-posko.html`, `alat-komunikasi.html`) are the same gap: existing =
  English dev-shell (input form + empty table, some endpoints not `allow_guest` /
  missing); mockup = Indonesian KPI dashboard (4–6 tiles + 4–10 data panels +
  right detail rail). Plan doc has per-page KEEP / ADD / BACKEND, shared
  components to build once, a guest-endpoint checklist, and a suggested 12-step
  order. **Rule from owner: additive only — never remove an existing menu/form/
  table that the mockup omits; move it into a `<details>`, keep it.** Pages with
  no mockup (ai-*, sync-console, data-consolidation, map, disaster-detail,
  contact-directory, kirim/edit-bantuan, laporan-masyarakat, recovery,
  donor-program, posko-detail, posko-medis-detail) are left as-is.
- **Dapur Umum (`pages/dapur-umum.html` + `assets/js/dapur-umum.js`) — BUILT &
  DEPLOYED (2026-09-02), step 1 of the 12-step order.** Matches
  `assets/img/mockup/dapur umum.png`: 6 KPI tiles (Jiwa Dilayani / Kapasitas
  Porsi per Hari / Produksi Hari Ini / Gap Porsi / Bahan Kritis / Distribusi
  Hari Ini, all clickable → `.rn-ba-modal` drill reused from Bencana Aktif),
  Target Layanan, a `.rn-donut` (new shared CSS component — CSS
  `conic-gradient` ring + legend, no chart library) breakdown of today's
  production by status, Stok Bahan Dapur table, Kebutuhan Bahan Kritis cards,
  Jadwal Masak + Distribusi Makanan Hari Ini (both **derived from real
  `RN Kitchen Production` rows**, not a separate schedule doctype — grouped by
  today's date, status mapped prepared→Menunggu/Siap Kirim,
  dispatched→Proses/Dalam Perjalanan, distributed→Selesai/Terkirim), Relawan
  Dapur (`RN Volunteer Profile.assigned_posko`), Status Gas/BBM (stock items
  keyword-matched: gas/lpg/solar/bensin/bbm/genset/elpiji), Evidence Foto Dapur
  (same unified `event_evidence` feed as Posko Logistik, narrowed to this
  posko). Old form + 3 raw list panels (Kitchen Stock riwayat / Meal
  Productions / Stock Movements / Record Meal Production) kept, moved into
  `<details>` per the additive-only rule.
  - **Backend:** new guest endpoint `rescue_net.api_kitchen.kitchen_board(posko,
    disaster_event)` — one payload: `totals` + `kpi_items` (each KPI's
    underlying list with `href`), `target_layanan`, `produksi_donut`,
    `stok_bahan`, `kebutuhan_kritis`, `jadwal_masak`,
    `distribusi_hari_ini_list`, `relawan_dapur`, `gas_bbm`, `bukti`. Stock
    status (`aman`/`waspada`/`kritis`) is `available/basis` ratio via the
    existing `_stock_state()` helper — honest given there's no "kebutuhan"
    doctype for kitchen ingredients (no invented thresholds). "Kapasitas Porsi
    / Hari" = historical daily-total peak across all of this posko's
    productions (no capacity field on `RN Posko`) — an accepted data-thin
    deviation, documented same as Bencana Aktif/Welcome.
  - **Fixed pre-existing bug:** `rescue_net.api_kitchen.dashboard` was
    `@frappe.whitelist()` (login-only) so the page's guest legacy panels 403'd
    with "not whitelisted" — the exact bug this plan flagged. Now
    `allow_guest=True` + `rn_actor(required=False)`; the manager allow-list
    (`_allowed_poskos`) only gates *authenticated* actors — a guest requesting
    one explicit `posko` gets a public read of that posko only (same guest-read
    model as `kitchen_board`/`logistik_board`). Confirmed with the user before
    applying (loosening an auth check).
  - **Seed enrichment (posko-sim-dapur):** backfilled `production_time` on 2
    pre-existing productions that had it null (also fixed in `kitchen_board`
    with a `creation`-timestamp fallback so future null-time rows don't zero
    out "hari ini" data), added 2 more productions (dispatched + distributed,
    different hours today), `rn_beneficiary_count=380`, 2 stock observations
    (Beras 40kg, Gas LPG 12kg 1 tabung), 1 `RN Volunteer Profile` assigned to
    the posko. Script + container backups:
    `api_kitchen.py.bak-20260902-*-kitchenboard` /
    `-guestdash`.
  - Deployed to `osiun-frappe-backend` (md5 verified) + restarted. Playwright
    `/volume1/docker/osiun-playwright-check/rn-dapur-umum.js` (cold worker can
    exceed 25s on this endpoint — it unions several doctypes incl.
    `event_evidence`; a second run after warm-up renders fine). Verified: all 6
    KPIs correct, all 6 drills open with real items, donut/tables/relawan/fuel
    render, only pre-existing (unrelated) console noise is `session_info` 403
    for guests (shared `session-role.js` behaviour on every page).
  - Cache-busters: `style.css`/`dapur-umum.js` → `?v=dapur-20260902`.
  - **Layout precision pass (2026-09-02b):** owner asked for pixel-closer match
    to the mock-up. Row 2 changed from a 3-col grid to the mock-up's real
    4-column layout (Target Layanan / Produksi donut / Stok Bahan Dapur table /
    Kebutuhan Bahan Kritis, widths `.95fr .95fr 1.7fr 1.1fr`); Target Layanan
    switched from 3 boxed mini-cards to plain stacked rows (matches mock-up,
    fits the now-narrower column); Evidence + Gas/BBM row widened to an
    asymmetric `1.6fr 1fr` split; stock status pill "aman" now uses the
    existing `.chip.ok` (green) instead of a neutral chip. **No AI image-gen
    tool is available in this environment** — asked the owner how to handle
    "Evidence Foto Dapur" (empty for posko-sim-dapur, no real uploads yet);
    they chose labeled icon/gradient placeholder tiles (`.rn-dp-photo-placeholder`,
    honestly marked "Simulasi") over an empty-state or fabricated photos, shown
    alongside the real "Unggah Foto" tile — swaps automatically for real thumbs
    once evidence exists for the posko.

- **Shelter & Akomodasi (`pages/shelter-detail.html` + `assets/js/shelter-detail.js`)
  — BUILT & DEPLOYED (2026-09-02), step 2 of the 12-step order.** Mock-up is a
  **cross-shelter overview**, unlike the old page which was single-posko
  detail — so the new dashboard is always the cross-shelter view for the
  active `?event=`, and the old single-posko form/lists stay in `<details>`
  scoped to `?id=` as before (additive, both modes coexist on one page).
  6 KPI tiles (Total Penghuni / Kapasitas Maksimal / Overcapacity / Kelompok
  Rentan / Air Bersih Kritis / Sanitasi Kritis, all clickable → `.rn-ba-modal`
  drill), Daftar Shelter table (row click → that shelter's `posko-detail`-style
  link), Kapasitas & Okupansi `.rn-donut`, Kebutuhan Dasar (5-category catalog
  keyword-matched against open `RN Shelter Need`, not invented thresholds),
  Kelompok Rentan table (from latest `RN Shelter Occupancy` per shelter),
  Check-in/Check-out Hari Ini (real `RN Shelter Household` rows), Peringatan
  Keselamatan (overcapacity + critical open needs), Dokumentasi & Bukti
  (unified evidence feed, placeholder tiles when empty — same pattern as
  Dapur Umum).
  - **Backend:** new guest endpoint `rescue_net.api_shelter.shelter_board
    (disaster_event)` in `api_shelter.py`. Two mock-up panels have **no
    backing doctype and were honestly omitted/adapted, not fabricated**:
    "Akomodasi Relawan/Petugas" (volunteer/officer lodging isn't tracked
    anywhere — empty-state note explaining why) and literal "Toilet/MCK
    Tersedia N / Titik Air N" counts (no physical-asset inventory doctype —
    "Sanitasi & Air" instead shows count of open critical sanitation/water
    `RN Shelter Need` records, which *is* real). Also found mid-build: the
    HTML form for Record Occupancy has always collected `sanitation_status`/
    `water_status`/`electricity_status`/`safety_status`, but
    `create_occupancy()` never accepted or persisted them (not in the
    `RN Shelter Occupancy` doctype at all) — pre-existing gap from before
    this session, left as-is (out of scope for a layout pass; would need a
    schema change). Noted here so it isn't mistaken for new breakage.
  - **Fixed the same guest-whitelist bug as Dapur Umum**, in two files this
    time: `api_shelter.dashboard` and `api_logistics.dashboard` (both feed
    this page's legacy per-posko panels) were login-only, 403ing for guests.
    Now `allow_guest=True` + `rn_actor(required=False)`, manager allow-list
    only gates authenticated actors. `api_logistics._accessible_poskos` also
    had a latent `actor.name` crash for `actor=None` (no `if not actor`
    guard) — fixed alongside. Confirmed with the user before applying (same
    as the Dapur Umum precedent).
  - **Removed `dms-inline.js` from this page** — found it auto-injecting a
    broken "Registrasi Pengungsi" panel (`rnFetch is not defined`: dead
    pre-Frappe-migration code hitting a retired FastAPI `/dms-gap/` route
    that was never ported, landing right above the new dashboard). Confirmed
    `posko-logistik.html` already dropped this same script during its own
    rebuild — consistent precedent. The feature it tried to provide
    (evacuee/family registration) is already covered by real, working
    `RN Shelter Household` data in the new Check-in/Check-out panel, so
    nothing functional was actually lost. `donor-program.html` still has the
    same dead include — untouched (out of scope today).
  - **Seed enrichment (posko-sim-shelter):** fresh `RN Shelter Occupancy`
    snapshot pushed to 215/200 (a real overcapacity example to show the
    alert/status), 5 `RN Shelter Household` check-in/moved/checked-out rows
    dated today, 2 more `RN Shelter Need` (Air Bersih, Sanitasi — both
    critical) so "Kebutuhan Dasar" has more than one category open. The
    event-sim-001 overview also picks up `SIM-NS-POSKO-WARGA`'s existing
    merged-function shelter data (1200/1400) with no seeding needed.
  - Deployed to `osiun-frappe-backend` (md5 verified) + restarted. Playwright
    `/volume1/docker/osiun-playwright-check/rn-shelter.js`. Verified: all 6
    KPIs correct, all 4 drills open with real items, table/donut/panels
    render, only pre-existing `session_info` 403 remains.
  - Cache-busters: `style.css`/`shelter-detail.js` → `?v=shelter-20260902`.

- **Manajemen Relawan (`pages/management-relawan.html` + `assets/js/relawan.js`)
  — BUILT & DEPLOYED (2026-09-02), step 3 of the 12-step order.** Event-wide
  dashboard: 5 clickable KPIs (Relawan Terdaftar / Available Hari Ini / Sedang
  Bertugas / Butuh Penugasan / Fatigue Risk), Daftar Relawan table with
  live client-side search, Filter Keterampilan (bar-chart-style skill
  breakdown), Papan Penugasan, Jenis Relawan (4 tiles), evidence-free per
  the mock-up. Old panels (Ringkasan/raw Daftar Relawan list/Assignments +
  both forms) kept in `<details>`.
  - **Backend:** new guest endpoint `rescue_net.api_volunteer.volunteer_board
    (disaster_event)`. Adaptations forced by the real schema (documented in
    the function docstring, not silently faked):
    - No "Organisasi" field on `RN Volunteer Profile` — joined via
      `user_account` → `RN Organization Membership` → `RN Organization.title`;
      shows "-" when a profile has no linked user account (true for most
      self-reported sim volunteers).
    - "Filter Keterampilan" / "Jenis Relawan" categories are keyword buckets
      over real `main_skill`/`skill_tags` text (Medis/Evakuasi/Search & Found/
      Pickup & Transport/Dapur & Logistik/Komunikasi/Shelter), not the
      mock-up's exact fixed category set — our skill values don't carry those
      labels.
    - "Papan Penugasan" = assignments still `planned` (created but not yet
      accepted by the assignee). The schema binds one `RN Volunteer
      Assignment` to exactly one `volunteer` at creation time — there is no
      "open task needing N relawan" concept to draw an unfilled-slot board
      from, so this is honestly relabelled as "menunggu konfirmasi: <nama>"
      rather than faking an "Isi Penugasan" call-to-action.
    - "Fatigue Risk" = real signal: assignments `checked_in`/`in_progress`
      running ≥ `FATIGUE_HOURS_THRESHOLD` (12h) since `checked_in_at`.
    - "Akomodasi & Keselamatan" panel has no backing doctype — same
      documented gap as Shelter's "Akomodasi Relawan/Petugas"; empty-state
      note points back to that.
  - **Fixed the same guest-whitelist bug** in `api_volunteer.dashboard`
    (login-only → 403 for guests on this public page's legacy panels). Now
    `allow_guest=True` + `rn_actor(required=False)`; manager gate only
    applies to authenticated actors. Confirmed with the user first (3rd
    occurrence of this exact fix — Dapur Umum, Shelter, now Relawan).
  - **Seed enrichment:** 2 new `RN Volunteer Profile` (Rina Kartika —
    Medis/Triage, Yusuf Hidayat — Search & Found/K9 Handler, both
    `available`) + 2 `RN Volunteer Assignment` in `planned` status so
    "Butuh Penugasan"/"Papan Penugasan" aren't empty. event-sim-001 already
    had 6 profiles + 5 `in_progress` assignments (the LD2–LD6 Landrover set,
    checked in 2026-08-26 — now ~161h ago, which is why Fatigue Risk shows 5).
  - Deployed to `osiun-frappe-backend` (md5 verified) + restarted. Playwright
    `/volume1/docker/osiun-playwright-check/rn-relawan.js`. Verified: all 5
    KPIs correct, all 5 drills open with real items, search filter works,
    skill bars/tiles/papan render, only pre-existing 403s remain
    (`session_info` for guests + a role-gated form check, both unrelated).
  - Cache-busters: `style.css`/`relawan.js` → `?v=relawan-20260902`.

- **Manajemen Distribusi (`pages/management-distribusi.html` +
  `assets/js/distribusi.js`) — BUILT & DEPLOYED (2026-09-02), step 4 of the
  12-step order.** Biggest page so far. 6 clickable KPIs (Transport Space /
  Kapasitas Darat / Laut / Udara / Kebutuhan Belum Match / Distribusi
  Terhambat), a **read-only** 4-column Papan Pencocokan (Kebutuhan / Bantuan /
  Relawan Pickup / Transportasi — deep-links to the owning module rather than
  a drag/drop redesign; no page anywhere in the app has that interaction
  pattern, so it wasn't invented here either), Ruang Transportasi with real
  Darat/Laut/Udara tabs + donut + Unit Aktif table, Alur Distribusi (Live
  Shipment, all 18 real `RN Distribution Flow` rows) with a Trace column,
  Peringatan & Hambatan, and a static reference footer (Pedoman Kemasan /
  Panduan Berat & Volume — reuses `_LOGISTIK_CONVERSIONS` / Trace & Barcode).
  Old panels (Bantuan Perlu Pickup, Donatur Antar Sendiri, both forms,
  Transport Space Tersedia, Distribution Flow raw list) kept in `<details>`.
  - **Owner directive this session: when a mock-up panel has no backing data,
    build it for real (new fields/records), don't just document the gap.**
    Applied here:
    - `RN Transport Space` only had 1 darat record — Laut/Udara existed only
      as loose text on `SIM-NS-FLOW-TNIAL`/`SIM-NS-FLOW-GARUDA`
      (`transport_type` was `None` on both). Created 2 real records (TNI AL
      KRI, TNI AU/Garuda Cargo — capacities matched to their existing
      `RN Aid Offer` "Kapasitas Angkut Laut/Udara" rows) + linked both flows
      to them via `transport_space`/`transport_type`. The Laut/Udara KPI
      tiles are now backed by genuine master data, not a hidden zero.
    - **"Otomatis Cocokkan" is a real write endpoint**, not a UI-only button:
      `rescue_net.api_control_centre.auto_match_distribution` (login
      required — no guest write, matches every other create_* endpoint in
      the app) greedily pairs an open `RN Logistic Need` with an
      case-insensitive item-name-matching available `RN Aid Offer` and a
      free `RN Transport Space`, then actually creates an
      `RN Distribution Flow`. Verified via console as Administrator (rolled
      back after, no permanent test data): 1 real match found (Obat-Obatan).
      Guest click shows a graceful "perlu login sebagai operator" message
      rather than a raw 403.
  - **Backend:** new guest endpoint `rescue_net.api_control_centre.
    distribusi_board(disaster_event)`. Capacity % is volume-basis (m³);
    utilised = transport_status in reserved/assigned/in_transit/arrived/
    completed. "Kebutuhan Belum Match" = open needs with no
    `RN Distribution Flow.logistic_need` pointing at them. "Peringatan"
    combines blocked flows + aid offers unpicked ≥3 days + any transport
    type ≥90% utilised — all real, derived signals.
  - Deployed to `osiun-frappe-backend` (md5 verified) + restarted. Playwright
    `/volume1/docker/osiun-playwright-check/rn-distribusi.js`. Verified: all
    6 KPIs correct, 4 drills open (2 item-list, 2 capacity-info), matching
    board counts (20/15/1/1) render, transport tabs switch correctly (Laut
    100%/900m³ verified), 18-row Alur Distribusi table, 6 real Peringatan
    cards, auto-match guest-guard message, only pre-existing 403s remain.
  - Cache-busters: `style.css`/`distribusi.js` → `?v=distribusi-20260902`.

- **Volunteer accommodation/safety gap fix + public volunteer registration
  (2026-09-02c).** Owner asked to go back and build real backing for the 2
  gaps left honest-empty in steps 2–3 (per the "complete, don't omit"
  directive), then separately asked for a public "daftar jadi relawan" entry
  point after sharing a new blueprint doc excerpt.
  - **2 new DocTypes** (first ones added this project, not just Custom
    Fields): `RN Volunteer Accommodation` (`location_name`, `posko`,
    `accommodation_type`, `capacity_beds`, `occupants_count`,
    `is_safe_point`, `safety_status`, ...) and `RN Safety Briefing`
    (`title`, `scheduled_at`, `location`, `briefing_status`, ...). Files
    under `frappe_shadow/apps/rescue_net/rescue_net/rescue_net/doctype/`,
    same minimal JSON shape as every other doctype in this app (`doctype`,
    `name`, `module`, `custom`, `is_submittable`, `title_field`, `fields`,
    `permissions` — no extra boilerplate needed). Deployed + `bench migrate`
    on `osiun-frappe-backend` (no errors; verified both doctypes + new
    columns exist via console). Seeded 3 accommodation records + 3 safety
    briefings (2 today) for event-sim-001.
  - `RN Volunteer Profile` got 3 new fields (`skill_category` select,
    `preferences`, `equipment_owned`, `needs_transport` check) — the exact
    set the blueprint's Management Relawan section calls for ("katagori
    keahlian, waktu berangkat, preferences/pilihan, fasilitas yang
    tersedia"). Migrated alongside the 2 new doctypes.
  - `api_shelter.shelter_board` → new `akomodasi_relawan` list (real, from
    `RN Volunteer Accommodation`); `shelter-detail.html`'s "Akomodasi
    Relawan/Petugas" panel now a real table instead of the empty-state note.
  - `api_volunteer.volunteer_board` → new `akomodasi_keselamatan` block
    (beds available/occupied, safe-point count, today's briefings);
    `management-relawan.html`'s "Akomodasi & Keselamatan" panel now real
    stat tiles + a briefing list.
  - **New public endpoint `rescue_net.api_volunteer.register_volunteer`**
    (`allow_guest=True`, rate-limited 10/hour by `contact`, mirrors
    `api_auth.register`'s pattern) — the blueprint's "sarana pendaftaran
    relawan yang mau berangkat". Unlike `create_profile` it needs no login;
    creates a standalone `RN Volunteer Profile` (no `user_account`, same
    shape as most existing sim/community volunteers), `self_reported`,
    immediately live on the board. New "+ Daftar Jadi Relawan" button in
    `management-relawan.html`'s header opens a modal form (Nama, Kontak,
    Kategori Keahlian, Skill Tambahan, Waktu Tersedia, Lokasi, Preferensi,
    Peralatan, Butuh Transport checkbox, Catatan) — no page reload, calls
    the endpoint directly, refreshes the board on success. Verified
    end-to-end via Playwright: filled + submitted the real form in a real
    browser, `kpiTerdaftar` went 8→9, then cleaned up the test record.
  - Deployed to `osiun-frappe-backend` (md5 verified). Playwright
    `/volume1/docker/osiun-playwright-check/rn-relawan-accom.js`. Cache-busters
    bumped to `?v=shelter-20260902b` / `?v=relawan-20260902b`.

- **Mobile/responsive bug fix (2026-09-02d, cross-cutting).** While checking
  the 4 pages above at a 390px viewport (owner asked to keep HP layout in
  scope, not just defer it to a final pass): CSS Grid items default to
  `min-width: auto`, so a wide child (a `.rn-table` with many columns) forced
  the whole grid track — and the page — wider than the viewport, even though
  the table's own `.rn-table-wrap{overflow-x:auto}` was supposed to contain
  it. Fixed at the shared root: `.content-grid > *, .kpi-grid > * { min-width:
  0; }` appended near `.content-grid`'s definition in `style.css`, plus
  every mockup-alignment page's `@media` breakpoint that collapsed a grid to
  a single column changed from bare `grid-template-columns: 1fr` to
  `minmax(0, 1fr)` (bare `1fr` has the same implicit-`auto`-minimum problem).
  Confirmed via `getBoundingClientRect` (not `scrollWidth` — Chromium's
  `scrollWidth`/Playwright fullPage screenshots don't respect `body{overflow-x:
  hidden}` and give false positives) that `body`/`.app-shell`/`main` are all
  exactly viewport-width post-fix, with wide tables now correctly scrolling
  inside their own `.rn-table-wrap`. This fix is global, so it also protects
  every page still to be built — worth remembering if a future page's mobile
  screenshot looks fine but an automated `scrollWidth` check flags overflow.

- **Evidence Center (`pages/evidence.html` + `assets/js/evidence.js`) —
  BUILT & DEPLOYED (2026-09-02), step 5 of the 12-step order.** 6 clickable
  KPIs (Evidence Baru / Pending Verifikasi / Restricted / Geotagged / Dokumen
  Serah Terima / Video Evidence), Filter Modul chips (counts from real data,
  not the mock-up's fixed list), search, a real client-side CSV export of
  the currently filtered rows, and a rich table (thumbnail, module chip,
  lokasi, waktu, uploader+role, verifikasi, visibilitas) with client
  pagination — same pattern as Daftar Relawan/Daftar Shelter. Old "Upload
  Evidence" form kept in `<details>` (still calls `api_frontend_bridge.
  upload_evidence`, login required, untouched). The old GET-based
  `#evidenceList` legacy panel was dropped — it called a redundant, still
  login-gated `evidence_context` bridge wrapping the exact same
  `event_evidence()` feed my new guest dashboard already fetches, so nothing
  was actually lost, just de-duplicated.
  - **Backend:** new guest endpoint `rescue_net.api_control_centre.
    evidence_board(disaster_event)`, built on top of the already-unified
    `event_evidence()`. Extended `_ev_norm()`/`event_evidence()` with 3 new
    derived fields per the mock-up's needs:
    - `module` — classified from `report_type` first (the real signal on
      community-submitted evidence, e.g. "logistics"/"medical"/"shelter";
      `linked_object_type` is uniformly "RN Community Report" for that whole
      source so it can't distinguish modules alone), falling back to
      `linked_object_type` keyword-matching for `RN Operational Evidence`
      rows (real DocType names like "RN Kitchen Production").
    - `visibility` — **new real field**, not fabricated: added
      `visibility_scope` (Select: restricted/public) to both
      `RN Operational Evidence` (default `restricted` — everything is stored
      as a private file per `add_evidence()`'s own validators) and
      `RN Community Report Evidence` (default `public` — community reports
      are meant to be transparent). Migrated on `osiun-frappe-backend`.
      Existing pre-migration rows read back as their doctype's default via
      `_ev_norm`'s fallback (`kw.get("visibility_scope") or "restricted"`).
    - `mime` — from `file_type` when the source doctype has it (Community
      Report Evidence), else guessed from the URL extension.
    Geotagged = real non-(0,0) lat/lng (several rows import verbatim
    `0.0/0.0` from earlier migration — treated as "no GPS", not fabricated
    as tagged). "Video Evidence" stayed honestly `0` — no real video asset
    exists anywhere in the demo set, and a fake unplayable link would be
    worse than an honest empty KPI.
  - **Debugging note (cost real time, worth remembering):** newly seeded
    `RN Operational Evidence` rows silently failed to appear in
    `event_evidence()`'s output — not a code bug. `push()` dedupes by
    `evidence_url`, and the seed script reused an *existing* demo image
    filename (`masyarakat_donasi.jpg`, no query string) that an unrelated
    but same-event `RN Community Report Evidence` row already used, so the
    new rows were silently deduped away. Every other seed script in this
    project already appends a unique `?ev=<tag>` suffix to demo image URLs
    for exactly this reason — this is the first time it was skipped, and
    the fix was just to add the suffix. Always append a unique `?ev=` tag to
    reused demo image URLs.
  - Seed: 2 `RN Operational Evidence` rows (today, `pending`, one
    `evidence_type=document` for "Dokumen Serah Terima") linked to real
    today-dated Dapur Umum/Shelter records from earlier in this session.
  - Deployed to `osiun-frappe-backend` (md5 verified) + restarted. Playwright
    `/volume1/docker/osiun-playwright-check/rn-evidence.js` (desktop + 390px
    mobile). Verified: all 6 KPIs correct, module filter + search + pagination
    work, 4 drills open with real items, CSV export wired, mobile viewport
    exactly contained (no overflow).
  - Cache-busters: `style.css`/`evidence.js` → `?v=evidence-20260902`.

## System snapshot

- **Stack:** Frappe / MariaDB is the system of record. Site `osiun.localhost` in
  container `osiun-frappe-backend`. Legacy FastAPI (`rescue-net-api`) is retired
  (kept read-only for rollback). Do **not** re-enable it.
- **Public host:** `https://osiun.tail251e1e.ts.net` (Tailscale Funnel).
  Static site under `/rescue-net/`; Frappe API under `/rescue-net-frappe/api/method/...`.
- **Frappe app source of truth in this repo:** `frappe_shadow/apps/rescue_net/rescue_net/`.
  Deploy = copy the changed file into the container at
  `/home/frappe/frappe-bench/apps/rescue_net/rescue_net/…`, `chown frappe:frappe`,
  then `docker restart osiun-frappe-backend`. Back up the target first.
- **Run scripts:** `rn-push-main.sh` / `rn-push-dev.sh` push to GitHub (token from
  the sudo-only `/volume1/docker/osiun-deploy/osiun-deploy.env`).

## Current program: every page functional + matches its mockup + real data

Goal (owner): each `pages/*.html` should be user-friendly, functional, visually
match `assets/img/mockup/*.png`, and be populated with realistic "as if real
user input" data. Working the pages one at a time.

### DONE

- **Posko Logistik (`pages/posko-logistik.html` + `assets/js/logistik.js`) — mockup pass (2026-09-01)**
  - Layout reflowed to `assets/img/mockup/posko logistik.png`: left column =
    Kebutuhan Mendesak (new, bound to `logistik_board.urgent_needs`, columns =
    Item / Stok Tersedia / Gap (Kekurangan) / Estimasi Habis / Waktu Harus Tiba /
    Prioritas) → Kiriman Masyarakat → Barang Masuk/Keluar; right rail = Asal &
    Trace → **Bukti Kondisi & Lapangan** → Konversi & Volume. Old 10-col stock
    table moved to a collapsible **Kartu Stok Rinci** panel (keeps operator
    Penuhi / OTW actions). New topbar **Kategori** filter (`itemCategory()` keyword
    buckets) narrows both the Kebutuhan Mendesak and Kartu Stok Rinci tables.
  - **KPI cards now clickable** (`wireKpiCards`): Jiwa Dilayani → posko-detail;
    Stok Menipis → opens Kartu Stok Rinci; Kebutuhan Kritis → scrolls to
    Kebutuhan Mendesak; Bantuan Menuju Posko → OTW drawer (all incoming).
    `kpiJiwaEdit` ✎ now `stopPropagation`s.
  - **Bukti with photos, like Control Centre:** `logistik_board` returns `bukti`
    / `bukti_total` / `bukti_last_at` — `event_evidence(posko.disaster_event)`
    narrowed to rows naming this posko (`posko`==name, `linked_object_id`==name,
    or posko title inside `location_text`). Frontend `renderEvidence` splits by
    caption tag: `[Kondisi Stok]` / `[Kondisi Posko]` fill the two named tiles
    (thumbnail + "Diperbarui …", click → modal); the rest go to a general
    thumbnail grid; empty categories fall back to an "unggah foto" link
    (`evidence.html?…&kind=stok|posko`). `openBuktiModal` mirrors CC
    `openEvidenceModal` (enlarged photo, caption, lokasi, jenis / pelapor·role /
    status / waktu, "Buka gambar penuh"); `[..]` prefix stripped in display.
  - **Seed:** 9 `RN Community Report` (+ `RN Community Report Evidence` child,
    `file_url` = `/rescue-net/assets/img/demo-landrover/evidence/*.jpg?ev=<id>`,
    `uploader_user` set) for `SIM-NS-POSKO-WARGA`, `SIM-LOG-GUDANG-JOGJA`,
    `posko_nodes:posko-sim-logistik` — 3 each: `*-STOK` (`[Kondisi Stok]`),
    `*-POSKO` (`[Kondisi Posko]`), `*-1` (general). legacy_id `SIM-LOG-BUKTI-*`,
    re-runnable (deletes prior `SIM-LOG-BUKTI-%` evidence children first).
    `?ev=` query keeps `event_evidence`'s URL-dedup from collapsing reused images.
    Side effect: these also appear in the CC "Bukti Lapangan" feed for
    `event-sim-001` (genuine logistics field evidence — intended).
  - `api_control_centre.py` deployed to `osiun-frappe-backend` + restarted;
    `logistik_board` bukti verified live over guest HTTP. Playwright-checked via
    `http://host.docker.internal/rescue-net/` (`rn-logistik-mockup.js`,
    `rn-logistik-bukti.js`).

- **Control Centre (`pages/war-room.html` + `assets/js/rn-control-centre-final.js`)**
  - Drill-down item rows: whole row is now the link to `posko-detail.html`
    (removed the "Lanjut →" pill); `.cc-drill-item.is-link` hover + `→` affordance.
  - **"Kebutuhan Kritis" item cells clickable** (`.cc-need-item` → `openNeedPoskoDrill`):
    reuses the drill modal to show every posko with an open need for that item,
    from the guest `logistik_open_needs` feed (the SAME "papan kebutuhan" an
    outside / collector posko uses to choose an aid destination). Each posko card:
    priority, area, Butuh/Realisasi/Gap, jiwa, progress bar, and actions —
    **Jadikan tujuan bantuan →** `posko-logistik.html?id=<posko>&penuhi=<item>`
    (logistik.js boot reads `?penuhi=` → auto-opens the Penuhi drawer with Item +
    Satuan prefilled), plus *Lihat posko logistik* and *Donasi publik*
    (`kirim-bantuan.html`). Frontend-only; `logistik_open_needs` already
    `allow_guest=True`. Playwright: `rn-cc-needdrill.js`.
  - Map: posko coordinates corrected — no marker sits in open water (earlier bug).
  - "Kebutuhan Kritis" table shows real Butuh / Realisasi / Progress% / Gap
    (patch: `api_ai._enrich_needs` surfaces `realized_quantity`/`gap` from
    `RN Logistic Need.legacy_payload`).
  - "Prioritas Keputusan" shows real text from records (ranked unmet needs +
    `RN Action Plan` + active `RN Recovery Project`), not a bare "Prioritas" label.
  - "Bukti Lapangan Terkini" shows real photos; clicking opens an enlarged
    detail modal (added to war-room.html; JS `openEvidenceModal` extended).
  - KPI boxes + module tiles are clickable → the page that manages that metric,
    each with a tooltip explaining what it measures (`linkCard` in the JS).
- **Two end-to-end simulations seeded (real DB records, with login codes):**
  1. `event-sim-001` "Simulasi Gempa Rescue-Net" — + national-support layer:
     BNPB / TNI AL / Garuda / Posko Logistik Warga / Relawan Pelajar
     (orgs `SIM-NS-*`, users `NASKOMANDO/BNPB/TNIAL/GARUDA/WARGA/PELAJAR`).
  2. `event-karhutla-kalbar-2026` "Karhutla Kalimantan Barat 2026" —
     BPBD Kalbar / Manggala Agni / Satgas Udara TNI AU / BKSDA+Yayasan Satwa /
     MPA. Poskos incl. **Pos Kesehatan ISPA**, **Posko Medis Satwa & Wildlife**,
     **Pos Alat Kerja & Logistik Pemadaman**, Helibase Water Bombing, Pos OMC,
     Pos Sekat Kanal Gambut, Rumah Singgah Udara Bersih. Users `KH*`.
     Every Control Centre module populated (stok, medis manusia+satwa, relawan,
     search & found, shelter, program khusus, recovery).
  - Seed scripts live outside the repo at
    `/volume1/docker/osiun-playwright-check/out-cc-map-20260831/`
    (`rn_natsim_v2.py`, `rn_natsim_needs.py`, `rn_karhutla.py`,
    `rn_karhutla_e2e.py`, `vis_setup.py`, `seed_evidence_rows.py`) —
    re-runnable, idempotent (upsert by `legacy_id`).
  - **Evidence is real DB input, user-attributed:** every sim photo has an
    `RN Community Report Evidence` row (`report` link + `file_url` +
    `uploader_user` = the operator's `RN User Account`), and the parent
    `RN Community Report.reporter_user` is set too. `event_evidence()` prefers
    the structured child row (dedup by URL), so the Control Centre "Bukti"
    panel and the Evidence page show the SAME records WITH "Pelapor /
    Pengunggah: <user> (<role>)".
- **Step A of the visibility feature (deployed):**
  - New `frappe_shadow/apps/rescue_net/rescue_net/visibility.py` —
    `effective_posko_share(posko, actor)` → `full` | `summary` from
    `RN Organization.control_centre_share` (`full_authorized` / `aggregate`),
    `RN Posko.public_detail` (when `allow_posko_public_choice`), and owner /
    member / System-Manager override.
  - `api_control_centre.map_points()` emits `share_mode` + `detail_allowed` +
    `posko_id` + `organization` per point.
  - `api_control_centre.event_evidence(event)` — **one** unified evidence feed
    (RN Community Report legacy_payload + RN Community Report Evidence +
    RN Evidence File + RN Operational Evidence). `public_dashboard` returns it as
    `evidence`; `api_frontend_bridge.evidence_context` returns the same list, so
    the Control Centre "Bukti Lapangan" and the Evidence page are consistent.

### DONE — Posko function model (collector/receiver + merged shelter/kitchen)

Per owner: a posko logistik is either **pengumpul** (collector, safe area, 0
beneficiaries) or **penerima** (receiver, disaster area, serves beneficiaries).
Beneficiaries may sit in a **separate** shelter posko or a **merged** one; when
creating a posko you choose which functions (logistics / shelter / dapur umum)
live in that single posko so one admin / one login runs it. Logistics supply
comes from **another posko logistik** (has kartu stok) OR **direct from the
public / masyarakat** (NO kartu stok — one-off or repeated shipments).

- **Frappe (deployed, verified — shadow md5 == container md5):**
  - Custom Fields (no migrate): `RN Posko.rn_fn_logistics/rn_fn_shelter/
    rn_fn_kitchen` (Check) + `RN Posko.rn_logistics_role` (Select
    `\ncollector\nreceiver`). Backfilled 14 poskos from `posko_type`.
  - `api_control_centre._posko_functions(name)` → `{functions[], logistics_role,
    is_collector, is_merged}`. Wired into `posko_detail` (spread into
    `result["posko"]`), `map_points` (per-point `functions` / `logistics_role`
    via `_row_fns`), and `logistik_board` (returns `functions`,
    `logistics_role`, `is_collector`, `public_shipments`).
  - `_public_shipments(name)` → `RN Aid Offer` where `target_posko==name`,
    shaped `{donor_name,item_name,quantity,unit,status,ready_at,wave}` (wave from
    `legacy_payload.wave` / `public_repeated`).
  - New whitelisted `set_posko_functions(posko, functions, logistics_role)`
    (JSON or CSV `functions`) — sets the 4 fields, returns `_posko_functions`.
  - Seed `rn_posko_functions.py` (idempotent, ran OK): WARGA
    (`SIM-NS-POSKO-WARGA`) = merged logistics+shelter+kitchen, receiver, 1200
    jiwa, with `RN Shelter Occupancy SIM-MERGE-SHELTER-WARGA` (1200) +
    `RN Kitchen Production SIM-MERGE-KITCHEN-WARGA` (1200 portions);
    `SIM-LOG-GUDANG-JOGJA` = collector; 3 repeated public shipments
    `SIM-PUB-SHIP-1..3` (Komunitas Peduli Bandung Raya, Air Mineral, waves 1-3)
    toward WARGA.
- **Frontend:**
  - **Merged-posko function switcher = a sidebar TOP GROUP, login-only**
    (owner's ask: split the sidebar in two — top group picks which function of
    the merged posko, bottom groups are the normal menu; and it only shows when
    logged in, because a merged posko is run by ONE operator handling all 3
    functions). Implemented once in `assets/js/rn-navigation-v2.js` →
    `mountPoskoFunctionGroup(nav)`: bails unless `isLoggedIn()`
    (`RN_SESSION.getUser()` truthy) AND the URL has `?id=`; calls guest
    `api_control_centre.posko_functions`; if `functions.length >= 2` prepends a
    `<details open data-rn-group="posko-fn">` group labelled `Posko: <title>`
    with one child link per active function (Logistik → `posko-logistik.html`,
    Shelter → `shelter-detail.html`, Dapur Umum → `dapur-umum.html`, each
    `?id=&event=`). Re-runs on the `rn:frappe-session` event (session-role.js
    fires it after the authoritative check) so the group appears/disappears
    with login state; `removePoskoFunctionGroup` handles the negative cases.
    Accordion re-wired idempotently (`wireAccordion`, `data-rnAccordionWired`).
    `posko-logistik.html` also syncs `?id=` into the URL + calls
    `window.rnRefreshPoskoFunctionGroup()` in `loadBoard()` so picking a posko
    from the `#logistikPoskoSelect` dropdown updates the sidebar group too.
    Works on every unified-nav page (logistik / shelter / dapur / posko-detail)
    with NO per-page markup. CSS accent in `rn-navigation-v2.css`
    (`[data-rn-group="posko-fn"]`). Old in-page `#poskoFnNav` bar +
    `logistik.js` `renderFnNav`/`FN_PAGES` removed. Playwright-verified:
    guest → no group; logged-in + merged posko → group first/open/3 links on
    all 3 pages; not-merged / no-`id` → none.
  - `pages/posko-logistik.html`: `<div id="logistikRoleBanner">` +
    `<section id="publicShipPanel">` "Kiriman Masyarakat" table.
  - `assets/js/logistik.js`: `renderRoleBanner` (collector = blue, receiver =
    amber w/ jiwa count), `renderPublicShipments`; `renderKpi` is
    collector-aware (Jiwa Dilayani card → "Peran Posko" / "Pengumpul", ✎ hidden).
  - `pages/organisasi-posko.html` create-posko form: `.rn-fn-picker` fieldset
    (fn_logistics / fn_shelter / fn_kitchen checkboxes) + `logistics_role`
    select. `assets/js/org-posko.js` `setupPoskoForm` rewritten to read
    `form.elements` properly (fixes a pre-existing `form.title` bug), then calls
    `create_posko` → `set_posko_functions`.
  - `style.css`: `.rn-fn-nav/.rn-fn-tab/.rn-fn-label`, `.rn-role-banner`
    (is-collector / is-receiver), `.rn-fn-picker/.rn-check`. Cache-buster
    `?v=poskofn-20260831` on style.css (all pages), logistik.js, org-posko.js,
    rn-frappe-client.js (organisasi-posko.html).
  - **Playwright-verified** via `http://host.docker.internal/rescue-net/…`
    (wait ≥ 8 s — single gunicorn worker is slow):
    WARGA → fn-nav "Logistik · Shelter · Dapur Umum", role banner "Penerima …
    melayani 1.200 jiwa", Kiriman Masyarakat panel visible, detail penuh;
    JOGJA → "Peran Posko / Pengumpul", ✎ hidden, blue collector banner, fn-nav
    hidden, no public-ship panel; create-posko form has all 3 checkboxes + the
    role select.

### DONE — KPI drill-down across groups (2026-09-01)

Every Control Centre KPI box + module tile now opens an in-page **drill-down
modal** listing the underlying items/objects/situations, grouped by the owning
organisation. Each item row shows its posko + organisation and a **"Lanjut →"**
link to `posko-detail.html`. An organisation that shares only `aggregate`
(closed coordination) contributes **counts/totals only** — no item rows
(`🔒 … menutup koordinasi rinci`); `full_authorized` orgs (or a posko whose
`public_detail=public` overrides an aggregate org) contribute the full list.

- **Backend (`api_control_centre.py`, deployed to container — RESTART PENDING):**
  new guest endpoint `kpi_drilldown(disaster_event, dimension, limit=500)`.
  Dimensions: `kebutuhan` (RN Logistic Need + RN Shelter Need),
  `posko_kritis` (map_points critical), `distribusi` / `distribusi_terhambat`
  (RN Distribution Flow), `medis` (RN Medical Case), `donasi` (RN Aid Offer),
  `stok` (RN Stock Observation, latest per posko+item), `relawan`
  (RN Volunteer Assignment), `program` (RN Donor Program), `search`
  (RN Missing/Found Person Report). `_OrgResolver` caches posko→org→share;
  `_group_by_org` splits each group's rows into `items` (share=full) vs
  `hidden_count` (share=summary) and always emits `count` / `posko_count` /
  `total_quantity` / `total_gap` / `critical_count`. Guest-tested on both sims:
  karhutla `kebutuhan` → BPBD(full_authorized)=8 items, BKSDA(aggregate but
  KH-POSKO-SATWA public)=1 item, MPA/MANGGALA(aggregate)=summary only.
- **Frontend:** `rn-control-centre-final.js` — new `drillCard()` / `openDrill()`
  / `renderDrill()` replace the six KPI `linkCard()` calls and the six module
  `linkCard()` calls. `war-room.html` — `#drillModal` markup + cache-buster
  `?v=drill-20260901` on the css/js tags. `rn-control-centre-final.css` — full
  `.cc-drill-*` block (green "Terbuka · rincian" / amber "Tertutup · ringkasan"
  badges, per-item posko/org + Lanjut link, footer legend + "Buka halaman
  modul →" fallback link).
- **DEPLOY STATE:** `api_control_centre.py` deployed to `osiun-frappe-backend`
  + container restarted; `kpi_drilldown` verified live over guest HTTP.
  Container backup `api_control_centre.py.bak-20260901-drill`.
- **Data backfill (2026-09-01):** every `RN Aid Offer` had `target_posko` set
  so donations attribute to an org and appear in the `donasi` drill-down +
  posko-logistik "Kiriman Masyarakat". Script
  `out-cc-map-20260831/fix_aid_offer_target_posko.py` (idempotent, ran OK,
  18 rows). 0 aid offers remain without a posko. Detail-vs-summary still
  depends on the org's `control_centre_share`: karhutla/sim-001 show plenty of
  detail; `event-aceh-2025` shows summary-only because "BPBD Aceh Barat" is
  `aggregate` (flip it to `full_authorized` if that event should show detail).

### NEXT

- Merged-posko function switcher is now a sidebar top group and shows on all
  unified-nav pages — DONE. The dropdown-refresh polish is also DONE:
  `logistik.js` `loadBoard()` already `history.replaceState`s the picked
  `?id=` and calls `window.rnRefreshPoskoFunctionGroup()`
  (`rn-navigation-v2.js:363`), which re-runs `mountPoskoFunctionGroup`.
- `api_ai._build_context` volunteer count — **DONE + DEPLOYED (2026-09-01).**
  `_build_context` now fetches `volunteers = _rows("RN Volunteer Assignment",
  …, 200)` and `summary` emits `volunteer_count` + `volunteer_assignment_count`
  (= `len(volunteers)`). Frontend `rn-control-centre-final.js:1790` reads
  `s.volunteer_count` → the "Relawan" module tile now shows the real count.
  Deployed to `osiun-frappe-backend` + restarted; container backup
  `api_ai.py.bak-20260901-155253-volcount`. Verified live over guest HTTP:
  `public_context` summary → `volunteer_count = 5` for both `event-sim-001`
  and `event-karhutla-kalbar-2026`.
- General page-by-page sweep: many pages still hardcode `event-aceh-2025` and
  target the retired FastAPI/PG.

### IN PROGRESS / NEXT

- **Posko Logistik page rebuilt to the DMS mock-up (`blueprint/dms*.pdf`,
  `assets/img/mockup/posko logistik.png`).** Was forms-only; now a real
  dashboard: posko selector + share banner, 4 KPI tiles (Jiwa Dilayani / Stok
  Menipis / Kebutuhan Kritis / Bantuan Menuju Posko), "Kebutuhan Mendesak"
  table (item / stok tersedia / gap / estimasi habis / waktu tiba / prioritas),
  "Asal & Trace Logistik" (nearest incoming flow + step tracker), "Upload Foto
  Kondisi" (-> evidence page), "Konversi & Volume" reference, "Barang Masuk /
  Keluar" tabs, and the two create forms tucked in a collapsed <details>.
  Backend: guest `api_control_centre.logistik_board(posko, disaster_event)`
  (reuses `posko_detail`). **E2E logistics chain added:**
  - Custom Fields (no migrate): `RN Posko.rn_beneficiary_count/note/updated_at`,
    `RN Stock Observation.rn_daily_consumption/rn_consumption_source`,
    `RN Distribution Flow.rn_movement_type`.
  - New endpoints: `logistik_stock_cards`, `logistik_incoming`,
    `logistik_open_needs` (public papan kebutuhan), `set_posko_beneficiary`,
    `set_item_consumption`, `fulfill_need` (public → creates RN Aid Offer vs a
    need). `logistik_board` now returns `stock_cards` (per-item: stok ada /
    masuk 7h / keluar 7h / OTW / kebutuhan / gap / laju konsumsi / estimasi
    habis = stok÷laju, + a variant with OTW) and `incoming` (each with a
    `distribusi_url` deep-link).
  - Seed `rn_logistik_e2e.py`: collector posko `SIM-LOG-GUDANG-JOGJA`
    (Yogyakarta, `rn_beneficiary_count=0`, `collection_hub`) + org + user
    `GUDANGJOGJA` → `RN Transport Space` convoy → `RN Distribution Flow` chain
    Jogja → BNPB hub → WARGA (disaster posko, 1200 jiwa) → consumption flows;
    stock rows at each hop; 2 aid offers toward WARGA. So the DB graph is
    connected: non-disaster collector → transport → hub → disaster posko →
    beneficiaries.
  - Frontend `logistik.js`: "Kartu Stok" table, editable Jiwa Dilayani (✎),
    OTW cell → drawer of inbound flows → "Proses distribusi →", "Penuhi" →
    fulfill_need form. `SIM-NS-WARGA`/`SIM-NS-BNPB` flipped to
    `full_authorized` so the cards show.
  NOTE: Frappe is a single worker; `logistik_board` is heavy (~0.2-0.5s local
  but the NAS→Funnel DNS is flaky — test via `http://host.docker.internal/`
  from the Playwright container, or `docker exec ... curl localhost:8000`).



- **Step B — DONE:** `assets/js/rn-public-header.js` now renders a shared
  disaster-event `<select>` ("BENCANA") in the public header on all 27 pages
  that include it (war-room.html keeps its own). Reads `?event=` → localStorage
  `rn_active_event` → `event-sim-001`; injects `?event=` into the URL when
  missing (`history.replaceState`) so each page's own JS can read it; on change
  reloads with the new `?event=`. Options come from
  `rescue_net.api_ai.public_active_disasters` (guest); degrades to the single
  current option if that fetch fails. CSS `.rn-event-picker` in `style.css`
  (header grid → 4 cols; mobile → own row). Cache-busters bumped to
  `?v=eventpicker-20260831` on rn-public-header.js and style.css.
  NOTE: many pages still hardcode a `Disaster Event ID` default in their own
  forms/JS (e.g. `event-aceh-2025`) and still target the retired FastAPI/PG —
  wiring each page to consume the picked `?event=` and hit Frappe is the
  page-by-page pass (part of Step C / the general functional sweep).
- **Step C — DONE (core):** new guest endpoint
  `rescue_net.api_control_centre.posko_detail(posko, disaster_event)` returns a
  safe **summary** rollup always, plus a `detail` bundle (needs/stocks/flows/
  offers/officer) only when `effective_posko_share` says `full`. `posko-detail.js`
  now calls it: shows a green "Detail penuh" / amber "Ringkasan saja — <org>
  menutup koordinasi" banner (`.rn-share-banner`), a "Ringkasan Posko" rollup
  panel (always), and the per-record sections only in full mode. Control Centre
  map-marker popups now show `Koordinasi: detail terbuka | ringkasan` and a
  "Buka detail/ringkasan posko →" link to `posko-detail.html?id=…&event=…`
  (uses `point.posko_id` + `detail_allowed` from `map_points`). Verified:
  ISPA(org full_authorized)→full, GAMBUT(org aggregate)→summary,
  SATWA(posko public_detail=public override)→full, MANGGALA(aggregate)→summary.
  Summary-only viewers now also get the create/record forms hidden on
  posko-detail. `organisasi-posko.html` lists every posko of the active event
  (guest endpoint `api_control_centre.event_poskos`, used when the login-scoped
  `list_poskos` returns nothing) with a "koordinasi: detail terbuka | ringkasan
  (tertutup)" badge and a drill link to `posko-detail.html?id=&event=`. The
  Control Centre "Posko Kritis" KPI already routes here, so KPI → cross-org
  posko list → drill → full/summary works end to end.
  STEP C IS DONE. (A dedicated per-dimension aggregated list for the other KPI
  boxes — Jiwa Berisiko / Bantuan Mengalir / Medis Overload / Donasi — was not
  built; those still link to their module pages, which is acceptable.)
- **Step D — partly done** (`vis_setup.py`): KH-ORG-BPBD & SIM-NS-BNPB =
  `full_authorized`; KH-ORG-BKSDA `allow_posko_public_choice` + KH-POSKO-SATWA
  `public_detail=public`; KH-POSKO-MANGGALA critical, ISPA/HELIBASE urgent,
  SIM-NS-POSKO-TNIAL-SHIP critical.
- `api_ai._build_context` summary has no `volunteer_count` → the "Relawan"
  module tile always shows 0 (1-line fix pending).
- Pre-existing uncommitted frontend↔Frappe rewiring (~30 `assets/js/*.js`, most
  `api_*.py`) predates this program — being carried along in the same commits.

- **Verification & Approval (`pages/verification-approval.html` +
  `assets/js/verification-approval.js`) — BUILT & DEPLOYED (2026-09-02),
  step 6 of the 12-step order.** 6 clickable KPIs (User/Organisasi/Posko/
  Needs/Expense/Evidence Pending), a tabbed Antrian Verifikasi (paginated,
  click a row to select), Detail Item (real fields per kind, evidence
  thumbnails via `event_evidence`, real Trust Level/Verifier Terpercaya for
  Organisasi/Posko which already carry those fields — no fabricated numeric
  score for kinds that don't), a simplified-but-real 3-step Alur Persetujuan
  + Jejak Audit timeline (derived from the record's own creation/modified
  timestamps — the mock-up's 4-stage multi-reviewer flow doesn't exist in
  the data model, so it wasn't invented), and a Tindakan bar with 4 real
  write actions. Old "Trusted Verifier Network" panels (a genuinely distinct
  concept — identity/membership endorsement, not data approval) kept intact
  in `<details>`, untouched.
  - **Backend:** new module in `api_verification.py`: `approval_queue`,
    `approval_item_detail` (both guest), `approval_action` (login required).
    The queue aggregates 6 kinds against real doctypes: User (`RN User
    Account.role_request_status == "pending"` — literal match only; empty/
    None means "never requested a role", not "awaiting review", unlike
    every other kind where empty means self-reported/unverified — this
    distinction caused a real bug during testing, see below), Organisasi
    (`RN Organization.verification_status`), Posko (`RN Posko`, event-
    scoped), Needs (`RN Logistic Need` + `RN Shelter Need`, event-scoped via
    posko since Shelter Need has no `disaster_event` column of its own),
    Expense (`RN Distribution Flow` rows that actually have
    `estimated_cost`/`actual_cost` set — real field reuse, not a new
    doctype; empty for event-sim-001, honestly 0), Evidence (reuses
    `event_evidence()`, pending status).
  - **`approval_action`** actually changes data: approve/reject/
    request_revision/escalate set the right status field per kind
    (`role_request_status` for User, `verification_status` for the rest);
    approving a User additionally grants `doc.role = doc.requested_role` —
    completing the gap `api_auth.register()`'s own docstring flagged
    ("parks role as pending... does not grant it") that nothing else in the
    app had implemented yet. Escalate bumps `urgency`/`priority` to
    `critical` where the doctype has one. **"Merge" is deliberately not
    implemented** — safely deduplicating two records needs a target-picker +
    reconciliation flow this pass didn't have scope for; the UI says so
    instead of a decorative button.
  - **Bug fix while building this (real, worth remembering):** initial
    version counted 23 "User Pending" because it reused the same
    `PENDING_TERMS = {"pending","self_reported","",None}` set used for every
    other kind — but empty `role_request_status` is the default/normal state
    for an account that never asked for a role change, not a pending
    request. Fixed to match `"pending"` literally for the `user` kind only.
  - Deployed to `osiun-frappe-backend` (md5 verified) + restarted. Playwright
    `/volume1/docker/osiun-playwright-check/rn-verif.js` (desktop + 390px
    mobile). Verified: all 6 KPIs correct (0/1/2/15/0/2), tab filter + row
    select + detail fetch work, guest write shows a graceful login-required
    message, mobile viewport exactly contained.
  - Cache-busters: `style.css`/`verification-approval.js` → `?v=verif-20260902`.

- **Sidebar/header dedup across the whole site (2026-09-02e).** Owner flagged
  that the shared top public header (`rn-public-header.js`: About Us/Fitur
  Mockup/Home/Bencana Aktif/**Control Centre**/**Data Konsolidasi**/Download/
  Laporan Masyarakat/**Kirim Bantuan**/Login) duplicated 4 entries that were
  ALSO in every page's left sidebar (`Active Disasters`→index.html,
  `Control Centre`, `Data Konsolidasi`, `Kirim Bantuan`) — removed those 4
  `<a>` lines from the standard sidebar `<nav>` block across **29** files at
  once (Python regex pass, verified byte-identical block first via grep).
  Also gave `pages/war-room.html` (Control Centre) — which had its own
  bespoke 9-item icon sidebar, structurally unlike every other page's
  `.app-shell`/`.sidebar` — the same deduped 21-item module list (still
  inside its own `.cc-sidebar` container/CSS; did **not** touch its distinct
  `.cc-header` event-selector bar or attempt a full structural migration to
  `.app-shell` — that's separate, larger scope). Verified via Playwright:
  war-room.html renders with no JS errors and the new sidebar list; spot-
  checked dapur-umum/evidence/verification-approval still render correctly
  post-mass-edit (`rn-navcheck.js`).

- **Organisasi & Posko (`pages/organisasi-posko.html` + `assets/js/
  org-posko.js`) — BUILT & DEPLOYED (2026-09-02), step 7a of the 12-step
  order (paired with the new Registrasi & Verifikasi Posko page).** 4 KPIs
  (Organisasi Aktif/Posko Aktif/Pending Verifikasi/Anggota Terdaftar),
  Struktur Organisasi with a Pohon Hierarki/Daftar toggle (org → posko tree,
  click an org to select), and a detail rail with tabs (Ringkasan/Posko/
  Anggota/Program) showing real `trust_level`/`trusted_verifier_count` (no
  fabricated 0-100 score — checked the blueprint docs, there's no such
  formula documented, so none was invented) and a real signal checklist.
  Old create-org/create-posko forms + raw lists kept in `<details>`.
  - **Backend:** new guest endpoints `api_control_centre.org_posko_board`
    and `org_detail`. "Anggota Terdaftar" sums real `RN Organization
    Membership` (approved) *and* `RN User Account.organization` — the
    formal Membership doctype is sparsely populated in the seed data (1
    global row) while `RN User Account.organization` is much better
    populated (25 rows across 14 orgs), so both real sources are unioned
    rather than under-counting off the sparser one alone. "Program" reuses
    `RN Donor Program.owner_type=="organization"/owner_id` (a real but loose
    reference, not a proper Link field). Fixed a real bug while testing:
    `operational_status` isn't just active/offline — some sim posko records
    use it as a severity field (`critical`/`urgent`/`normal`), so "Posko
    Aktif" was undercounting until the "active" check was changed to "not
    explicitly offline/inactive/closed" instead of `== "active"` literally.
  - Deployed to `osiun-frappe-backend` (md5 verified) + restarted. Playwright
    `/volume1/docker/osiun-playwright-check/rn-orgposko.js` (desktop + 390px
    mobile). Verified: KPIs correct, tree/list toggle, org select → detail
    fetch + tabs all work, mobile viewport contained.
  - Cache-busters: `style.css`/`org-posko.js` → `?v=orgposko-20260902`.
  - **Backend prep also landed for the paired Registrasi & Verifikasi Posko
    page (frontend not yet built — next up):** `RN Posko` gained 3 new
    fields (`officer_in_charge_email`, `emergency_contact`, `facilities`),
    migrated. `api_community_cluster.create_posko` extended with matching
    optional kwargs (backward compatible); added `update_posko`,
    `submit_posko_verification` ("Ajukan Verifikasi"), and `delete_posko`
    (real delete, but refuses — with a clear message to mark the posko
    offline instead — if any operational record still references it, so a
    click can't silently orphan data). New guest reads
    `api_control_centre.posko_verification_checklist` (5 real filled-field
    checks) and `posko_registry_board` (KPIs + Daftar Posko table).

- **Registrasi & Verifikasi Posko (`pages/registrasi-posko.html` +
  `assets/js/registrasi-posko.js`) — NEW PAGE, BUILT & DEPLOYED
  (2026-09-02), completes step 7/12.** 4 KPIs (Posko Aktif/Pending
  Verification/Official Verified/Community Verified), a full posko
  registration form (writes via the extended `create_posko`, login
  required), a real "Status Verifikasi Posko" checklist (5 items, each a
  literal filled-field check — Email/No HP/Identitas PIC/Lokasi/Trusted
  Verifier), Tindakan (Ajukan Verifikasi → `submit_posko_verification`,
  Hapus Posko → `delete_posko` with a confirm dialog, Simpan Draft →
  informational only since every posko is already a live draft from
  creation), and a searchable paginated Daftar Posko table. Editing an
  existing posko's full field set from the table isn't wired (would need a
  richer "get full posko" read than `posko_verification_checklist`
  returns) — selecting a row drives the checklist/actions panel, which is
  the mock-up's actual emphasis; the form stays create-focused. Linked into
  every other page's sidebar (see below).
  - Also added a small global `.btn:disabled { opacity:.45; cursor:not-
    allowed; }` to `style.css` — there was no disabled-button styling
    anywhere in the app before, so the new disabled Approve/Ajukan/etc.
    buttons on this page (and Verification & Approval's action bar) looked
    identical to enabled ones despite correctly blocking clicks.
  - Deployed to `osiun-frappe-backend`. Playwright `/volume1/docker/
    osiun-playwright-check/rn-regposko.js` (desktop + 390px mobile).
    Verified: KPIs correct, row select → real checklist + correctly
    disabled/enabled actions, guest form submit shows graceful login
    message, mobile viewport contained.
  - Cache-buster: `style.css`/`registrasi-posko.js` → `?v=regposko-20260902`.
  - **Rolled the "Registrasi & Verifikasi Posko" sidebar link out to every
    other page** (24 files via a Python regex insert after the "Organisasi
    & Posko" line; 2 more — `bencana-aktif.html`/`posko-logistik.html` —
    needed a second pass since they spell it `Organisasi &amp; Posko`
    (HTML entity) instead of a literal `&`, which the first regex missed).
    `control-centre-v4.html` (deprecated, superseded by `war-room.html`,
    already on the "no mockup" leave-as-is list) and
    `laporan-masyarakat.html`/`mockup.html` (no sidebar `<nav>` at all —
    different page types) were correctly left untouched.

- **Manajemen Alat Kerja (`pages/alat-kerja.html` + `assets/js/
  alat-kerja.js`) — BUILT & DEPLOYED (2026-09-02), step 8/12.** 6 KPIs (Alat
  Tersedia/Kebutuhan Alat/Operator Aktif/Dispatch Berjalan/BBM Kritis/Alat
  Rusak) with drill modal, Inventari Alat per Kategori (6 tiles: Ekskavator/
  Genset/Pompa Air/Forklift/Chainsaw/Perahu Karet, each with a Ready/
  Assigned/Maintenance/Critical breakdown from real `availability_status`),
  Operator & Tenaga Teknis (from `RN Work Tool Deployment.operator_name`),
  Matching Kebutuhan Alat (open requests ranked by priority, each showing
  real candidate-resource count/name), Jadwal Dispatch Alat table, Lokasi
  Kerja & Produktivitas (completion-rate progress bar per destination),
  BBM & Support Operasional, QR/Asset Tracking (honest static lookup table —
  no camera scanner exists, said so on the page instead of faking it), and
  Hambatan Alat Kerja + Ringkasan Hari Ini. Old "Buat Request Alat Kerja" +
  "Daftar Request Alat Kerja" kept working, moved into `<details
  class="rn-input-drawer">`.
  - **Backend:** new guest endpoint `api_resource_tools.tools_board
    (disaster_event)` → `{totals, kpi_items, categories, operators, matches,
    dispatch, sites, fuel, blockers, summary, asset_registry}`. PIC name/
    phone are never included (same privacy discipline as the existing
    `dashboard()`/`restricted_resource()`). Fixed the same latent guest-
    whitelist bug found on every prior page's legacy `dashboard()` —
    `api_resource_tools.dashboard()` was `@frappe.whitelist()` (login-only,
    threw a raw 403 for anonymous visitors); changed to `allow_guest=True` +
    `rn_actor(required=False)`, confirmed with the user first per the
    established pattern. Ownership-scoped visibility (`_visible_resource`/
    `_visible_request`) is untouched, so a guest still sees an empty list
    there by design — that's what the new `tools_board` is for.
  - **Data gap found and filled (per "kalau kamu menemukan menu atau fungsi
    yang nggak ada di existing, laporkan dan lengkapi"):** `RN Resource
    Profile`/`RN Work Tool Request`/`RN Work Tool Deployment` existed with a
    full field model but were essentially empty for `event-sim-001` (3
    Resource Profiles system-wide, 0 tagged to any event, 0 requests, 0
    deployments) — the mockup's whole page would have been empty states.
    Seeded real rows instead of fabricating payload data: 30 `RN Resource
    Profile` (5 units × 6 categories, spread across available/limited/
    maintenance/unavailable so every legend bucket and KPI has a genuine
    non-zero count), 9 `RN Work Tool Request` (priority/status mix, Aceh
    Barat locations consistent with `event-sim-001`'s existing narrative), 5
    `RN Work Tool Deployment` (operator name/skill, 2 dispatched today so
    "Dispatch Selesai"/"Jam Operasional" in Ringkasan Hari Ini are non-zero),
    3 `RN Stock Observation` (Solar/Bensin Pertalite/Oli at Posko BNPB
    Meulaboh — Bensin and Oli seeded intentionally low so "BBM Kritis" KPI
    has real matches). Owners: `organizations:org-bpbd-aceh` and
    `organizations:org-sim-tni` (both pre-existing, event-appropriate orgs).
    Ran `_refresh_request_status` after seeding deployments so
    `request_status` reflects real fulfillment state rather than staying
    "requested".
  - **"Ringkasan Hari Ini" fields are honestly derived, not fabricated:**
    Penggunaan % = active deployments ÷ total resources; Jam Operasional =
    sum of `completed_at − deployed_at` for today's completed deployments;
    Dispatch Selesai = today's completed-deployment count; Kerusakan Baru =
    resources in maintenance/unavailable whose `modified` date is today.
    Note: because all seed data was created in one session today, Kerusakan
    Baru currently reads as "all damaged equipment" rather than "newly
    damaged today" — an artifact of a freshly-seeded demo (same as every
    other page's "hari ini" stats), not a bug in the derivation.
  - Deployed to `osiun-frappe-backend` (md5 verified) + restarted. Playwright
    `/volume1/docker/osiun-playwright-check/rn-alatkerja.js` (desktop 1440px
    + 390px mobile). Verified: all 6 KPIs non-zero and correct, 6 category
    tiles, 5 operators, 4 open matches, 5 dispatch rows, 5 site rows, 3 fuel
    rows, 30-row asset registry, 12 blockers, drill modal opens with real
    items, legacy request-list panel now renders (previously hit the raw
    403), zero horizontal overflow at 390px.
  - Cache-buster: `style.css`/`alat-kerja.js` → `?v=alatkerja-20260902`.

- **Control Centre mobile menu fixed (2026-09-02, same day as step 8/9):**
  the owner flagged the sidebar changes "belum bener" on `war-room.html`.
  Root cause was two separate bugs: (1) the mobile ☰ button had no click
  handler and `.cc-sidebar` was `display:none` at ≤760px with no way to
  reveal it, so the already-deduped module list was completely unreachable
  on mobile — the only reachable mobile nav was a stale separate 5-item
  bottom tab bar (Control/Peta/Posko/Bantuan/Lainnya) that still linked
  "Bantuan" even though that item was deliberately removed everywhere else
  as a header duplicate. Fixed by wiring the ☰ button to a real off-canvas
  drawer (`.cc-sidebar.is-open` + backdrop) and deleting the dead bottom
  bar. (2) **Bigger finding:** `rn-navigation-v2.js` — loaded on every page
  except `war-room.html` — completely replaces whatever static `<nav><a>`
  list is in the HTML with its own hardcoded `CONFIG.posko`/`CONFIG.modules`
  grouped accordion at runtime. This means most of this session's careful
  static-`<nav>` edits (dedup pass, "Registrasi & Verifikasi Posko" rollout)
  were invisible on every page that loads this script — the real rendered
  menu is `CONFIG`, not the HTML. `war-room.html` was the one page that
  *didn't* load the script, so it alone showed the raw static list —
  looking structurally different from every other page even after the
  earlier dedup work landed. Fixed by (a) loading `rn-navigation-v2.js` +
  `.css` on `war-room.html` too (its `.cc-sidebar > nav` qualifies via the
  script's own `OPERATIONAL_LINKS` scoring, no other change needed), (b)
  adding the missing "Registrasi & Verifikasi Posko" item to `CONFIG.posko`
  (was never added there, only to the static per-page fallback), bumping
  `CONFIG.version` 2.0.2→2.0.3, and bumping the cache-buster query string
  on all 28 pages that load the script. Verified via Playwright
  (`rn-warroom-menu.js`, `rn-navcheck2.js`): all three spot-checked pages
  (dapur-umum/alat-kerja/war-room) now render the identical 23-item grouped
  menu (13 Posko + 10 Modul), war-room's mobile drawer opens/closes
  correctly with a backdrop, zero console errors, desktop layout unaffected.
  **Lesson for any future nav edit:** always check whether
  `rn-navigation-v2.js` is loaded on the page before assuming a static
  `<nav>` edit will be visible — if it's loaded, edit `CONFIG` in that file
  instead (or in addition, for the no-JS fallback).

- **Profil Sumber Daya (`pages/resource-profile.html` + `assets/js/
  resource-profile.js`) — BUILT & DEPLOYED (2026-09-02), step 9/12.** The
  mockup turned out to be a **personal volunteer/member profile** (status
  chips, profile card, Keahlian/Kendaraan/Fasilitas/Bantuan Barang/Wilayah
  Layanan/Waktu Ketersediaan/Kebutuhan Support cards, all self-editable) —
  not the old page's multi-category directory (Organizations/Posko/
  Volunteers/Tools), same kind of concept-swap as Shelter/Verification
  earlier in this pass. Old directory kept working inside `<details>`.
  - **Backend:** new guest endpoint `api_resource_tools.resource_profile_board
    (user_account)` — defaults to the logged-in session's `RN User Account`,
    else falls back to a seeded demo volunteer (`SIM-VOL-YUSUF`), same
    "sensible default when nothing specified" convention every other board
    uses for its event param. Kendaraan/Fasilitas/Bantuan Barang all map to
    real `RN Resource Profile` rows with `owner_type=individual` — new
    self-service write `add_personal_resource` (deliberately separate from
    the existing `create_resource_profile`, which gates on a MANAGER_ROLES
    operator role that a plain volunteer will never have; the right gate
    for "I manage my own stuff" is just "is this actually me", which
    required extending `_can_manage_reference` with an `individual` case).
    Kebutuhan Support maps to `RN Work Tool Request` — new self-service
    write `add_personal_support_need` using `requested_by_type="other"`,
    **not** `"individual"` — the doctype's own `validate()` only allows
    `{posko, organization, other}`, discovered by hitting a real
    `ValidationError` while seeding (the Select field on the JSON schema
    listed `individual` as valid for `RN Resource Profile.owner_type`, but
    `RN Work Tool Request.requested_by_type`'s Python `validate()` has a
    narrower, separate allow-list that doesn't include it). Skills/Wilayah
    Layanan/Waktu Ketersediaan/Tentang Saya/Edit Profil all write through
    `api_volunteer.update_profile`, extended with `skill_category`/
    `preferences`/`equipment_owned`/`service_areas`/`availability_schedule`
    kwargs (the function already existed with a correct self-ownership
    check via `doc.user_account == actor.name` — just missing params for
    fields the mock-up needed).
  - **New `RN Volunteer Profile` fields** (migrated): `service_areas`,
    `availability_schedule` (both Small Text, one line per entry, parsed/
    joined client-side — same free-text-list pattern as `skill_tags`,
    deliberately not new child-table doctypes since nothing else in the app
    uses that pattern and the data is inherently simple key-value lines).
  - **Trust chips are honest, not fabricated:** "Tingkat Kepercayaan"/"ID
    Terverifikasi" read the volunteer profile's real `verification_status`
    (self_reported/verified) rather than inventing the mock-up's 0-100
    numeric score — same "no invented formula" call already made for
    Organisasi & Posko's trust display. Email/HP Terverifikasi are a plain
    "field is filled" check, same honesty level as Registrasi Posko's
    verification checklist elsewhere in this app.
  - **Demo persona seeded:** enriched an existing thin volunteer record
    ("Yusuf Hidayat", Search & Found/K9 Handler, Samatiga Aceh Barat) rather
    than inventing a new one — linked a new `RN User Account`
    (`SIM-VOL-YUSUF`, `legacy_id`-named since native accounts require a
    linked Frappe `User` the autoname can hash, which sim/demo accounts
    don't have), filled skill_tags/service_areas/availability_schedule/
    notes, and added 5 `RN Resource Profile` rows (2 kendaraan, 1 fasilitas,
    2 barang_bantuan) + 3 `RN Work Tool Request` (BBM/Tenda/Peralatan Masak)
    owned by that account.
  - Also fixed the same recurring guest-whitelist-style issue on the
    *legacy* directory panel while in there: its `Promise.all([dashboard,
    api_ai.context, control_centre_volunteers])` had no per-call `.catch`,
    so `api_ai.context` (never guest-whitelisted) rejecting the whole
    `Promise.all` silently blanked the entire drawer for guests — including
    the Organizations/Resources data that `dashboard()` already returns
    correctly since its earlier guest-access fix. Added per-call `.catch`
    fallbacks (matching the existing pattern already used for
    `control_centre_volunteers`) so each of the 4 legacy panels degrades
    independently. Also wired the KPI counters in that panel
    (`kpiOrg`/`kpiPosko`/`kpiVolunteer`/`kpiResource`), which had never
    been set by any code since the page was first built — a pre-existing,
    unrelated bug fixed opportunistically while already in the function.
  - Deployed to `osiun-frappe-backend` (md5 verified) + restarted. Playwright
    `/volume1/docker/osiun-playwright-check/rn-resprofile.js` (desktop 1440px
    + 390px mobile). Verified: identity/chips/skills/kendaraan/fasilitas/
    barang/wilayah/jadwal/kebutuhan all render real seeded data, guest write
    attempts show a graceful "perlu login" message (no crash), legacy drawer
    renders without error, zero horizontal overflow at 390px.
  - Cache-buster: `style.css`/`resource-profile.js` → `?v=resprofile-20260902`.

- **Control Centre header stacking fixed (2026-09-02, "menu numpuk"):**
  after loading `rn-public-header.js` on `war-room.html` (previous entry),
  the owner flagged it looked stacked/crowded. Playwright bounding-rect
  measurement found the real bug: `.rn-public-links` (the header's 10 nav
  links) had no `flex-wrap`, so at 1440px they overflowed their grid column
  by ~31px (`scrollWidth` 947 vs 916px available), visually colliding the
  "Login/registrasi" pill with the disaster-event picker next to it —
  `overlap:true` measured via `getBoundingClientRect`, confirmed present
  on *every* page (not war-room-specific), just newly visible because this
  was the first time this session anyone looked closely at the header on
  a freshly-touched page. Fixed by adding `flex-wrap:wrap` + `min-width:0`
  to `.rn-public-links` in both `style.css` (site-wide) and the new
  `rn-public-header-standalone.css` (war-room's copy) — wraps to a second
  centered row instead of overflowing. Re-measured `overlap:false` on both
  a normal page and war-room.html after the fix. The mobile 3-row stack
  war-room now has (public header w/ picker + `.cc-mobile-bar` + its own
  `.cc-header` title bar) was checked too and found to NOT be worse than
  a normal page's 2-row stack (drawer-topbar + public header, then that
  page's own `.topbar` — comparable total height) — so left as-is; the
  actual "numpuk" was the desktop overlap, not extra mobile rows.

- **Manajemen Alat Kerja extended: Object Kerja + AI equipment-grouping
  (2026-09-02, owner directive, same day as step 8 build):** two real
  additions to `pages/alat-kerja.html`/`assets/js/alat-kerja.js`, not
  originally in the mock-up but requested directly.
  - **Object Kerja & Prediksi Kebutuhan Alat** — new doctype `RN Work
    Object` (object_type: longsoran/jembatan_putus/puing_berat/
    pohon_tumbang/akses_terendam/lainnya, size_value + size_unit,
    location, status). New guest endpoint `api_resource_tools.
    work_objects_board(disaster_event)` runs each object through a small,
    explicitly-documented heuristic (`_EQUIP_PREDICTION_RULES`, e.g. "1
    ekskavator per ~150 m³ material longsor") to predict equipment
    category + quantity, then cross-references real `ready_available`
    count per category (same categories as the Inventari Alat tiles) to
    surface a real `gap`. Deliberately labelled as a heuristic estimate,
    not an engineering calculation, both in the API response
    (`method_note`) and on the page. New writes `create_work_object`
    (login required, any authenticated actor — deliberately not gated to
    MANAGER_ROLES since reporting a damaged object is closer to a field
    report than an operator action) and `update_work_object_status`
    (manager-gated). Seeded 4 objects for event-sim-001 tied to the
    existing Aceh Barat narrative (longsoran KM 12, jembatan putus Alue
    Gajah, puing Pasar Meulaboh, pohon tumbang jalur evakuasi Samatiga).
  - **Kelompok Alat (Normalisasi AI Lintas Posko)** — `tools_board` gained
    a `groups` key that groups every Resource Profile (any owner —
    organization/posko/individual, i.e. genuinely cross-posko) by a
    canonical group name, so the same equipment scattered across many
    owners with different raw names/units still rolls up into one line.
    Reused real, already-existing infrastructure instead of building a
    new "AI" concept from scratch: added `canonical_category/group/item` +
    `normalization_source/confidence/status` fields to `RN Resource
    Profile` (exact same field shape already used on `RN Stock
    Observation`/`RN Community Need`), and extended
    `rescue_net.intelligence.normalization.classify_text()` (the app's
    existing rule-based keyword classifier, previously only wired to
    Community Need classification) with 6 new specific rules — Ekskavator/
    Genset/Pompa Air/Forklift/Chainsaw/Perahu Karet — replacing one overly
    generic "Alat Berat" rule that would have lumped them all together.
    Groups honestly show a `source` (`manual` when an operator set
    canonical fields directly, `rule` when `classify_text()` guessed it
    live, never a fabricated black-box "ai" call for what's actually
    deterministic keyword matching) and `avg_confidence`. **Different
    units are never summed** — `same_unit:false` groups return
    `total_qty:null` and a per-unit `unit_breakdown` array instead (e.g.
    Genset: 5×`unit` + 2×`set`, shown as two separate chips) — backfilled
    the 30 step-8 seed resources with `normalization_source=manual,
    confidence=100` and added one extra Genset row in a different unit
    from a different org specifically so this case is real and visible in
    the demo, not just structurally supported.
  - Deployed to `osiun-frappe-backend` (md5 verified, migrated cleanly) +
    restarted. Playwright `/volume1/docker/osiun-playwright-check/
    rn-alatkerja2.js`: 4 object cards with real predictions/gaps render,
    10 group rows including the mixed-unit Genset case, guest write shows
    graceful "perlu login" message, zero mobile overflow, zero console
    errors.
  - Cache-buster: `style.css`/`alat-kerja.js` → `?v=alatkerja-20260902b`.

- **Public header redesigned (2026-09-02, "renggang, kaya web amatiran"):**
  the header worked correctly but looked unprofessional — 68px tall, two
  wrapped rows, 20px gaps, a lone logo with no wordmark, "Login/registrasi"
  as a bare unstyled link, a 260px-wide event-picker select. Redesigned for
  density: added a "Rescue-Net" wordmark next to the logo; pulled the login
  link out of the nav-links row into its own grid cell as a solid coral CTA
  button; tightened link padding/font/gaps and switched centered→left-
  aligned so all 9 links fit one row at common desktop widths (measured via
  Playwright: natural nowrap width 924px→779px vs 806px available column,
  down from the original 947px overflow bug fixed earlier); shrunk the
  event-picker (260px/38px→200px/32px) and header height (68px→56px, with
  the `.sidebar`/`.app-shell` top-offset calc()s updated to match). Mirrored
  into `rn-public-header-standalone.css` for Control Centre. This is a
  judgment-call redesign (not a bug fix) — if the owner wants further
  tightening or a different visual direction, expect another round.

- **Program Khusus (`pages/program-khusus.html` + `assets/js/
  program-khusus.js`) — BUILT & DEPLOYED (2026-09-02), step 10/12.** 6 KPIs
  (Program Aktif/Critical/Selesai/Milestone Terlambat/Lokasi Belum
  Terlayani/Butuh Support) with drill modal, Daftar Program list (tabs
  Semua/Aktif/Critical/Selesai, progress bars) driving a detail panel with
  Ringkasan/Anggaran/Riwayat tabs. Old "Buat Program"/"Update Progress"
  forms preserved in `<details>`.
  - **Backend:** new guest endpoints `api_donor_program.program_board`/
    `program_detail`. Key discovery: `program_type == "special_program"`
    was never a real scoping filter — it was only ever the create-form's
    default value; real seeded programs use domain-specific types
    (nutrition/education/psychosocial/energy_support/health/
    water_sanitation). Dropped that filter entirely — the board now shows
    every public `RN Donor Program` regardless of type, using
    `program_type` purely as a display category label.
  - **Honest deviations from the mock-up** (documented in the plan doc, not
    silently dropped): "Rencana Kerja"/"Dokumen"/"Catatan" as separate
    tabs, a "Lokasi Implementasi" mini-map, and "Verifikasi Output" were
    NOT built — no per-line rencana-kerja/dokumen data or per-program
    coordinates exist in the data model, and Anggaran + Riwayat Update
    already serve as an honest progress source of truth. The 4 mock-up
    "Support" cards (Logistik/Distribusi/Relawan/Alat Kerja) are real
    deep-links to the relevant module pages, not a fabricated "Butuh
    Support" status/quantity — no relational field ties a Donor Program to
    a specific need in another module, so faking that status would have
    been invented data.
  - **KPIs are honestly derived, not fabricated:** "Milestone Terlambat" =
    active programs whose real `end_date` has already passed; "Lokasi
    Belum Terlayani" = distinct locations among active programs with zero
    updates; "Butuh Support" = active + high/critical priority + progress
    <50%, all from real fields. `progress_percent` uses the latest real
    Update's value when one exists, else derives from
    `current_amount/target_amount` — never fabricated.
  - **Data was thin, enriched rather than invented:** the 4 existing
    event-sim-001 `RN Donor Program` rows had zero budget/date/officer
    fields and 3 had never received an Update — filled in budget_target/
    received/spent, start/end dates, officer_in_charge, and added a real
    Update per program using each program's own existing
    current_amount/target_amount ratio (not arbitrary numbers). Added 2
    more programs (Toilet Portable Darurat [active, 45%], Pos Kesehatan
    Keliling [completed, 100%]) to round out the KPI/filter demo (one late
    milestone, one completed example, etc.).
  - Fixing the same recurring guest-whitelist bug on the legacy panel's
    `context()` endpoint was offered and the owner declined this time
    ("Jangan, biarkan") — legacy drawer still shows a 403 for guests,
    left as-is; the new `program_board`/`program_detail` guest endpoints
    are unaffected and fully functional.
  - Deployed to `osiun-frappe-backend` (md5 verified) + restarted.
    Playwright `/volume1/docker/osiun-playwright-check/rn-progkhusus.js`:
    6 KPIs correct, 6 program cards, filter tabs work, card selection
    swaps detail panel, Anggaran/Riwayat tabs render real data, KPI drill
    modal works, zero mobile overflow, zero console errors (aside from the
    intentionally-left-alone legacy 403).
  - Cache-buster: `style.css`/`program-khusus.js` → `?v=progkhusus-20260902`.

## Rules / gotchas

- **Frappe bench console via stdin** breaks on multi-line `for` loops and on
  comprehensions that close over semicolon-assigned locals (IPython splits
  globals/locals). Wrap scripts as
  `exec(open('/tmp/x.py').read(), {'__name__':'__main__'})` (one line).
- `File.file_url` rejects site-relative paths that aren't `/files/…`. Store sim
  evidence in `legacy_payload.evidence.image` (or `RN Community Report Evidence`,
  whose `file_url` is a plain Data field) pointing at
  `/rescue-net/assets/img/demo-landrover/evidence/<name>.jpg`.
- Do not hardcode map pins in JS; fix coordinates on the `RN Posko` record.
- Playwright runs only inside Docker image `mcr.microsoft.com/playwright:v1.56.1-noble`
  (host chromium lacks GUI libs). Scripts in `/volume1/docker/osiun-playwright-check/`.
