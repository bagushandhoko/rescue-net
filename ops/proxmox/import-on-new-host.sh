#!/bin/sh
# Pulihkan bundel dari export-from-nas.sh di server baru (Debian/Ubuntu + Docker + plugin compose), sebagai root.
#   sh import-on-new-host.sh /path/ke/bundle-YYYYMMDD-HHMMSS [--check]
# --check : hanya periksa prasyarat dan checksum bundel (tidak mengubah apa pun).
# Tidak menyalakan Cloudflare Tunnel: itu langkah cutover manual (lihat README.md).
set -eu
BUNDLE=${1:?pakai: sh import-on-new-host.sh <folder-bundel> [--check]}
CHECK=0; [ "${2:-}" = "--check" ] && CHECK=1
HERE=$(cd "$(dirname "$0")" && pwd)
ENVF="$HERE/.env"

say() { printf '== %s\n' "$*"; }
die() { printf 'GAGAL: %s\n' "$*" >&2; exit 1; }
rand() { head -c 24 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 28; }

say "0. prasyarat"
command -v docker >/dev/null || die "docker belum terpasang"
docker compose version >/dev/null 2>&1 || die "plugin 'docker compose' belum terpasang"
command -v git >/dev/null || die "git belum terpasang"
[ -d "$BUNDLE/db" ] || die "$BUNDLE bukan bundel yang valid"
(cd "$BUNDLE" && sha256sum -c SHA256SUMS --quiet) || die "checksum bundel tidak cocok (salinan rusak?)"
echo "   bundel utuh: $(head -1 "$BUNDLE/MANIFEST.txt")"
[ $CHECK -eq 1 ] && { say "mode --check selesai: aman dilanjutkan"; exit 0; }

# ------------------------------------------------------------------ .env
if [ ! -f "$ENVF" ]; then
  say "1. membuat .env (password DB baru diacak; token tunnel dari bundel)"
  TOKEN=$(sed -n 's/^TUNNEL_TOKEN=//p' "$BUNDLE/secrets/cloudflared.env" 2>/dev/null || true)
  cat > "$ENVF" <<EOT
BASE=/srv/sacrn
RN_SITE=osiun.localhost
RN_DB_ROOT_PASSWORD=$(rand)
SAC_SITE=sac.localhost
SAC_DB_ROOT_PASSWORD=$(rand)
SAC_ADMIN_PASSWORD=$(rand)
RN_ADMIN_PASSWORD=$(rand)
TUNNEL_TOKEN=$TOKEN
EOT
  chmod 600 "$ENVF"
fi
# shellcheck disable=SC1090
. "$ENVF"
dc() { docker compose --env-file "$ENVF" -f "$HERE/docker-compose.yml" "$@"; }

# ------------------------------------------------------------------ sumber
say "2. kode sumber dari git bundle -> $BASE/src"
mkdir -p "$BASE"/src "$BASE"/rn/{mariadb,sites,logs,apps} "$BASE"/sac/{mariadb,sites,logs,apps}
for n in rescue-net sac-frappe sac-web; do
  [ -d "$BASE/src/$n/.git" ] || git clone -q "$BUNDLE/git/$n.bundle" "$BASE/src/$n"
done
rm -rf "$BASE/rn/apps/rescue_net" "$BASE/sac/apps/sac_portal"
cp -a "$BASE/src/rescue-net/frappe_shadow/apps/rescue_net" "$BASE/rn/apps/rescue_net"
cp -a "$BASE/src/sac-frappe/apps/sac_portal" "$BASE/sac/apps/sac_portal"
[ -f "$BUNDLE/static/rescue-net-app.tgz" ] && tar xzf "$BUNDLE/static/rescue-net-app.tgz" -C "$BASE/src"

# ------------------------------------------------------------------ database & redis
say "3. MariaDB + Redis"
dc up -d mariadb redis-cache redis-queue db sac-redis-cache sac-redis-queue
i=0; until [ "$(docker inspect -f '{{.State.Health.Status}}' rn-mariadb 2>/dev/null)" = healthy ] && [ "$(docker inspect -f '{{.State.Health.Status}}' sac-frappe-db 2>/dev/null)" = healthy ]; do
  i=$((i+1)); [ $i -gt 60 ] && die "MariaDB tidak sehat"; sleep 3; done

# kerangka folder sites dari image (volume kosong menutupi isinya)
skeleton() { # folder-sites-host
  [ -f "$1/apps.txt" ] || docker run --rm -v "$1":/t --entrypoint sh frappe/erpnext:v15 -c 'cp -a /home/frappe/frappe-bench/sites/. /t/'
}
skeleton "$BASE/rn/sites"; skeleton "$BASE/sac/sites"
# kontainer frappe berjalan sebagai uid 1000 (frappe)
chown -R 1000:1000 "$BASE"/rn/sites "$BASE"/rn/logs "$BASE"/rn/apps "$BASE"/sac/sites "$BASE"/sac/logs "$BASE"/sac/apps

