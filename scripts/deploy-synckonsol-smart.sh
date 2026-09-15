#!/bin/sh
# ============================================================
# Deploy the 2026-09-15 "Sync Data Konsolidasi — smarter" change:
#   - guest read-only + org/event-scoped edit + System Manager sees all
#     (access_policy.py, api_frontend_bridge.py, api_intelligence.py)
#   - manual "Override manual" on rollup groups
#     (new doctype RN Consolidation Group Override)
#   - manual "Analisa AI" on rollup groups + sync conflicts (api_ai.py)
#   - RN Sync Log.status() now returns `name`/error_message/
#     disaster_event_id (api_sync.py) so the Sync tab can link/analyze
#
#   sh scripts/deploy-synckonsol-smart.sh [site]
# ============================================================
set -eu

DOCKER="${RN_DOCKER:-sudo docker}"
C="${RN_FRAPPE_CONTAINER:-osiun-frappe-backend}"
HOSTPORT="${RN_FRAPPE_HOSTPORT:-8095}"
SRC="/volume1/web/rescue-net/frappe_shadow/apps/rescue_net/rescue_net"
DST="/home/frappe/frappe-bench/apps/rescue_net/rescue_net"
SITE="${1:-}"

echo "=== container: $C ==="
$DOCKER ps --filter "name=$C" --format '{{.Names}} {{.Status}}'

echo
echo "1. Python compile (host-side sanity)"
python3 -m py_compile \
  "$SRC/access_policy.py" \
  "$SRC/api_frontend_bridge.py" \
  "$SRC/api_intelligence.py" \
  "$SRC/api_ai.py" \
  "$SRC/api_sync.py"

echo
echo "2. Copy backend files into the container"
$DOCKER cp "$SRC/access_policy.py"        "$C:$DST/access_policy.py"
$DOCKER cp "$SRC/api_frontend_bridge.py"  "$C:$DST/api_frontend_bridge.py"
$DOCKER cp "$SRC/api_intelligence.py"     "$C:$DST/api_intelligence.py"
$DOCKER cp "$SRC/api_ai.py"               "$C:$DST/api_ai.py"
$DOCKER cp "$SRC/api_sync.py"             "$C:$DST/api_sync.py"
$DOCKER cp "$SRC/rescue_net/doctype/rn_consolidation_group_override" "$C:$DST/rescue_net/doctype/"

echo
echo "2b. Fix ownership/perms (docker cp lands dirs unreadable to the frappe user"
echo "    on this NAS — bench migrate then SILENTLY skips the doctype)."
$DOCKER exec -u root "$C" bash -lc "
  cd '$DST' &&
  chown -R frappe:frappe access_policy.py api_frontend_bridge.py api_intelligence.py \
    api_ai.py api_sync.py rescue_net/doctype/rn_consolidation_group_override &&
  chmod -R u+rwX,go+rX access_policy.py api_frontend_bridge.py api_intelligence.py \
    api_ai.py api_sync.py rescue_net/doctype/rn_consolidation_group_override &&
  echo '   perms fixed' &&
  ( find rescue_net/doctype/rn_consolidation_group_override -type f ! -perm -004 ) | sed 's/^/   still-unreadable: /' || true
"

echo
echo "3. Resolve site"
if [ -z "$SITE" ]; then
  SITE="$($DOCKER exec "$C" sh -lc 'cat /home/frappe/frappe-bench/sites/currentsite.txt 2>/dev/null' | tr -d '[:space:]')"
  echo "   site (currentsite.txt): $SITE"
fi
[ -n "$SITE" ] || { echo "ERROR: could not resolve site — pass it as arg 1"; exit 1; }

echo
echo "4. bench migrate (creates RN Consolidation Group Override table)"
$DOCKER exec "$C" bash -lc "cd /home/frappe/frappe-bench && bench --site '$SITE' migrate"

echo
echo "5. Restart container"
$DOCKER restart "$C"
sleep 6

echo
echo "6. Smoke checks"
echo "-- RN Consolidation Group Override doctype exists:"
$DOCKER exec "$C" bash -lc "cd /home/frappe/frappe-bench && bench --site '$SITE' execute frappe.db.exists --args \"['DocType','RN Consolidation Group Override']\"" || true
echo "-- guest read on consolidation_summary (want HTTP 200, not 403):"
curl -s -o /dev/null -w '   HTTP %{http_code}\n' \
  "http://127.0.0.1:$HOSTPORT/api/method/rescue_net.api_frontend_bridge.consolidation_summary?disaster_event=event-sim-001" || true
echo "-- guest read on control_centre_summary (want HTTP 200):"
curl -s -o /dev/null -w '   HTTP %{http_code}\n' \
  "http://127.0.0.1:$HOSTPORT/api/method/rescue_net.api_intelligence.control_centre_summary" || true
echo "-- guest write on rebuild_consolidated_needs (want HTTP 403, login required):"
curl -s -o /dev/null -w '   HTTP %{http_code}\n' -X POST \
  "http://127.0.0.1:$HOSTPORT/api/method/rescue_net.api_intelligence.rebuild_consolidated_needs" \
  -d "disaster_event=event-sim-001" || true

echo
echo "OK. Next: real-login + guest Playwright pass on data-consolidation.html."
