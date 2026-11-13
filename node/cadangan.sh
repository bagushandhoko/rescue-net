#!/bin/sh
# Rescue-Net Node — cadangan lengkap (database + berkas publik/privat + site_config berisi kunci enkripsi).
#   ./cadangan.sh            -> node/backups/<waktu>/
# Folder hasilnya bisa disalin ke server lain lalu: ./pasang.sh --pulihkan backups/<waktu>
# PERHATIAN: site_config.json berisi kunci enkripsi & kata sandi DB -> simpan rahasia (chmod 600).
set -eu
cd "$(dirname "$0")"
SITE=$(sed -n 's/^RN_SITE=//p' .env | tail -1); SITE=${SITE:-osiun.localhost}
TS=$(date +%Y%m%d-%H%M%S); OUT=backups/$TS; mkdir -p "$OUT"
docker compose exec -T -u root backend chown frappe:frappe /backups/$TS
docker compose exec -T backend bash -lc "cd /home/frappe/frappe-bench && bench --site $SITE backup --with-files --backup-path /backups/$TS && cp sites/$SITE/site_config.json /backups/$TS/site_config.json" | tail -6
chmod 700 "$OUT"; chmod 600 "$OUT"/*
( cd "$OUT" && sha256sum * > SHA256SUMS )
ls -la "$OUT"
echo "Cadangan: $OUT"
