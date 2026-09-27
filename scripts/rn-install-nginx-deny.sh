#!/bin/sh
# Owner, as root (sudo sh scripts/rn-install-nginx-deny.sh): stop nginx from
# serving the non-website files of this repo. Rolls back if nginx -t fails.
set -eu
SRC="$(cd "$(dirname "$0")/.." && pwd)/ops/nginx/www.rescue-net-static-deny.conf"
DST=/usr/local/etc/nginx/conf.d/www.rescue-net-static-deny.conf
BASE=https://osiun.tail251e1e.ts.net/rescue-net

cp "$SRC" "$DST"
chmod 644 "$DST"
if ! nginx -t; then
  rm -f "$DST"
  echo "nginx -t failed — removed $DST, nothing changed."
  exit 1
fi
nginx -s reload
sleep 2

fail=0
check() { # expected path
  got=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/$2")
  if [ "$got" = "$1" ]; then echo "ok   $got $2"; else echo "FAIL $got (want $1) $2"; fail=1; fi
}
check 404 .git/config
check 404 HANDOVER.md
check 404 frappe_shadow/ops/docker-compose.shadow.yml
check 404 docs/NEXT_STEPS.md
check 404 blueprint/dms.pdf
check 404 assets/img/rescuenet_ui_design_images_all.zip
check 200 index.html
check 200 pages/war-room.html
check 200 sw.js
check 200 manifest.webmanifest
check 200 assets/js/rn-ui.js
exit $fail