# salinan sementara berkas yang perlu dibaca kontainer (folder bundel 700 root tidak bisa ditembus uid 1000)
TMP="$BASE/restore-tmp"; rm -rf "$TMP"; mkdir -p "$TMP/db" "$TMP/secrets"
cp "$BUNDLE"/db/*database.sql.gz "$BUNDLE"/db/*files.tar "$TMP/db/" 2>/dev/null || true
cp "$BUNDLE"/secrets/rn-site_config.json "$BUNDLE"/secrets/sac-site_config.json "$TMP/secrets/"

# ------------------------------------------------------------------ pulihkan situs (skrip dalam kontainer)
cat > "$BASE/restore-site.sh" <<'EOS'
#!/bin/bash
# env: SITE PRE DBHOST APP DBROOT ADMINPW  (dijalankan di kontainer frappe/erpnext)
set -ex
cd /home/frappe/frappe-bench
[ "$APP" = rescue_net ] && ./env/bin/pip install -q -e apps/rescue_net
grep -qx "$APP" sites/apps.txt || { [ -n "$(tail -c1 sites/apps.txt)" ] && echo >> sites/apps.txt; echo "$APP" >> sites/apps.txt; }
bench set-config -g db_host "$DBHOST"
bench set-config -gp db_port 3306
bench set-config -g redis_cache redis://redis-cache:6379
bench set-config -g redis_queue redis://redis-queue:6379
bench set-config -g redis_socketio redis://redis-queue:6379
bench set-config -gp socketio_port 9000
bench set-config -g default_site "$SITE"
[ -e sites/assets ] || ln -s /home/frappe/frappe-bench/assets sites/assets
if [ ! -d "sites/$SITE" ]; then
  bench new-site "$SITE" --mariadb-root-password "$DBROOT" --admin-password "$ADMINPW" --mariadb-user-host-login-scope='%'
fi
DB=$(ls /bundle/$PRE-*database.sql.gz | sort | tail -1)
PUB=$(ls /bundle/$PRE-*-files.tar 2>/dev/null | grep -v private | sort | tail -1 || true)
PRV=$(ls /bundle/$PRE-*private-files.tar 2>/dev/null | sort | tail -1 || true)
bench --site "$SITE" --force restore "$DB" --mariadb-root-password "$DBROOT" ${PUB:+--with-public-files "$PUB"} ${PRV:+--with-private-files "$PRV"}
# kunci enkripsi, host_name, allow_cors, dll. dari situs lama (tanpa menimpa kredensial DB baru)
./env/bin/python - <<PY
import json
old = json.load(open("/secrets/$PRE-site_config.json"))
p = "sites/$SITE/site_config.json"; cur = json.load(open(p))
for k, v in old.items():
    if not k.startswith("db_"): cur[k] = v
json.dump(cur, open(p, "w"), indent=1)
PY
bench --site "$SITE" migrate
bench --site "$SITE" clear-cache
EOS
chmod 644 "$BASE/restore-site.sh"

say "4. pulihkan Rescue-Net ($RN_SITE)"
docker run --rm --network sacrn_rn-net --entrypoint bash \
  -e SITE="$RN_SITE" -e PRE=rn -e DBHOST=mariadb -e APP=rescue_net -e DBROOT="$RN_DB_ROOT_PASSWORD" -e ADMINPW="$RN_ADMIN_PASSWORD" \
  -v "$BASE/rn/sites":/home/frappe/frappe-bench/sites -v "$BASE/rn/logs":/home/frappe/frappe-bench/logs \
  -v "$BASE/rn/apps/rescue_net":/home/frappe/frappe-bench/apps/rescue_net \
  -v "$TMP/db":/bundle:ro -v "$TMP/secrets":/secrets:ro -v "$BASE/restore-site.sh":/restore-site.sh:ro \
  frappe/erpnext:v15 /restore-site.sh

say "5. pulihkan SAC ($SAC_SITE)"
docker run --rm --network sacrn_sac-net --entrypoint bash \
  -e SITE="$SAC_SITE" -e PRE=sac -e DBHOST=db -e APP=sac_portal -e DBROOT="$SAC_DB_ROOT_PASSWORD" -e ADMINPW="$SAC_ADMIN_PASSWORD" \
  -e PYTHONPATH=/home/frappe/frappe-bench/apps/sac_portal \
  -v "$BASE/sac/sites":/home/frappe/frappe-bench/sites -v "$BASE/sac/logs":/home/frappe/frappe-bench/logs \
  -v "$BASE/sac/apps/sac_portal":/home/frappe/frappe-bench/apps/sac_portal:ro \
  -v "$TMP/db":/bundle:ro -v "$TMP/secrets":/secrets:ro -v "$BASE/restore-site.sh":/restore-site.sh:ro \
  frappe/erpnext:v15 /restore-site.sh

rm -rf "$TMP"   # berisi site_config (kunci enkripsi): jangan dibiarkan

# ------------------------------------------------------------------ jalankan
say "6. menyalakan semua layanan (TANPA tunnel)"
dc up -d
sleep 25
sh "$HERE/verify.sh" || echo "   ada probe gagal: lihat 'docker compose logs <layanan>' sebelum cutover"

cat <<'EOT'

== SELESAI (tunnel belum dinyalakan). Langkah cutover ada di README.md bagian 6:
   1. hentikan tulis di NAS, ekspor ulang bundel akhir, ulangi import (atau salin selisih),
   2. matikan cloudflared di NAS:  sudo docker stop cloudflared
   3. nyalakan di server baru:     docker compose --env-file .env --profile tunnel up -d cloudflared
   4. sh verify.sh  +  coba login nyata (Rescue-Net, portal SAC, Google)
EOT
