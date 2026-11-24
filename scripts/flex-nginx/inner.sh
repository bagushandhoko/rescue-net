#!/bin/sh
# Dijalankan DI DALAM LXC 201 oleh scripts/flex-nginx-apply.sh. $1 = check|apply, $2 = stempel waktu.
set -eu
NODE=/opt/rescue-net/node; NEW=/tmp/rn-nginx-new/nginx; WEB=rescuenet-web-1
IMG=$(docker inspect $WEB --format '{{.Config.Image}}')
envof() { docker inspect $WEB --format '{{range .Config.Env}}{{println .}}{{end}}' | grep "^$1=" | cut -d= -f2-; }
echo "== uji di kontainer sementara"
OUT=$(docker run --rm --network rescuenet-net \
  -e RN_SITE="$(envof RN_SITE)" -e RN_DOMAIN="$(envof RN_DOMAIN)" -e NGINX_ENVSUBST_OUTPUT_DIR=/etc/nginx \
  -v $NEW:/etc/nginx/templates:ro -v /opt/rescue-net:/repo:ro -v rescuenet_sites:/sites:ro \
  "$IMG" sh -c '/docker-entrypoint.sh nginx -t' 2>&1 || true)
echo "$OUT" | grep -E "^nginx: |emerg" || true
echo "$OUT" | grep -q "test is successful" || { echo "UJI GAGAL - situs tidak disentuh."; exit 1; }
[ "$1" = check ] && { echo "UJI LULUS (mode --check, tidak dipasang)."; exit 0; }
echo "== pasang + reload tanpa putus"
cp -a $NODE/nginx $NODE/nginx.bak-$2
cp -r $NEW/. $NODE/nginx/
if docker exec $WEB sh -c '/docker-entrypoint.d/20-envsubst-on-templates.sh >/dev/null && nginx -t 2>&1 && nginx -s reload'; then
  echo RELOAD-OK
else
  echo "RELOAD GAGAL - kembalikan $NODE/nginx.bak-$2"
  rm -rf $NODE/nginx/* && cp -r $NODE/nginx.bak-$2/. $NODE/nginx/
  docker exec $WEB sh -c '/docker-entrypoint.d/20-envsubst-on-templates.sh >/dev/null && nginx -s reload'
  exit 1
fi
sleep 1
curl -s -o /dev/null -w "situs=%{http_code}\n" -H "Host: rescue-net.online" http://127.0.0.1:8182/rescue-net/
