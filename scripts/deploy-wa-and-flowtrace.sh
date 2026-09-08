#!/bin/sh
# ============================================================
# Deploy three 2026-09-08 changes that need the Frappe container:
#   1. WhatsApp-send            (commit 88ee9ad)
#   2. logistik flow_trace / QR (commit d15fe51)
#   3. org hierarchy + merge + org AI-key UI (commit 2956329)
#
#   sh scripts/deploy-wa-and-flowtrace.sh [site]
#
# [site] defaults to sites/currentsite.txt inside the container
# (osiun.localhost). docker is invoked as `sudo docker` on this NAS —
# override with RN_DOCKER=docker if yours doesn't need sudo.
# ============================================================
set -eu

DOCKER="${RN_DOCKER:-sudo docker}"
C="${RN_FRAPPE_CONTAINER:-osiun-frappe-backend}"
HOSTPORT="${RN_FRAPPE_HOSTPORT:-8095}"        # 127.0.0.1:8095 -> :8000
SRC="/volume1/web/rescue-net/frappe_shadow/apps/rescue_net/rescue_net"
DST="/home/frappe/frappe-bench/apps/rescue_net/rescue_net"
SITE="${1:-}"

echo "=== container: $C ==="
$DOCKER ps --filter "name=$C" --format '{{.Names}} {{.Status}}'

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
$DOCKER cp "$SRC/api_notify.py"              "$C:$DST/api_notify.py"
$DOCKER cp "$SRC/api_community_cluster.py"   "$C:$DST/api_community_cluster.py"
$DOCKER cp "$SRC/api_control_centre.py"      "$C:$DST/api_control_centre.py"
$DOCKER cp "$SRC/hooks.py"                   "$C:$DST/hooks.py"
$DOCKER cp "$SRC/setup/notification_defaults.py" "$C:$DST/setup/notification_defaults.py"
$DOCKER cp "$SRC/rescue_net/doctype/rn_notification_setting" "$C:$DST/rescue_net/doctype/"
$DOCKER cp "$SRC/rescue_net/doctype/rn_notification_log"     "$C:$DST/rescue_net/doctype/"
# org hierarchy + merge
$DOCKER cp "$SRC/rescue_net/doctype/rn_organization"       "$C:$DST/rescue_net/doctype/"
$DOCKER cp "$SRC/rescue_net/doctype/rn_org_merge_request"  "$C:$DST/rescue_net/doctype/"

echo
echo "3. Resolve site"
if [ -z "$SITE" ]; then
  SITE="$($DOCKER exec "$C" sh -lc 'cat /home/frappe/frappe-bench/sites/currentsite.txt 2>/dev/null' | tr -d '[:space:]')"
  echo "   site (currentsite.txt): $SITE"
fi
[ -n "$SITE" ] || { echo "ERROR: could not resolve site — pass it as arg 1"; exit 1; }

echo
echo "4. bench migrate (creates RN Notification Setting/Log + RN Org Merge Request,"
echo "   adds RN Organization.parent_organization, runs after_migrate seed)"
$DOCKER exec "$C" bash -lc "cd /home/frappe/frappe-bench && bench --site '$SITE' migrate"

echo
echo "5. Restart container"
$DOCKER restart "$C"
sleep 6

echo
echo "6. Smoke checks"
echo "-- flow_trace bogus id (want an app JSON error, not HTTP 500):"
curl -s -o /dev/null -w '   HTTP %{http_code}\n' \
  "http://127.0.0.1:$HOSTPORT/api/method/rescue_net.api_control_centre.flow_trace?flow=__nope__" || true
echo "-- notification defaults row:"
$DOCKER exec "$C" bash -lc "cd /home/frappe/frappe-bench && bench --site '$SITE' execute rescue_net.setup.notification_defaults.install_defaults" || true
echo "-- RN Org Merge Request doctype exists:"
$DOCKER exec "$C" bash -lc "cd /home/frappe/frappe-bench && bench --site '$SITE' execute frappe.db.exists --args \"['DocType','RN Org Merge Request']\"" || true
echo "-- RN Organization.parent_organization column:"
$DOCKER exec "$C" bash -lc "cd /home/frappe/frappe-bench && bench --site '$SITE' execute frappe.db.has_column --args \"['RN Organization','parent_organization']\"" || true

echo
echo "OK. Next:"
echo " - notifikasi-settings.html as System Manager -> 'Kirim tes' => status=simulated row."
echo " - lacak-logistik.html?flow=<a real flow name> => tracker timeline."
echo " - Koordinasi Organisasi (as an org owner) -> 'Organisasi Saya': hierarki,"
echo "   kirim/terima permintaan merger, dan simpan kunci AI organisasi."
