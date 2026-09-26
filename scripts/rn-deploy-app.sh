#!/bin/sh
# Deploy the rescue_net Frappe app from this repo to production
# (osiun-frappe-backend / osiun.localhost), then migrate, restart, probe.
#
#   sh scripts/rn-deploy-app.sh
#
# 1. backup: app code tarball in the container + bench DB backup
# 2. copy every app file from git (tests excluded) — files that exist only in
#    production are left alone; the offline app's static files go to
#    /volume1/web/rescue-net-app/
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

echo "== 2b. offline app (static files) =="
APP_SRC="$REPO/apps/rescue-net-app"
APP_DST=/volume1/web/rescue-net-app
if [ -d "$APP_DST" ]; then
  # the built downloads (APK, desktop zips) and local backups stay in place
  (cd "$APP_SRC" && git ls-files) | while read -r f; do
    mkdir -p "$APP_DST/$(dirname "$f")" && cp "$APP_SRC/$f" "$APP_DST/$f"
  done
  echo "offline app -> $APP_DST"
fi

echo "== 3. migrate + restart =="
sudo docker exec "$C" sh -c "cd $B && bench --site $SITE migrate 2>&1 | tail -8 && bench --site $SITE clear-cache"
echo "== 3b. remove leftovers the copy step never deletes =="
# the old catch-all module folder (DocTypes moved to rescue_net/rn_<domain>/ in
# phase 4, plus stale pre-git API copies) and *.pre-* / *.bak* file copies
sudo docker exec -u root "$C" sh -c "cd $B/apps/rescue_net/rescue_net && rm -rf rescue_net && find . \\( -name '*.pre-*' -o -name '*.bak*' -o -name '*.BEFORE*' \\) -not -path '*/node_modules/*' -type f -print -delete | wc -l | sed 's/^/stale copies removed: /'"
sudo docker restart "$C" >/dev/null
i=0
until [ "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8095/api/method/ping)" = "200" ]; do
  i=$((i + 1)); [ $i -gt 60 ] && { echo "backend not up after 5 min"; exit 1; }; sleep 5
done

echo "== 4. probe =="
for m in "rescue_net.api_resource_tools.work_objects_board?disaster_event=event-sim-001" \
         rescue_net.api_ai.ai_providers \
         rescue_net.api_control_centre.active_disasters_board \
         "rescue_net.api_frontend_bridge.community_reports?disaster_event=event-sim-001" \
         rescue_net.api_events.disasters \
         rescue_net.api_device.unit_catalog; do
  printf '%-78s %s\n' "$m" "$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:8095/api/method/$m")"
done
echo "done"
