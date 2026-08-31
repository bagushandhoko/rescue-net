# Rescue-Net — Working Handover

> Living status doc so a fresh session (any AI account, or a teammate) can pull
> this repo and immediately know **what is done, what is in flight, what is next**.
> Update this file in the same commit as the work it describes.

_Last updated: 2026-08-31_

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
    `rn_karhutla_e2e.py`, `vis_setup.py`) — re-runnable, idempotent (upsert by
    `legacy_id`).
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

### IN PROGRESS / NEXT

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
- **Step C:** `pages/posko-detail.html` + `pages/organisasi-posko.html` render a
  **summary** vs **full-detail** view driven by `share_mode` / `detail_allowed`;
  KPI box → aggregated cross-org list (`?focus=…`) → drill into a posko.
- **Step D:** flip 1–2 sim orgs to `full_authorized`, set some posko
  `operational_status` to critical/warning (partly done in `vis_setup.py`), so
  both visibility modes and map colours are visible.
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
