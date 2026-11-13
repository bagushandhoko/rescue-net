#!/bin/sh
# Rescue-Net Node — pasang dalam satu perintah (Suri, 2026-11-13).
#
#   ./pasang.sh                         instal BARU (situs kosong + admin)
#   ./pasang.sh --pulihkan <folder>     instal lalu PULIHKAN data dari hasil ./cadangan.sh (pindah server)
#   ./pasang.sh --dengan-jobs           sekalian nyalakan worker & scheduler (JANGAN di server uji berdata asli)
#
# Kebutuhan: Linux + Docker Engine + plugin compose, akses internet (unduh image), repo ini utuh
# (paket memakai ../frappe_shadow/apps/rescue_net dan halaman web di folder induk).
set -eu
cd "$(dirname "$0")"
PULIH=""; JOBS=""
while [ $# -gt 0 ]; do
  case "$1" in
    --pulihkan) PULIH="$2"; shift 2 ;;
    --dengan-jobs) JOBS=1; shift ;;
    *) echo "opsi tidak dikenal: $1" >&2; exit 2 ;;
  esac
done
say() { printf '\n== %s\n' "$*"; }
acak() { tr -dc 'A-Za-z0-9' </dev/urandom 2>/dev/null | head -c "${1:-24}"; }

say "1. cek kebutuhan"
command -v docker >/dev/null || { echo "Docker belum terpasang (https://docs.docker.com/engine/install/)" >&2; exit 1; }
docker compose version >/dev/null || { echo "plugin docker compose belum terpasang" >&2; exit 1; }
[ -d ../frappe_shadow/apps/rescue_net ] && [ -d ../pages ] || { echo "jalankan dari folder node/ di dalam repo rescue-net yang utuh" >&2; exit 1; }
# paket .tar dari menu Setting > Cadangan & Pindah Server: bongkar dulu ke node/backups/<nama>/
case "$PULIH" in
  *.tar)
    T="backups/$(basename "$PULIH")"; [ -f "$T" ] || { echo "taruh berkas .tar di node/backups/ ($PULIH)" >&2; exit 1; }
    D=$(tar tf "$T" | head -1 | cut -d/ -f1); tar xf "$T" -C backups/ && PULIH="backups/$D"
    ( cd "$PULIH" && sha256sum -c SHA256SUMS >/dev/null ) || { echo "checksum paket TIDAK cocok - berkas rusak" >&2; exit 1; } ;;
