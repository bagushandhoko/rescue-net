#!/usr/bin/env bash
set -euo pipefail
DOCKER=${DOCKER:-/usr/local/bin/docker}
SUDO_PASSWORD=${SUDO_PASSWORD:-003180}
FRAPPE_URL=${FRAPPE_URL:-http://127.0.0.1:8095}
RN_WEB_URL=${RN_WEB_URL:-http://127.0.0.1/rescue-net/}
RN_API_URL=${RN_API_URL:-http://127.0.0.1/rescue-net-api/}

sudo_docker() {
  printf '%s\n' "$SUDO_PASSWORD" | sudo -S "$DOCKER" "$@"
}

require_http_head() {
  local label=$1
  local url=$2
  local line
  line=$(curl -sS -I --max-time 20 "$url" | head -n 1 || true)
  echo "$label $line"
  case "$line" in
    *" 200 "*|*" 302 "*) return 0 ;;
    *) echo "FAIL: $label unhealthy" >&2; return 1 ;;
  esac
}

require_json_contains() {
  local label=$1
  local url=$2
  local needle=$3
  local body
  body=$(curl -sS --max-time 30 "$url")
  echo "$label ${body:0:240}"
  if [[ "$body" != *"$needle"* ]]; then
    echo "FAIL: $label missing $needle" >&2
    return 1
  fi
}

check_mounts() {
  for name in osiun-frappe-backend osiun-frappe-worker-default osiun-frappe-scheduler; do
    mounts=$(sudo_docker inspect "$name" --format '{{json .Mounts}}')
    echo "MOUNT $name $mounts"
    if [[ "$mounts" != *"/home/frappe/frappe-bench/apps/rescue_net"* ]]; then
      echo "FAIL: $name missing rescue_net persistent mount" >&2
      return 1
    fi
  done
}

check_import() {
  sudo_docker exec -u frappe osiun-frappe-backend bash -lc 'cd /home/frappe/frappe-bench && ./env/bin/python - <<PY
import rescue_net
print("IMPORT rescue_net", rescue_net.__file__)
PY'
}

check_validation() {
  sudo_docker exec -u frappe osiun-frappe-backend bash -lc 'cd /home/frappe/frappe-bench && bench --site osiun.localhost execute rescue_net.migration.status.build_status_report_json' | grep -q 'ready-for-next-shadow-step'
  echo "VALIDATION ready-for-next-shadow-step"
}

check_mounts
check_import
require_http_head RN_WEB "$RN_WEB_URL"
require_json_contains RN_API "$RN_API_URL" "running"
require_http_head FRAPPE_SHADOW "$FRAPPE_URL/"
require_json_contains FRAPPE_COMPAT "$FRAPPE_URL/api/method/rescue_net.compat.api.health" "shadow-only"
check_validation
echo "SMOKE PASS frappe-shadow shadow-only"
