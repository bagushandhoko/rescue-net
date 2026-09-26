#!/bin/sh
# Deploy the rescue_net Frappe app from this repo to production
# (osiun-frappe-backend / osiun.localhost), then migrate, restart, probe.
#
#   sh scripts/rn-deploy-app.sh
#
# 1. backup: app code tarball in the container + bench DB backup
# 2. copy every app file from git (tests excluded) — files that exist only in
#    production are left alone
# 3. bench migrate (new DocTypes / fields), clear-cache, restart
# 4. probe a few endpoints — every line should say 200
# Rollback: tar xzf /home/frappe/rn-app-backup-<ts>.tgz -C apps (in the
# container) + restore the printed DB backup with bench restore.
set -e
C=osiun-frappe-backend
SITE=osiun.localhost
B=/home/frappe/frappe-bench
REPO=$(cd "$(dirname "$0")/.." && pwd)
TS=$(date +%Y%m%d-%H%M%S)
TAR=/tmp/rn-deploy-$TS.tar

echo "== 1. backup =="
sudo docker exec -u root "$C" sh -c "cd $B && tar czf /home/frappe/rn-app-backup-$TS.tgz -C apps rescue_net"
echo "app code -> /home/frappe/rn-app-backup-$TS.tgz"
sudo docker exec "$C" sh -c "cd $B && bench --site $SITE backup | tail -2"

echo "== 2. copy app files =="
cd "$REPO/frappe_shadow/apps/rescue_net"
git ls-files rescue_net | grep -v '^rescue_net/tests/' > "$TAR.list"
tar cf "$TAR" -T "$TAR.list"
sudo docker cp "$TAR" "$C:$TAR"
sudo docker exec -u root "$C" sh -c "cd $B/apps/rescue_net && tar xf $TAR && tar tf $TAR | xargs chown frappe:frappe && find rescue_net -type d -newer $TAR -exec chown frappe:frappe {} + ; rm -f $TAR"
rm -f "$TAR" "$TAR.list"
echo "copied"

echo "== 3. migrate + restart =="
sudo docker exec "$C" sh -c "cd $B && bench --site $SITE migrate 2>&1 | tail -8 && bench --site $SITE clear-cache"
sudo docker restart "$C" >/dev/null
i=0
until [ "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8095/api/method/ping)" = "200" ]; do
  i=$((i + 1)); [ $i -gt 60 ] && { echo "backend not up after 5 min"; exit 1; }; sleep 5
done

echo "== 4. probe =="
for m in "rescue_net.api_resource_tools.work_objects_board?disaster_event=event-sim-001" \
         rescue_net.api_ai.ai_providers \
         rescue_net.api_control_centre.active_disasters_board \
         "rescue_net.api_frontend_bridge.community_reports?disaster_event=event-sim-001"; do
  printf '%-78s %s\n' "$m" "$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:8095/api/method/$m")"
done
echo "done"
