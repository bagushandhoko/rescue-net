# Phase 5 step 3 — web vs offline app: duplicated logic and a decision to take (2026-09-26)

Architecture-review phase 5 asks whether the website and the separate offline app
(`apps/rescue-net-app`, served as `/rescue-net-app/`, wrapped with Capacitor for the Android/iOS/desktop
downloads) should share code. This is the audit and a recommendation; **nothing has been merged yet**.

## What the app does, and where the web already does the same

| App feature (`src/app.js`, 975 lines) | Web equivalent | Duplicated? |
|---|---|---|
| Offline queue in `localStorage`, retry on reconnect, `api_sync.push` | `assets/js/rn-sync-engine.js` (329 lines) — same idea, same endpoint, used by 6 pages (e.g. Laporan Masyarakat queues a report while offline) | **yes — two queues, two formats** |
| Community report form + evidence photo | `pages/laporan-masyarakat.html` + `community-report.js` (now with AI narrative intake, posko routing, follow-ups, login gate) | **yes — the app's form is the older, poorer copy** |
| Admin-area tree (province → village), wilayah.id fallback | Laporan Masyarakat / Registrasi Posko area pickers (`api_admin_areas`) | yes |
| Choose active disaster, create a disaster | Bencana Aktif / event picker on every page | yes |
| Device / posko registration | `pages/registrasi-posko.html` (the real flow with approval) | yes — the app now only records the device |
| Consolidation view, duplicate check, rebuild | `pages/data-consolidation.html` | yes |
| Unit catalogue / normaliser | Kelompok Alat / normalisation on the web boards | partly |
| Frappe client (session, CSRF, error text) | `assets/js/rn-frappe-client.js` | yes — re-implemented in the app in phase 3 |
| Installable (manifest + service worker) | **no** — the website has no manifest / service worker | the app's only unique part |

So the app's only real difference is that it is **installable and works fully offline**; every screen it
has exists on the web, usually in a newer and stricter form (login gate, routing, validations).

## Options

**A. Keep two front ends, share modules.** Move `rn-frappe-client.js`, `rn-sync-engine.js`, `rn-ui.js` and
the area picker into a shared folder both load (the PWA from `/rescue-net/assets/js/`, the native builds
copy them at build time). Keeps two sets of screens to maintain; every new rule (like the report login
gate) must still be built twice.

**B. One front end — make the website the app (recommended).** Add a web manifest and a service worker to
the website (app shell + the offline queue it already has), point the Capacitor builds at the website's
pages, and retire `apps/rescue-net-app/src/app.js`. One set of screens, one offline queue, one Frappe
client; the Android/desktop downloads become a wrapper of the same pages.

Cost of B (rough): manifest + service worker + "works offline" pass on the pages that field users need
offline (Laporan Masyarakat, Posko Logistik, Registrasi Posko, Shelter) — a few focused sessions; rebuild of
the native wrappers on `/volume1/web/rescue-net-build`. No framework change — plain JS stays (step 4:
**no framework migration is proposed**; nothing in the audit needs one).

## Decision for the owner

1. **B** (one front end, website becomes the installable app), or **A** (two front ends sharing modules)?
2. Until then the app stays as it is (on Frappe since phase 3) — no user-visible change.
