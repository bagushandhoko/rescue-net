# Rescue-Net — Working Handover

> Living status doc so a fresh session (any AI account, or a teammate) can pull
> this repo and immediately know **what is done, what is in flight, what is next**.
> Update this file in the same commit as the work it describes.

_Last updated: 2026-08-31 (posko function model)_

---

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

- **Control Centre (`pages/war-room.html` + `assets/js/rn-control-centre-final.js`)**
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

### NEXT

- Merged-posko function switcher is now a sidebar top group and shows on all
  unified-nav pages — DONE. Remaining polish: on `posko-logistik.html` the
  posko can also be changed via the `#logistikPoskoSelect` dropdown; the
  sidebar group only reflects the URL `?id=`, so switching via the dropdown
  doesn't refresh it. Have `logistik.js` push the new id into the URL
  (`history.replaceState`) and re-call `mountPoskoFunctionGroup`, or just
  reload with `?id=`.
- `api_ai._build_context` summary has no `volunteer_count` → the "Relawan"
  module tile always shows 0 (1-line fix pending).
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
