# Rescue-Net — Working Handover

> Living status doc so a fresh session (any AI account, or a teammate) can pull
> this repo and immediately know **what is done, what is in flight, what is next**.
> Update this file in the same commit as the work it describes.

_Last updated: 2026-09-01 (mockup-alignment pass: welcome polish; auth.html rebuilt + api_auth.register DEPLOYED; NEW pages/bencana-aktif.html + active_disasters_board endpoint DEPLOYED & Playwright-verified)_

---

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
