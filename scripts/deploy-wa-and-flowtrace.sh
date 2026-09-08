#!/bin/sh
# ============================================================
# Deploy: WhatsApp-send (commit 88ee9ad) + logistik flow_trace / QR
# (this change).  Run on the NAS — needs docker + bench, which the
# assistant's session cannot execute.
#
#   sh scripts/deploy-wa-and-flowtrace.sh <site>
#
# <site> = the Frappe site name (bench --site <site> ...). If omitted,
# the script tries the only site under sites/ automatically.
# ============================================================
set -eu

C="${RN_FRAPPE_CONTAINER:-osiun-frappe-backend}"
SRC="/volume1/web/rescue-net/frappe_shadow/apps/rescue_net/rescue_net"
DST="/home/frappe/frappe-bench/apps/rescue_net/rescue_net"
SITE="${1:-}"

echo "=== container: $C ==="
docker ps --filter "name=$C" --format '{{.Names}} {{.Status}}'

echo
echo "1. Python compile (host-side sanity)"
python3 -m py_compile \
  "$SRC/api_notify.py" \
  "$SRC/api_community_cluster.py" \
  "$SRC/api_control_centre.py" \
  "$SRC/hooks.py" \
  "$SRC/setup/notification_defaults.py"

echo
echo "2. Copy backend files into the container"
docker cp "$SRC/api_notify.py"              "$C:$DST/api_notify.py"
docker cp "$SRC/api_community_cluster.py"   "$C:$DST/api_community_cluster.py"
docker cp "$SRC/api_control_centre.py"      "$C:$DST/api_control_centre.py"
docker cp "$SRC/hooks.py"                   "$C:$DST/hooks.py"
docker cp "$SRC/setup/notification_defaults.py" "$C:$DST/setup/notification_defaults.py"
docker cp "$SRC/rescue_net/doctype/rn_notification_setting" "$C:$DST/rescue_net/doctype/"
docker cp "$SRC/rescue_net/doctype/rn_notification_log"     "$C:$DST/rescue_net/doctype/"

echo
echo "3. Resolve site"
if [ -z "$SITE" ]; then
  SITE="$(docker exec "$C" sh -lc 'ls -1 /home/frappe/frappe-bench/sites | grep -v -e assets -e apps.txt -e common_site_config.json | head -n1')"
  echo "   auto-detected site: $SITE"
fi
[ -n "$SITE" ] || { echo "ERROR: could not resolve site — pass it as arg 1"; exit 1; }

echo
echo "4. Migrate (creates RN Notification Setting / Log + runs after_migrate seed)"
docker exec "$C" bash -lc "cd /home/frappe/frappe-bench && bench --site '$SITE' migrate"

echo
echo "5. Restart"
docker restart "$C"
sleep 5

echo
echo "6. Smoke checks"
BASE="http://127.0.0.1"
echo "-- flow_trace (expects 'Kiriman tidak ditemukan' for a bogus id, NOT a 500):"
docker exec "$C" bash -lc "curl -s -o /dev/null -w '%{http_code}\n' '$BASE/rescue-net-frappe/api/method/rescue_net.api_control_centre.flow_trace?flow=__nope__'" || true
echo "-- notification defaults row:"
docker exec "$C" bash -lc "cd /home/frappe/frappe-bench && bench --site '$SITE' execute rescue_net.setup.notification_defaults.install_defaults" || true

echo
echo "OK. Next: open pages/notifikasi-settings.html as System Manager -> 'Kirim tes'"
echo "should log status=simulated in RN Notification Log."
echo "And open pages/lacak-logistik.html?flow=<a real flow name> to see the tracker."
