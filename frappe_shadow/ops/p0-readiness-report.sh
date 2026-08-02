#!/usr/bin/env bash
set -euo pipefail
ROOT=${ROOT:-/volume1/web/rescue-net}
OPS_DIR=${OPS_DIR:-/volume1/docker/osiun-frappe-shadow/ops}
FRAPPE_URL=${FRAPPE_URL:-http://127.0.0.1:8095}
REPORT_PATH=${REPORT_PATH:-$ROOT/frappe_shadow/ops/P0_READINESS_REPORT.md}
LATEST_BACKUP=$(find "$ROOT/_archive/frappe-p0-precutover" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort | tail -n 1 || true)
GIT_COMMIT=$(cd "$ROOT" && git log -1 --oneline)
STATUS_JSON=$(curl -sS --max-time 30 "$FRAPPE_URL/api/method/rescue_net.compat.api.status")
HEALTH_JSON=$(curl -sS --max-time 20 "$FRAPPE_URL/api/method/rescue_net.compat.api.health")
RN_API_JSON=$(curl -sS --max-time 20 http://127.0.0.1/rescue-net-api/)
RN_WEB_HEAD=$(curl -sS -I --max-time 20 http://127.0.0.1/rescue-net/ | head -n 1)
FRAPPE_HEAD=$(curl -sS -I --max-time 20 "$FRAPPE_URL/" | head -n 1)

mkdir -p "$(dirname "$REPORT_PATH")"

cat > "$REPORT_PATH" <<EOF
# Rescue-Net P0 Frappe Readiness Report

Generated at: $(date -Iseconds)

## Decision State

- Mode: shadow-only
- Cutover allowed: false
- Production reroute: not performed
- Latest Git commit: $GIT_COMMIT

## Health

- Rescue-Net web: $RN_WEB_HEAD
- Rescue-Net API: $RN_API_JSON
- Frappe shadow web: $FRAPPE_HEAD
- Frappe compatibility API: $HEALTH_JSON

## Latest Backup Pack

- Path: ${LATEST_BACKUP:-none}
EOF

if [[ -n "$LATEST_BACKUP" && -f "$LATEST_BACKUP/MANIFEST.txt" ]]; then
  {
    echo
    echo '```text'
    cat "$LATEST_BACKUP/MANIFEST.txt"
    echo '```'
    echo
    echo 'SHA256:'
    echo
    echo '```text'
    cat "$LATEST_BACKUP/SHA256SUMS"
    echo '```'
  } >> "$REPORT_PATH"
fi

cat >> "$REPORT_PATH" <<EOF

## Shadow Status Snapshot

\`\`\`json
$STATUS_JSON
\`\`\`

## Required Before Any Real Cutover

1. Explicit owner approval for cutover window.
2. Freeze P0 writes on existing Rescue-Net.
3. Run fresh pre-cutover backup.
4. Run final sync rehearsal or final sync procedure.
5. Run P0 cutover dry-run gate.
6. Confirm rollback path and backup paths.
7. Only then perform an approved reroute action.
EOF

cp "$REPORT_PATH" "$OPS_DIR/P0_READINESS_REPORT.md"
echo "READINESS_REPORT $REPORT_PATH"
