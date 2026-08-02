#!/usr/bin/env bash
set -euo pipefail
DOCKER=${DOCKER:-/usr/local/bin/docker}
SUDO_PASSWORD=${SUDO_PASSWORD:-003180}
FRAPPE_URL=${FRAPPE_URL:-http://127.0.0.1:8095}
OPS_DIR=${OPS_DIR:-/volume1/docker/osiun-frappe-shadow/ops}

sudo_docker() {
  printf '%s\n' "$SUDO_PASSWORD" | sudo -S "$DOCKER" "$@"
}

"$OPS_DIR/smoke-shadow.sh"

status_json=$(curl -sS --max-time 30 "$FRAPPE_URL/api/method/rescue_net.compat.api.status")
echo "STATUS ${status_json:0:360}"

if [[ "$status_json" != *"ready-for-next-shadow-step"* ]]; then
  echo "FAIL: readiness is not ready-for-next-shadow-step" >&2
  exit 1
fi

if [[ "$status_json" != *'"cutover_allowed":false'* ]]; then
  echo "FAIL: compatibility status must remain cutover_allowed:false before explicit owner approval" >&2
  exit 1
fi

sudo_docker exec -u frappe osiun-frappe-backend bash -lc 'cd /home/frappe/frappe-bench && bench --site osiun.localhost execute rescue_net.migration.validation.build_validation_report_json' | grep -Eq 'failure_count(\\?":|":) 0'
echo "VALIDATION failure_count=0"

echo "MANUAL BEFORE CUTOVER: freeze P0 writes, backup PostgreSQL, backup Frappe MariaDB, run final import_live, backfill links, rebuild War Room, rerun this gate."
echo "P0 CUTOVER GATE PASS shadow-only dry-run"
