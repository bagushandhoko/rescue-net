#!/bin/sh
# Rescue-Net isolated test stack — a separate MariaDB + Redis + Frappe bench
# that shares NOTHING with production (osiun-frappe-* / osiun.localhost).
#
#   sh scripts/rn-test-stack.sh up      # start containers (idempotent)
#   sh scripts/rn-test-stack.sh init    # create site rescuenet-test.localhost + install rescue_net
#   sh scripts/rn-test-stack.sh test [extra run-tests args]   # run the rescue_net test suite
#   sh scripts/rn-test-stack.sh migrate # bench migrate on the test site (after DocType JSON changes)
#   sh scripts/rn-test-stack.sh down    # stop + remove containers (volumes kept)
#   sh scripts/rn-test-stack.sh wipe    # down + delete the test volumes (fresh start)
#
# The app source is copied from this repo into the test bench on every
# init/test/migrate, so tests always run against the code in git (not
# whatever is deployed in production).
# Same image as production (frappe/erpnext:v15 → frappe 15.113.4); ERPNext is
# NOT installed on the test site because rescue_net does not depend on it.
set -eu

D="sudo docker"
REPO=$(cd "$(dirname "$0")/.." && pwd)
APP_SRC="$REPO/frappe_shadow/apps/rescue_net"
NET=rescuenet-test
DB=rescuenet-test-db
REDIS=rescuenet-test-redis
BENCH=rescuenet-test-bench
SITE=rescuenet-test.localhost
IMAGE=frappe/erpnext:v15
# Throwaway credentials for a throwaway DB that is only reachable on the
# private docker network $NET (no published ports).
DB_ROOT_PW=rn_test_root
ADMIN_PW=rn_test_admin
B=/home/frappe/frappe-bench

running() { [ "$($D inspect -f '{{.State.Running}}' "$1" 2>/dev/null || true)" = "true" ]; }

up() {
  $D network inspect $NET >/dev/null 2>&1 || $D network create --subnet 10.78.0.0/24 $NET >/dev/null
  if ! running $DB; then
    $D rm -f $DB >/dev/null 2>&1 || true
    $D run -d --name $DB --network $NET --network-alias mariadb \
      -e MYSQL_ROOT_PASSWORD=$DB_ROOT_PW \
      -v rescuenet-test-db:/var/lib/mysql \
      mariadb:10.6 \
      --character-set-server=utf8mb4 --collation-server=utf8mb4_unicode_ci \
      --skip-character-set-client-handshake \
      --innodb-buffer-pool-size=64M --performance-schema=OFF >/dev/null
  fi
  if ! running $REDIS; then
    $D rm -f $REDIS >/dev/null 2>&1 || true
    $D run -d --name $REDIS --network $NET --network-alias redis \
      redis:7-alpine redis-server --save "" --maxmemory 64mb >/dev/null
  fi
  if ! running $BENCH; then
    $D rm -f $BENCH >/dev/null 2>&1 || true
    # Named volume for sites/: docker seeds it from the image (apps.txt, assets).
    $D run -d --name $BENCH --network $NET \
      -v rescuenet-test-sites:$B/sites \
      -e PYTHONPATH=$B/apps/rescue_net \
      --entrypoint sleep $IMAGE infinity >/dev/null
  fi
  # Wait for MariaDB.
  i=0
  until $D exec $DB mysqladmin ping -uroot -p$DB_ROOT_PW --silent >/dev/null 2>&1; do
    i=$((i + 1)); [ $i -gt 60 ] && { echo "mariadb did not start" >&2; exit 1; }
    sleep 2
  done
  echo "test stack up"
}

bexec() { $D exec -w $B $BENCH "$@"; }

# Copy the repo's app source into the test bench (a bind mount does not work:
# Synology ACLs on /volume1 hide the repo from the container's uid 1000).
sync_app() {
  $D exec -u root $BENCH rm -rf $B/apps/rescue_net
  $D cp "$APP_SRC" $BENCH:$B/apps/rescue_net
  $D exec -u root $BENCH sh -c "chown -R 1000:1000 $B/apps/rescue_net && chmod -R u+rwX,go+rX $B/apps/rescue_net && find $B/apps/rescue_net -name __pycache__ -prune -exec rm -rf {} +"
}

# Test-site-only preparation.
prepare_site() {
  # tests create many Users per minute; Frappe throttles at 60/hour by default
  bexec bench --site $SITE set-config --parse throttle_user_limit 100000 >/dev/null
}

init() {
  up
  sync_app
  bexec sh -c "printf 'frappe\\nerpnext\\nrescue_net\\n' > sites/apps.txt"
  $D exec -i -w $B $BENCH sh -c "cat > sites/common_site_config.json" <<EOF
{
 "db_host": "mariadb",
 "redis_cache": "redis://redis:6379/0",
 "redis_queue": "redis://redis:6379/1",
 "redis_socketio": "redis://redis:6379/2",
 "default_site": "$SITE"
}
EOF
  if bexec test -d sites/$SITE; then
    echo "site $SITE already exists (use 'wipe' then 'init' for a fresh one)"
  else
    bexec bench new-site $SITE --db-root-password $DB_ROOT_PW \
      --admin-password $ADMIN_PW --mariadb-user-host-login-scope='%' \
      --install-app rescue_net
  fi
  bexec bench --site $SITE set-config allow_tests true
  bexec bench --site $SITE set-config developer_mode 0
  prepare_site
  bexec bench --site $SITE list-apps
}

case "${1:-}" in
  up) up ;;
  init) init ;;
  test)
    shift
    up
    sync_app
    prepare_site
    bexec bench --site $SITE run-tests --app rescue_net "$@"
    ;;
  migrate) up; sync_app; bexec bench --site $SITE migrate ;;
  shell) up; $D exec -it -w $B $BENCH bash ;;
  down) $D rm -f $BENCH $REDIS $DB >/dev/null 2>&1 || true; echo "test stack down" ;;
  wipe)
    $D rm -f $BENCH $REDIS $DB >/dev/null 2>&1 || true
    $D volume rm rescuenet-test-db rescuenet-test-sites >/dev/null 2>&1 || true
    echo "test stack wiped"
    ;;
  *) sed -n '2,15p' "$0"; exit 1 ;;
esac
