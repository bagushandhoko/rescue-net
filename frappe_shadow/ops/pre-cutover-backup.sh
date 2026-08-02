#!/usr/bin/env bash
set -euo pipefail
DOCKER=${DOCKER:-/usr/local/bin/docker}
SUDO_PASSWORD=${SUDO_PASSWORD:-003180}
ROOT=${ROOT:-/volume1/web/rescue-net}
ARCHIVE_ROOT=${ARCHIVE_ROOT:-$ROOT/_archive/frappe-p0-precutover}
TS=${TS:-$(date +%Y%m%d-%H%M%S)}
OUT="$ARCHIVE_ROOT/$TS"
PG_CONTAINER=${PG_CONTAINER:-postgres-main}
PG_USER=${PG_USER:-postgres}
PG_DB=${PG_DB:-rescuenet_db}
FRAPPE_DB_CONTAINER=${FRAPPE_DB_CONTAINER:-osiun-frappe-mariadb}
FRAPPE_DB=${FRAPPE_DB:-_c85854d8ca9ba7b8}
FRAPPE_DB_ROOT_PASSWORD=${FRAPPE_DB_ROOT_PASSWORD:-osiun_root_123}

sudo_docker() {
  printf '%s\n' "$SUDO_PASSWORD" | sudo -S "$DOCKER" "$@"
}

mkdir -p "$OUT"
echo "BACKUP_DIR $OUT"

sudo_docker exec "$PG_CONTAINER" pg_dump -U "$PG_USER" -Fc "$PG_DB" > "$OUT/rescuenet_pg.dump"
sudo_docker exec -e MYSQL_PWD="$FRAPPE_DB_ROOT_PASSWORD" "$FRAPPE_DB_CONTAINER" mariadb-dump -uroot "$FRAPPE_DB" > "$OUT/frappe_shadow_mariadb.sql"

sha256sum "$OUT/rescuenet_pg.dump" "$OUT/frappe_shadow_mariadb.sql" > "$OUT/SHA256SUMS"
cat > "$OUT/MANIFEST.txt" <<EOF
created_at=$TS
mode=frappe-p0-precutover-backup
source_postgres_container=$PG_CONTAINER
source_postgres_db=$PG_DB
frappe_mariadb_container=$FRAPPE_DB_CONTAINER
frappe_mariadb_db=$FRAPPE_DB
cutover_allowed=false
notes=Backup pack only. Existing Rescue-Net routing remains unchanged.
EOF

ls -lh "$OUT"
echo "BACKUP PASS $OUT"
