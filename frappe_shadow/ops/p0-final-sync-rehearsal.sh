#!/usr/bin/env bash
set -euo pipefail
DOCKER=${DOCKER:-/usr/local/bin/docker}
SUDO_PASSWORD=${SUDO_PASSWORD:-003180}
OPS_DIR=${OPS_DIR:-/volume1/docker/osiun-frappe-shadow/ops}

sudo_docker() {
  printf '%s\n' "$SUDO_PASSWORD" | sudo -S "$DOCKER" "$@"
}

bench_exec() {
  local method=$1
  sudo_docker exec -u frappe osiun-frappe-backend bash -lc "cd /home/frappe/frappe-bench && bench --site osiun.localhost execute $method"
}

echo "STEP source/target status before"
bench_exec rescue_net.migration.status.build_status_report_json

echo "STEP import_live"
bench_exec rescue_net.migration.import_from_rescuenet_pg.import_live

echo "STEP backfill_links"
bench_exec rescue_net.migration.link_backfill.backfill_links

echo "STEP build_shadow_snapshot"
bench_exec rescue_net.migration.war_room.build_shadow_snapshot

echo "STEP validation"
bench_exec rescue_net.migration.validation.build_validation_report_json | grep -Eq 'failure_count(\\?":|":) 0'
echo "VALIDATION failure_count=0"

echo "STEP p0 cutover dry-run gate"
"$OPS_DIR/p0-cutover-gate.sh"

echo "P0 FINAL SYNC REHEARSAL PASS shadow-only"