esac
if [ -n "$PULIH" ] && [ ! -f "backups/$(basename "$PULIH")/site_config.json" ]; then
  C=$(ls backups/$(basename "$PULIH")/*site_config_backup.json 2>/dev/null | head -1 || true)
  [ -n "$C" ] && cp "$C" "backups/$(basename "$PULIH")/site_config.json"
fi
[ -z "$PULIH" ] || [ -f "backups/$(basename "$PULIH")/site_config.json" ] || { echo "folder cadangan tidak lengkap/tidak di node/backups/: $PULIH" >&2; exit 1; }

say "2. pengaturan (.env)"
[ -f .env ] || cp .env.example .env
setv() { if grep -q "^$1=" .env; then sed -i "s#^$1=.*#$1=$2#" .env; else echo "$1=$2" >> .env; fi; }
getv() { sed -n "s/^$1=//p" .env | tail -1; }
[ -n "$(getv RN_DB_ROOT_PASSWORD)" ] || setv RN_DB_ROOT_PASSWORD "$(acak 28)"
[ -n "$(getv RN_ADMIN_PASSWORD)" ] || setv RN_ADMIN_PASSWORD "$(acak 16)"
CPU=$(nproc); RAM_MB=$(awk '/MemTotal/{print int($2/1024)}' /proc/meminfo)
if [ -z "$(getv RN_WORKERS)" ]; then W=$((CPU * 2 + 1)); [ $W -gt 17 ] && W=17; [ $W -lt 3 ] && W=3; setv RN_WORKERS "$W"; fi
if [ -z "$(getv RN_DB_BUFFER)" ]; then B=$((RAM_MB / 5)); [ $B -lt 256 ] && B=256; [ $B -gt 4096 ] && B=4096; setv RN_DB_BUFFER "${B}M"; fi
chmod 600 .env
SITE=$(getv RN_SITE); DOMAIN=$(getv RN_DOMAIN)
echo "situs=$SITE domain=$DOMAIN cpu=$CPU ram=${RAM_MB}MB workers=$(getv RN_WORKERS) db_buffer=$(getv RN_DB_BUFFER)"
mkdir -p backups

say "3. unduh image & nyalakan database"
docker compose pull -q mariadb redis-cache redis-queue backend web
docker compose up -d mariadb redis-cache redis-queue
for i in $(seq 1 60); do [ "$(docker compose ps --format '{{.Health}}' mariadb)" = healthy ] && break; sleep 3; done

B() { docker compose run --rm --no-deps -T --entrypoint bash backend -lc "cd /home/frappe/frappe-bench && $*"; }
say "4. siapkan bench (apps.txt, konfigurasi bersama)"
B "printf 'frappe\\nerpnext\\nrescue_net\\n' > sites/apps.txt; cat sites/apps.txt; \
   ./env/bin/pip install -q -e apps/rescue_net; \
   bench set-config -g db_host mariadb; bench set-config -gp db_port 3306; \
   bench set-config -g redis_cache redis://redis-cache:6379; bench set-config -g redis_queue redis://redis-queue:6379; \
   bench set-config -g redis_socketio redis://redis-queue:6379; bench set-config -gp socketio_port 9000; \
   bench set-config -g default_site $SITE"

if B "test -f sites/$SITE/site_config.json"; then
  echo "situs $SITE sudah ada: dilewati (tidak ditimpa)"
else
  say "5. buat situs $SITE (frappe + erpnext + rescue_net) — beberapa menit"
  B "bench new-site $SITE --mariadb-root-password '$(getv RN_DB_ROOT_PASSWORD)' --admin-password '$(getv RN_ADMIN_PASSWORD)' \
     --mariadb-user-host-login-scope='%' --install-app erpnext --install-app rescue_net"
  if [ -n "$PULIH" ]; then
    say "6. pulihkan data dari $PULIH"
    N=$(basename "$PULIH"); [ -d "backups/$N" ] || { echo "letakkan folder cadangan di node/backups/ (sekarang: $PULIH)" >&2; exit 1; }
    DB=$(cd "backups/$N" && ls *-database.sql.gz | head -1)
    PUB=$(cd "backups/$N" && ls *-files.tar 2>/dev/null | grep -v private | head -1 || true)
    PRV=$(cd "backups/$N" && ls *-private-files.tar 2>/dev/null | head -1 || true)
    docker compose run --rm --no-deps -T -u root --entrypoint chown backend -R frappe:frappe /backups/$N
    B "bench --site $SITE restore /backups/$N/$DB --mariadb-root-password '$(getv RN_DB_ROOT_PASSWORD)' \
       ${PUB:+--with-public-files /backups/$N/$PUB} ${PRV:+--with-private-files /backups/$N/$PRV} --force"
    # kunci enkripsi WAJIB sama dengan server lama (API key AI, token WhatsApp, login Google tersimpan terenkripsi)
    EK=$(grep -o '"encryption_key": *"[^"]*"' "backups/$N/site_config.json" | sed 's/.*: *"\(.*\)"/\1/')
    if [ -n "$EK" ]; then B "bench --site $SITE set-config encryption_key '$EK'"
    else echo "PERINGATAN: cadangan tanpa encryption_key (situs belum pernah menyimpan rahasia) - dilewati"; fi
  fi
fi

say "7. migrasi skema & alamat publik"
B "bench --site $SITE migrate && bench --site $SITE set-config host_name 'https://$DOMAIN' && bench --site $SITE clear-cache"

say "8. nyalakan layanan"
if [ -n "$JOBS" ]; then docker compose --profile jobs up -d; else docker compose up -d; fi
PORT=$(getv RN_WEB_PORT)
for i in $(seq 1 60); do curl -fs -o /dev/null "http://127.0.0.1:$PORT/rescue-net-frappe/api/method/rescue_net.api_auth.account_status" && break; sleep 3; done

say "9. uji"
for u in /rescue-net/ /rescue-net/pages/bencana-aktif.html \
         "/rescue-net-frappe/api/method/rescue_net.api_control_centre.active_disasters_board" ; do
  printf '%s  %s\n' "$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT$u")" "$u"
done
echo
echo "SELESAI. Web: http://127.0.0.1:$PORT/rescue-net/   (admin: Administrator / lihat RN_ADMIN_PASSWORD di .env)"
[ -n "$JOBS" ] || echo "Catatan: worker & scheduler BELUM jalan. Nyalakan di server utama: docker compose --profile jobs up -d"
