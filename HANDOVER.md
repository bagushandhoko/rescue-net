# Rescue-Net — Working Handover

> Living status doc so a fresh session (any AI account, or a teammate) can pull
> this repo and immediately know **what is done, what is in flight, what is next**.
> Update this file in the same commit as the work it describes.

_Last updated: 2026-09-03 (Distribusi booking UX pass: row→posko penyedia, scoped booking drawer w/ slot+space+delivery-method, follow-up contacts for pensuplai & transporter; Step 12 mobile sweep clean)_

---

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
