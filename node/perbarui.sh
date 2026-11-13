#!/bin/sh
# Rescue-Net Node — pasang versi terbaru dari repo (setelah git pull): cadangan dulu, migrasi, restart.
#   git pull && ./perbarui.sh
set -eu
cd "$(dirname "$0")"
SITE=$(sed -n 's/^RN_SITE=//p' .env | tail -1); SITE=${SITE:-osiun.localhost}
./cadangan.sh
docker compose exec -T backend bash -lc "cd /home/frappe/frappe-bench && ./env/bin/pip install -q -e apps/rescue_net && bench --site $SITE migrate && bench --site $SITE clear-cache"
PROF=""; docker compose ps --services --status running | grep -qx scheduler && PROF="--profile jobs"
docker compose $PROF up -d --force-recreate backend $( [ -n "$PROF" ] && echo worker scheduler ) web
echo "Diperbarui ke $(git -C .. log -1 --format='%h %s')"
