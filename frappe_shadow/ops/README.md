# Frappe Shadow Runtime Ops

This directory mirrors the runtime configuration used by `/volume1/docker/osiun-frappe-shadow`.

The Rescue-Net Frappe app is mounted persistently from `apps/rescue_net` into backend, worker, and scheduler containers. Each container installs the app editable before starting its Frappe process so recreated containers can import `rescue_net` without manual docker copy.

Current mode remains shadow-only. These files do not authorize production reroute or cutover.

## Smoke Test

Run `./smoke-shadow.sh` on the server to verify the shadow runtime after restart/recreate. It checks persistent app mounts, Python import, Rescue-Net existing web/API health, Frappe shadow health, compatibility API, and migration readiness.

If Frappe website pages return `No module named osiun_core`, clear the stale `installed_apps` default in the shadow MariaDB so it contains only `["frappe", "erpnext", "rescue_net"]`, then clear Frappe cache.

## P0 Cutover Gate

Run `./p0-cutover-gate.sh` before any P0 cutover discussion. It is a dry-run gate only: it runs smoke checks, validates shadow readiness, confirms compatibility API remains shadow-only, and prints the manual steps still required before any reroute.
